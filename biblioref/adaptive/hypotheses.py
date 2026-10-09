"""Shadow segmentation and hypothesis comparison for BiblioRef v0.8.x."""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

from biblioref.adaptive.scoring import collect_boundary_candidates, evidence_summary
from biblioref.adaptive.geometry import zone_geometry_diagnostics, detect_repeated_decorations
from biblioref.adaptive.order_profile import infer_order_profile
from biblioref.adaptive.context import summarize_document_context, classify_document_pages
from biblioref.adaptive.page_flow import analyze_page_flows
from biblioref.adaptive.input_hygiene import detect_input_decorations, public_decoration_report
from biblioref.adaptive.input_surveillance import summarize_input_surveillance, summarize_candidate_conflicts
from biblioref.audit.surveillance import analyze_surveillance
from biblioref.adaptive.reconciliation import analyze_reconciliation
from biblioref.adaptive.validation import compare_hypotheses, evaluate_hypothesis
from biblioref.adaptive.verification import verify_discovered_region
from biblioref.adaptive.stable_conflicts import (
    diagnose_stable_context_conflict,
    diagnose_stable_segmentation_conflict,
    combine_stable_conflict_diagnostics,
)
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    SIN_FECHA_RX,
    YEAR_RX,
    _clean_text,
    _is_reference_heading,
)


def _shadow_segments(zone: AdaptiveLayoutZone, candidates: Sequence[Dict]) -> List[Dict]:
    by_index = {int(item["line_index"]): item for item in candidates}
    segments: List[Dict] = []
    current: List[tuple[int, LayoutLine]] = []
    evidence: Dict | None = None

    def flush() -> None:
        nonlocal current, evidence
        if not current:
            return
        text = _clean_text(" ".join(line.text for _, line in current))
        pages = sorted({int(line.page) for _, line in current})
        flags = []
        if len(pages) > 1:
            flags.append("cross_page")
        if not YEAR_RX.search(text) and not SIN_FECHA_RX.search(text):
            flags.append("no_year")
        first_line = current[0][1]
        segments.append({
            "reference_text": text,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "n_pages_spanned": len(pages),
            "n_source_lines": len(current),
            "source_lines": [
                {
                    "line_index": int(line_index),
                    "page": int(line.page),
                    "page_height": round(float(line.page_height), 2),
                    "x0": round(float(line.x0), 2),
                    "y0": round(float(line.y0), 2),
                    "x1": round(float(line.x1), 2),
                    "y1": round(float(line.y1), 2),
                    "median_font_size": round(float(line.median_font_size or 0.0), 2),
                    "fragment_count": int(line.fragment_count or 0),
                    "text": line.text,
                } for line_index, line in current
            ],
            "reference_start_x": round(float(first_line.x0), 2),
            "shadow_boundary_score": evidence.get("score") if evidence else None,
            "shadow_boundary_label": evidence.get("label") if evidence else "implicit_first",
            "shadow_boundary_signals": [
                item["signal"] for item in evidence.get("contributions", [])
            ] if evidence else [],
            "audit_flags": ";".join(flags),
        })
        current = []
        evidence = None

    for index, line in enumerate(zone.lines):
        text = line.text.strip()
        if not text or _is_reference_heading(line):
            continue
        item = by_index.get(index)
        active = bool(item and item["active_shadow_boundary"])
        if active:
            flush()
            current = [(index, line)]
            evidence = item
        elif current:
            current.append((index, line))
        elif YEAR_OR_SOURCE_RX.search(text):
            # A conservative implicit start prevents losing the beginning of a
            # zone when the first record is atypical. It is labelled clearly.
            current = [(index, line)]
            evidence = None
    flush()
    return segments



