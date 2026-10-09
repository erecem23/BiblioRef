"""PDFium must survive concurrent use from several threads.

The local application serves page images and analyses from a thread pool.
Without a process-wide lock, concurrent PDFium calls corrupted its global
state and every later call failed with "Failed to load document (PDFium: Data
format error)".
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests_support import pdf_factory

pytest.importorskip("pypdfium2")

from biblioref.ingestion.pdfium_backend import (  # noqa: E402
    clear_pdfium_layout_line_cache,
    extract_layout_lines_pdfium,
    page_dimensions_pdfium,
    pdf_page_count_pdfium,
)
from biblioref.ingestion.pdfium_primitives import PdfiumMatrix, open_pdfium_document  # noqa: E402

N_PAGES = 12


def _thesis_like_pdf(tmp_path):
    pages = []
    for number in range(1, N_PAGES + 1):
        items = [(f"Running header page {number}", 72, 40, 9)]
        for row in range(30):
            items.append((f"({row + 1}) Author A, Author B. Title of reference {row + 1}. Journal 2020;{row}:1-10.",
                          72, 80 + row * 22, 10))
        pages.append(items)
    return pdf_factory.write_pdf(tmp_path / "thesis.pdf", pages)


def _render(path, page_index):
    with open_pdfium_document(path) as document:
        page = document[page_index]
        page.get_text("dict")
        return len(page.get_pixmap(matrix=PdfiumMatrix(1.35, 1.35)).tobytes("png"))


def _mixed(path, job):
    kind = job % 4
    if kind == 0:
        clear_pdfium_layout_line_cache()
        return len(extract_layout_lines_pdfium(path))
    if kind == 1:
        return pdf_page_count_pdfium(path)
    if kind == 2:
        return page_dimensions_pdfium(path, 1 + job % N_PAGES)
    return _render(path, job % N_PAGES)


def _outcome(fn, *args):
    try:
        fn(*args)
        return "ok"
    except Exception as exc:  # pragma: no cover - the failure mode under test
        return f"{type(exc).__name__}: {exc}"


def test_concurrent_rendering_and_extraction_do_not_corrupt_pdfium(tmp_path):
    path = _thesis_like_pdf(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        renders = list(pool.map(lambda i: _outcome(_render, path, i % N_PAGES), range(48)))
        mixed = list(pool.map(lambda i: _outcome(_mixed, path, i), range(64)))
    assert Counter(renders) == Counter({"ok": 48})
    assert Counter(mixed) == Counter({"ok": 64})
    # PDFium still works afterwards in the same process.
    assert _outcome(_render, path, 0) == "ok"
