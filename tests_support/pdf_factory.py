"""Minimal backend-neutral PDF writer used only by tests.

This module intentionally implements only the tiny subset of the PyMuPDF fixture
API historically used by BiblioRef tests. It never participates in production
extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence


TextItem = tuple[str, float, float, float]
PageItems = Sequence[TextItem]


def _pdf_escape(text: str) -> bytes:
    data = text.encode("cp1252", errors="replace")
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def _stream_for_page(items: PageItems, height: float) -> bytes:
    chunks: list[bytes] = []
    for text, x, y_from_top, font_size in items:
        y_pdf = float(height) - float(y_from_top)
        chunks.append(
            (
                "BT\n"
                f"/F1 {_number(font_size)} Tf\n"
                f"1 0 0 1 {_number(x)} {_number(y_pdf)} Tm\n"
            ).encode("ascii")
            + b"("
            + _pdf_escape(text)
            + b") Tj\nET\n"
        )
    return b"".join(chunks)


def _serialize_pages(
    page_specs: Sequence[tuple[float, float, PageItems]],
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    if not page_specs:
        page_specs = [(595.0, 842.0, [])]

    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    info_parts = []
    for key, pdf_key in (("title", "Title"), ("author", "Author"), ("subject", "Subject"), ("keywords", "Keywords")):
        value = (metadata or {}).get(key)
        if value:
            info_parts.append(b"/" + pdf_key.encode("ascii") + b" (" + _pdf_escape(str(value)) + b")")
    objects[4] = b"<< " + b" ".join(info_parts) + b" >>"

    kids: list[str] = []
    for index, (width, height, items) in enumerate(page_specs):
        page_obj = 5 + index * 2
        content_obj = page_obj + 1
        kids.append(f"{page_obj} 0 R")
        stream = _stream_for_page(items, height)
        objects[content_obj] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
        objects[page_obj] = (
            "<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {_number(width)} {_number(height)}] "
            "/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_obj} 0 R >>"
        ).encode("ascii")

    objects[2] = (
        f"<< /Type /Pages /Count {len(page_specs)} /Kids [{' '.join(kids)}] >>"
    ).encode("ascii")

    max_obj = max(objects)
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_obj + 1)
    for obj_num in range(1, max_obj + 1):
        offsets[obj_num] = len(output)
        output.extend(f"{obj_num} 0 obj\n".encode("ascii"))
        output.extend(objects[obj_num])
        output.extend(b"\nendobj\n")

    startxref = len(output)
    output.extend(f"xref\n0 {max_obj + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for obj_num in range(1, max_obj + 1):
        output.extend(f"{offsets[obj_num]:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R /Info 4 0 R >>\n"
            f"startxref\n{startxref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def pdf_bytes(
    pages: Sequence[PageItems],
    *,
    width: float = 595.0,
    height: float = 842.0,
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    specs = [(float(width), float(height), list(page)) for page in pages]
    return _serialize_pages(specs, metadata)


def write_pdf(
    path: str | Path,
    pages: Sequence[PageItems],
    *,
    width: float = 595.0,
    height: float = 842.0,
    metadata: Mapping[str, str] | None = None,
) -> Path:
    target = Path(path)
    target.write_bytes(pdf_bytes(pages, width=width, height=height, metadata=metadata))
    return target


@dataclass
class _Page:
    width: float = 595.0
    height: float = 842.0
    items: list[TextItem] = field(default_factory=list)

    def insert_text(self, point, text: str, fontsize: float = 11.0, **_kwargs) -> None:
        x, y = point
        self.items.append((str(text), float(x), float(y), float(fontsize)))


class Document:
    def __init__(self) -> None:
        self._pages: list[_Page] = []
        self._metadata: dict[str, str] = {}
        self._closed = False

    @property
    def metadata(self) -> dict[str, str]:
        return dict(self._metadata)

    def set_metadata(self, metadata: Mapping[str, str]) -> None:
        self._metadata = {str(k): str(v) for k, v in metadata.items() if v is not None}

    def new_page(self, width: float = 595.0, height: float = 842.0, **_kwargs) -> _Page:
        page = _Page(float(width), float(height))
        self._pages.append(page)
        return page

    def tobytes(self) -> bytes:
        specs = [(p.width, p.height, p.items) for p in self._pages]
        return _serialize_pages(specs, self._metadata)

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.tobytes())

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "Document":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def open(*args, stream=None, filetype=None, **kwargs) -> Document:
    if args or stream is not None:
        raise NotImplementedError(
            "The neutral test PDF writer creates PDFs only; it does not reopen existing PDFs."
        )
    return Document()