def assess_shadow_zone_quality(shadow: Sequence[Dict], candidates: Sequence[Dict]) -> Dict:
    """Conservative post-segmentation quality gate for review datasets.

    The gate never changes validated output and never deletes the raw shadow
    report.  It only says whether a shadow zone is structurally clean enough to
    be surfaced as a candidate bibliography dataset without manual inspection.

    Development evidence from heterogeneous theses showed a transferable
    failure shape: narrative/body zones produce a small number of enormous
    pseudo-references, whereas real bibliographies may contain an occasional
    long entry but not a large *share* of giant segments.
    """
    n_segments = len(shadow)
    word_counts = [len(str(item.get("reference_text", "") or "").split()) for item in shadow]
    ge140 = sum(count >= 140 for count in word_counts)
    ge500 = sum(count >= 500 for count in word_counts)
    max_words = max(word_counts, default=0)
    giant_ratio = (ge140 / n_segments) if n_segments else 0.0
    n_active = sum(bool(item.get("active_shadow_boundary")) for item in candidates)
    n_evaluated = len(candidates)
    active_ratio = (n_active / n_evaluated) if n_evaluated else 0.0

    narrative_shape = bool(
        n_segments >= 4
        and ge140 >= 2
        and giant_ratio >= 0.20
        and max_words >= 200
    )

    reasons = []
    if narrative_shape:
        reasons.append("giant_segment_share_ge_20pct")
        reasons.append("multiple_segments_ge_140_words")
        reasons.append("max_segment_ge_200_words")

    return {
        "candidate_dataset_eligible": not narrative_shape,
        "verdict": "narrative_contamination_requires_review" if narrative_shape else "structurally_usable_shadow_zone",
        "n_segments": n_segments,
        "segments_ge_140_words": ge140,
        "segments_ge_500_words": ge500,
        "max_segment_words": max_words,
        "giant_segment_ratio": round(giant_ratio, 4),
        "active_boundary_ratio": round(active_ratio, 4),
        "reasons": reasons,
        "auto_apply": False,
    }

def analyze_zone_shadow(
    zone_id: int,
    zone: AdaptiveLayoutZone,
    effective_records: Sequence[Dict],
    decoration_report: Dict | None = None,
) -> Dict:
    candidates = collect_boundary_candidates(zone)
    shadow = _shadow_segments(zone, candidates)
    zone_quality = assess_shadow_zone_quality(shadow, candidates)
    page_pairs = analyze_page_flows(zone.lines, candidates, decoration_report=decoration_report)
    surveillance = analyze_surveillance(shadow, candidates, page_pairs)
    reconciliation = analyze_reconciliation(shadow, candidates, surveillance=surveillance, page_flows=page_pairs)
    baseline_eval = evaluate_hypothesis(effective_records, "effective_baseline")
    shadow_eval = evaluate_hypothesis(shadow, "interpretable_scoring_shadow")
    comparison = compare_hypotheses(baseline_eval, shadow_eval)

    noteworthy = [
        item for item in candidates
        if item["active_shadow_boundary"] or item["label"] in {"strong", "plausible", "weak"}
    ]
    scores = [float(item["score"]) for item in noteworthy]
    return {
        "zone_id": int(zone_id),
        "mode": "shadow",
        "baseline_is_unchanged": True,
        "candidate_evidence_summary": evidence_summary(candidates),
        "shadow_zone_quality": zone_quality,
        "geometry_diagnostics": zone_geometry_diagnostics(zone.lines),
        "order_profile": infer_order_profile(zone.lines),
        "input_surveillance": {
            **summarize_input_surveillance(zone.lines, decoration_report),
            "candidate_conflicts": summarize_candidate_conflicts(candidates),
        },
        "page_flow": {
            "diagnostic_only": True,
            "auto_apply": False,
            "page_pairs": page_pairs,
        },
        "surveillance": surveillance,
        "reconciliation": reconciliation,
        "candidate_score_median": round(float(statistics.median(scores)), 2) if scores else 0.0,
        "baseline": baseline_eval,
        "shadow_candidate": shadow_eval,
        "comparison": comparison,
        "noteworthy_boundaries": noteworthy,
        "shadow_segments_preview": [
            {
                "reference_start_page": item["reference_start_page"],
                "reference_start_x": item["reference_start_x"],
                "shadow_boundary_score": item["shadow_boundary_score"],
                "shadow_boundary_label": item["shadow_boundary_label"],
                "shadow_boundary_signals": item["shadow_boundary_signals"],
                "n_pages_spanned": item.get("n_pages_spanned", 1),
                "n_source_lines": item.get("n_source_lines", 0),
                "surveillance_flags": surveillance.get("records", [])[idx].get("surveillance_flags", []) if idx < len(surveillance.get("records", [])) else [],
                "surveillance_severity": surveillance.get("records", [])[idx].get("highest_severity", "NONE") if idx < len(surveillance.get("records", [])) else "NONE",
                "text_preview": item["reference_text"][:220],
            }
            for idx, item in enumerate(shadow[:25])
        ],
    }


