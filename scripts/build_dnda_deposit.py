#!/usr/bin/env python3
"""Build a source-only BiblioRef package suitable for DNDA deposit preparation.

The script intentionally packages *tracked source/documentation files* rather
than the runtime environment. Third-party packages, corpora, PDFs, builds and
credentials are excluded. It does not submit anything to DNDA.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "legal_deposit_build"

ALLOWED_SUFFIXES = {
    ".py",
    ".html",
    ".htm",
    ".js",
    ".css",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".bat",
    ".cmd",
    ".ps1",
    ".iss",
    ".gitignore",
    ".gitattributes",
}

ALLOWED_BASENAMES = {
    "Dockerfile",
    "Makefile",
}

EXCLUDED_PREFIXES = {
    ".git/",
    ".github/workflows/",  # operational credentials/workflows are not needed to identify the work
    ".venv/",
    "venv/",
    ".buildvenv/",
    "build/",
    "dist/",
    "legal_deposit_build/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "corpus/",
    "data/",
    "datasets/",
    "downloads/",
}

EXCLUDED_SUFFIXES = {
    ".pdf",
    ".whl",
    ".zip",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyd",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".xlsx",
    ".xls",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".sqlite",
    ".db",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

SENSITIVE_NAME_PARTS = {
    "client_secret",
    "credentials",
    "oauth_token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    ".env",
}


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def git_commit() -> str:
    return run_git("rev-parse", "HEAD")


def git_status_porcelain() -> str:
    return run_git("status", "--porcelain")


def tracked_files() -> list[Path]:
    output = run_git("ls-files", "-z")
    return [Path(item) for item in output.split("\0") if item]


def is_sensitive(path: Path) -> bool:
    lowered = path.as_posix().lower()
    basename = path.name.lower()
    return any(part in lowered or part == basename for part in SENSITIVE_NAME_PARTS)


def is_excluded(path: Path) -> bool:
    posix = path.as_posix()
    lowered = posix.lower()

    if any(lowered.startswith(prefix.lower()) for prefix in EXCLUDED_PREFIXES):
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if is_sensitive(path):
        return True
    return False


def is_allowed_source(path: Path) -> bool:
    if is_excluded(path):
        return False
    if path.name in ALLOWED_BASENAMES:
        return True
    if path.name in {".gitignore", ".gitattributes"}:
        return True
    return path.suffix.lower() in ALLOWED_SUFFIXES


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if not (ROOT / ".git").exists():
        print("ERROR: ejecutar desde un checkout Git de BiblioRef.", file=sys.stderr)
        return 2

    dirty = git_status_porcelain()
    if dirty:
        print(
            "ERROR: el repositorio tiene cambios sin commit. "
            "Para un snapshot reproducible, commit o descarte esos cambios primero.",
            file=sys.stderr,
        )
        print(dirty, file=sys.stderr)
        return 3

    commit = git_commit()
    short = commit[:12]
    stamp = date.today().isoformat()
    package_name = f"BiblioRef_DNDA_{stamp}_{short}"
    package_dir = OUTPUT_ROOT / package_name
    source_dir = package_dir / "01_CODIGO_FUENTE" / "biblioref_source"

    if package_dir.exists():
        shutil.rmtree(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    included: list[Path] = []
    excluded: list[Path] = []

    for relative in tracked_files():
        absolute = ROOT / relative
        if not absolute.is_file():
            continue
        if is_allowed_source(relative):
            target = source_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(absolute, target)
            included.append(relative)
        else:
            excluded.append(relative)

    identification = package_dir / "00_IDENTIFICACION"
    documentation = package_dir / "02_DOCUMENTACION"
    tests_dir = package_dir / "03_PRUEBAS"
    identification.mkdir(parents=True, exist_ok=True)
    documentation.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    write_text(identification / "GIT_COMMIT.txt", commit + "\n")
    write_text(
        identification / "VERSION.txt",
        f"BiblioRef\nSnapshot date: {stamp}\nGit commit: {commit}\n",
    )
    write_text(
        identification / "MANIFEST.txt",
        "\n".join(path.as_posix() for path in sorted(included)) + "\n",
    )
    write_text(
        identification / "EXCLUDED_TRACKED_FILES.txt",
        "# Tracked files intentionally excluded from the source deposit package\n"
        + "\n".join(path.as_posix() for path in sorted(excluded))
        + "\n",
    )

    legal_docs = [
        ROOT / "README.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "docs/legal/IP_RELEASE_CHECKLIST.md",
        ROOT / "docs/legal/IP_SNAPSHOT_2026_09_09.md",
        ROOT / "docs/legal/PYMUPDF_DECISION.md",
        ROOT / "docs/legal/DNDA_DEPOSIT_PACKAGE.md",
    ]
    for source in legal_docs:
        if source.exists():
            shutil.copy2(source, documentation / source.name)

    write_text(
        tests_dir / "TEST_RESULTS.txt",
        "Run the project test suite for this exact commit and replace this note "
        "with the frozen test output before physical deposit.\n",
    )

    hashes: list[str] = []
    for path in sorted(package_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            digest = sha256_file(path)
            rel = path.relative_to(package_dir).as_posix()
            hashes.append(f"{digest}  {rel}")
    write_text(identification / "SHA256SUMS.txt", "\n".join(hashes) + "\n")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_ROOT / f"{package_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUTPUT_ROOT))

    zip_hash = sha256_file(zip_path)
    write_text(
        OUTPUT_ROOT / f"{package_name}.zip.sha256.txt",
        f"{zip_hash}  {zip_path.name}\n",
    )

    print(f"Snapshot: {commit}")
    print(f"Files included: {len(included)}")
    print(f"Tracked files excluded: {len(excluded)}")
    print(f"Package: {zip_path}")
    print(f"SHA-256: {zip_hash}")
    print("Review EXCLUDED_TRACKED_FILES.txt and TEST_RESULTS.txt before deposit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
