from pathlib import Path

import pytest

from tests_support import pdf_factory
from biblioref.ingestion import clear_layout_line_cache, extract_layout_lines
from biblioref.ingestion import pdf as pdf_module
from biblioref.ingestion.backend_context import (
    available_pdf_backends,
    use_pdf_backend,
)
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    use_extraction_context,
)

ROOT = Path(__file__).resolve().parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"


def _write_hanging_indent_pdf(path: Path) -> Path:
    pages = [
        [
            ("Bibliography", 72, 72, 14),
            ("Alpha, A. (2020). First title.", 72, 110, 11),
            ("Continuation of first title and source.", 96, 128, 11),
            ("Beta, B. (2021). Second title.", 72, 162, 11),
            ("Continuation of second title.", 96, 180, 11),
        ],
        [
            ("Gamma, C. (2022). Third title.", 72, 92, 11),
            ("Continuation on another page.", 96, 110, 11),
        ],
        [
            ("Delta, D. (2023). Fourth title.", 72, 92, 11),
            ("Final continuation.", 96, 110, 11),
        ],
    ]
    return pdf_factory.write_pdf(path, pages)


def _write_two_column_pdf(path: Path) -> Path:
    pages = [
        [
            ("Left A", 60, 100, 11),
            ("Right A", 330, 100, 11),
            ("Left B", 60, 126, 11),
            ("Right B", 330, 126, 11),
        ],
        [
            ("Left C", 60, 100, 11),
            ("Right C", 330, 100, 11),
            ("Left D", 60, 126, 11),
            ("Right D", 330, 126, 11),
        ],
        [
            ("Left E", 60, 100, 11),
            ("Right E", 330, 100, 11),
        ],
    ]
    return pdf_factory.write_pdf(path, pages)


def _assert_exact_slice(pdf: Path, backend: str, start_page: int, end_page: int) -> None:
    with use_pdf_backend(backend):
        clear_layout_line_cache()
        full = extract_layout_lines(pdf)
        historical = pdf_module._extract_layout_lines_range_historical(
            pdf,
            start_page,
            end_page,
            0.9,
        )
    sliced = [
        line for line in full
        if start_page <= int(line.page) <= end_page
    ]
    assert historical == sliced


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_full_layout_slice_exact_on_grammar_fixture(backend):
    for start_page, end_page in ((1, 1), (4, 6), (9, 9)):
        _assert_exact_slice(GRAMMAR_PDF, backend, start_page, end_page)


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_full_layout_slice_exact_on_hanging_indent_fixture(tmp_path, backend):
    pdf = _write_hanging_indent_pdf(tmp_path / f"hanging-{backend}.pdf")
    for start_page, end_page in ((1, 1), (1, 2), (2, 3)):
        _assert_exact_slice(pdf, backend, start_page, end_page)


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_full_layout_slice_exact_on_same_baseline_two_column_fixture(tmp_path, backend):
    pdf = _write_two_column_pdf(tmp_path / f"columns-{backend}.pdf")
    for start_page, end_page in ((1, 1), (1, 2), (2, 3)):
        _assert_exact_slice(pdf, backend, start_page, end_page)


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_proven_backend_uses_full_layout_slice_without_historical_call(
    tmp_path, backend, monkeypatch
):
    pdf = _write_hanging_indent_pdf(tmp_path / f"slice-hit-{backend}.pdf")
    context = ExtractionContext.for_pdf(pdf, backend, reuse_enabled=True)
    with use_pdf_backend(backend), use_extraction_context(context):
        full = extract_layout_lines(pdf)

        def forbidden(*args, **kwargs):
            raise AssertionError("historical range extractor should not run")

        monkeypatch.setattr(
            pdf_module,
            "_extract_layout_lines_range_historical",
            forbidden,
        )
        ranged = pdf_module.extract_layout_lines_range(pdf, 1, 2, 0.9)

    expected = [line for line in full if 1 <= int(line.page) <= 2]
    assert ranged == expected
    assert ranged is not full
    assert context.counters["range_layout_full_slice_hits"] == 1
    assert context.counters["range_layout_backend_calls"] == 0


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_full_layout_slice_falls_back_for_unproved_tolerance(
    tmp_path, backend, monkeypatch
):
    pdf = _write_hanging_indent_pdf(tmp_path / f"slice-tolerance-{backend}.pdf")
    context = ExtractionContext.for_pdf(pdf, backend, reuse_enabled=True)
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    with use_pdf_backend(backend), use_extraction_context(context):
        extract_layout_lines(pdf)
        monkeypatch.setattr(
            pdf_module,
            "_extract_layout_lines_range_historical",
            counted,
        )
        result = pdf_module.extract_layout_lines_range(pdf, 1, 2, 1.1)

    assert result
    assert len(calls) == 1
    assert context.counters["range_layout_full_slice_hits"] == 0
    assert context.counters["range_layout_backend_calls"] == 1


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_full_layout_slice_falls_back_for_unrepresented_or_invalid_page(
    tmp_path, backend, monkeypatch
):
    # Page 2 is intentionally blank: a fail-closed slice must delegate rather
    # than infer that a missing page key means a valid empty page.
    pdf = pdf_factory.write_pdf(
        tmp_path / f"slice-blank-{backend}.pdf",
        [[("Page one", 72, 72, 11)], [], [("Page three", 72, 72, 11)]],
    )
    context = ExtractionContext.for_pdf(pdf, backend, reuse_enabled=True)
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append((args[1], args[2]))
        return original(*args, **kwargs)

    with use_pdf_backend(backend), use_extraction_context(context):
        extract_layout_lines(pdf)
        monkeypatch.setattr(
            pdf_module,
            "_extract_layout_lines_range_historical",
            counted,
        )
        assert pdf_module.extract_layout_lines_range(pdf, 2, 2, 0.9) == []
        with pytest.raises(ValueError, match="Rango de páginas fuera de límite"):
            pdf_module.extract_layout_lines_range(pdf, 1, 4, 0.9)

    assert calls == [(2, 2), (1, 4)]
    assert context.counters["range_layout_full_slice_hits"] == 0