def build_adaptive_shadow_report(
    layout_zones: Sequence[AdaptiveLayoutZone],
    summaries: Sequence[Dict],
    effective_records_by_zone: Dict[int, Sequence[Dict]],
    document_lines: Sequence[LayoutLine] | None = None,
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Analyze zones already accepted by the validated bibliography route.

    Region verification is not re-run here because the stable detection route is
    itself the prior bibliography-zone gate. The adaptive layer only questions
    segmentation inside an already accepted zone.
    """
    full_lines = list(document_lines or [])
    input_decorations = detect_input_decorations(full_lines) if full_lines else {"confirmed": [], "watch": [], "confirmed_keys": set(), "watch_keys": set(), "n_confirmed": 0, "n_watch": 0}
    zone_reports = []
    stable_page_roles = page_roles if page_roles is not None else (classify_document_pages(full_lines) if full_lines else {})
    for zone_id, zone in enumerate(layout_zones, 1):
        if zone_id > len(summaries):
            break
        effective_records = effective_records_by_zone.get(zone_id, [])
        report = analyze_zone_shadow(
            zone_id, zone, effective_records, decoration_report=input_decorations
        )
        context_diag = diagnose_stable_context_conflict(
            full_lines, zone, summaries[zone_id - 1], summaries, zone_id, page_roles=stable_page_roles
        )
        segmentation_diag = diagnose_stable_segmentation_conflict(
            zone, effective_records, report
        )
        stable_diag = combine_stable_conflict_diagnostics(
            context_diag, segmentation_diag
        )
        report["stable_conflict_diagnostics"] = stable_diag
        report["region_verification"] = {
            "verdict": "accepted_by_stable_route",
            "allows_shadow_segmentation": True,
            "reason": "stable_bibliography_zone_detection_is_the_prior_gate",
            "stable_context_conflict_requires_review": bool(context_diag.get("requires_review")),
            "diagnostic_only": True,
        }
        zone_reports.append(report)

    statuses = [item["comparison"]["status"] for item in zone_reports]
    conflict_ids = [
        item["zone_id"] for item in zone_reports
        if item.get("stable_conflict_diagnostics", {}).get("requires_review")
    ]
    review_ids = sorted(set(
        [item["zone_id"] for item in zone_reports if item["comparison"]["requires_review"]]
        + conflict_ids
    ))
    if conflict_ids:
        overall = "manual_review_required"
    elif any(status == "manual_review_required" for status in statuses):
        overall = "manual_review_required"
    elif any(status == "ambiguous" for status in statuses):
        overall = "ambiguous"
    elif any(status in {"candidate_supported", "candidate_worth_reviewing"} for status in statuses):
        overall = "candidate_worth_reviewing"
    else:
        overall = "stable_preferred"

    document_context = summarize_document_context(full_lines, stable_page_roles) if full_lines else {}
    decorations = detect_repeated_decorations(full_lines) if full_lines else {"n_repeated_decorations": 0, "items": [], "minimum_pages": 0, "keys": set()}
    return {
        "version": ADAPTIVE_ANALYSIS_VERSION,
        "mode": "shadow",
        "decision_policy": "document_context_then_verify_region_then_geometry_score_boundaries_never_replace_output",
        "probabilities_used": False,
        "auto_apply": False,
        "document_context": document_context,
        "repeated_decorations": {k: v for k, v in decorations.items() if k != "keys"},
        "input_hygiene": {
            "decorations": public_decoration_report(input_decorations),
            "diagnostic_only": True,
            "auto_apply": False,
        },
        "overall_status": overall,
        "review_zone_ids": review_ids,
        "stable_context_conflict_zone_ids": [
            item["zone_id"] for item in zone_reports
            if item.get("stable_conflict_diagnostics", {}).get("context", {}).get("requires_review")
        ],
        "stable_segmentation_conflict_zone_ids": [
            item["zone_id"] for item in zone_reports
            if item.get("stable_conflict_diagnostics", {}).get("segmentation", {}).get("requires_review")
        ],
        "stable_structural_conflict_zone_ids": conflict_ids,
        "n_stable_structural_conflicts": len(conflict_ids),
        "n_zones_analyzed": len(zone_reports),
        "region_verification_gate": "stable_route_preverified_with_diagnostic_conflict_layer",
        "zones": zone_reports,
    }


def build_discovered_shadow_report(
    lines: Sequence[LayoutLine],
    regions: Sequence[Dict],
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Verify and, only when verified, segment discovered regions in shadow mode."""
    from biblioref.adaptive.discovery import build_shadow_zone_from_region

    input_decorations = detect_input_decorations(lines)
    zone_reports = []
    verification_reports = []
    review_ids = []

    for region in regions:
        region_id = int(region["region_id"])
        verification = verify_discovered_region(lines, region, page_roles=page_roles)
        verification_entry = {
            "region_id": region_id,
            "discovered_region": dict(region),
            "region_verification": verification,
            "segmentation_attempted": False,
        }
        verification_reports.append(verification_entry)
        review_ids.append(region_id)

        # Critical v0.8.3 gate: layout discovery is not permission to segment.
        if not verification["allows_shadow_segmentation"]:
            continue

        try:
            zone = build_shadow_zone_from_region(lines, region)
        except ValueError:
            verification_entry["region_verification"] = dict(verification)
            verification_entry["region_verification"]["verdict"] = "region_build_failed"
            verification_entry["region_verification"]["allows_shadow_segmentation"] = False
            verification_entry["region_verification"]["reasons"] = ["verified_region_had_no_buildable_lines"]
            continue

        report = analyze_zone_shadow(region_id, zone, [], decoration_report=input_decorations)
        report["discovered_region"] = dict(region)
        original_start_y = float(region.get("start_y", 0.0) or 0.0)
        actual_start_y = float(zone.lines[0].y0) if zone.lines else original_start_y
        report["backward_region_expansion"] = {
            "expanded": actual_start_y < original_start_y - 1.0,
            "original_start_y": round(original_start_y, 2),
            "actual_start_y": round(actual_start_y, 2),
            "text_preview": zone.lines[0].text.strip()[:180] if zone.lines else "",
        }
        report["region_verification"] = verification
        report["segmentation_attempted"] = True
        zone_reports.append(report)
        verification_entry["segmentation_attempted"] = True

    statuses = [item["comparison"]["status"] for item in zone_reports]
    verified_count = sum(
        item["region_verification"]["verdict"] == "verified_bibliographic_region"
        for item in verification_reports
    )
    plausible_count = sum(
        item["region_verification"]["verdict"] in {"plausible_but_unverified", "context_conflict_requires_review"}
        for item in verification_reports
    )
    rejected_count = sum(
        item["region_verification"]["verdict"] == "insufficient_bibliographic_evidence"
        for item in verification_reports
    )

    if not verification_reports:
        overall = "not_run"
    elif not zone_reports:
        overall = "bibliographic_region_unverified"
    elif any(status == "manual_review_required" for status in statuses):
        overall = "manual_review_required"
    elif any(status == "ambiguous" for status in statuses):
        overall = "ambiguous"
    else:
        # Even a verified region only permits a review-only segmentation
        # hypothesis when the validated route had abstained.
        overall = "candidate_worth_reviewing"

    document_context = summarize_document_context(lines, page_roles)
    decorations = detect_repeated_decorations(lines)
    return {
        "version": ADAPTIVE_ANALYSIS_VERSION,
        "mode": "shadow",
        "decision_policy": "document_context_then_verify_region_then_geometry_score_boundaries_never_replace_output",
        "probabilities_used": False,
        "auto_apply": False,
        "document_context": document_context,
        "repeated_decorations": {k: v for k, v in decorations.items() if k != "keys"},
        "input_hygiene": {
            "decorations": public_decoration_report(input_decorations),
            "diagnostic_only": True,
            "auto_apply": False,
        },
        "overall_status": overall,
        "review_zone_ids": review_ids,
        "n_regions_discovered": len(verification_reports),
        "n_regions_verified": verified_count,
        "n_regions_plausible_unverified": plausible_count,
        "n_regions_rejected": rejected_count,
        "n_zones_analyzed": len(zone_reports),
        "source": "adaptive_layout_discovery_after_base_abstention",
        "region_verification_gate": "required_before_shadow_segmentation",
        "region_verifications": verification_reports,
        "zones": zone_reports,
    }
