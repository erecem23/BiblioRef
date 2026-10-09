"""Pipeline-level differential validation for experimental PDF backends.

This module never changes BiblioRef's default backend. It selects a backend in
a context local to each replay so layout extraction, rescue, coverage,
structural repairs and two-pass diagnostics all observe the same engine.
"""
from __future__ import annotations

import difflib
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

import biblioref.pipeline as pipeline

from biblioref.ingestion.backend_context import use_pdf_backend


_PIPELINE_DIFF_LOCK = threading.Lock()
_REFERENCE_TEXT_EQUIVALENCE = 0.999

_ZONE_SEMANTIC_FIELDS = (
    "zone_id",
    "heading",
    "zone_role",
    "start_page",
    "end_page",
    "style",
    "n_segments",
    "segmentation_method",
    "termination_reason",
    "zone_completeness",
    "start_confidence_label",
    "end_confidence_label",
    "numeric_first_marker",
    "numeric_last_marker",
    "numeric_missing_markers",
    "numeric_duplicate_markers",
    "numeric_sequence_warning",
)

# These fields are backend geometry/diagnostic or hashes derived from raw PDF
# spelling. They remain visible in ``records.raw_exact`` but do not decide
# bibliographic equivalence between two engines.
_RECORD_BACKEND_FIELDS = {
    "reference_start_x",
    "audit_flags",
    "reference_fingerprint",
    "duplicate_group_id",
}
_RECORD_TEXT_FIELDS = {"reference_text", "annotation_text"}


def _project(items: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {field: item.get(field) for field in fields if field in item}
        for item in items
    ]


def _first_mismatch(left: Sequence[Any], right: Sequence[Any]) -> Dict[str, Any] | None:
    for index in range(max(len(left), len(right))):
        left_item = left[index] if index < len(left) else None
        right_item = right[index] if index < len(right) else None
        if left_item != right_item:
            return {
                "index": index,
                "pymupdf": left_item,
                "pdfium": right_item,
            }
    return None


def _summary(report: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "n_zones": report.get("n_zones"),
        "n_records_selected": report.get("n_records_selected"),
        "n_occurrences_all_zones": report.get("n_occurrences_all_zones"),
        "n_unique_references": report.get("n_unique_references"),
        "n_duplicate_groups": report.get("n_duplicate_groups"),
        "algorithm_version": report.get("algorithm_version"),
    }


def _canonical_bibliographic_text(value: Any) -> str:
    """Canonical text used only by the backend migration gate.

    Backend engines routinely disagree on where PDF word-boundary whitespace
    lives.  Record count/order and semantic metadata are checked separately, so
    whitespace is non-semantic here.  Punctuation and every non-whitespace
    character are preserved.  PDF discretionary soft hyphens are normalized to
    the ordinary hyphen character, never deleted.
    """
    text = str(value or "").replace("\xad", "-")
    return re.sub(r"\s+", "", text)


def _text_similarity(left: Any, right: Any) -> float:
    a = _canonical_bibliographic_text(left)
    b = _canonical_bibliographic_text(right)
    if a == b:
        return 1.0
    return float(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio())


def _candidate_superset(stable_value: Any, candidate_value: Any) -> dict[str, Any] | None:
    """Return insertion-only evidence when candidate preserves all stable text.

    This is intentionally asymmetric: a candidate may add recoverable content,
    but any deletion, replacement or reordering remains a migration failure.
    Raw text is still reported elsewhere, so accepting a possible superset never
    hides the backend difference.
    """
    stable = _canonical_bibliographic_text(stable_value)
    candidate = _canonical_bibliographic_text(candidate_value)
    if not stable or stable == candidate:
        return None
    matcher = difflib.SequenceMatcher(None, stable, candidate, autojunk=False)
    insertions: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            inserted = candidate[j1:j2]
            if inserted:
                insertions.append(inserted)
            continue
        return None
    if not insertions:
        return None
    return {
        "relation": "possible_content_superset",
        "inserted_text": insertions,
        "added_characters": sum(len(x) for x in insertions),
    }


