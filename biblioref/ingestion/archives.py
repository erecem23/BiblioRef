"""Safe ZIP ingestion for batches of thesis PDFs.

This module deliberately does not parse bibliographies.  It only turns a ZIP
archive into a sequence of local PDF files plus provenance metadata.  The
normal BiblioRef PDF preflight/extraction pipeline remains authoritative.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

ZIP_INGESTION_VERSION = "zip-ingestion-0.1"
MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024  # 2 GiB
MAX_ZIP_MEMBER_UNCOMPRESSED = 1024 * 1024 * 1024     # 1 GiB
MAX_ZIP_COMPRESSION_RATIO = 250.0
MAX_NESTED_ZIP_DEPTH = 2


class ZipIngestionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedPdf:
    path: Path
    display_name: str
    archive_member: str
    archive_chain: tuple[str, ...]
    sha256: str
    size_bytes: int

    def provenance(self) -> dict:
        return {
            "source": "zip",
            "zip_ingestion_version": ZIP_INGESTION_VERSION,
            "archive_member": self.archive_member,
            "archive_chain": list(self.archive_chain),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _safe_member_name(raw: str) -> PurePosixPath:
    name = str(raw or "").replace("\\", "/")
    p = PurePosixPath(name)
    if not name or name.startswith("/") or p.is_absolute() or ".." in p.parts:
        raise ZipIngestionError(f"Ruta insegura dentro del ZIP: {raw!r}")
    # Windows drive/UNC tricks become ordinary first components after slash
    # normalization, so reject a colon in the first component as well.
    if p.parts and ":" in p.parts[0]:
        raise ZipIngestionError(f"Ruta insegura dentro del ZIP: {raw!r}")
    return p


def _looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"%PDF-" in fh.read(1024)
    except OSError:
        return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_archive(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ZipIngestionError(f"ZIP con demasiados elementos ({len(infos)} > {MAX_ZIP_ENTRIES})")
    total = 0
    for info in infos:
        _safe_member_name(info.filename)
        if info.flag_bits & 0x1:
            raise ZipIngestionError("Los ZIP cifrados/con contraseña no están soportados")
        if info.is_dir():
            continue
        if info.file_size > MAX_ZIP_MEMBER_UNCOMPRESSED:
            raise ZipIngestionError(f"Elemento demasiado grande dentro del ZIP: {info.filename}")
        total += int(info.file_size or 0)
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise ZipIngestionError("El ZIP supera el límite de tamaño descomprimido permitido")
        if info.compress_size and info.file_size >= 50 * 1024 * 1024:
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > MAX_ZIP_COMPRESSION_RATIO:
                raise ZipIngestionError(f"Compresión sospechosa (posible zip bomb): {info.filename}")
    return infos


def extract_pdfs_from_zip(
    archive_path: str | Path,
    destination: str | Path,
    *,
    max_depth: int = MAX_NESTED_ZIP_DEPTH,
) -> tuple[list[ExtractedPdf], list[str]]:
    """Extract PDFs from a ZIP (including nested ZIPs) safely.

    Only PDF and nested ZIP members are materialized.  Other files are ignored.
    Returned PDF paths are unique files in ``destination``; original archive
    paths are retained in provenance metadata.
    """
    src = Path(archive_path)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    found: list[ExtractedPdf] = []
    warnings: list[str] = []

    def walk(zip_path: Path, chain: tuple[str, ...], depth: int) -> None:
        if depth > max_depth:
            warnings.append(f"ZIP anidado omitido por profundidad máxima: {' > '.join(chain)}")
            return
        try:
            with zipfile.ZipFile(zip_path) as zf:
                infos = _validate_archive(zf)
                for info in infos:
                    if info.is_dir():
                        continue
                    rel = _safe_member_name(info.filename)
                    lower = rel.name.lower()
                    if not (lower.endswith(".pdf") or lower.endswith(".zip")):
                        continue
                    # Never trust the member path as a local destination.  A
                    # random prefix avoids collisions between archive folders.
                    suffix = ".pdf" if lower.endswith(".pdf") else ".zip"
                    with tempfile.NamedTemporaryFile(prefix="biblioref_zip_", suffix=suffix, dir=dest, delete=False) as tmp:
                        with zf.open(info, "r") as inp:
                            shutil.copyfileobj(inp, tmp, length=1024 * 1024)
                        tmp_path = Path(tmp.name)
                    member_label = "/".join(rel.parts)
                    if lower.endswith(".zip"):
                        try:
                            walk(tmp_path, chain + (member_label,), depth + 1)
                        finally:
                            tmp_path.unlink(missing_ok=True)
                        continue
                    if not _looks_like_pdf(tmp_path):
                        warnings.append(f"Se omitió {member_label}: extensión .pdf pero contenido no reconocido como PDF")
                        tmp_path.unlink(missing_ok=True)
                        continue
                    found.append(ExtractedPdf(
                        path=tmp_path,
                        display_name=rel.name,
                        archive_member=member_label,
                        archive_chain=chain,
                        sha256=_sha256(tmp_path),
                        size_bytes=tmp_path.stat().st_size,
                    ))
        except zipfile.BadZipFile as exc:
            raise ZipIngestionError(f"ZIP inválido o dañado: {zip_path.name}") from exc

    walk(src, (src.name,), 0)
    return found, warnings


__all__ = [
    "ZIP_INGESTION_VERSION",
    "ZipIngestionError",
    "ExtractedPdf",
    "extract_pdfs_from_zip",
]
