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

from biblioref.ingestion.pdfium_lock import PDFIUM_LOCK


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
    return _rgb_buffer_png(width, height, stride, bytes(bitmap.buffer))


def _rgb_buffer_png(width: int, height: int, stride: int, source: bytes) -> bytes:
    """Encode raw 8-bit RGB rows (``stride`` bytes apart) as PNG."""
    row_bytes = width * 3
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
        with PDFIUM_LOCK:
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
        with PDFIUM_LOCK:
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
                with PDFIUM_LOCK:
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

            with PDFIUM_LOCK:
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
        with PDFIUM_LOCK:
            self._page.close()


class PdfiumDocument:
    def __init__(self, path: str | Path):
        with PDFIUM_LOCK:
            self._pdf = pdfium.PdfDocument(str(path))
        self._pages: list[PdfiumPage] = []
        self._closed = False

    @property
    def page_count(self) -> int:
        with PDFIUM_LOCK:
            return len(self._pdf)

    @property
    def metadata(self) -> dict[str, Any]:
        try:
            with PDFIUM_LOCK:
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
        with PDFIUM_LOCK:
            self._pdf.close()

    def __enter__(self) -> "PdfiumDocument":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def open_pdfium_document(path: str | Path, *args, **kwargs) -> PdfiumDocument:
    if args or kwargs:
        raise TypeError("The PDFium compatibility opener accepts only a PDF path")
    return PdfiumDocument(path)


_MARK_RGB = (180, 83, 9)  # --warn #b45309, as in the PyMuPDF renderer
_MARK_FILL_OPACITY = 0.08


def _draw_mark(buffer: bytearray, width: int, height: int, stride: int,
               left: int, top: int, right: int, bottom: int, line: int) -> None:
    """Tint a box and outline it with a 3-on/2-off dashed border, in place."""
    left, right = max(0, left), min(width - 1, right)
    top, bottom = max(0, top), min(height - 1, bottom)
    if right <= left or bottom <= top:
        return
    dash_on, dash_off = 3 * line, 2 * line
    keep = 1 - _MARK_FILL_OPACITY
    tint = [round(channel * _MARK_FILL_OPACITY) for channel in _MARK_RGB]
    for y in range(top, bottom + 1):
        row = y * stride
        for x in range(left, right + 1):
            i = row + x * 3
            buffer[i] = round(buffer[i] * keep) + tint[0]
            buffer[i + 1] = round(buffer[i + 1] * keep) + tint[1]
            buffer[i + 2] = round(buffer[i + 2] * keep) + tint[2]
    colour = bytes(_MARK_RGB)

    def paint(x: int, y: int) -> None:
        i = y * stride + x * 3
        buffer[i:i + 3] = colour

    for offset in range(line):
        for x in range(left, right + 1):
            if (x - left) % (dash_on + dash_off) < dash_on:
                paint(x, min(bottom, top + offset))
                paint(x, max(top, bottom - offset))
        for y in range(top, bottom + 1):
            if (y - top) % (dash_on + dash_off) < dash_on:
                paint(min(right, left + offset), y)
                paint(max(left, right - offset), y)


def render_band_png_pdfium(
    pdf_path: str | Path,
    page_number: int,
    top: float,
    bottom: float,
    zoom: float = 1.6,
    mark: tuple[float, float] | None = None,
) -> bytes:
    """PDFium version of ``render_band_png``: a horizontal strip of the text column."""
    scale = max(0.01, float(zoom))
    with PDFIUM_LOCK:
        with PdfiumDocument(pdf_path) as document:
            if not 1 <= page_number <= document.page_count:
                raise ValueError("Página fuera de rango.")
            page = document[page_number - 1]
            width, height = float(page.rect.width), float(page.rect.height)
            top = max(0.0, min(float(top), height - 2))
            bottom = max(top + 8.0, min(float(bottom), height))
            blocks = page.get_text("dict")["blocks"]
            x0 = max(0.0, min((block["bbox"][0] for block in blocks), default=width * 0.1) - 6)
            x1 = min(width, max((block["bbox"][2] for block in blocks), default=width * 0.9) + 6)
            if x1 - x0 < 40:
                x0, x1 = 0.0, width
            bitmap = page._page.render(
                scale=scale,
                crop=(x0, height - bottom, width - x1, top),
                force_bitmap_format=raw.FPDFBitmap_BGR,
                rev_byteorder=True,
            )
            try:
                pixel_width, pixel_height = int(bitmap.width), int(bitmap.height)
                stride, channels = int(bitmap.stride), int(bitmap.n_channels)
                buffer = bytearray(bytes(bitmap.buffer))
            finally:
                bitmap.close()
    if channels != 3:
        raise ValueError(f"Unexpected PDFium bitmap channels: {channels}")
    if mark:
        m0, m1 = max(top, float(mark[0])), min(bottom, float(mark[1]))
        if m1 > m0:
            _draw_mark(
                buffer, pixel_width, pixel_height, stride,
                left=round(1.5 * scale), top=round((m0 - top) * scale),
                right=round((x1 - x0 - 1.5) * scale), bottom=round((m1 - top) * scale),
                line=max(1, round(1.1 * scale)),
            )
    return _rgb_buffer_png(pixel_width, pixel_height, stride, bytes(buffer))


__all__ = [
    "PdfiumDocument",
    "PdfiumMatrix",
    "PdfiumPage",
    "open_pdfium_document",
    "render_band_png_pdfium",
]
