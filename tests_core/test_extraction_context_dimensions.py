from pathlib import Path

import pytest

from tests_support import pdf_factory
from biblioref.ingestion.backend_context import active_pdf_backend
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    use_extraction_context,
)


def write_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = pdf_factory.open()
    for text in page_texts:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_page_dimensions_are_cached_per_page(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "dims.pdf", ["one", "two"])
    context = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=True)
    calls = []
    original = pdf_module._page_dimensions_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_page_dimensions_historical", counted)
    with use_extraction_context(context):
        first = pdf_module.page_dimensions(pdf, 1)
        second = pdf_module.page_dimensions(pdf, 1)
        third = pdf_module.page_dimensions(pdf, 2)

    assert first == (595.0, 842.0)
    assert second == first
    assert third == first
    assert len(calls) == 2
    assert context.counters["dimension_requests"] == 3
    assert context.counters["dimension_backend_calls"] == 2
    assert context.counters["dimension_cache_hits"] == 1


def test_dimension_cache_disabled_reads_historical_twice(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "disabled-dims.pdf", ["one"])
    context = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=False)
    calls = []
    original = pdf_module._page_dimensions_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_page_dimensions_historical", counted)
    with use_extraction_context(context):
        pdf_module.page_dimensions(pdf, 1)
        pdf_module.page_dimensions(pdf, 1)

    assert len(calls) == 2
    assert context.counters["dimension_cache_hits"] == 0


def test_dimension_cache_does_not_cross_document_or_backend(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    first = write_pdf(tmp_path / "first.pdf", ["one"])
    second = write_pdf(tmp_path / "second.pdf", ["two"])
    active = active_pdf_backend()
    other_backend = "pdfium" if active == "pymupdf" else "pymupdf"
    calls = []
    original = pdf_module._page_dimensions_historical

    def counted(*args, **kwargs):
        calls.append(str(args[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_page_dimensions_historical", counted)

    document_context = ExtractionContext.for_pdf(first, active, reuse_enabled=True)
    with use_extraction_context(document_context):
        pdf_module.page_dimensions(second, 1)
        pdf_module.page_dimensions(second, 1)

    backend_context = ExtractionContext.for_pdf(first, other_backend, reuse_enabled=True)
    with use_extraction_context(backend_context):
        pdf_module.page_dimensions(first, 1)
        pdf_module.page_dimensions(first, 1)

    assert len(calls) == 4
    assert document_context.counters["dimension_cache_hits"] == 0
    assert backend_context.counters["dimension_cache_hits"] == 0


def test_invalid_dimension_request_is_never_cached(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "invalid.pdf", ["one"])
    context = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=True)
    calls = []
    original = pdf_module._page_dimensions_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_page_dimensions_historical", counted)
    with use_extraction_context(context):
        with pytest.raises(ValueError, match="Página fuera de rango"):
            pdf_module.page_dimensions(pdf, 2)
        with pytest.raises(ValueError, match="Página fuera de rango"):
            pdf_module.page_dimensions(pdf, 2)

    assert len(calls) == 2
    assert context.get_cached_dimensions(2) is None
    assert context.counters["dimension_cache_hits"] == 0
