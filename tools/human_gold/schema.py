"""Stdlib-only loading and fail-closed validation for benchmark JSONL data."""

import json
import re
import math
from pathlib import Path


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_PARTITIONS = {"pilot", "primary", "stress"}


def _stable_hash(value: str) -> int:
    """FNV-1a over JavaScript-compatible UTF-16 code units."""
    result = 2166136261
    encoded = value.encode("utf-16le")
    for offset in range(0, len(encoded), 2):
        code_unit = int.from_bytes(encoded[offset:offset + 2], "little")
        result ^= code_unit
        result = (result * 16777619) & 0xFFFFFFFF
    return result


def deterministic_sample_ids(document_id: str, partition: str, references: list[dict]) -> list[str]:
    """Return the immutable transcription task set used by the annotation UI."""
    wanted = 5 if partition == "stress" else 10
    if len(references) <= wanted:
        return [reference["gold_ref_id"] for reference in references]
    chosen = {
        0, len(references) - 1,
        math.floor((len(references) - 1) * .25 + .5),
        math.floor((len(references) - 1) * .5 + .5),
        math.floor((len(references) - 1) * .75 + .5),
    }
    remaining = sorted(
        ((index, _stable_hash(f"{document_id}+{index + 1}"))
         for index, reference in enumerate(references) if index not in chosen),
        key=lambda item: (item[1], item[0]),
    )
    for index, _ in remaining:
        if len(chosen) >= wanted:
            break
        chosen.add(index)
    return [references[index]["gold_ref_id"] for index in sorted(chosen)]


def load_jsonl(path: Path) -> list[dict]:
    """Load non-blank JSONL records, requiring every record to be an object."""
    rows = []
    try:
        with Path(path).open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON at line {line_number}") from exc
                if not isinstance(row, dict):
                    raise ValueError(f"JSONL record at line {line_number} is not an object")
                rows.append(row)
    except OSError as exc:
        raise ValueError(f"cannot read JSONL: {Path(path)}") from exc
    return rows


def _require(row, field, expected):
    if field not in row or not isinstance(row[field], expected):
        raise ValueError(f"missing or invalid field: {field}")


def _sha(value, label="sha256"):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"invalid {label}")


def _ratio(value, label="y ratio"):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"invalid {label}: {value}")


def validate_manifest(rows: list[dict]) -> None:
    """Validate manifest uniqueness, selection, partition, and digest invariants."""
    if not isinstance(rows, list):
        raise ValueError("manifest must be a list")
    document_ids = set()
    shas = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("manifest row is not an object")
        for field in ("document_id", "partition", "sha256", "selected_before_biblioref_run"):
            _require(row, field, str if field in ("document_id", "partition", "sha256") else bool)
        document_id = row["document_id"]
        if not document_id:
            raise ValueError("invalid document_id")
        if document_id in document_ids:
            raise ValueError(f"duplicate document_id: {document_id}")
        document_ids.add(document_id)
        _sha(row["sha256"])
        if row["partition"] not in _PARTITIONS:
            raise ValueError(f"invalid partition: {row['partition']}")
        if not row["selected_before_biblioref_run"]:
            raise ValueError(f"selected_before_biblioref_run must be true: {document_id}")
        canonical_sha = row["sha256"].lower()
        if canonical_sha in shas:
            raise ValueError(f"duplicate sha256: {row['sha256']}")
        shas.add(canonical_sha)


def _validate_reference(ref, zone_start, zone_end):
    if not isinstance(ref, dict):
        raise ValueError("reference is not an object")
    required = ("gold_ref_id", "ordinal", "start_page", "start_y_ratio", "start_anchor", "flags")
    for field in required:
        expected = int if field in ("ordinal", "start_page") else ((int, float) if field == "start_y_ratio" else (list if field == "flags" else str))
        _require(ref, field, expected)
    if isinstance(ref["ordinal"], bool) or ref["ordinal"] < 1:
        raise ValueError("invalid ordinal")
    if isinstance(ref["start_page"], bool) or ref["start_page"] < zone_start or ref["start_page"] > zone_end:
        raise ValueError("reference start outside zone pages")
    _ratio(ref["start_y_ratio"])
    if "visible_text_gold" in ref and not isinstance(ref["visible_text_gold"], str):
        raise ValueError("invalid field: visible_text_gold")


