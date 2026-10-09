"""Public-interface and manual-workflow contracts for the human-gold evaluator."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SHA = "a" * 40


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    cache = tmp_path / "cache"
    cache.mkdir()
    pdf = cache / "doc-1.pdf"
    pdf.write_bytes(b"synthetic PDF fixture")
    digest = _sha(pdf)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "document_id": "doc-1", "partition": "pilot", "sha256": digest,
        "selected_before_biblioref_run": True, "pdf_filename": pdf.name,
    }) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({
        "document_id": "doc-1", "document_sha256": digest, "annotator_id": "tester",
        "annotation_complete": True, "document_has_target_bibliography": True,
        "full_text_sample_ids": ["doc-1-r1"],
        "zones": [{
            "gold_zone_id": "doc-1-z1", "role": "references", "heading_text": "References",
            "heading_present": True, "start_page": 1, "start_y_ratio": 0.1,
            "end_page": 1, "end_y_ratio": 0.9,
            "references": [{
                "gold_ref_id": "doc-1-r1", "ordinal": 1, "start_page": 1,
                "start_y_ratio": 0.2, "start_anchor": "Smith, J.", "flags": [],
                "visible_text_gold": "Smith, J. (2020). Example.",
            }],
        }],
    }) + "\n", encoding="utf-8")
    return manifest, gold, cache


def test_evaluator_uses_only_public_pipeline_scope_once_per_document(monkeypatch, tmp_path):
    from biblioref import pipeline
    from tools.human_gold.evaluate import evaluate

    manifest, gold, cache = _fixture_inputs(tmp_path)
    calls = []

    def stub_process_pdf(path, *, scope):
        calls.append((Path(path), scope))
        return {
            "software_version": "test-software", "algorithm_version": "test-algorithm",
            "zones": [{"start_page": 1, "end_page": 1}],
            "records": [{
                "reference_start_page": 1, "reference_text": "Smith, J. (2020). Example.",
                "start_y_ratio": 0.2,
            }],
        }

    monkeypatch.setattr(pipeline, "process_pdf", stub_process_pdf)
    monkeypatch.setattr("tools.human_gold.evaluate._git_sha", lambda explicit_candidate: CANDIDATE_SHA)
    evaluate(manifest, gold, cache, tmp_path / "results", bootstrap_n=0, candidate_git_sha=CANDIDATE_SHA)

    assert calls == [(cache / "doc-1.pdf", "all_reference_sections")]


def test_evaluator_writes_complete_reproducible_bundle(monkeypatch, tmp_path):
    from biblioref import pipeline
    from tools.human_gold.evaluate import evaluate

    manifest, gold, cache = _fixture_inputs(tmp_path)
    monkeypatch.setattr(pipeline, "process_pdf", lambda path, *, scope: {
        "software_version": "test-software", "algorithm_version": "test-algorithm",
        "zones": [{"start_page": 1, "end_page": 1}],
        "records": [{"reference_start_page": 1, "reference_text": "Smith, J. (2020). Example.", "start_y_ratio": 0.2}],
    })
    monkeypatch.setattr("tools.human_gold.evaluate._git_sha", lambda explicit_candidate: CANDIDATE_SHA)
    output = tmp_path / "results"

    result = evaluate(
        manifest, gold, cache, output, bootstrap_n=0, candidate_git_sha=CANDIDATE_SHA,
    )

    names = {"results.json", "per_document.jsonl", "summary.md", "bootstrap.json", "environment.json", "SHA256SUMS.txt"}
    assert {path.name for path in output.iterdir()} == names
    assert result["provenance"]["benchmark_version"] == "human_gold_v0_1"
    assert result["provenance"]["candidate_git_sha"] == CANDIDATE_SHA
    checksums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert all(name in checksums for name in names - {"SHA256SUMS.txt"})


def test_evaluator_refuses_missing_candidate_sha_before_extraction(monkeypatch, tmp_path):
    from biblioref import pipeline
    from tools.human_gold.evaluate import evaluate

    manifest, gold, cache = _fixture_inputs(tmp_path)
    calls = []

    def forbidden_process_pdf(*args, **kwargs):
        calls.append((args, kwargs))
        return {"zones": [], "records": []}

    monkeypatch.setattr(pipeline, "process_pdf", forbidden_process_pdf)
    with pytest.raises(ValueError, match="candidate git SHA is required"):
        evaluate(manifest, gold, cache, tmp_path / "results", bootstrap_n=0)
    assert calls == []


def test_candidate_sha_must_resolve_to_checked_out_head(monkeypatch):
    from tools.human_gold.evaluate import _git_sha

    candidate = "b" * 40

    def fake_check_output(command, **kwargs):
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return "/repo\n"
        if command[:3] == ["git", "rev-parse", "--verify"]:
            raise subprocess.CalledProcessError(128, command)
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    with pytest.raises(ValueError, match="candidate git SHA cannot be resolved"):
        _git_sha(candidate)


def test_human_gold_workflow_is_manual_only_and_requires_frozen_inputs():
    workflow = ROOT / ".github" / "workflows" / "human-gold-v0-1.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "candidate_sha:" in text
    assert "pdf_artifact_run_id:" in text
    assert "gold_path:" in text
    assert "--candidate-git-sha" in text


def test_production_code_has_no_human_gold_benchmark_dependency():
    sources = [*ROOT.glob("biblioref/**/*.py"), ROOT / "app.py"]
    forbidden = ("tools.human_gold", "benchmarks/human_gold_v0_1")
    offenders = [str(path.relative_to(ROOT)) for path in sources if any(token in path.read_text(encoding="utf-8") for token in forbidden)]
    assert offenders == []


def test_validator_cli_accepts_the_benchmark_jsonl(tmp_path):
    from tools.human_gold.validate_gold import main

    manifest, gold, _ = _fixture_inputs(tmp_path)
    assert main(["--manifest", str(manifest), "--gold", str(gold)]) == 0
