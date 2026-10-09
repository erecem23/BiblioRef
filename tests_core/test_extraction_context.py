from pathlib import Path
import subprocess
import sys

from tests_support import pdf_factory
from biblioref.ingestion.backend_context import active_pdf_backend
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    current_extraction_context,
    timed_extraction_stage,
    use_extraction_context,
)

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"


def write_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = pdf_factory.open()
    for text in page_texts:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_context_is_none_outside_activation():
    assert current_extraction_context() is None


def test_context_creation_does_not_require_existing_file(tmp_path):
    missing = tmp_path / "missing.pdf"
    context = ExtractionContext.for_pdf(
        missing,
        active_pdf_backend(),
        reuse_enabled=False,
    )
    assert context.resolved_path == str(missing.resolve())


def test_context_activates_and_resets(tmp_path):
    pdf = write_pdf(tmp_path / "a.pdf", ["alpha"])
    ctx = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=False)
    with use_extraction_context(ctx):
        assert current_extraction_context() is ctx
    assert current_extraction_context() is None


def test_context_rejects_other_document(tmp_path):
    first = write_pdf(tmp_path / "a.pdf", ["alpha"])
    second = write_pdf(tmp_path / "b.pdf", ["beta"])
    ctx = ExtractionContext.for_pdf(first, active_pdf_backend())
    assert ctx.matches(first, active_pdf_backend())
    assert not ctx.matches(second, active_pdf_backend())


def test_context_restores_outer_context(tmp_path):
    first = write_pdf(tmp_path / "outer.pdf", ["alpha"])
    second = write_pdf(tmp_path / "inner.pdf", ["beta"])
    outer = ExtractionContext.for_pdf(first, active_pdf_backend(), reuse_enabled=False)
    inner = ExtractionContext.for_pdf(second, active_pdf_backend(), reuse_enabled=False)

    with use_extraction_context(outer):
        assert current_extraction_context() is outer
        with use_extraction_context(inner):
            assert current_extraction_context() is inner
        assert current_extraction_context() is outer
    assert current_extraction_context() is None


def test_context_counts_times_and_indexes_full_layout(tmp_path):
    pdf = write_pdf(tmp_path / "layout.pdf", ["one", "two"])
    ctx = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=False)

    from biblioref.ingestion import extract_layout_lines

    lines = extract_layout_lines(pdf)
    ctx.increment("range_layout_requests")
    ctx.increment("range_layout_requests")
    ctx.register_full_layout(lines, y_tolerance=0.9, slice_safe=False)

    with use_extraction_context(ctx):
        with timed_extraction_stage("probe"):
            pass

    assert ctx.snapshot()["counters"]["range_layout_requests"] == 2
    assert list(ctx.lines_by_page[2]) == [line for line in lines if int(line.page) == 2]
    assert not ctx.full_layout_slice_safe
    assert ctx.timings["probe"] >= 0.0


def test_public_process_pdf_owns_one_context(monkeypatch):
    import biblioref.pipeline as pipeline

    original = ExtractionContext.for_pdf.__func__
    created = []

    def counted(cls, pdf_path, backend, reuse_enabled=True):
        ctx = original(cls, pdf_path, backend, reuse_enabled)
        created.append(ctx)
        return ctx

    monkeypatch.setattr(ExtractionContext, "for_pdf", classmethod(counted))
    pipeline.process_pdf(GRAMMAR_PDF, rescue_audit=False, adaptive_mode="off")
    assert len(created) == 1
    assert current_extraction_context() is None


def test_public_process_pdf_reuses_manually_active_context(monkeypatch):
    import biblioref.pipeline as pipeline

    context = ExtractionContext.for_pdf(
        GRAMMAR_PDF,
        active_pdf_backend(),
        reuse_enabled=False,
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("process_pdf must reuse the active extraction context")

    with use_extraction_context(context):
        monkeypatch.setattr(ExtractionContext, "for_pdf", classmethod(unexpected))
        pipeline.process_pdf(GRAMMAR_PDF, rescue_audit=False, adaptive_mode="off")
        assert current_extraction_context() is context


def test_monitor_only_ingestion_records_backend_work(tmp_path):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "monitor.pdf", ["one", "two"])
    context = ExtractionContext.for_pdf(
        pdf,
        active_pdf_backend(),
        reuse_enabled=False,
    )

    with use_extraction_context(context):
        full = pdf_module.extract_layout_lines(pdf)
        page_one = pdf_module.extract_layout_lines_range(pdf, 1, 1)
        dimensions = pdf_module.page_dimensions(pdf, 1)

    assert full
    assert page_one
    assert dimensions == (595.0, 842.0)
    assert context.counters["full_layout_requests"] == 1
    assert context.counters["full_layout_backend_calls"] == 1
    assert context.counters["range_layout_requests"] == 1
    assert context.counters["range_layout_backend_calls"] == 1
    assert context.counters["dimension_requests"] == 1
    assert context.counters["dimension_backend_calls"] == 1
    assert context.full_layout == tuple(full)
    assert context.get_cached_range(1, 1, 0.9) == tuple(page_one)
    assert context.get_cached_dimensions(1) == dimensions
    # Capability is evidence-backed even in monitor-only mode; reuse_enabled
    # remains the guard that prevents the fast path from being used.
    assert context.full_layout_slice_safe


