from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import biblioref.pipeline as pipeline
from biblioref.ingestion import clear_layout_line_cache
from biblioref.ingestion.backend_context import available_pdf_backends, use_pdf_backend
from biblioref.ingestion.extraction_context import ExtractionContext, use_extraction_context
from tests_support import pdf_factory


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"

CASES = [
    {"adaptive_mode": "shadow", "rescue_audit": True, "scope": "all_reference_sections"},
    {"adaptive_mode": "off", "rescue_audit": True, "scope": "unique_references"},
    {"adaptive_mode": "shadow", "rescue_audit": False, "scope": "final_reference_section"},
    {"adaptive_mode": "shadow", "rescue_audit": True, "two_pass_shadow": True},
]


def run_with_reuse(pdf: Path, backend: str, reuse_enabled: bool, **kwargs):
    clear_layout_line_cache()
    context = ExtractionContext.for_pdf(
        pdf,
        backend,
        reuse_enabled=reuse_enabled,
    )
    with use_pdf_backend(backend), use_extraction_context(context):
        result = pipeline.process_pdf(pdf, **kwargs)
    return result, context


def _without_timings(value):
    # Wall-clock pass durations (two_pass_shadow.*.seconds) differ on every run.
    if isinstance(value, dict):
        return {k: _without_timings(v) for k, v in value.items() if k != "seconds"}
    if isinstance(value, list):
        return [_without_timings(v) for v in value]
    return value


@pytest.mark.parametrize("backend", available_pdf_backends())
@pytest.mark.parametrize("options", CASES)
def test_public_pipeline_report_is_exactly_equal_with_reuse(backend, options):
    baseline, _ = run_with_reuse(GRAMMAR_PDF, backend, False, **options)
    optimized, _ = run_with_reuse(GRAMMAR_PDF, backend, True, **options)
    assert _without_timings(baseline) == _without_timings(optimized)


def _coverage_heavy_pdf(path: Path) -> Path:
    pages = [
        [
            ("Bibliography", 72, 70, 14),
            ("Alpha, A. (2018). First reference. Journal One, 1, 1-10.", 72, 110, 11),
            ("Beta, B. (2019). Second reference. Journal Two, 2, 11-20.", 72, 150, 11),
        ],
        [
            ("Gamma, C. (2020). Third reference. Journal Three, 3, 21-30.", 72, 90, 11),
            ("Delta, D. (2021). Fourth reference. Journal Four, 4, 31-40.", 72, 130, 11),
        ],
        [
            ("Epsilon, E. (2022). Fifth reference. Journal Five, 5, 41-50.", 72, 90, 11),
            ("Zeta, F. (2023). Sixth reference. Journal Six, 6, 51-60.", 72, 130, 11),
        ],
        [
            ("Eta, G. (2024). Seventh reference. Journal Seven, 7, 61-70.", 72, 90, 11),
            ("Theta, H. (2025). Eighth reference. Journal Eight, 8, 71-80.", 72, 130, 11),
        ],
    ]
    return pdf_factory.write_pdf(path, pages)


@pytest.mark.parametrize("backend", available_pdf_backends())
def test_coverage_heavy_public_report_is_exactly_equal(tmp_path, backend):
    pdf = _coverage_heavy_pdf(tmp_path / f"coverage-heavy-{backend}.pdf")
    options = {
        "adaptive_mode": "shadow",
        "rescue_audit": True,
        "scope": "all_reference_sections",
    }
    baseline, _ = run_with_reuse(pdf, backend, False, **options)
    optimized, _ = run_with_reuse(pdf, backend, True, **options)
    assert baseline == optimized


def test_profiler_json_stdout_has_frozen_machine_shape():
    completed = subprocess.run(
        [
            sys.executable,
            "tools/profile_single_pdf.py",
            str(GRAMMAR_PDF),
            "--backend",
            "pdfium",
            "--reuse",
            "off",
            "--json",
            "-",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert set(payload) == {
        "pdf_sha256",
        "backend",
        "reuse_enabled",
        "total_seconds",
        "algorithm_version",
        "software_version",
        "n_records_selected",
        "n_zones",
        "coverage_status",
        "counters",
        "timings",
    }
    assert len(payload["pdf_sha256"]) == 64
    int(payload["pdf_sha256"], 16)
    assert payload["backend"] == "pdfium"
    assert payload["reuse_enabled"] is False
    assert payload["total_seconds"] >= 0.0
    assert isinstance(payload["n_records_selected"], int)
    assert isinstance(payload["n_zones"], int)
    assert isinstance(payload["counters"], dict)
    assert isinstance(payload["timings"], dict)
    assert "BiblioRef single-document profile" in completed.stderr


def test_profiler_help_contains_fresh_process_bash_and_powershell_recipes():
    completed = subprocess.run(
        [sys.executable, "tools/profile_single_pdf.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Bash fresh-process benchmark" in completed.stdout
    assert "PowerShell fresh-process benchmark" in completed.stdout
    assert "--reuse off" in completed.stdout
    assert "--reuse on" in completed.stdout