def _record_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in _RECORD_BACKEND_FIELDS and key not in _RECORD_TEXT_FIELDS
    }


def _compare_bibliographic_records(
    stable_records: Sequence[Mapping[str, Any]],
    candidate_records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if len(stable_records) != len(candidate_records):
        return {
            "equivalent": False,
            "threshold": _REFERENCE_TEXT_EQUIVALENCE,
            "min_reference_text_similarity": 0.0,
            "min_annotation_text_similarity": 0.0,
            "possible_content_supersets": [],
            "possible_content_superset_count": 0,
            "first_mismatch": {
                "reason": "record_count",
                "pymupdf": len(stable_records),
                "pdfium": len(candidate_records),
            },
        }

    min_reference = 1.0
    min_annotation = 1.0
    supersets: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(stable_records, candidate_records)):
        left_meta = _record_metadata(left)
        right_meta = _record_metadata(right)
        if left_meta != right_meta:
            return {
                "equivalent": False,
                "threshold": _REFERENCE_TEXT_EQUIVALENCE,
                "min_reference_text_similarity": round(min_reference, 6),
                "min_annotation_text_similarity": round(min_annotation, 6),
                "possible_content_supersets": supersets,
                "possible_content_superset_count": len(supersets),
                "first_mismatch": {
                    "index": index,
                    "reason": "semantic_metadata",
                    "pymupdf": left_meta,
                    "pdfium": right_meta,
                },
            }

        left_reference = left.get("reference_text")
        right_reference = right.get("reference_text")
        left_annotation = left.get("annotation_text")
        right_annotation = right.get("annotation_text")
        reference_similarity = _text_similarity(left_reference, right_reference)
        annotation_similarity = _text_similarity(left_annotation, right_annotation)
        min_reference = min(min_reference, reference_similarity)
        min_annotation = min(min_annotation, annotation_similarity)

        reference_superset = None
        annotation_superset = None
        if reference_similarity < _REFERENCE_TEXT_EQUIVALENCE:
            reference_superset = _candidate_superset(left_reference, right_reference)
        if annotation_similarity < _REFERENCE_TEXT_EQUIVALENCE:
            annotation_superset = _candidate_superset(left_annotation, right_annotation)

        reference_ok = reference_similarity >= _REFERENCE_TEXT_EQUIVALENCE or reference_superset is not None
        annotation_ok = annotation_similarity >= _REFERENCE_TEXT_EQUIVALENCE or annotation_superset is not None
        if reference_superset is not None or annotation_superset is not None:
            supersets.append({
                "index": index,
                "reference_text": reference_superset,
                "annotation_text": annotation_superset,
                "pymupdf_reference_text": left_reference,
                "pdfium_reference_text": right_reference,
            })

        if not reference_ok or not annotation_ok:
            return {
                "equivalent": False,
                "threshold": _REFERENCE_TEXT_EQUIVALENCE,
                "min_reference_text_similarity": round(min_reference, 6),
                "min_annotation_text_similarity": round(min_annotation, 6),
                "possible_content_supersets": supersets,
                "possible_content_superset_count": len(supersets),
                "first_mismatch": {
                    "index": index,
                    "reason": "bibliographic_text",
                    "reference_text_similarity": round(reference_similarity, 6),
                    "annotation_text_similarity": round(annotation_similarity, 6),
                    "pymupdf_reference_text": left_reference,
                    "pdfium_reference_text": right_reference,
                },
            }

    return {
        "equivalent": True,
        "threshold": _REFERENCE_TEXT_EQUIVALENCE,
        "min_reference_text_similarity": round(min_reference, 6),
        "min_annotation_text_similarity": round(min_annotation, 6),
        "possible_content_supersets": supersets,
        "possible_content_superset_count": len(supersets),
        "first_mismatch": None,
    }


