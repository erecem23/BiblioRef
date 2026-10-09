"""Regression coverage for the Task 5 reviewer findings."""

from __future__ import annotations

import hashlib
import json

import pytest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(ref_id, page, anchor, y=.2):
    return {"gold_ref_id": ref_id, "ordinal": 1, "start_page": page,
            "start_y_ratio": y, "start_anchor": anchor, "flags": [],
            "visible_text_gold": anchor}


def _gold(document_id, digest, partition="primary", zones=None):
    zones = zones if zones is not None else [{
        "gold_zone_id": "g1", "role": "references", "heading_text": "References",
        "heading_present": True, "start_page": 1, "start_y_ratio": .1,
        "end_page": 1, "end_y_ratio": .9, "references": [_ref("r1", 1, "One")],
    }]
    refs = [ref for zone in zones for ref in zone["references"]]
    return {"document_id": document_id, "document_sha256": digest, "annotator_id": "ann",
            "annotation_complete": True, "document_has_target_bibliography": True,
            "zones": zones, "full_text_sample_ids": [ref["gold_ref_id"] for ref in refs]}


def test_document_alignment_never_crosses_matched_zone_pairs(tmp_path):
    from tools.human_gold.evaluate import _document_result

    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"d")
    digest = _sha(pdf)
    gold = _gold("d", digest, zones=[
        {"gold_zone_id": "g1", "role": "references", "heading_text": "R1", "heading_present": True,
         "start_page": 1, "start_y_ratio": .1, "end_page": 1, "end_y_ratio": .9,
         "references": [_ref("r1", 1, "Alpha")]},
        {"gold_zone_id": "g2", "role": "references", "heading_text": "R2", "heading_present": True,
         "start_page": 5, "start_y_ratio": .1, "end_page": 5, "end_y_ratio": .9,
         "references": [_ref("r2", 5, "Beta")]},
    ])
    report = {"zones": [{"zone_id": 10, "start_page": 5, "end_page": 5}, {"zone_id": 20, "start_page": 1, "end_page": 1}],
              "records": [
                  {"zone_id": 10, "ref_in_zone": 1, "reference_start_page": 5, "start_y_ratio": .2, "reference_text": "Beta"},
                  {"zone_id": 20, "ref_in_zone": 1, "reference_start_page": 1, "start_y_ratio": .2, "reference_text": "Alpha"},
              ]}
    result = _document_result({"document_id": "d", "partition": "primary"}, gold, pdf, report)
    assert result["boundary"]["boundary"]["true_positive"] == 2
    assert result["boundary"]["matched_pairs"] == [
        {"gold_index": 0, "predicted_index": 1}, {"gold_index": 1, "predicted_index": 0},
    ]
    assert result["predicted_starts"][0]["zone_id"] == 10
    assert result["predicted_starts"][0]["ref_in_zone"] == 1


def test_headline_summary_is_primary_only_and_partitions_are_never_pooled():
    from tools.human_gold.metrics import summarize_partitions
    documents = [
        {"document_id": "p", "partition": "primary", "boundary": {"true_positive": 1, "predicted": 1, "gold": 1, "f1": 1}, "zone": {}},
        {"document_id": "s", "partition": "stress", "boundary": {"true_positive": 0, "predicted": 1, "gold": 1, "f1": 0}, "zone": {}},
        {"document_id": "x", "partition": "pilot", "boundary": {"true_positive": 0, "predicted": 1, "gold": 1, "f1": 0}, "zone": {}},
    ]
    result = summarize_partitions(documents, bootstrap_n=0)
    assert result["headline"]["count"]["documents"] == 1
    assert result["stress"]["count"]["documents"] == 1
    assert "pilot" not in result["headline"]
    assert result["pilot"]["count"]["documents"] == 1


