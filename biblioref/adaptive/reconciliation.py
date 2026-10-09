"""Reversible reconciliation hypotheses for BiblioRef v0.8.5-e.

The module never mutates validated output.  It consumes the shadow segmentation
and surveillance findings, generates local reversible alternatives (MERGE,
SPLIT, SHIFT, EXTEND), re-runs global structural checks and surveillance, and
classifies each proposal as SAFE_REPAIR, REVIEW_REPAIR, or AMBIGUOUS.

SAFE_REPAIR in v0.8.5-e means "safe enough to propose automatically", not
"already applied".  The effective extraction remains v0.6.1 and auto_apply is
false throughout this release.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, List, Sequence, Tuple

from biblioref.adaptive.validation import evaluate_hypothesis
from biblioref.audit.surveillance import analyze_surveillance
from biblioref.legacy.engine import _clean_text


REPAIR_CLASSES = {"SAFE_REPAIR", "REVIEW_REPAIR", "AMBIGUOUS"}


def _joined_text(source_lines: Sequence[Dict]) -> str:
    return _clean_text(" ".join(str(item.get("text", "")) for item in source_lines))


def _segment_from_sources(template: Dict, source_lines: Sequence[Dict], boundary: Dict | None = None) -> Dict:
    source_lines = [dict(item) for item in source_lines]
    pages = sorted({int(item.get("page", 1)) for item in source_lines}) or [int(template.get("reference_start_page", 1) or 1)]
    out = dict(template)
    out["source_lines"] = source_lines
    out["reference_text"] = _joined_text(source_lines)
    out["reference_start_page"] = pages[0]
    out["reference_end_page"] = pages[-1]
    out["n_pages_spanned"] = len(pages)
    out["n_source_lines"] = len(source_lines)
    if source_lines:
        out["reference_start_x"] = float(source_lines[0].get("x0", template.get("reference_start_x", 0.0)) or 0.0)
    if boundary is not None:
        out["shadow_boundary_score"] = boundary.get("score")
        out["shadow_boundary_label"] = boundary.get("label", "reconciled")
        out["shadow_boundary_signals"] = [item.get("signal") for item in boundary.get("contributions", []) if item.get("signal")]
    return out


def _merge_adjacent(segments: Sequence[Dict], left_index: int) -> List[Dict] | None:
    if left_index < 0 or left_index + 1 >= len(segments):
        return None
    result = [deepcopy(item) for item in segments]
    left, right = result[left_index], result[left_index + 1]
    merged_sources = list(left.get("source_lines") or []) + list(right.get("source_lines") or [])
    merged = _segment_from_sources(left, merged_sources)
    merged["reconciliation_origin"] = {"operation": "MERGE", "record_indices": [left_index, left_index + 1]}
    return result[:left_index] + [merged] + result[left_index + 2:]


def _candidate_source_position(segment: Dict, line_index: int) -> int | None:
    for pos, item in enumerate(segment.get("source_lines") or []):
        if item.get("line_index") is not None and int(item["line_index"]) == int(line_index):
            return pos
    return None


def _split_segment(segments: Sequence[Dict], record_index: int, line_index: int, boundary: Dict) -> List[Dict] | None:
    if record_index < 0 or record_index >= len(segments):
        return None
    result = [deepcopy(item) for item in segments]
    current = result[record_index]
    pos = _candidate_source_position(current, line_index)
    sources = list(current.get("source_lines") or [])
    if pos is None or pos <= 0 or pos >= len(sources):
        return None
    left = _segment_from_sources(current, sources[:pos])
    right = _segment_from_sources(current, sources[pos:], boundary=boundary)
    left["reconciliation_origin"] = {"operation": "SPLIT", "record_index": record_index, "side": "left"}
    right["reconciliation_origin"] = {"operation": "SPLIT", "record_index": record_index, "side": "right", "line_index": line_index}
    return result[:record_index] + [left, right] + result[record_index + 1:]


def _shift_prefix_to_previous(segments: Sequence[Dict], record_index: int, line_index: int, boundary: Dict) -> List[Dict] | None:
    """Move the prefix of record_index before line_index into the previous record."""
    if record_index <= 0 or record_index >= len(segments):
        return None
    result = [deepcopy(item) for item in segments]
    prev, current = result[record_index - 1], result[record_index]
    pos = _candidate_source_position(current, line_index)
    sources = list(current.get("source_lines") or [])
    if pos is None or pos <= 0 or pos >= len(sources):
        return None
    prev_sources = list(prev.get("source_lines") or []) + sources[:pos]
    new_prev = _segment_from_sources(prev, prev_sources)
    new_current = _segment_from_sources(current, sources[pos:], boundary=boundary)
    new_prev["reconciliation_origin"] = {"operation": "SHIFT", "direction": "to_previous", "record_index": record_index}
    new_current["reconciliation_origin"] = {"operation": "SHIFT", "direction": "new_start", "record_index": record_index, "line_index": line_index}
    return result[:record_index - 1] + [new_prev, new_current] + result[record_index + 1:]


def _candidate_by_line(candidates: Sequence[Dict]) -> Dict[int, Dict]:
    return {int(item["line_index"]): item for item in candidates if item.get("line_index") is not None}


def _alert_flags(record: Dict) -> set[str]:
    return set(record.get("surveillance_flags") or [])


def _evidence_families(evidence: Iterable[str], boundary: Dict | None = None) -> List[str]:
    families = set()
    items = [str(x) for x in evidence if x]
    if boundary:
        items += [str(item.get("signal")) for item in boundary.get("contributions", []) if item.get("signal")]
    for signal in items:
        s = signal.lower()
        if any(k in s for k in ["short", "long", "length", "median"]): families.add("length")
        if any(k in s for k in ["terminal", "incomplete", "hyphen", "connector"]): families.add("terminal")
        if any(k in s for k in ["author", "institutional", "date", "year"]): families.add("grammar")
        if any(k in s for k in ["order", "alphabet", "numeric_regime", "marker"]): families.add("regime_order")
        if any(k in s for k in ["page_flow", "cross_page", "page_"]): families.add("page_flow")
        if any(k in s for k in ["source", "publisher", "conference", "continuation"]): families.add("continuation")
        if any(k in s for k in ["internal", "boundary"]): families.add("internal_boundary")
        if any(k in s for k in ["doi", "url", "metadata"]): families.add("bibliographic_metadata")
    return sorted(families)


def _summary_counts(surveillance: Dict) -> Tuple[int, int, int]:
    summary = surveillance.get("summary", {})
    return (
        int(summary.get("n_watch_or_high_records", 0)),
        int(summary.get("n_high_watch_records", 0)),
        int(summary.get("n_flagged_records", 0)),
    )


def _compare_alternative(
    baseline_segments: Sequence[Dict], alternative: Sequence[Dict], candidates: Sequence[Dict], page_flows: Sequence[Dict]
) -> Dict:
    base_eval = evaluate_hypothesis(baseline_segments, "reconciliation_baseline")
    alt_eval = evaluate_hypothesis(alternative, "reconciliation_alternative")
    base_surv = analyze_surveillance(baseline_segments, candidates, page_flows)
    alt_surv = analyze_surveillance(alternative, candidates, page_flows)
    bw, bh, bf = _summary_counts(base_surv)
    aw, ah, af = _summary_counts(alt_surv)
    score_delta = float(alt_eval.get("structural_score_0_10", 0.0)) - float(base_eval.get("structural_score_0_10", 0.0))
    evidence_delta = float(alt_eval.get("evidence_ratio", 0.0)) - float(base_eval.get("evidence_ratio", 0.0))
    watch_delta = aw - bw
    high_delta = ah - bh
    flagged_delta = af - bf
    no_structural_damage = score_delta >= -0.25 and evidence_delta >= -0.05 and int(alt_eval.get("n_giant_segments", 0)) == 0
    surveillance_improves = high_delta < 0 or (high_delta == 0 and watch_delta < 0) or (high_delta == 0 and watch_delta == 0 and flagged_delta < 0)
    dominates = bool(no_structural_damage and surveillance_improves)
    return {
        "baseline": base_eval,
        "alternative": alt_eval,
        "baseline_surveillance": base_surv.get("summary", {}),
        "alternative_surveillance": alt_surv.get("summary", {}),
        "structural_score_delta": round(score_delta, 3),
        "evidence_ratio_delta": round(evidence_delta, 3),
        "watch_or_high_delta": watch_delta,
        "high_watch_delta": high_delta,
        "flagged_record_delta": flagged_delta,
        "no_structural_damage": no_structural_damage,
        "surveillance_improves": surveillance_improves,
        "dominates_baseline": dominates,
    }


def _classify(operation: str, source_severity: str, evidence_families: Sequence[str], comparison: Dict, *, order_conflict: bool = False, unique: bool = True) -> Tuple[str, List[str]]:
    reasons = []
    if comparison.get("dominates_baseline"):
        reasons.append("alternative_improves_surveillance_without_structural_damage")
    else:
        reasons.append("alternative_does_not_clearly_dominate_baseline")
    if order_conflict:
        reasons.append("proposal_depends_on_order_conflict_override")
    if not unique:
        reasons.append("multiple_local_repair_locations_are_plausible")
    if len(evidence_families) >= 3:
        reasons.append("three_or_more_independent_evidence_families")
    else:
        reasons.append("limited_evidence_family_diversity")

    safe = (
        source_severity == "HIGH_WATCH"
        and len(evidence_families) >= 3
        and comparison.get("dominates_baseline")
        and not order_conflict
        and unique
        and operation in {"MERGE", "SPLIT", "EXTEND"}
    )
    if safe:
        return "SAFE_REPAIR", reasons
    if comparison.get("dominates_baseline") or order_conflict:
        return "REVIEW_REPAIR", reasons
    return "AMBIGUOUS", reasons


def _proposal_payload(operation: str, classification: str, reasons: List[str], evidence_families: List[str], comparison: Dict, **kwargs) -> Dict:
    out = {
        "operation": operation,
        "classification": classification,
        "auto_applied": False,
        "proposal_only": True,
        "reversible": True,
        "evidence_families": evidence_families,
        "reasons": reasons,
        "comparison": comparison,
    }
    out.update(kwargs)
    return out


def analyze_reconciliation(
    segments: Sequence[Dict],
    candidates: Sequence[Dict],
    surveillance: Dict | None = None,
    page_flows: Sequence[Dict] | None = None,
) -> Dict:
    """Generate and evaluate reversible repairs without applying them."""
    segments = [deepcopy(item) for item in segments]
    candidates = [deepcopy(item) for item in candidates]
    page_flows = [deepcopy(item) for item in (page_flows or [])]
    surveillance = deepcopy(surveillance) if surveillance is not None else analyze_surveillance(segments, candidates, page_flows)
    cand_by_line = _candidate_by_line(candidates)
    proposals: List[Dict] = []

    records = surveillance.get("records", [])
    for row in records:
        i = int(row.get("record_index", -1))
        flags = _alert_flags(row)
        severity = str(row.get("highest_severity", "NONE"))
        alert_evidence = [e for alert in row.get("alerts", []) for e in alert.get("evidence", [])]

        if "SPLIT_WATCH" in flags and i > 0:
            alt = _merge_adjacent(segments, i - 1)
            if alt:
                comparison = _compare_alternative(segments, alt, candidates, page_flows)
                fam = _evidence_families(alert_evidence)
                cls, reasons = _classify("MERGE", severity, fam, comparison)
                proposals.append(_proposal_payload(
                    "MERGE", cls, reasons, fam, comparison,
                    source_record_indices=[i - 1, i], target_record_index=i - 1,
                    trigger_flags=sorted(flags), source_severity=severity,
                    text_preview=(str(segments[i - 1].get("reference_text", ""))[-100:] + " || " + str(segments[i].get("reference_text", ""))[:120]),
                ))

        if "MERGE_WATCH" in flags and 0 <= i < len(segments):
            internal_lines = [
                int(item.get("line_index")) for item in (segments[i].get("source_lines") or [])[1:]
                if item.get("line_index") is not None and int(item.get("line_index")) in cand_by_line
            ]
            plausible = []
            for line_index in internal_lines:
                c = cand_by_line[line_index]
                if c.get("semantic_anchor") or float(c.get("score", 0.0)) >= 3.0 or c.get("features", {}).get("strong_alphabetical_inversion"):
                    plausible.append((line_index, c))
            unique = len(plausible) == 1
            for line_index, boundary in plausible:
                alt = _split_segment(segments, i, line_index, boundary)
                if not alt:
                    continue
                comparison = _compare_alternative(segments, alt, candidates, page_flows)
                order_conflict = bool(boundary.get("features", {}).get("strong_alphabetical_inversion"))
                boundary_evidence = [x.get("signal") for x in boundary.get("contributions", []) if x.get("signal")]
                fam = _evidence_families([*alert_evidence, *boundary_evidence], boundary)
                cls, reasons = _classify("SPLIT", severity, fam, comparison, order_conflict=order_conflict, unique=unique)
                proposals.append(_proposal_payload(
                    "SPLIT", cls, reasons, fam, comparison,
                    source_record_indices=[i], target_record_index=i, split_line_index=line_index,
                    trigger_flags=sorted(flags), source_severity=severity,
                    boundary_score=boundary.get("score"), boundary_label=boundary.get("label"),
                    boundary_text=boundary.get("text_preview") or boundary.get("text") or "",
                    order_conflict=order_conflict,
                ))

            # SHIFT is useful when a false split and a hidden true start occur in
            # the same current segment: move its leading continuation material
            # backward while retaining the real start.
            if "SPLIT_WATCH" in flags and i > 0:
                for line_index, boundary in plausible[:1]:
                    alt = _shift_prefix_to_previous(segments, i, line_index, boundary)
                    if not alt:
                        continue
                    comparison = _compare_alternative(segments, alt, candidates, page_flows)
                    order_conflict = bool(boundary.get("features", {}).get("strong_alphabetical_inversion"))
                    fam = _evidence_families([*alert_evidence, "internal_boundary", "continuation_prefix"], boundary)
                    cls, reasons = _classify("SHIFT", severity, fam, comparison, order_conflict=order_conflict, unique=True)
                    proposals.append(_proposal_payload(
                        "SHIFT", cls, reasons, fam, comparison,
                        source_record_indices=[i - 1, i], target_record_index=i,
                        split_line_index=line_index, trigger_flags=sorted(flags), source_severity=severity,
                        order_conflict=order_conflict,
                    ))

        if "ZONE_END_TRUNCATION_WATCH" in flags:
            fam = _evidence_families(alert_evidence + ["page_flow", "zone_end"])
            proposals.append({
                "operation": "EXTEND",
                "classification": "AMBIGUOUS",
                "auto_applied": False,
                "proposal_only": True,
                "reversible": True,
                "source_record_indices": [i],
                "target_record_index": i,
                "trigger_flags": sorted(flags),
                "source_severity": severity,
                "evidence_families": fam,
                "reasons": ["zone_end_looks_incomplete", "extension_requires_source_context_outside_current_zone"],
                "requires_external_source_context": True,
                "comparison": None,
            })

    # Page-flow extension: if the next physical page strongly looks like a
    # continuation but segmentation contains a new record there, propose an
    # EXTEND (implemented as a reversible merge hypothesis).
    for flow in page_flows:
        if flow.get("flow_state") != "likely_continuation":
            continue
        from_page, to_page = flow.get("from_page"), flow.get("to_page")
        pairs = [
            idx for idx in range(len(segments) - 1)
            if segments[idx].get("reference_end_page") == from_page and segments[idx + 1].get("reference_start_page") == to_page
        ]
        for idx in pairs[:1]:
            alt = _merge_adjacent(segments, idx)
            if not alt:
                continue
            comparison = _compare_alternative(segments, alt, candidates, page_flows)
            signals = list(flow.get("signals", [])) + ["page_flow_likely_continuation"]
            fam = _evidence_families(signals)
            margin = int(flow.get("continuation_support", 0)) - int(flow.get("boundary_support", 0))
            source_severity = "HIGH_WATCH" if margin >= 3 else "WATCH"
            cls, reasons = _classify("EXTEND", source_severity, fam, comparison, unique=True)
            proposals.append(_proposal_payload(
                "EXTEND", cls, reasons, fam, comparison,
                source_record_indices=[idx, idx + 1], target_record_index=idx,
                from_page=from_page, to_page=to_page, page_flow_margin=margin,
                page_flow_signals=flow.get("signals", []), source_severity=source_severity,
            ))

    # De-duplicate exact local operations.
    unique_props = []
    seen = set()
    for p in proposals:
        key = (p.get("operation"), tuple(p.get("source_record_indices", [])), p.get("split_line_index"), p.get("from_page"), p.get("to_page"))
        if key in seen:
            continue
        seen.add(key)
        unique_props.append(p)
    proposals = unique_props

    counts = {name: sum(p["classification"] == name for p in proposals) for name in sorted(REPAIR_CLASSES)}
    operation_counts = {op: sum(p["operation"] == op for p in proposals) for op in ["MERGE", "SPLIT", "SHIFT", "EXTEND"]}
    return {
        "version": "0.8.5-e-reconciliation1",
        "mode": "proposal_only",
        "auto_apply": False,
        "effective_output_changed": False,
        "repair_authority": "shadow_safe_proposal_only",
        "allowed_operations": ["MERGE", "SPLIT", "SHIFT", "EXTEND"],
        "classification_levels": ["SAFE_REPAIR", "REVIEW_REPAIR", "AMBIGUOUS"],
        "n_proposals": len(proposals),
        "classification_counts": counts,
        "operation_counts": operation_counts,
        "proposals": proposals,
        "policy": {
            "safe_repair_is_not_applied_in_this_release": True,
            "safe_requires_high_watch": True,
            "safe_requires_three_evidence_families": True,
            "safe_requires_global_dominance": True,
            "order_conflict_repairs_require_review": True,
        },
    }


__all__ = ["analyze_reconciliation"]