def validate_gold(manifest_rows: list[dict], gold_rows: list[dict]) -> None:
    """Validate gold annotations against a previously validated manifest."""
    validate_manifest(manifest_rows)
    if not isinstance(gold_rows, list):
        raise ValueError("gold must be a list")
    manifest = {row["document_id"]: row for row in manifest_rows}
    seen_documents = set()
    for gold in gold_rows:
        if not isinstance(gold, dict):
            raise ValueError("gold row is not an object")
        required = ("document_id", "document_sha256", "annotator_id", "annotation_complete",
                    "document_has_target_bibliography", "zones", "full_text_sample_ids")
        for field in required:
            _require(gold, field, bool if field in ("annotation_complete", "document_has_target_bibliography") else (list if field in ("zones", "full_text_sample_ids") else str))
        document_id = gold["document_id"]
        if document_id not in manifest:
            raise ValueError(f"gold document not in manifest: {document_id}")
        if document_id in seen_documents:
            raise ValueError(f"duplicate gold document_id: {document_id}")
        seen_documents.add(document_id)
        _sha(gold["document_sha256"], "document_sha256")
        if gold["document_sha256"].lower() != manifest[document_id]["sha256"].lower():
            raise ValueError(f"SHA-256 mismatch: {document_id}")
        if not gold["annotation_complete"]:
            raise ValueError(f"annotation_complete must be true: {document_id}")
        if not gold["document_has_target_bibliography"]:
            if gold["zones"] or gold["full_text_sample_ids"]:
                raise ValueError(f"no-target annotation must not contain zones or samples: {document_id}")
            continue
        zone_ids = set()
        ref_ids = set()
        for item in gold["zones"]:
            if not isinstance(item, dict):
                raise ValueError("zone is not an object")
            for field in ("gold_zone_id", "role", "heading_text"):
                _require(item, field, str)
            for field in ("start_page", "end_page"):
                _require(item, field, int)
                if isinstance(item[field], bool):
                    raise ValueError(f"missing or invalid field: {field}")
            for field in ("start_y_ratio", "end_y_ratio"):
                _require(item, field, (int, float))
                _ratio(item[field])
            _require(item, "heading_present", bool)
            _require(item, "references", list)
            if item["start_page"] < 1 or item["end_page"] < item["start_page"]:
                raise ValueError("invalid zone page range")
            if item["start_page"] == item["end_page"] and item["end_y_ratio"] < item["start_y_ratio"]:
                raise ValueError("invalid zone y range")
            if item["gold_zone_id"] in zone_ids:
                raise ValueError(f"duplicate gold_zone_id: {item['gold_zone_id']}")
            zone_ids.add(item["gold_zone_id"])
            ordinals = []
            for ref in item["references"]:
                _validate_reference(ref, item["start_page"], item["end_page"])
                if ref["gold_ref_id"] in ref_ids:
                    raise ValueError(f"duplicate gold_ref_id: {ref['gold_ref_id']}")
                ref_ids.add(ref["gold_ref_id"])
                ordinals.append(ref["ordinal"])
            if ordinals != list(range(1, len(ordinals) + 1)):
                raise ValueError(f"ordinal sequence invalid in zone: {item['gold_zone_id']}")
        references = [reference for zone in gold["zones"] for reference in zone["references"]]
        expected_samples = deterministic_sample_ids(document_id, manifest[document_id]["partition"], references)
        samples = gold["full_text_sample_ids"]
        if samples != expected_samples or len(samples) != len(set(samples)):
            raise ValueError(f"invalid deterministic full-text sample IDs: {document_id}")
        references_by_id = {reference["gold_ref_id"]: reference for reference in references}
        for sample_id in samples:
            text = references_by_id[sample_id].get("visible_text_gold")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"missing visible_text_gold for sampled reference: {sample_id}")
    missing = sorted(set(manifest) - seen_documents)
    if missing:
        raise ValueError(f"missing gold document: {missing[0]}")