def test_validator_rejects_development_overlap_and_records_exclusion_sha(tmp_path):
    from tools.human_gold.validate_gold import validate_paths
    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"d"); digest = _sha(pdf)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"document_id": "d", "partition": "primary", "sha256": digest,
                                    "selected_before_biblioref_run": True, "development_overlap": False,
                                    "source_item_url": "https://x/d"}) + "\n")
    gold = tmp_path / "gold.jsonl"; gold.write_text(json.dumps(_gold("d", digest)) + "\n")
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions.write_text(json.dumps({"identity_type": "stable_url", "identity": "https://x/d"}) + "\n")
    with pytest.raises(ValueError, match="development exclusion overlap"):
        validate_paths(manifest, gold, exclusions)


def test_validator_requires_explicit_negative_overlap_and_identity_when_exclusions_supplied(tmp_path):
    from tools.human_gold.validate_gold import validate_paths
    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"d"); digest = _sha(pdf)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"document_id": "d", "partition": "primary", "sha256": digest,
                                    "selected_before_biblioref_run": True}) + "\n")
    gold = tmp_path / "gold.jsonl"; gold.write_text(json.dumps(_gold("d", digest)) + "\n")
    exclusions = tmp_path / "exclusions.jsonl"; exclusions.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="development_overlap must be false"):
        validate_paths(manifest, gold, exclusions)


def test_validator_requires_exact_deterministic_visible_text_samples():
    from tools.human_gold.schema import deterministic_sample_ids, validate_gold
    manifest = [{"document_id": "d", "partition": "primary", "sha256": "a" * 64, "selected_before_biblioref_run": True}]
    refs = [_ref(f"r{index}", 1, f"Text {index}") for index in range(12)]
    for index, ref in enumerate(refs, 1): ref["ordinal"] = index
    annotation = _gold("d", "a" * 64, zones=[{"gold_zone_id": "g", "role": "references", "heading_text": "R", "heading_present": True,
                                                "start_page": 1, "start_y_ratio": .1, "end_page": 1, "end_y_ratio": .9, "references": refs}])
    annotation["full_text_sample_ids"] = deterministic_sample_ids("d", "primary", refs)
    validate_gold(manifest, [annotation])
    annotation["full_text_sample_ids"] = annotation["full_text_sample_ids"][:-1] + ["r2"]
    with pytest.raises(ValueError, match="deterministic full-text sample IDs"):
        validate_gold(manifest, [annotation])


def test_deterministic_sample_hash_uses_flattened_ordinal_not_reference_id():
    from tools.human_gold.schema import deterministic_sample_ids
    refs = [_ref(f"arbitrary-{index * 17}", 1, "text") for index in range(12)]
    renamed = [{**ref, "gold_ref_id": f"renamed-{index}"} for index, ref in enumerate(refs)]
    selected = deterministic_sample_ids("d", "primary", refs)
    renamed_selected = deterministic_sample_ids("d", "primary", renamed)
    selected_indexes = [next(index for index, ref in enumerate(refs) if ref["gold_ref_id"] == sample) for sample in selected]
    renamed_indexes = [next(index for index, ref in enumerate(renamed) if ref["gold_ref_id"] == sample) for sample in renamed_selected]
    assert selected_indexes == renamed_indexes


def test_localization_caches_page_layout_and_backend_failure_is_unresolved(monkeypatch, tmp_path):
    import tools.human_gold.evaluate as evaluate
    calls = []
    def failed(*args):
        calls.append(args); raise RuntimeError("backend failed")
    monkeypatch.setattr(evaluate, "_layout_lines_for_pages", failed)
    records = [{"zone_id": 1, "ref_in_zone": 1, "reference_start_page": 1, "reference_text": "One"},
               {"zone_id": 1, "ref_in_zone": 2, "reference_start_page": 1, "reference_text": "Two"}]
    localized = evaluate.localize_predicted_starts(records, tmp_path / "d.pdf")
    assert len(calls) == 1
    assert [row["localization_status"] for row in localized] == ["unresolved", "unresolved"]


