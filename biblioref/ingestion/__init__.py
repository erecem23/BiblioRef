"""PDF and archive ingestion public API.

PDF symbols are resolved lazily to avoid importing the full legacy extraction
engine when callers only need archive handling or backend selection.
"""

from importlib import import_module

from biblioref.ingestion.archives import (
    ZIP_INGESTION_VERSION,
    ExtractedPdf,
    ZipIngestionError,
    extract_pdfs_from_zip,
)

_PDF_EXPORTS = {
    "LayoutLine",
    "clear_layout_line_cache",
    "extract_layout_lines",
    "extract_layout_lines_range",
    "page_dimensions",
    "pdf_page_count",
    "pdf_preflight",
    "render_band_png",
    "render_page_png",
    "stream_file_to_disk",
}


def __getattr__(name: str):
    if name in _PDF_EXPORTS:
        return getattr(import_module("biblioref.ingestion.pdf"), name)
    if name == "compare_pdf_backends":
        return import_module(
            "biblioref.ingestion.pdf_backend_compare"
        ).compare_pdf_backends
    raise AttributeError(name)

__all__ = [
    "LayoutLine",
    "clear_layout_line_cache",
    "extract_layout_lines",
    "extract_layout_lines_range",
    "page_dimensions",
    "pdf_page_count",
    "pdf_preflight",
    "render_band_png",
    "render_page_png",
    "stream_file_to_disk",
    "compare_pdf_backends",
    "ZIP_INGESTION_VERSION",
    "ExtractedPdf",
    "ZipIngestionError",
    "extract_pdfs_from_zip",
]