def test_pipeline_records_monitor_only_stage_timings():
    import biblioref.pipeline as pipeline

    context = ExtractionContext.for_pdf(
        GRAMMAR_PDF,
        active_pdf_backend(),
        reuse_enabled=False,
    )
    with use_extraction_context(context):
        pipeline.process_pdf(
            GRAMMAR_PDF,
            adaptive_mode="off",
            rescue_audit=True,
        )

    expected = {
        "effective_base",
        "long_segment_reconciliation",
        "dominant_margin_reconciliation",
        "first_reference_reconciliation",
        "rescue_audit",
        "coverage",
    }
    assert expected <= set(context.timings)
    assert all(context.timings[name] >= 0.0 for name in expected)


def test_single_pdf_profiler_cli_exists_and_has_help():
    completed = subprocess.run(
        [sys.executable, "tools/profile_single_pdf.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--backend" in completed.stdout
    assert "--reuse" in completed.stdout


def test_identical_range_request_is_memoized(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "memo.pdf", ["one", "two", "three"])
    context = ExtractionContext.for_pdf(
        pdf,
        active_pdf_backend(),
        reuse_enabled=True,
    )
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_extract_layout_lines_range_historical", counted)
    with use_extraction_context(context):
        first = pdf_module.extract_layout_lines_range(pdf, 1, 2)
        second = pdf_module.extract_layout_lines_range(pdf, 1, 2)

    assert first == second
    assert first is not second
    assert len(calls) == 1
    assert context.counters["range_layout_requests"] == 2
    assert context.counters["range_layout_backend_calls"] == 1
    assert context.counters["range_layout_cache_hits"] == 1


def test_range_cache_key_includes_range_and_tolerance(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "keys.pdf", ["one", "two", "three"])
    context = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=True)
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append((args[1], args[2], args[3]))
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_extract_layout_lines_range_historical", counted)
    with use_extraction_context(context):
        pdf_module.extract_layout_lines_range(pdf, 1, 2, 0.9)
        pdf_module.extract_layout_lines_range(pdf, 1, 3, 0.9)
        pdf_module.extract_layout_lines_range(pdf, 1, 2, 0.8)

    assert len(calls) == 3
    assert context.counters["range_layout_cache_hits"] == 0


def test_range_cache_does_not_cross_document_or_backend(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    first = write_pdf(tmp_path / "first.pdf", ["one", "two"])
    second = write_pdf(tmp_path / "second.pdf", ["alpha", "beta"])
    active = active_pdf_backend()
    other_backend = "pdfium" if active == "pymupdf" else "pymupdf"
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append(str(args[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_extract_layout_lines_range_historical", counted)

    document_context = ExtractionContext.for_pdf(first, active, reuse_enabled=True)
    with use_extraction_context(document_context):
        pdf_module.extract_layout_lines_range(second, 1, 1)
        pdf_module.extract_layout_lines_range(second, 1, 1)

    backend_context = ExtractionContext.for_pdf(first, other_backend, reuse_enabled=True)
    with use_extraction_context(backend_context):
        pdf_module.extract_layout_lines_range(first, 1, 1)
        pdf_module.extract_layout_lines_range(first, 1, 1)

    assert len(calls) == 4
    assert document_context.counters["range_layout_cache_hits"] == 0
    assert backend_context.counters["range_layout_cache_hits"] == 0


def test_range_cache_disabled_runs_historical_path_twice(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module

    pdf = write_pdf(tmp_path / "disabled.pdf", ["one", "two"])
    context = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=False)
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_extract_layout_lines_range_historical", counted)
    with use_extraction_context(context):
        pdf_module.extract_layout_lines_range(pdf, 1, 1)
        pdf_module.extract_layout_lines_range(pdf, 1, 1)

    assert len(calls) == 2
    assert context.counters["range_layout_cache_hits"] == 0