def test_layout_opening_match_allows_one_sided_numeric_marker_but_rejects_conflict():
    from tools.human_gold.evaluate import _opening_matches
    assert _opening_matches("Smith, J. Example", {"text": "[12] Smith, J. Example"})
    assert not _opening_matches("[11] Smith, J. Example", {"text": "[12] Smith, J. Example"})


def test_pdfium_localizes_a_real_pdf_fixture(tmp_path):
    import pypdfium2
    from tests_support.pdf_factory import write_pdf
    from tools.human_gold.evaluate import localize_predicted_starts
    assert hasattr(pypdfium2, "PdfDocument")
    pdf = tmp_path / "pdfium-layout-fixture.pdf"
    write_pdf(pdf, [[("[12] Smith, J. Example Title", 24, 40, 12)]], width=216, height=288)
    localized = localize_predicted_starts([
        {"zone_id": 1, "ref_in_zone": 1, "reference_start_page": 1, "reference_text": "Smith, J. Example"},
    ], pdf)
    assert localized[0]["localization_status"] == "layout_match"
    assert 0 < localized[0]["start_y_ratio"] < 1


def test_layout_matching_uses_expected_x_and_column_local_monotonicity(monkeypatch, tmp_path):
    import tools.human_gold.evaluate as evaluate
    monkeypatch.setattr(evaluate, "_layout_lines_for_pages", lambda *_: {1: [
        {"text": "Smith, J. Example", "x0": 10, "y0": 10, "height": 100},
        {"text": "Smith, J. Example", "x0": 10, "y0": 30, "height": 100},
        {"text": "Smith, J. Example", "x0": 150, "y0": 10, "height": 100},
    ]})
    localized = evaluate.localize_predicted_starts([
        {"zone_id": 1, "ref_in_zone": 1, "reference_start_page": 1, "reference_start_x": 10, "reference_text": "Smith, J. Example"},
        {"zone_id": 1, "ref_in_zone": 2, "reference_start_page": 1, "reference_start_x": 10, "reference_text": "Smith, J. Example"},
        {"zone_id": 1, "ref_in_zone": 3, "reference_start_page": 1, "reference_start_x": 150, "reference_text": "Smith, J. Example"},
    ], tmp_path / "d.pdf")
    assert [row["start_y_ratio"] for row in localized] == [.1, .3, .1]


def test_public_audit_status_sets_review_required_and_is_recorded(tmp_path):
    from tools.human_gold.evaluate import _document_result
    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"d"); digest = _sha(pdf)
    result = _document_result({"document_id": "d", "partition": "primary"}, _gold("d", digest), pdf,
                              {"zones": [], "records": [], "post_extraction_audit": {"status": "manual_review_required", "version": "v"}})
    assert result["review_required"] is True
    assert result["post_extraction_audit"]["status"] == "manual_review_required"


def test_boundary_first_and_last_misses_are_document_edges_not_zone_totals(tmp_path):
    from tools.human_gold.evaluate import _document_result
    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"d"); digest = _sha(pdf)
    gold = _gold("d", digest, zones=[
        {"gold_zone_id": "g1", "role": "references", "heading_text": "R", "heading_present": True,
         "start_page": 1, "start_y_ratio": .1, "end_page": 1, "end_y_ratio": .9, "references": [_ref("r1", 1, "A")]},
        {"gold_zone_id": "g2", "role": "references", "heading_text": "R", "heading_present": True,
         "start_page": 2, "start_y_ratio": .1, "end_page": 2, "end_y_ratio": .9, "references": [_ref("r2", 2, "B")]},
    ])
    result = _document_result({"document_id": "d", "partition": "primary"}, gold, pdf, {"zones": [], "records": []})
    assert result["boundary"]["missed_first_reference_count"] == 1
    assert result["boundary"]["missed_last_reference_count"] == 1


