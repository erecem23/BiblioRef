import json

import pytest

from tools.human_gold.schema import load_jsonl, validate_gold, validate_manifest


def manifest_row(document_id="d1", sha256=None, partition="primary", selected=True):
    return {
        "document_id": document_id,
        "partition": partition,
        "sha256": sha256 or "a" * 64,
        "selected_before_biblioref_run": selected,
    }


def zone(refs=None, **overrides):
    value = {
        "gold_zone_id": "z1",
        "role": "references",
        "start_page": 1,
        "end_page": 2,
        "start_y_ratio": 0.1,
        "end_y_ratio": 0.9,
        "heading_present": True,
        "heading_text": "References",
        "references": refs if refs is not None else [
            {"gold_ref_id": "r1", "ordinal": 1, "start_page": 1,
             "start_y_ratio": 0.2, "start_anchor": "One", "flags": [], "visible_text_gold": "One"}
        ],
    }
    value.update(overrides)
    return value


def reference(ref_id="r1", ordinal=1, page=1, y=0.2):
    return {"gold_ref_id": ref_id, "ordinal": ordinal, "start_page": page,
            "start_y_ratio": y, "start_anchor": "Anchor", "flags": [], "visible_text_gold": "Anchor"}


def gold(document_id="d1", sha256=None, zones=None, samples=None, complete=True):
    return {
        "document_id": document_id,
        "document_sha256": sha256 or "a" * 64,
        "annotator_id": "ann-1",
        "annotation_complete": complete,
        "document_has_target_bibliography": True,
        "zones": zones if zones is not None else [zone()],
        "full_text_sample_ids": samples if samples is not None else ["r1"],
    }


def test_manifest_rejects_duplicate_document_id():
    with pytest.raises(ValueError, match="duplicate document_id: d1"):
        validate_manifest([manifest_row(), manifest_row(sha256="b" * 64)])


@pytest.mark.parametrize("field,value,message", [
    ("sha256", "bad", "invalid sha256"),
    ("partition", "unknown", "invalid partition"),
])
def test_manifest_rejects_invalid_values(field, value, message):
    row = manifest_row(**{field: value})
    with pytest.raises(ValueError, match=message):
        validate_manifest([row])


def test_manifest_rejects_duplicate_sha():
    with pytest.raises(ValueError, match="duplicate sha256"):
        validate_manifest([manifest_row("d1"), manifest_row("d2")])


def test_manifest_requires_pre_run_selection():
    with pytest.raises(ValueError, match="selected_before_biblioref_run"):
        validate_manifest([manifest_row(selected=False)])


def test_manifest_accepts_only_pilot_primary_and_stress_partitions():
    for partition in ("pilot", "primary", "stress"):
        validate_manifest([manifest_row(partition=partition)])
    with pytest.raises(ValueError, match="invalid partition: reserve"):
        validate_manifest([manifest_row(partition="reserve")])


def test_gold_rejects_duplicate_zone_id():
    with pytest.raises(ValueError, match="duplicate gold_zone_id: z1"):
        validate_gold([manifest_row()], [gold(zones=[zone(), zone()])])


def test_gold_rejects_duplicate_reference_id():
    refs = [reference(), reference()]
    with pytest.raises(ValueError, match="duplicate gold_ref_id: r1"):
        validate_gold([manifest_row()], [gold(zones=[zone(refs)])])


def test_gold_requires_ordinal_sequence_per_zone():
    refs = [reference(ordinal=1), reference(ref_id="r2", ordinal=3)]
    with pytest.raises(ValueError, match="ordinal sequence"):
        validate_gold([manifest_row()], [gold(zones=[zone(refs)])])


def test_gold_rejects_reference_outside_zone_pages_and_y_range():
    bad_page = [reference(page=3)]
    with pytest.raises(ValueError, match="outside zone pages"):
        validate_gold([manifest_row()], [gold(zones=[zone(bad_page)])])
    bad_y = [reference(y=1.1)]
    with pytest.raises(ValueError, match="y ratio"):
        validate_gold([manifest_row()], [gold(zones=[zone(bad_y)])])


def test_gold_rejects_boolean_zone_page_numbers():
    with pytest.raises(ValueError, match="missing or invalid field: start_page"):
        validate_gold([manifest_row()], [gold(zones=[zone(start_page=True)])])


def test_gold_accepts_multi_page_zone_with_independent_y_ratios():
    validate_gold([manifest_row()], [gold(zones=[zone(
        start_page=1, start_y_ratio=0.9, end_page=2, end_y_ratio=0.1
    )])])


def test_gold_rejects_manifest_sha_mismatch():
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_gold([manifest_row()], [gold(sha256="b" * 64)])


def test_gold_requires_complete_annotation_and_full_text_sample():
    with pytest.raises(ValueError, match="annotation_complete"):
        validate_gold([manifest_row()], [gold(complete=False)])
    with pytest.raises(ValueError, match="deterministic full-text"):
        validate_gold([manifest_row()], [gold(samples=[])])


def test_load_jsonl_reads_objects(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps({"a": 1}) + "\n" + "\n" + json.dumps({"b": 2}) + "\n")
    assert load_jsonl(path) == [{"a": 1}, {"b": 2}]
