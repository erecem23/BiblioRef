"""High-level, interface-independent BiblioRef extraction pipeline.

v0.9.0 preserves the validated v0.6.1 extraction decisions and adds an
interpretable adaptive *shadow* layer. Regions discovered after stable-route
abstention must first pass an independent bibliography-region verification gate.
Shadow analysis may generate and compare alternative segmentations, but it never
replaces records or zones.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Literal, Sequence

from biblioref.adaptive.discovery import discover_shadow_regions
from biblioref.adaptive.hypotheses import build_adaptive_shadow_report, build_discovered_shadow_report
from biblioref.adaptive.stable_conflicts import build_effective_zone_conflict_diagnostics
from biblioref.adaptive.two_pass import build_two_pass_shadow
from biblioref.adaptive.context import summarize_document_context, classify_document_pages
from biblioref.adaptive.geometry import detect_repeated_decorations
from biblioref.adaptive.input_hygiene import detect_input_decorations, public_decoration_report
from biblioref.core.config import (
    ADAPTIVE_ANALYSIS_VERSION,
    ALGORITHM_VERSION,
    BASE_VERSION,
    SOFTWARE_VERSION,
    STABLE_ENGINE_VERSION,
    RESCUE_ROUTER_VERSION,
)
from biblioref.core.types import Report, Scope
from biblioref.detection.fallback import (
    process_pdf_v06,
    _heading_supported_region,
    _expanded_region_start_y,
)
from biblioref.detection.repair import logical_running_header_groups, repair_decision
from biblioref.extraction.resegmentation import segment_enhanced_zone
from biblioref.extraction.boundary_reconciliation import build_hanging_indent_boundary_repair
from biblioref.extraction.marker_regime import build_hierarchical_marker_repair
from biblioref.extraction.numeric_rescue import (
    build_numeric_layout_resegmentation, numeric_filter_candidate,
    extend_numeric_candidate_end_page,
)
from biblioref.extraction.column_reflow import build_column_reflow_repair_v2
from biblioref.ingestion import extract_layout_lines
from biblioref.audit.manual import process_manual_zone
from biblioref.audit.models import ManualZoneSpec
from biblioref.legacy.engine import (
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    _annotate_duplicates,
    _select_scope,
    detect_adaptive_layout_zones,
    AdaptiveLayoutZone,
    LayoutLine,
    diagnose_adaptive_style,
    diagnose_adaptive_layout,
    _is_footer,
    _is_small_font_noise,
)

AdaptiveMode = Literal["off", "shadow"]
VALID_ADAPTIVE_MODES = {"off", "shadow"}

DUPLICATE_FIELDS = {
    "reference_fingerprint",
    "duplicate_group_id",
    "duplicate_occurrence_count",
    "duplicate_zone_ids",
    "is_repeated_across_zones",
}


def _record_with_zone_metadata(
    segment: Dict, zone_id: int, ref_in_zone: int, summary: Dict
) -> Dict:
    record = dict(segment)
    record.update({
        "zone_id": zone_id,
        "ref_in_zone": ref_in_zone,
        "zone_heading": summary["heading"],
        "zone_role": summary["zone_role"],
        "zone_start_page": summary["start_page"],
        "zone_end_page": summary["end_page"],
        "zone_start_confidence_score": summary["start_confidence_score"],
        "zone_start_confidence_label": summary["start_confidence_label"],
        "zone_end_confidence_score": summary["end_confidence_score"],
        "zone_end_confidence_label": summary["end_confidence_label"],
        "zone_completeness": summary["zone_completeness"],
        "zone_termination_reason": summary["termination_reason"],
        "zone_adaptive_limit_exceeded": summary["adaptive_limit_exceeded"],
    })
    return record


def _with_modular_metadata(result: Report) -> Report:
    output = dict(result)
    output["software_version"] = SOFTWARE_VERSION
    output["base_version"] = BASE_VERSION
    output["algorithm_version"] = ALGORITHM_VERSION
    output["adaptive_analysis_version"] = ADAPTIVE_ANALYSIS_VERSION
    output["architecture"] = "modular_v13_candidate_region_marker_layout_regimes"
    return output


def _not_run_shadow(reason: str, lines=None, page_roles=None) -> Dict:
    lines = list(lines or [])
    context = summarize_document_context(lines, page_roles) if lines else {}
    decorations = detect_repeated_decorations(lines) if lines else {"minimum_pages": 0, "n_repeated_decorations": 0, "items": [], "keys": set()}
    input_decorations = detect_input_decorations(lines) if lines else {"confirmed": [], "watch": [], "confirmed_keys": set(), "watch_keys": set(), "n_confirmed": 0, "n_watch": 0}
    return {
        "version": ADAPTIVE_ANALYSIS_VERSION,
        "mode": "shadow",
        "decision_policy": "document_context_then_verify_region_then_geometry_score_boundaries_never_replace_output",
        "probabilities_used": False,
        "auto_apply": False,
        "document_context": context,
        "repeated_decorations": {k: v for k, v in decorations.items() if k != "keys"},
        "input_hygiene": {"decorations": public_decoration_report(input_decorations), "diagnostic_only": True, "auto_apply": False},
        "overall_status": "not_run",
        "reason": reason,
        "review_zone_ids": [],
        "stable_context_conflict_zone_ids": [],
        "stable_segmentation_conflict_zone_ids": [],
        "stable_structural_conflict_zone_ids": [],
        "n_stable_structural_conflicts": 0,
        "n_regions_discovered": 0,
        "n_regions_verified": 0,
        "n_regions_plausible_unverified": 0,
        "n_regions_rejected": 0,
        "n_zones_analyzed": 0,
        "region_verification_gate": "required_before_shadow_segmentation",
        "region_verifications": [],
        "zones": [],
    }


def _rescope_existing_report(base_all: Report, scope: Scope) -> Report:
    """Select a public scope from an all-zones report without rerunning extraction."""
    if scope == "all_reference_sections":
        return dict(base_all)
    output = dict(base_all)
    occurrences = list(base_all.get("records", []))
    final_zone_id = len(base_all.get("zones", [])) if base_all.get("zones") else None
    selected = _select_scope(occurrences, scope, final_zone_id=final_zone_id)
    output["scope"] = scope
    output["scope_definition"] = SCOPE_DEFINITIONS[scope]
    output["records"] = selected
    output["n_records_selected"] = len(selected)
    return output





def _return_nonstable_base_with_shadow(
    base_all: Report,
    scope: Scope,
    adaptive_mode: AdaptiveMode,
    lines: Sequence[LayoutLine],
) -> Report:
    """Preserve the pre-v0.6.5 public contract when no new repair is applied."""
    result = _rescope_existing_report(base_all, scope)
    if adaptive_mode == "shadow":
        page_roles = classify_document_pages(lines)
        page_count = max((int(line.page) for line in lines), default=0)
        regions = discover_shadow_regions(lines, page_count)
        if regions:
            result["adaptive_shadow"] = build_discovered_shadow_report(lines, regions, page_roles=page_roles)
            result["adaptive_shadow"]["base_detection_method"] = base_all.get(
                "detection_decision", {}
            ).get("method")
        else:
            result["adaptive_shadow"] = _not_run_shadow(
                "base_route_abstained_and_no_adaptive_layout_region_was_found", lines, page_roles
            )

        summaries = [dict(zone) for zone in result.get("zones", [])]
        if summaries:
            diagnostic_layout_zones = detect_adaptive_layout_zones(lines)
            by_zone: Dict[int, List[Dict]] = defaultdict(list)
            for record in result.get("records", []):
                try:
                    by_zone[int(record.get("zone_id", 0) or 0)].append(record)
                except (TypeError, ValueError):
                    continue
            effective_diag = build_effective_zone_conflict_diagnostics(
                lines,
                diagnostic_layout_zones,
                summaries,
                by_zone,
                discovered_shadow_report=result.get("adaptive_shadow"),
                page_roles=page_roles,
            )
            result["adaptive_shadow"]["stable_effective_zone_diagnostics"] = effective_diag
            for key in (
                "stable_context_conflict_zone_ids",
                "stable_segmentation_conflict_zone_ids",
                "stable_structural_conflict_zone_ids",
                "n_stable_structural_conflicts",
            ):
                result["adaptive_shadow"][key] = effective_diag.get(key)
            if effective_diag.get("stable_structural_conflict_zone_ids"):
                result["adaptive_shadow"]["overall_status"] = "manual_review_required"
    return _with_modular_metadata(result)

def _normalize_zone_summary(summary: Dict) -> Dict:
    """Fill the metadata contract expected by downstream reconciliation.

    Stable summaries already contain these fields. Candidate/fallback summaries
    historically exposed a smaller public schema, so v0.6.5 supplies equivalent
    conservative defaults without changing stable values.
    """
    out = dict(summary)
    start_page = int(out.get("start_page") or 0)
    end_page = int(out.get("end_page") or start_page or 0)
    combined_score = float(out.get("combined_confidence_score") or out.get("start_confidence_score") or 0.85)
    combined_label = str(out.get("combined_confidence_label") or out.get("start_confidence_label") or "medium")
    out.setdefault("zone_role", "primary_references")
    out.setdefault("start_confidence_score", combined_score)
    out.setdefault("start_confidence_label", combined_label)
    out.setdefault("end_confidence_score", combined_score)
    out.setdefault("end_confidence_label", combined_label)
    out.setdefault("zone_completeness", "requires_confirmation")
    out.setdefault("termination_reason", "effective_candidate_boundary")
    out.setdefault("adaptive_limit_exceeded", False)
    out.setdefault("zone_span_pages", max(1, end_page - start_page + 1) if start_page else 1)
    return out

def _layout_zone_from_effective_summary(
    lines: Sequence[LayoutLine], summary: Dict
) -> AdaptiveLayoutZone | None:
    """Reconstruct an AdaptiveLayoutZone from an already accepted effective zone.

    CandidateRegionV2 is intentionally detected outside the stable heading route.
    Before v0.6.5, those candidate zones could be segmented once by the fallback
    path but could not enter the same geometry/marker reconciliation stack used by
    stable zones.  This bridge gives an accepted effective zone the same geometric
    representation without changing its original detection decision.
    """
    try:
        start_page = int(summary.get("start_page") or 0)
        end_page = int(summary.get("end_page") or start_page)
        start_y = float(summary.get("start_y") or 0.0)
        raw_end_y = summary.get("end_y")
        end_y = float(raw_end_y) if raw_end_y is not None else None
    except (TypeError, ValueError):
        return None
    if start_page <= 0 or end_page < start_page:
        return None

    body: List[LayoutLine] = []
    for line in lines:
        page = int(line.page)
        if page < start_page or page > end_page:
            continue
        if page == start_page and float(line.y0) <= start_y + 1.0:
            continue
        if page == end_page and end_y is not None and float(line.y0) >= end_y - 1.0:
            continue
        if _is_footer(line):
            continue
        body.append(line)
    if not body:
        return None

    style = diagnose_adaptive_style([str(line.text or "") for line in body[:400]])
    layout = diagnose_adaptive_layout(body[:400], style)
    cleaned = [line for line in body if not _is_small_font_noise(line, layout)]
    if cleaned:
        body = cleaned
    first = body[0]
    heading_text = str(summary.get("heading") or "Candidate bibliography region")
    heading = LayoutLine(
        page=start_page,
        page_height=float(first.page_height),
        text=heading_text,
        x0=float(first.x0),
        y0=start_y,
        x1=float(first.x1),
        y1=start_y + max(float(first.median_font_size), 10.0),
        median_font_size=float(first.median_font_size),
        fragment_count=1,
    )
    span = end_page - start_page + 1
    confidence = float(summary.get("combined_confidence_score") or 0.85)
    label = str(summary.get("combined_confidence_label") or "medium")
    return AdaptiveLayoutZone(
        heading=heading,
        lines=body,
        start_page=start_page,
        end_page=end_page,
        style=style,
        layout=layout,
        termination_reason=str(summary.get("termination_reason") or "effective_candidate_boundary"),
        confidence_score=confidence,
        confidence_label=label,
        confidence_reasons=["effective_zone_reconstructed_for_reconciliation"],
        start_confidence_score=float(summary.get("start_confidence_score") or confidence),
        start_confidence_label=str(summary.get("start_confidence_label") or label),
        start_confidence_reasons=["effective_zone_start_preserved"],
        end_confidence_score=float(summary.get("end_confidence_score") or confidence),
        end_confidence_label=str(summary.get("end_confidence_label") or label),
        end_confidence_reasons=["effective_zone_end_preserved"],
        zone_completeness=str(summary.get("zone_completeness") or "requires_confirmation"),
        adaptive_soft_limit_pages=0,
        zone_span_pages=span,
        adaptive_limit_exceeded=bool(summary.get("adaptive_limit_exceeded", False)),
    )


def _provisional_candidate_region_report(
    pdf_path: str | Path,
    lines: Sequence[LayoutLine],
    base_all: Report,
) -> tuple[Report, List[AdaptiveLayoutZone]] | None:
    """Materialize one independently verified candidate region for repair only.

    The provisional records are never returned unless a downstream structural
    regime (numeric, hierarchical, column or boundary reconciliation) actually
    passes its own gate.  This lets a strong region survive a poor first
    segmentation (for example, a two-column bibliography) without weakening the
    public fallback quality gate.
    """
    page_count = max((int(line.page) for line in lines), default=0)
    regions = list(base_all.get("candidate_reference_regions", []) or [])
    if not regions or page_count <= 0:
        return None
    region = _heading_supported_region(lines, regions, page_count)
    if region is None or not region.get("heading_support"):
        return None
    start_y = _expanded_region_start_y(lines, region)
    heading_text = str((region.get("heading_support") or {}).get("text") or "Candidate bibliography region")
    spec = ManualZoneSpec(
        start_page=int(region["start_page"]),
        start_y=float(start_y),
        end_page=int(region["end_page"]),
        end_y=None,
        heading_text=heading_text,
        note="CandidateRegionV2 provisional geometry; requires downstream structural repair.",
    )
    try:
        inferred = process_manual_zone(pdf_path, spec, lines, zone_id=1)
    except ValueError:
        return None
    zone_summary = dict(inferred["zone"])
    zone_summary.update({
        "manual_zone": False,
        "detection_method": "candidate_region_v2_provisional",
        "requires_confirmation": True,
        "termination_reason": "candidate_reference_density_end",
        "zone_completeness": "requires_confirmation",
        "combined_confidence_score": float(region.get("confidence_score") or 0.0),
        "combined_confidence_label": "high" if float(region.get("confidence_score") or 0.0) >= 0.90 else "medium",
        "inference_evidence": region.get("evidence", ""),
    })
    records: List[Dict] = []
    for record in inferred.get("records", []):
        item = dict(record)
        item.update({
            "manual_zone": False,
            "detection_method": "candidate_region_v2_provisional",
            "audit_status": "pending_review",
            "audit_note": "Zona candidata provisional: sólo efectiva si una reparación estructural pasa su gate.",
        })
        records.append(item)
    provisional = dict(base_all)
    provisional["zones"] = [zone_summary]
    provisional["records"] = records
    provisional["n_zones"] = 1
    provisional["n_occurrences_all_zones"] = len(records)
    provisional["n_records_selected"] = len(records)
    provisional["detection_decision"] = {
        **dict(base_all.get("detection_decision", {})),
        "method": "candidate_region_v2_provisional",
        "stable_output_preserved": False,
        "requires_confirmation": True,
        "reason": "heading_plus_reference_density_region_materialized_for_structural_repair_only",
        "candidate_region": {k: region.get(k) for k in ("start_page", "end_page", "start_y", "style_guess", "confidence_score", "evidence", "heading_support")},
    }
    layout_zone = _layout_zone_from_effective_summary(lines, zone_summary)
    if layout_zone is None:
        return None
    return provisional, [layout_zone]

def _process_pdf_effective(
    pdf_path: str | Path,
    scope: Scope = "all_reference_sections",
    adaptive_mode: AdaptiveMode = "shadow",
    two_pass_shadow: bool = False,
) -> Report:
    """Extract references and optionally run adaptive analysis in shadow mode.

    ``adaptive_mode='shadow'`` is deliberately non-destructive: the returned
    ``records``, ``zones`` and extraction decision remain those of the validated
    v0.6.1 algorithm. The additional ``adaptive_shadow`` field records region
    verification, candidate boundaries and whole-segmentation comparisons for
    inspection.
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    if adaptive_mode not in VALID_ADAPTIVE_MODES:
        raise ValueError(
            f"Invalid adaptive_mode {adaptive_mode!r}; choose one of {sorted(VALID_ADAPTIVE_MODES)}"
        )

    lines = extract_layout_lines(pdf_path)
    original_base_all = process_pdf_v06(pdf_path, scope="all_reference_sections", lines=lines)
    base_all = original_base_all
    base_detection_method = str(base_all.get("detection_decision", {}).get("method") or "")
    provisional_candidate_requires_repair = False

    if base_detection_method == "stable_v0_5_3_route":
        layout_zones = detect_adaptive_layout_zones(lines)
    else:
        # Candidate/fallback zones used to return before the geometry and marker
        # reconciliation stack.  Reconstruct accepted effective zones so they
        # can use the same downstream gates as stable zones.
        summaries_existing = [dict(zone) for zone in base_all.get("zones", [])]
        layout_zones = [
            zone for zone in (
                _layout_zone_from_effective_summary(lines, summary)
                for summary in summaries_existing
            ) if zone is not None
        ]
        if not summaries_existing or len(layout_zones) != len(summaries_existing):
            provisional = _provisional_candidate_region_report(pdf_path, lines, base_all)
            if provisional is not None:
                base_all, layout_zones = provisional
                base_detection_method = "candidate_region_v2_provisional"
                provisional_candidate_requires_repair = True
            else:
                # No accepted or independently verified candidate can enter the
                # effective stack. Preserve the historical audit/fallback output.
                return _return_nonstable_base_with_shadow(
                    original_base_all, scope, adaptive_mode, lines
                )
    summaries = [_normalize_zone_summary(dict(zone)) for zone in base_all.get("zones", [])]
    if base_detection_method != "stable_v0_5_3_route":
        # Candidate density can stop before a short final bibliography page.
        # Extend only when the exact numeric backbone itself proves continuity.
        for summary in summaries:
            extension = extend_numeric_candidate_end_page(
                pdf_path, int(summary.get("start_page") or 0), int(summary.get("end_page") or 0)
            )
            if extension.get("extended"):
                summary["original_end_page"] = summary.get("end_page")
                summary["end_page"] = int(extension["end_page"])
                summary["zone_span_pages"] = int(summary["end_page"]) - int(summary.get("start_page") or summary["end_page"]) + 1
                summary["candidate_numeric_end_extension"] = extension
        # Rebuild layout zones after any candidate-only structural extension.
        rebuilt_layout = [
            zone for zone in (
                _layout_zone_from_effective_summary(lines, summary) for summary in summaries
            ) if zone is not None
        ]
        if len(rebuilt_layout) == len(summaries):
            layout_zones = rebuilt_layout
    base_records = base_all.get("records", [])
    by_zone: Dict[int, List[Dict]] = defaultdict(list)
    for record in base_records:
        by_zone[int(record["zone_id"])].append(record)

    replacements: Dict[int, List[Dict]] = {}
    repair_reports: List[Dict] = []
    boundary_repair_reports: List[Dict] = []
    marker_regime_reports: List[Dict] = []
    numeric_regime_reports: List[Dict] = []
    column_reflow_reports: List[Dict] = []
    legacy_repaired_ids: set[int] = set()
    boundary_repaired_ids: set[int] = set()
    marker_repaired_ids: set[int] = set()
    numeric_repaired_ids: set[int] = set()
    column_repaired_ids: set[int] = set()
    segmentation_method_by_zone: Dict[int, str] = {}

    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        base_zone_records = list(by_zone.get(zone_id, []))
        current_records = base_zone_records
        declared_style = str(summary.get("style", ""))

        # v0.6.5 marker regime: raw 1..N geometry is allowed to prove that a
        # bibliography is numeric even when the legacy style profiler called it
        # author-year.  This matters for bare markers such as ``1 Author``.
        # The exact sequence + coverage gates make the evidence stronger than
        # the pre-existing style label.
        numeric = build_numeric_layout_resegmentation(pdf_path, layout_zone, current_records)
        if not numeric.get("accepted") and declared_style in {"numeric", "bracket_key"}:
            numeric = numeric_filter_candidate(current_records)

        numeric_regime_reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            **{k: v for k, v in numeric.items() if k != "segments"},
        })
        if numeric.get("accepted"):
            summary["original_style"] = summary.get("style")
            summary["style"] = "numeric"
            current_records = [
                _record_with_zone_metadata(segment, zone_id, index, summary)
                for index, segment in enumerate(numeric.get("segments", []), 1)
            ]
            replacements[zone_id] = current_records
            numeric_repaired_ids.add(zone_id)
            segmentation_method_by_zone[zone_id] = "marker_regime_numeric_v0_6_5"

        elif declared_style not in {"numeric", "bracket_key"}:
            # An audit-required CandidateRegionV2 is provisional until a strong
            # v0.6.5 structural regime proves its segmentation.  Do not let the
            # older generic resegmentation alone promote a two-column or otherwise
            # unresolved candidate. Accepted fallback zones (for example UNR14)
            # are not provisional and retain the historical repair stack.
            if not provisional_candidate_requires_repair:
                # Pass 1: preserve the evidence-gated v0.6.1 resegmentation.
                enhanced, diagnostics = segment_enhanced_zone(layout_zone)
                decision = repair_decision(current_records, enhanced, diagnostics)
                if decision["accepted"]:
                    current_records = [
                        _record_with_zone_metadata(segment, zone_id, index, summary)
                        for index, segment in enumerate(enhanced, 1)
                    ]
                    replacements[zone_id] = current_records
                    legacy_repaired_ids.add(zone_id)
                    segmentation_method_by_zone[zone_id] = "evidence_gated_v0_6_1_repair"
                    repair_reports.append({
                        "zone_id": zone_id,
                        "heading": summary.get("heading", ""),
                        **decision,
                    })

                # Pass 2 (v0.6.5): physical hanging-indent boundary reconciliation.
                boundary = build_hanging_indent_boundary_repair(layout_zone, current_records)
                if boundary.get("accepted"):
                    current_records = [
                        _record_with_zone_metadata(segment, zone_id, index, summary)
                        for index, segment in enumerate(boundary.get("segments", []), 1)
                    ]
                    replacements[zone_id] = current_records
                    boundary_repaired_ids.add(zone_id)
                    segmentation_method_by_zone[zone_id] = "post_segmentation_boundary_reconciliation_v0_6_5"
                    public_boundary = {k: v for k, v in boundary.items() if k != "segments"}
                    boundary_repair_reports.append({
                        "zone_id": zone_id,
                        "heading": summary.get("heading", ""),
                        "repair_stage": "post_segmentation_boundary_reconciliation",
                        **public_boundary,
                    })

        # v0.6.5: chapter-local bibliographies can number references as 5.1.,
        # 5.2., ... .  This pass requires an exact local sequence and shared
        # layout margin, so ordinary document section numbering is ignored.
        hierarchical = build_hierarchical_marker_repair(layout_zone, current_records)
        marker_regime_reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            **{k: v for k, v in hierarchical.items() if k != "segments"},
        })
        if hierarchical.get("accepted"):
            summary["original_style"] = summary.get("style")
            summary["style"] = "hierarchical_numeric"
            current_records = [
                _record_with_zone_metadata(segment, zone_id, index, summary)
                for index, segment in enumerate(hierarchical.get("segments", []), 1)
            ]
            replacements[zone_id] = current_records
            marker_repaired_ids.add(zone_id)
            segmentation_method_by_zone[zone_id] = "marker_regime_hierarchical_v0_6_5"

        # v0.6.5 layout regime: two columns are detected by a persistent vertical
        # gutter, not only by a hard-coded x-mode separation.  The existing v2
        # quality gate still decides whether column-major order may replace the
        # current segmentation.
        if int(summary.get("zone_span_pages", 1) or 1) >= 2 and zone_id not in marker_repaired_ids:
            column = build_column_reflow_repair_v2(pdf_path, layout_zone, current_records)
            column_reflow_reports.append({
                "zone_id": zone_id,
                "heading": summary.get("heading", ""),
                **{k: v for k, v in column.items() if k != "segments"},
            })
            if column.get("accepted"):
                summary["original_style"] = summary.get("style")
                summary["style"] = column.get("candidate_style", summary.get("style"))
                current_records = [
                    _record_with_zone_metadata(segment, zone_id, index, summary)
                    for index, segment in enumerate(column.get("segments", []), 1)
                ]
                replacements[zone_id] = current_records
                column_repaired_ids.add(zone_id)
                segmentation_method_by_zone[zone_id] = "layout_regime_column_reflow_v0_6_5"

    logical_groups = logical_running_header_groups(summaries)
    effective_records_by_zone: Dict[int, List[Dict]] = {
        zone_id: list(replacements.get(zone_id, by_zone.get(zone_id, [])))
        for zone_id in range(1, len(summaries) + 1)
    }
    adaptive_shadow = None
    if adaptive_mode == "shadow":
        page_roles = classify_document_pages(lines)
        adaptive_shadow = build_adaptive_shadow_report(
            layout_zones,
            summaries,
            effective_records_by_zone,
            document_lines=lines,
            page_roles=page_roles,
        )

    if not replacements:
        # Non-stable routes must remain byte-for-byte/public-schema compatible
        # unless a new repair actually changes the output. This also prevents a
        # repair-only provisional candidate from leaking into public records.
        if base_detection_method != "stable_v0_5_3_route":
            source_report = original_base_all if provisional_candidate_requires_repair else base_all
            return _return_nonstable_base_with_shadow(
                source_report, scope, adaptive_mode, lines
            )
        result = _rescope_existing_report(base_all, scope)
        result["logical_zone_groups"] = logical_groups
        if logical_groups:
            result["detection_decision"] = dict(result["detection_decision"])
            result["detection_decision"]["structural_warnings"] = [
                "running_heading_fragmentation"
            ]
        if adaptive_shadow is not None:
            result["adaptive_shadow"] = adaptive_shadow
        return _with_modular_metadata(result)

    combined: List[Dict] = []
    for zone_id in range(1, len(summaries) + 1):
        records = replacements.get(zone_id, by_zone.get(zone_id, []))
        for record in records:
            clean = {
                key: value
                for key, value in dict(record).items()
                if key not in DUPLICATE_FIELDS
            }
            combined.append(clean)

    occurrences, duplicate_groups = _annotate_duplicates(combined)
    selected = _select_scope(
        occurrences,
        scope,
        final_zone_id=len(summaries) if summaries else None,
    )
    repaired_ids = set(replacements)
    for summary in summaries:
        zone_id = int(summary["zone_id"])
        summary["segmentation_method"] = segmentation_method_by_zone.get(zone_id, "stable_v0_4_4")
        summary["n_segments"] = len(replacements.get(zone_id, by_zone.get(zone_id, [])))

    result = {
        **{
            key: value
            for key, value in base_all.items()
            if key not in {
                "records",
                "zones",
                "duplicate_groups",
                "scope",
                "scope_definition",
                "n_occurrences_all_zones",
                "n_unique_references",
                "n_duplicate_groups",
                "n_occurrences_in_duplicate_groups",
                "n_repeated_occurrences_beyond_first",
                "n_records_selected",
                "detection_decision",
                "software_version",
            }
        },
        "software_version": SOFTWARE_VERSION,
        "base_version": BASE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "adaptive_analysis_version": ADAPTIVE_ANALYSIS_VERSION,
        "architecture": "modular_v13_candidate_region_marker_layout_regimes",
        "stable_engine_version": STABLE_ENGINE_VERSION,
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_zones": len(summaries),
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(
            group["occurrence_count"] for group in duplicate_groups
        ),
        "n_repeated_occurrences_beyond_first": sum(
            group["occurrence_count"] - 1 for group in duplicate_groups
        ),
        "n_records_selected": len(selected),
        "zones": summaries,
        "duplicate_groups": duplicate_groups,
        "records": selected,
        "logical_zone_groups": logical_groups,
        "segmentation_repairs": repair_reports,
        "detection_decision": {
            "method": (
                "layout_regime_column_reflow_v0_6_5" if column_repaired_ids else
                "marker_regime_hierarchical_v0_6_5" if marker_repaired_ids else
                "marker_regime_numeric_v0_6_5" if numeric_repaired_ids else
                "post_segmentation_boundary_reconciliation_v0_6_5" if boundary_repaired_ids else
                "stable_zone_resegmentation_v0_6_1"
            ),
            "stable_output_preserved": False,
            "zone_detection_preserved": base_detection_method == "stable_v0_5_3_route",
            "requires_confirmation": True,
            "reason": (
                "candidate_region_promoted_after_independent_region_evidence_and_structural_repair_gate"
                if base_detection_method != "stable_v0_5_3_route"
                else "stable_zones_preserved_and_v0_6_5_marker_or_layout_regime_gate_triggered"
                if (column_repaired_ids or marker_repaired_ids or numeric_repaired_ids)
                else "stable_zones_preserved_and_missing_physical_boundaries_reconciled_before_parsing"
                if boundary_repaired_ids
                else "stable_zones_preserved_but_undersegmentation_evidence_triggered_repair"
            ),
            "repaired_zone_ids": sorted(repaired_ids),
            "base_decision": original_base_all.get("detection_decision", {}),
        },
    }
    if base_detection_method != "stable_v0_5_3_route":
        result["detection_decision"]["candidate_region_bridge"] = True
    if boundary_repaired_ids:
        result["boundary_reconciliation_repairs"] = boundary_repair_reports
        result["detection_decision"]["boundary_reconciled_zone_ids"] = sorted(boundary_repaired_ids)
    if numeric_repaired_ids:
        result["numeric_marker_regime_repairs"] = numeric_regime_reports
        result["detection_decision"]["numeric_marker_repaired_zone_ids"] = sorted(numeric_repaired_ids)
    if marker_repaired_ids:
        result["hierarchical_marker_regime_repairs"] = marker_regime_reports
        result["detection_decision"]["hierarchical_marker_repaired_zone_ids"] = sorted(marker_repaired_ids)
    if column_repaired_ids:
        result["column_layout_regime_repairs"] = column_reflow_reports
        result["detection_decision"]["column_reflow_repaired_zone_ids"] = sorted(column_repaired_ids)
    if adaptive_shadow is not None:
        result["adaptive_shadow"] = adaptive_shadow
    return result


