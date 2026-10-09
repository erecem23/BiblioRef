"""Narrow PyMuPDF-compatible primitives backed by PDFium.

The bibliography algorithms only need a small document surface: page count,
page dimensions, plain/structured text, document metadata and PNG rendering.
Keeping that surface here lets legacy heuristics run unchanged while the
validated object-level layout adapter remains the source of PDFium geometry.
"""
from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterator

import pypdfium2 as pdfium
from pypdfium2 import raw


@dataclass(frozen=True)
class PdfiumMatrix:
    x: float
    y: float


@dataclass(frozen=True)
class _Rect:
    width: float
    height: float


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)
    )


def _rgb_bitmap_png(bitmap) -> bytes:
    """Encode a PDFium RGB bitmap as PNG using only the standard library."""
    width = int(bitmap.width)
    height = int(bitmap.height)
    stride = int(bitmap.stride)
    channels = int(bitmap.n_channels)
    if width <= 0 or height <= 0 or channels != 3:
        raise ValueError(
            f"Unexpected PDFium bitmap geometry: {width}x{height}, {channels} channels"
        )
    source = bytes(bitmap.buffer)
    row_bytes = width * channels
    scanlines = bytearray()
    for row in range(height):
        start = row * stride
        scanlines.append(0)  # PNG filter: None
        scanlines.extend(source[start:start + row_bytes])
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
        + _png_chunk(b"IEND", b"")
    )


class _PdfiumPixmap:
    def __init__(self, page, scale: float):
        self._page = page
        self._scale = max(0.01, float(scale))

    def tobytes(self, output: str = "png") -> bytes:
        if str(output).lower() != "png":
            raise ValueError("The PDFium compatibility renderer only emits PNG")
        bitmap = self._page.render(
            scale=self._scale,
            force_bitmap_format=raw.FPDFBitmap_BGR,
            rev_byteorder=True,
        )
        try:
            return _rgb_bitmap_png(bitmap)
        finally:
            bitmap.close()


class PdfiumPage:
    def __init__(self, document: "PdfiumDocument", index: int):
        self._document = document
        self._index = int(index)
        self._page = document._pdf[self._index]
        width, height = self._page.get_size()
        self.rect = _Rect(float(width), float(height))
        self._text_cache: str | None = None
        self._dict_cache: dict[str, Any] | None = None
        self._closed = False

    def get_text(self, mode: str = "text"):
        normalized = str(mode or "text").lower()
        if normalized == "text":
            if self._text_cache is None:
                textpage = self._page.get_textpage()
                try:
                    self._text_cache = str(textpage.get_text_range() or "")
                finally:
                    textpage.close()
            return self._text_cache
        if normalized != "dict":
            raise ValueError(f"Unsupported PDFium text mode: {mode!r}")
        if self._dict_cache is None:
            # Import lazily to avoid a module cycle during legacy-engine setup.
            from biblioref.ingestion.pdfium_backend import _page_fragments

            textpage = self._page.get_textpage()
            try:
                fragments = _page_fragments(
                    self._page, textpage, float(self.rect.height)
                )
            finally:
                textpage.close()
            fragments.sort(key=lambda item: (item["y0"], item["x0"]))
            blocks = []
            for item in fragments:
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                bbox = (
                    float(item["x0"]),
                    float(item["y0"]),
                    float(item["x1"]),
                    float(item["y1"]),
                )
                sizes = [float(value) for value in item.get("sizes", []) if value]
                size = float(median(sizes)) if sizes else 0.0
                span = {"text": text, "bbox": bbox, "size": size}
                blocks.append({
                    "type": 0,
                    "bbox": bbox,
                    "lines": [{"bbox": bbox, "spans": [span]}],
                })
            self._dict_cache = {"blocks": blocks}
        return self._dict_cache

    def get_pixmap(self, matrix: PdfiumMatrix | None = None, alpha: bool = False):
        del alpha
        scale = float(getattr(matrix, "x", 1.0)) if matrix is not None else 1.0
        return _PdfiumPixmap(self._page, scale)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._page.close()


class PdfiumDocument:
    def __init__(self, path: str | Path):
        self._pdf = pdfium.PdfDocument(str(path))
        self._pages: list[PdfiumPage] = []
        self._closed = False

    @property
    def page_count(self) -> int:
        return len(self._pdf)

    @property
    def metadata(self) -> dict[str, Any]:
        try:
            raw_metadata = self._pdf.get_metadata_dict() or {}
        except Exception:
            raw_metadata = {}
        return {
            str(key).lower(): value
            for key, value in raw_metadata.items()
        }

    def __len__(self) -> int:
        return self.page_count

    def __getitem__(self, index: int) -> PdfiumPage:
        value = int(index)
        if value < 0:
            value += self.page_count
        if not 0 <= value < self.page_count:
            raise IndexError(value)
        page = PdfiumPage(self, value)
        self._pages.append(page)
        return page

    def load_page(self, index: int) -> PdfiumPage:
        return self[index]

    def __iter__(self) -> Iterator[PdfiumPage]:
        for index in range(self.page_count):
            yield self[index]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for page in reversed(self._pages):
            try:
                page.close()
            except Exception:
                pass
        self._pages.clear()
        self._pdf.close()

    def __enter__(self) -> "PdfiumDocument":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def open_pdfium_document(path: str | Path, *args, **kwargs) -> PdfiumDocument:
    if args or kwargs:
        raise TypeError("The PDFium compatibility opener accepts only a PDF path")
    return PdfiumDocument(path)


__all__ = [
    "PdfiumDocument",
    "PdfiumMatrix",
    "PdfiumPage",
    "open_pdfium_document",
]
