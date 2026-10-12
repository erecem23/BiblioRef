"""BiblioRef extraction pipeline v0.6.8 combined wrapper.

The wrapper preserves the integrated 0.6.7 structural stack and its historical
layer labels, then applies the narrow explicit-heading first-reference
reconciliation before public rescoping, audit and coverage.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from functools import wraps
from pathlib import Path
from typing import Dict, List, Literal, Sequence

from . import pipeline_v065 as _v065
from .pipeline_v065 import *  # re-export the established public surface
from biblioref.core.config import ALGORITHM_VERSION
from biblioref.extraction.dominant_margin_reconciliation import build_dominant_margin_repair
from biblioref.extraction.first_reference_repair import apply_first_reference_repair
from biblioref.extraction.continuation import CONTINUATION_VERSION, continue_numbered_zones
from biblioref.extraction.url_rejoin import rejoin_broken_urls
from biblioref.extraction.effective_repairs import build_vertical_gap_repair
from biblioref.extraction.structural_repairs_v067 import (
    RC1_ORIGIN,
    build_column_reflow_repair_v067,
    build_long_segment_raw_hanging_indent_repair,
)
from biblioref.ingestion.backend_context import active_pdf_backend
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    current_extraction_context,
    timed_extraction_stage,
    use_extraction_context,
)

_ORIGINAL_EFFECTIVE = _v065._process_pdf_effective


def _install_diagnostic_timing_hooks() -> None:
    """Install idempotent ContextVar-aware timing wrappers.

    The wrappers are permanent once installed, so concurrent thesis processing
    never races on temporary module monkeypatches. With no active extraction
    context ``timed_extraction_stage`` is a no-op.
    """
    from biblioref import rescue as rescue_module
    from biblioref.audit import coverage as coverage_module

    def wrap(module, name: str, stage: str) -> None:
        current = getattr(module, name)
        if getattr(current, "_biblioref_timing_stage", None) == stage:
            return

        @wraps(current)
        def measured(*args, **kwargs):
            with timed_extraction_stage(stage):
                return current(*args, **kwargs)

        measured._biblioref_timing_stage = stage
        setattr(module, name, measured)

    wrap(rescue_module, "diagnose_and_recommend", "rescue_audit")
    wrap(coverage_module, "build_coverage_report", "coverage")


def _timed_two_pass_shadow(*args, **kwargs):
    with timed_extraction_stage("two_pass_shadow"):
        return globals()["build_two_pass_shadow"](*args, **kwargs)


def _records_by_zone(records) -> Dict[int, List[Dict]]:
    by_zone: Dict[int, List[Dict]] = defaultdict(list)
    for record in records or []:
        try:
            by_zone[int(record.get("zone_id") or 0)].append(record)
        except (TypeError, ValueError):
            continue
    return by_zone


def _rebuild_with_replacements(
    result: Dict,
    summaries: List[Dict],
    by_zone: Dict[int, List[Dict]],
    replacements: Dict[int, List[Dict]],
) -> Dict:
    combined: List[Dict] = []
    for zone_id in range(1, len(summaries) + 1):
        zone_records = replacements.get(zone_id, by_zone.get(zone_id, []))
        for record in zone_records:
            combined.append({
                key: value for key, value in dict(record).items()
                if key not in _v065.DUPLICATE_FIELDS
            })
    occurrences, duplicate_groups = _v065._annotate_duplicates(combined)
    selected = _v065._select_scope(
        occurrences,
        result.get("scope", "all_reference_sections"),
        final_zone_id=len(summaries) if summaries else None,
    )
    out = dict(result)
    out["records"] = selected
    out["zones"] = summaries
    out["duplicate_groups"] = duplicate_groups
    out["n_occurrences_all_zones"] = len(occurrences)
    out["n_unique_references"] = len(_v065._select_scope(occurrences, "unique_references"))
    out["n_duplicate_groups"] = len(duplicate_groups)
    out["n_occurrences_in_duplicate_groups"] = sum(g["occurrence_count"] for g in duplicate_groups)
    out["n_repeated_occurrences_beyond_first"] = sum(g["occurrence_count"] - 1 for g in duplicate_groups)
    out["n_records_selected"] = len(selected)
    out["algorithm_version"] = ALGORITHM_VERSION
    return out


def _promote_rc_column_labels(base_all: Dict) -> Dict:
    """Correct v0.6.5 labels when the monkeypatched RC1 candidate actually fired."""
    result = dict(base_all)
    reports = list(result.get("column_layout_regime_repairs", []) or [])
    repaired = {
        int(report.get("zone_id") or 0)
        for report in reports
        if report.get("accepted") and "v0_6_7" in str(report.get("reason") or "")
    }
    repaired.discard(0)
    if not repaired:
        return result
    summaries = [dict(zone) for zone in result.get("zones", [])]
    for zone_id in repaired:
        if 1 <= zone_id <= len(summaries):
            summaries[zone_id - 1]["segmentation_method"] = "layout_regime_column_reflow_v0_6_7"
    result["zones"] = summaries
    decision = dict(result.get("detection_decision", {}))
    decision["method"] = "layout_regime_column_reflow_v0_6_7"
    decision["column_reflow_v067_zone_ids"] = sorted(repaired)
    decision["rc1_structural_origin"] = RC1_ORIGIN
    result["detection_decision"] = decision
    return result


def _apply_long_segment_reconciliation(
    pdf_path: str | Path,
    base_all: Dict,
    lines,
    adaptive_mode: str,
) -> Dict:
    """Apply the UNR30 RC1 route only when moderate under-segmentation is visible."""
    result = dict(base_all)
    summaries = [dict(z) for z in result.get("zones", [])]
    records = list(result.get("records", []))
    if not summaries or not records or lines is None:
        result["algorithm_version"] = ALGORITHM_VERSION
        return result
    layout_zones = _v065.detect_adaptive_layout_zones(lines)
    if len(layout_zones) != len(summaries):
        result["algorithm_version"] = ALGORITHM_VERSION
        return result

    by_zone = _records_by_zone(records)
    replacements: Dict[int, List[Dict]] = {}
    raw_reports: List[Dict] = []
    gap_reports: List[Dict] = []
    raw_ids: set[int] = set()
    gap_ids: set[int] = set()
    blocked = {
        "post_segmentation_boundary_reconciliation_v0_6_5",
        "marker_regime_numeric_v0_6_5",
        "marker_regime_hierarchical_v0_6_5",
        "layout_regime_column_reflow_v0_6_5",
        "layout_regime_column_reflow_v0_6_7",
    }

    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        if str(summary.get("segmentation_method") or "") in blocked:
            continue
        current_records = list(by_zone.get(zone_id, []))
        long_segments_180 = sum(
            len(str(record.get("reference_text", "")).split()) >= 180
            for record in current_records
        )
        if long_segments_180 < 2:
            continue
        raw = build_long_segment_raw_hanging_indent_repair(layout_zone, current_records)
        raw_reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            "trigger_long_segments_180": long_segments_180,
            **{key: value for key, value in raw.items() if key != "segments"},
        })
        if raw.get("accepted"):
            current = [
                _v065._record_with_zone_metadata(segment, zone_id, index, summary)
                for index, segment in enumerate(raw.get("segments", []), 1)
            ]
            replacements[zone_id] = current
            summary["segmentation_method"] = "raw_hanging_indent_long_segment_reconciliation_v0_6_7"
            summary["n_segments"] = len(current)
            raw_ids.add(zone_id)
            continue

        gap = build_vertical_gap_repair(layout_zone, current_records)
        gap_reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            "trigger_long_segments_180": long_segments_180,
            **{key: value for key, value in gap.items() if key != "segments"},
        })
        if gap.get("accepted"):
            current = [
                _v065._record_with_zone_metadata(segment, zone_id, index, summary)
                for index, segment in enumerate(gap.get("segments", []), 1)
            ]
            replacements[zone_id] = current
            summary["segmentation_method"] = "long_segment_vertical_gap_reconciliation_v0_6_7"
            summary["n_segments"] = len(current)
            gap_ids.add(zone_id)

    if raw_reports:
        result["long_segment_raw_hanging_indent_attempts"] = raw_reports
    if gap_reports:
        result["long_segment_vertical_gap_attempts"] = gap_reports
    if not replacements:
        result["algorithm_version"] = ALGORITHM_VERSION
        return result

    result = _rebuild_with_replacements(result, summaries, by_zone, replacements)
    decision = dict(result.get("detection_decision", {}))
    repaired = set(decision.get("repaired_zone_ids", []) or []) | set(replacements)
    if raw_ids:
        decision["method"] = "raw_hanging_indent_long_segment_reconciliation_v0_6_7"
        decision["raw_hanging_indent_repaired_zone_ids"] = sorted(raw_ids)
        decision["reason"] = "moderately_long_undersegmented_records_reconciled_by_raw_hanging_indent"
    elif gap_ids:
        decision["method"] = "long_segment_vertical_gap_reconciliation_v0_6_7"
        decision["long_segment_gap_repaired_zone_ids"] = sorted(gap_ids)
        decision["reason"] = "moderately_long_undersegmented_records_reconciled_by_vertical_gap"
    decision["stable_output_preserved"] = False
    decision["repaired_zone_ids"] = sorted(repaired)
    decision["rc1_structural_origin"] = RC1_ORIGIN
    result["detection_decision"] = decision

    if adaptive_mode == "shadow":
        effective_by_zone = {
            zid: list(replacements.get(zid, by_zone.get(zid, [])))
            for zid in range(1, len(summaries) + 1)
        }
        page_roles = _v065.classify_document_pages(lines)
        result["adaptive_shadow"] = _v065.build_adaptive_shadow_report(
            layout_zones,
            summaries,
            effective_by_zone,
            document_lines=lines,
            page_roles=page_roles,
        )
    return result


def _apply_dominant_margin_reconciliation(
    pdf_path: str | Path,
    base_all: Dict,
    lines,
    adaptive_mode: str,
) -> Dict:
    """Preserve the independent Cabrera repair after stronger structural regimes."""
    result = dict(base_all)
    summaries = [dict(z) for z in result.get("zones", [])]
    records = list(result.get("records", []))
    if not summaries or not records or lines is None:
        result["algorithm_version"] = ALGORITHM_VERSION
        return result
    layout_zones = _v065.detect_adaptive_layout_zones(lines)
    if len(layout_zones) != len(summaries):
        result["algorithm_version"] = ALGORITHM_VERSION
        return result
    by_zone = _records_by_zone(records)

    blocked_methods = {
        "post_segmentation_boundary_reconciliation_v0_6_5",
        "marker_regime_numeric_v0_6_5",
        "marker_regime_hierarchical_v0_6_5",
        "layout_regime_column_reflow_v0_6_5",
        "layout_regime_column_reflow_v0_6_7",
        "raw_hanging_indent_long_segment_reconciliation_v0_6_7",
        "long_segment_vertical_gap_reconciliation_v0_6_7",
    }
    replacements: Dict[int, List[Dict]] = {}
    reports: List[Dict] = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        if str(summary.get("segmentation_method") or "") in blocked_methods:
            continue
        base_zone_records = list(by_zone.get(zone_id, []))
        candidate = build_dominant_margin_repair(lines, layout_zone, base_zone_records)
        if not candidate.get("accepted"):
            continue
        current = [
            _v065._record_with_zone_metadata(segment, zone_id, index, summary)
            for index, segment in enumerate(candidate.get("segments", []), 1)
        ]
        replacements[zone_id] = current
        summary["segmentation_method"] = "dominant_margin_topology_reconciliation_v0_6_6"
        summary["n_segments"] = len(current)
        reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            "repair_stage": "dominant_margin_topology_reconciliation",
            "integrated_algorithm_version": "0.6.7",
            **{key: value for key, value in candidate.items() if key != "segments"},
        })
    if not replacements:
        result["algorithm_version"] = ALGORITHM_VERSION
        return result

    result = _rebuild_with_replacements(result, summaries, by_zone, replacements)
    result["dominant_margin_reconciliation_repairs"] = reports
    decision = dict(result.get("detection_decision", {}))
    repaired = set(decision.get("repaired_zone_ids", []) or []) | set(replacements)
    decision.update({
        "method": "dominant_margin_topology_reconciliation_v0_6_6",
        "stable_output_preserved": False,
        "reason": "stable_zones_preserved_and_dominant_margin_topology_reconciled_before_parsing",
        "repaired_zone_ids": sorted(repaired),
        "dominant_margin_reconciled_zone_ids": sorted(replacements),
        "integrated_algorithm_version": "0.6.7",
    })
    result["detection_decision"] = decision

    if adaptive_mode == "shadow":
        effective_by_zone = {
            zid: list(replacements.get(zid, by_zone.get(zid, [])))
            for zid in range(1, len(summaries) + 1)
        }
        page_roles = _v065.classify_document_pages(lines)
        result["adaptive_shadow"] = _v065.build_adaptive_shadow_report(
            layout_zones,
            summaries,
            effective_by_zone,
            document_lines=lines,
            page_roles=page_roles,
        )
    return result


def _apply_first_reference_reconciliation(
    pdf_path: str | Path,
    base_all: Dict,
) -> Dict:
    result = dict(base_all)
    zones = [dict(zone) for zone in result.get("zones", [])]
    before = list(result.get("records", []))
    after, repairs = apply_first_reference_repair(
        pdf_path,
        zones,
        before,
    )
    if not repairs:
        return result

    after_by_zone = _records_by_zone(after)
    repaired_zone_ids = sorted({
        int(repair["zone_id"])
        for repair in repairs
    })
    for zone_id in repaired_zone_ids:
        if 1 <= zone_id <= len(zones):
            zones[zone_id - 1]["n_segments"] = len(
                after_by_zone.get(zone_id, [])
            )

    rebuilt = _rebuild_with_replacements(
        result,
        zones,
        _records_by_zone(before),
        after_by_zone,
    )
    rebuilt["first_reference_repairs"] = repairs
    decision = dict(rebuilt.get("detection_decision", {}))
    decision["first_reference_repaired_zone_ids"] = repaired_zone_ids
    decision["stable_output_preserved"] = False
    rebuilt["detection_decision"] = decision
    return rebuilt


def _apply_continuation_reconciliation(base_all: Dict, lines) -> Dict:
    """0.6.21 (C1): extend a numbered zone over the pages that continue its list."""
    zones = list(base_all.get("zones") or [])
    records = list(base_all.get("records") or [])
    if not zones or not records or not lines:
        return base_all
    new_zones, new_records, repairs = continue_numbered_zones(zones, records, lines)
    if not repairs:
        return base_all
    rebuilt = _rebuild_with_replacements(base_all, new_zones, _records_by_zone(new_records), {})
    rebuilt["continuation_repairs"] = repairs
    decision = dict(rebuilt.get("detection_decision", {}))
    decision["continuation_zone_ids"] = sorted(r["zone_id"] for r in repairs)
    decision["stable_output_preserved"] = False
    rebuilt["detection_decision"] = decision
    return rebuilt


#: 0.6.13: a heading repeated in this many zones before the bibliography is a label, not a section.
INTERNAL_LIST_MIN_REPEATS = 3
#: ... and only when those zones are small next to the final bibliography.
INTERNAL_LIST_MAX_SHARE = 0.10
INTERNAL_LIST_MIN_FINAL_RECORDS = 50


def _heading_key(text) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z]+", " ", folded).strip()


def _drop_repeated_internal_lists(result: dict) -> dict:
    """Drop zones opened by one heading repeated inside the body.

    T0136 transcribes course syllabi; each has its own «Bibliografía:», and every
    one opened a zone of readings and numbered program items before the thesis's
    real «Referencias Bibliográficas:». Per-chapter bibliographies look alike, so
    the rule needs all of: the same heading in at least three zones, all of them
    before a final bibliography with another heading, and together no more than a
    tenth of its records.
    """
    zones = list(result.get("zones") or [])
    records = list(result.get("records") or [])
    if len(zones) < INTERNAL_LIST_MIN_REPEATS + 1:
        return result
    counts: dict = {}
    for record in records:
        counts[record.get("zone_id")] = counts.get(record.get("zone_id"), 0) + 1
    final = max(zones, key=lambda z: (counts.get(z.get("zone_id"), 0), z.get("start_page") or 0))
    final_n = counts.get(final.get("zone_id"), 0)
    if final_n < INTERNAL_LIST_MIN_FINAL_RECORDS:
        return result
    if any((z.get("start_page") or 0) > (final.get("start_page") or 0) for z in zones):
        return result
    final_key = _heading_key(final.get("heading"))
    groups: dict = {}
    for zone in zones:
        key = _heading_key(zone.get("heading"))
        if key and key != final_key:
            groups.setdefault(key, []).append(zone)
    dropped = []
    for group in groups.values():
        n = sum(counts.get(z.get("zone_id"), 0) for z in group)
        if len(group) >= INTERNAL_LIST_MIN_REPEATS and n <= INTERNAL_LIST_MAX_SHARE * final_n:
            dropped.extend(group)
    if not dropped:
        return result
    ids = {z.get("zone_id") for z in dropped}
    out = dict(result)
    out["zones"] = [z for z in zones if z.get("zone_id") not in ids]
    out["records"] = [r for r in records if r.get("zone_id") not in ids]
    if "n_records_selected" in out:
        out["n_records_selected"] = len(out["records"])
    out["internal_list_zones_dropped"] = [
        {"zone_id": z.get("zone_id"), "heading": z.get("heading"), "start_page": z.get("start_page"),
         "end_page": z.get("end_page"), "n_records": counts.get(z.get("zone_id"), 0)}
        for z in dropped
    ]
    out["default_effective_output_changed"] = True
    return out


def _rejoin_broken_urls(result: dict) -> dict:
    """0.6.17: a line break inside a URL left a space in it; see url_rejoin."""
    records = list(result.get("records") or [])
    changed = False
    fixed = []
    for record in records:
        text = str(record.get("reference_text") or "")
        joined = rejoin_broken_urls(text)
        if joined != text:
            record = dict(record, reference_text=joined)
            changed = True
        fixed.append(record)
    if not changed:
        return result
    out = dict(result)
    out["records"] = fixed
    return out


def _process_pdf_effective(
    pdf_path: str | Path,
    scope="all_reference_sections",
    adaptive_mode="shadow",
    two_pass_shadow: bool = False,
):
    captured = {}
    public_extract = globals()["extract_layout_lines"]
    original_extract = _v065.extract_layout_lines
    original_column_repair = _v065.build_column_reflow_repair_v2

    def capturing_extract(path):
        value = public_extract(path)
        captured["lines"] = value
        return value

    _v065.extract_layout_lines = capturing_extract
    _v065.classify_document_pages = globals()["classify_document_pages"]
    _v065.process_pdf_v06 = globals()["process_pdf_v06"]
    _v065.build_column_reflow_repair_v2 = build_column_reflow_repair_v067

    try:
        with timed_extraction_stage("effective_base"):
            base = _ORIGINAL_EFFECTIVE(
                pdf_path,
                scope="all_reference_sections",
                adaptive_mode=adaptive_mode,
                two_pass_shadow=two_pass_shadow,
            )
    finally:
        _v065.extract_layout_lines = original_extract
        _v065.build_column_reflow_repair_v2 = original_column_repair

    lines = captured.get("lines")
    base = _promote_rc_column_labels(base)
    with timed_extraction_stage("long_segment_reconciliation"):
        repaired = _apply_long_segment_reconciliation(pdf_path, base, lines, adaptive_mode)
    with timed_extraction_stage("dominant_margin_reconciliation"):
        repaired = _apply_dominant_margin_reconciliation(pdf_path, repaired, lines, adaptive_mode)
    with timed_extraction_stage("first_reference_reconciliation"):
        repaired = _apply_first_reference_reconciliation(pdf_path, repaired)
    with timed_extraction_stage("continuation_reconciliation"):
        repaired = _apply_continuation_reconciliation(repaired, lines)
    repaired = _drop_repeated_internal_lists(repaired)
    repaired = _rejoin_broken_urls(repaired)
    repaired["algorithm_version"] = ALGORITHM_VERSION
    repaired["algorithm_integration"] = {
        "version": "0.6.8",
        "preserved_base": "0.6.5",
        "cabrera_dominant_margin": "0.6.6",
        "rc1_structural_origin": RC1_ORIGIN,
        "first_reference_repair": "0.6.8-core-first-reference-1",
        "continuation": CONTINUATION_VERSION,
    }
    if scope != "all_reference_sections":
        repaired = _v065._rescope_existing_report(repaired, scope)
        repaired["algorithm_version"] = ALGORITHM_VERSION
    return repaired


_v065._process_pdf_effective = _process_pdf_effective


def _process_pdf_with_active_context(*args, **kwargs):
    _install_diagnostic_timing_hooks()
    _v065.build_two_pass_shadow = _timed_two_pass_shadow
    result = _v065.process_pdf(*args, **kwargs)
    result["algorithm_version"] = ALGORITHM_VERSION
    if (
        result.get("dominant_margin_reconciliation_repairs")
        or result.get("detection_decision", {}).get("column_reflow_v067_zone_ids")
        or result.get("detection_decision", {}).get("raw_hanging_indent_repaired_zone_ids")
        or result.get("detection_decision", {}).get("long_segment_gap_repaired_zone_ids")
        or result.get("first_reference_repairs")
        or result.get("continuation_repairs")
    ):
        result["default_effective_output_changed"] = True
    return result


def process_pdf(*args, **kwargs):
    existing = current_extraction_context()
    if existing is not None:
        return _process_pdf_with_active_context(*args, **kwargs)

    pdf_path = args[0] if args else kwargs["pdf_path"]
    context = ExtractionContext.for_pdf(
        pdf_path,
        backend=active_pdf_backend(),
        reuse_enabled=True,
    )
    with use_extraction_context(context):
        with timed_extraction_stage("process_pdf"):
            return _process_pdf_with_active_context(*args, **kwargs)