def test_git_sha_resolves_from_evaluator_repository_not_callers_cwd(monkeypatch):
    import tools.human_gold.evaluate as evaluate
    calls = []
    candidate = "a" * 40
    def output(command, **kwargs):
        calls.append((command, kwargs))
        if command[-1] == "--show-toplevel": return "/repo\n"
        if "status" in command: return ""
        return candidate + "\n"
    monkeypatch.setattr(evaluate.subprocess, "check_output", output)
    assert evaluate._git_sha(candidate) == candidate
    assert all("cwd" in kwargs for _, kwargs in calls)


def test_git_sha_rejects_dirty_and_mismatched_explicit_candidates(monkeypatch):
    import tools.human_gold.evaluate as evaluate
    candidate = "a" * 40
    def dirty(command, **_kwargs):
        if command[-1] == "--show-toplevel": return "/repo\n"
        if "status" in command: return " M tools/human_gold/evaluate.py\n"
        return candidate + "\n"
    monkeypatch.setattr(evaluate.subprocess, "check_output", dirty)
    with pytest.raises(ValueError, match="tracked changes"):
        evaluate._git_sha(candidate)

    requested = "b" * 40
    def clean(command, **_kwargs):
        if command[-1] == "--show-toplevel": return "/repo\n"
        if "status" in command: return ""
        if "--verify" in command: return requested + "\n"
        return candidate + "\n"
    monkeypatch.setattr(evaluate.subprocess, "check_output", clean)
    with pytest.raises(ValueError, match="does not match"):
        evaluate._git_sha(requested)


def test_provenance_rejects_mixed_report_versions_before_writing(tmp_path):
    from tools.human_gold.evaluate import _provenance
    manifest = tmp_path / "manifest.jsonl"; manifest.write_text("{}\n")
    gold = tmp_path / "gold.jsonl"; gold.write_text("{}\n")
    with pytest.raises(ValueError, match="inconsistent software"):
        _provenance(manifest, gold, [{"software_version": "a", "algorithm_version": "1"}, {"software_version": "b", "algorithm_version": "1"}], 0)


def test_provenance_uses_the_frozen_exclusion_registry_sha_key(monkeypatch, tmp_path):
    import tools.human_gold.evaluate as evaluate
    monkeypatch.setattr(evaluate, "_git_sha", lambda *_: "a" * 40)
    manifest = tmp_path / "manifest.jsonl"; manifest.write_text("{}\n")
    gold = tmp_path / "gold.jsonl"; gold.write_text("{}\n")
    exclusions = tmp_path / "exclusions.jsonl"; exclusions.write_text("{}\n")
    provenance = evaluate._provenance(manifest, gold, [], 0, exclusions)
    assert "exclusion_registry_sha256" in provenance
    assert "exclusions_sha256" not in provenance


def test_unmatched_anchor_only_start_is_counted_as_physically_unresolved():
    from tools.human_gold.evaluate import _zone_boundary_alignment
    gold = {"zones": []}
    boundary = _zone_boundary_alignment(gold, [], [{"localization_status": "anchor_only", "reference_text": "Smith, J."}], {"matched_pairs": []})
    assert boundary["unresolved_predicted_start_count"] == 1


def test_bundle_is_byte_for_byte_repeatable_without_a_wall_clock(tmp_path):
    from tools.human_gold.evaluate import _write_bundle
    from tools.human_gold.metrics import summarize_partitions
    summaries = summarize_partitions([], bootstrap_n=0)
    provenance = {"benchmark_version": "human_gold_v0_1", "candidate_git_sha": "a" * 40,
                  "bootstrap_seed": 1, "bootstrap_n": 0}
    results = {"provenance": provenance, "summary": summaries["headline"], "partition_summaries": summaries}
    _write_bundle(tmp_path, results, [], summaries["headline"], summaries, provenance)
    first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    _write_bundle(tmp_path, results, [], summaries["headline"], summaries, provenance)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == first
    assert b"created_at" not in first["environment.json"]