def _rescue_candidate_comparison(stable: Report, candidate: Report, profile: str) -> Dict:
    """Compact comparison; never claims that a rescue candidate is better."""
    return {
        "profile": profile,
        "stable_n_zones": len(stable.get("zones", []) or []),
        "candidate_n_zones": len(candidate.get("zones", []) or []),
        "zone_delta": len(candidate.get("zones", []) or []) - len(stable.get("zones", []) or []),
        "stable_n_records": len(stable.get("records", []) or []),
        "candidate_n_records": len(candidate.get("records", []) or []),
        "record_delta": len(candidate.get("records", []) or []) - len(stable.get("records", []) or []),
        "requires_confirmation": profile != "stable",
        "automatic_preference": False,
    }


def process_pdf(
    pdf_path: str | Path,
    scope: Scope = "all_reference_sections",
    adaptive_mode: AdaptiveMode = "shadow",
    two_pass_shadow: bool = False,
    rescue_profile: str = "stable",
    rescue_audit: bool = True,
    rescue_chain: Sequence[str] | None = None,
) -> Report:
    """Public v0.9.9 candidate pipeline.

    The v0.9.0 effective path is always computed first.  The two-pass layer and
    selective-rescue router are diagnostic/explicit only: neither can silently
    replace effective records or zones.  A non-stable ``rescue_profile`` means
    the caller explicitly requested an alternative candidate for comparison.
    """
    from biblioref.rescue import (
        RESCUE_PROFILES, VALID_RESCUE_PROFILES, TOPOLOGY_CHANGING_RESCUES,
        apply_rescue, apply_rescue_chain, diagnose_and_recommend,
    )

    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    if adaptive_mode not in VALID_ADAPTIVE_MODES:
        raise ValueError(
            f"Invalid adaptive_mode {adaptive_mode!r}; choose one of {sorted(VALID_ADAPTIVE_MODES)}"
        )
    if rescue_profile not in VALID_RESCUE_PROFILES:
        raise ValueError(
            f"Invalid rescue_profile {rescue_profile!r}; choose one of {list(VALID_RESCUE_PROFILES)}"
        )
    chain = [str(p) for p in (rescue_chain or []) if str(p) and str(p) != "stable"]
    if chain and rescue_profile != "stable":
        raise ValueError("Use either rescue_profile or rescue_chain, not both")

    # Compute the effective all-zones report once. Public scopes are a pure
    # in-memory selection, preserving the v0.8.11/v0.9.0 no-rerun guarantee.
    base_all = _process_pdf_effective(
        pdf_path,
        scope="all_reference_sections",
        adaptive_mode=adaptive_mode,
        two_pass_shadow=False,
    )
    stable_result = (
        dict(base_all)
        if scope == "all_reference_sections"
        else _rescope_existing_report(base_all, scope)
    )

    diagnostic = None
    if rescue_audit:
        diagnostic = diagnose_and_recommend(pdf_path, base_all)

    if chain:
        assert base_all is not None
        result = apply_rescue_chain(pdf_path, base_all, scope, chain)
        result = dict(result)
        result["effective_extraction_version"] = f"{SOFTWARE_VERSION}-effective/{ALGORITHM_VERSION}-algorithm"
        result["rescue_candidate_comparison"] = {
            "profiles": chain,
            "stable_n_zones": len(stable_result.get("zones", []) or []),
            "candidate_n_zones": len(result.get("zones", []) or []),
            "stable_n_records": len(stable_result.get("records", []) or []),
            "candidate_n_records": len(result.get("records", []) or []),
            "requires_confirmation": True,
            "automatic_preference": False,
        }
    elif rescue_profile == "stable":
        result = dict(stable_result)
    else:
        assert base_all is not None
        result = apply_rescue(pdf_path, base_all, scope, rescue_profile)
        result = dict(result)
        result["effective_extraction_version"] = f"{SOFTWARE_VERSION}-effective/{ALGORITHM_VERSION}-algorithm"
        result["rescue_candidate_comparison"] = _rescue_candidate_comparison(
            stable_result, result, rescue_profile
        )

    # Additive router metadata only; effective architecture remains the v0.9.0
    # architecture so downstream users can distinguish extraction from routing.
    result["software_version"] = SOFTWARE_VERSION
    result["rescue_router_version"] = RESCUE_ROUTER_VERSION
    result["rescue_profile"] = rescue_profile
    result["rescue_chain"] = chain
    result["rescue_auto_apply"] = False
    result["default_effective_output_changed"] = bool(
        result.get("boundary_reconciliation_repairs")
        or result.get("numeric_marker_regime_repairs")
        or result.get("hierarchical_marker_regime_repairs")
        or result.get("column_layout_regime_repairs")
        or result.get("segmentation_repairs")
    )
    if diagnostic is not None:
        result["post_extraction_audit"] = diagnostic
        if chain or rescue_profile != "stable":
            applied_profiles = chain or [rescue_profile]
            topology_changed = any(p in TOPOLOGY_CHANGING_RESCUES for p in applied_profiles)
            if topology_changed:
                result["post_rescue_audit"] = {
                    "version": RESCUE_ROUTER_VERSION,
                    "status": "not_run_after_zone_topology_change",
                    "reason": "candidate_zone_ids_no_longer_align_with_original_layout_zones",
                    "recommendations": [],
                    "default_output_changed": False,
                }
            else:
                # Re-audit the explicit candidate so the UI/API can propose the
                # next distinct rescue without silently applying it.
                result["post_rescue_audit"] = diagnose_and_recommend(pdf_path, result)

    # v0.9.6: independent post-extraction coverage and physical page-boundary checks.
    # These helpers never alter records/zones; they surface discrepancies for review.
    try:
        from biblioref.audit.coverage import build_coverage_report
        result["coverage_report"] = build_coverage_report(pdf_path, result)
    except Exception as exc:
        result["coverage_report"] = {
            "version": "0.9.6-coverage1",
            "status": "unavailable",
            "possible_missing": [],
            "page_boundaries": [],
            "merged_suspects": [],
            "summary": {"n_possible_missing": 0, "n_page_boundaries": 0, "n_page_boundaries_review": 0},
            "error": str(exc),
        }
    if two_pass_shadow:
        result["two_pass_shadow"] = build_two_pass_shadow(pdf_path, stable_result)
    return result