def compare_pipeline_backends(
    pdf_path: str | Path,
    *,
    scope: str = "all_reference_sections",
    adaptive_mode: str = "shadow",
    two_pass_shadow: bool = False,
) -> Dict[str, Any]:
    """Run the current pipeline once per backend and compare its output."""
    path = Path(pdf_path)

    with _PIPELINE_DIFF_LOCK:
        with use_pdf_backend("pymupdf"):
            started = time.perf_counter()
            stable = pipeline.process_pdf(
                path,
                scope=scope,
                adaptive_mode=adaptive_mode,
                two_pass_shadow=two_pass_shadow,
            )
            stable_elapsed = time.perf_counter() - started

        with use_pdf_backend("pdfium"):
            started = time.perf_counter()
            candidate = pipeline.process_pdf(
                path,
                scope=scope,
                adaptive_mode=adaptive_mode,
                two_pass_shadow=two_pass_shadow,
            )
            candidate_elapsed = time.perf_counter() - started

    stable_zones = list(stable.get("zones", []) or [])
    candidate_zones = list(candidate.get("zones", []) or [])
    stable_zone_semantics = _project(stable_zones, _ZONE_SEMANTIC_FIELDS)
    candidate_zone_semantics = _project(candidate_zones, _ZONE_SEMANTIC_FIELDS)

    stable_records = list(stable.get("records", []) or [])
    candidate_records = list(candidate.get("records", []) or [])
    stable_decision = stable.get("detection_decision")
    candidate_decision = candidate.get("detection_decision")

    records_raw_exact = stable_records == candidate_records
    record_equivalence = _compare_bibliographic_records(stable_records, candidate_records)
    zones_exact = stable_zones == candidate_zones
    zones_semantic_exact = stable_zone_semantics == candidate_zone_semantics
    detection_decision_exact = stable_decision == candidate_decision
    summary_equal = _summary(stable) == _summary(candidate)

    strict_raw_passes = bool(records_raw_exact and zones_semantic_exact and summary_equal)
    bibliographic_passes = bool(
        record_equivalence["equivalent"]
        and zones_semantic_exact
        and summary_equal
    )

    return {
        "pdf": str(path),
        "scope": scope,
        "stable_backend": "pymupdf",
        "candidate_backend": "pdfium",
        "stable_backend_changed": False,
        "elapsed_seconds": {
            "pymupdf": round(stable_elapsed, 6),
            "pdfium": round(candidate_elapsed, 6),
            "pdfium_over_pymupdf": round(candidate_elapsed / stable_elapsed, 6)
            if stable_elapsed > 0
            else None,
        },
        "summary": {
            "pymupdf": _summary(stable),
            "pdfium": _summary(candidate),
            "equal": summary_equal,
        },
        "zones": {
            "raw_exact": zones_exact,
            "semantic_exact": zones_semantic_exact,
            "first_raw_mismatch": _first_mismatch(stable_zones, candidate_zones),
            "first_semantic_mismatch": _first_mismatch(
                stable_zone_semantics,
                candidate_zone_semantics,
            ),
        },
        "records": {
            "raw_exact": records_raw_exact,
            "exact": records_raw_exact,
            "first_raw_mismatch": _first_mismatch(stable_records, candidate_records),
            "bibliographic_equivalence": record_equivalence,
        },
        "detection_decision": {
            "exact": detection_decision_exact,
            "pymupdf": stable_decision,
            "pdfium": candidate_decision,
        },
        "strict_raw_gate": {
            "passes": strict_raw_passes,
            "requires_raw_exact_records": True,
            "requires_semantic_zone_equivalence": True,
        },
        "migration_gate": {
            "passes": bibliographic_passes,
            "requires_bibliographic_record_equivalence": True,
            "reference_text_similarity_threshold": _REFERENCE_TEXT_EQUIVALENCE,
            "requires_semantic_zone_equivalence": True,
            "raw_record_geometry_may_differ": True,
            "raw_zone_geometry_may_use_tolerance": True,
        },
    }
