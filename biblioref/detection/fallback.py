"""Conservative v0.6 fallback, detached from pandas and the visual interface."""

from pathlib import Path
import re
from statistics import median
from typing import Dict, List, Sequence

from biblioref.audit.detection import detect_reference_like_regions, candidate_heading_lines
from biblioref.audit.manual import process_manual_zone
from biblioref.audit.models import ManualZoneSpec
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.core.types import Scope
from biblioref.ingestion import LayoutLine, extract_layout_lines
from biblioref.legacy.engine import (
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    _annotate_duplicates,
    _select_scope,
    process_pdf_stable,
)


FALLBACK_VERSION = "0.6.0"
from biblioref.core.config import STABLE_ENGINE_VERSION


def assess_stable_result(report: Dict) -> Dict:
    """Decide whether the established route may be preserved unchanged."""
    zones = report.get("zones", [])
    records = report.get("records", [])
    word_counts = [len(str(item.get("reference_text", "")).split()) for item in records]
    giant_segments = sum(value >= 700 for value in word_counts)
    sparse_long_zones = sum(
        int(zone.get("zone_span_pages", 1) or 1) >= 3
        and int(zone.get("n_segments", 0) or 0) <= 2
        for zone in zones
    )
    low_confidence_zones = sum(
        str(zone.get("combined_confidence_label", "")).lower() == "low"
        for zone in zones
    )

    reasons: List[str] = []
    if not zones:
        reasons.append("no_stable_zone")
    if zones and not records:
        reasons.append("stable_zones_without_records")
    if giant_segments and (len(records) <= 10 or giant_segments / max(len(records), 1) >= 0.25):
        reasons.append("giant_segments")
    sparse_is_blocking = bool(
        sparse_long_zones
        and (len(zones) <= 2 or sparse_long_zones >= max(1, len(zones) / 2))
    )
    if sparse_is_blocking:
        reasons.append("sparse_long_zone")
    if zones and low_confidence_zones == len(zones):
        reasons.append("all_zones_low_confidence")

    preserve = not reasons
    score = 1.0
    if "no_stable_zone" in reasons:
        score = 0.0
    else:
        score -= min(0.45, giant_segments * 0.15)
        score -= min(0.30, sparse_long_zones * 0.15) if sparse_is_blocking else 0.0
        score -= 0.20 if "all_zones_low_confidence" in reasons else 0.0
    return {
        "preserve_stable_output": preserve,
        "stable_quality_score": round(max(0.0, score), 3),
        "reasons": reasons or ["stable_output_accepted"],
        "n_giant_segments": giant_segments,
        "n_sparse_long_zones": sparse_long_zones,
        "n_low_confidence_zones": low_confidence_zones,
    }




def _heading_supported_region(lines: Sequence[LayoutLine], regions: Sequence[Dict], page_count: int) -> Dict | None:
    """Select one reference-density region independently supported by a heading-like line.

    v0.6.5 treats lexical/layout headings and reference-density discovery as
    parallel evidence streams.  A region may therefore be promoted even when
    the stable heading vocabulary did not recognize the exact wording, but only
    when one late region has a nearby heading candidate and strong reference
    density.  This is intentionally more conservative than simply adding every
    new phrase to the heading dictionary.
    """
    headings = [
        h for h in candidate_heading_lines(lines)
        if int(h.get("page", 0) or 0) >= max(1, int(page_count * 0.55))
    ]
    supported: List[Dict] = []
    for region in regions:
        start = int(region.get("start_page", 0) or 0)
        end = int(region.get("end_page", start) or start)
        signals = int(region.get("n_boundary_signals", 0) or 0)
        score = float(region.get("confidence_score", 0.0) or 0.0)
        if signals < 5 or score < 0.90:
            continue
        nearby = [
            h for h in headings
            if 0 <= start - int(h.get("page", 0) or 0) <= 2
            or start <= int(h.get("page", 0) or 0) <= end
        ]
        if not nearby:
            continue
        heading = max(nearby, key=lambda h: (float(h.get("score", 0.0) or 0.0), -abs(start-int(h.get("page",0) or 0))))
        item = dict(region)
        item["heading_support"] = {k: heading.get(k) for k in ("page","y","text","score","reason")}
        item["start_page"] = int(heading.get("page") or start)
        item["start_y"] = float(heading.get("y") or region.get("start_y") or 0.0)
        item["detection_sources"] = ["heading_like_layout", "reference_density"]
        supported.append(item)
    # Multiple independent supported regions remain ambiguous; do not guess.
    unique = []
    seen = set()
    for item in supported:
        key = (int(item["start_page"]), int(item["end_page"]))
        if key not in seen:
            seen.add(key); unique.append(item)
    return unique[0] if len(unique) == 1 else None

def _region_is_conservative_candidate(region: Dict, page_count: int) -> bool:
    """Gate inferred zones so ordinary citation-rich prose is not auto-extracted."""
    start = int(region.get("start_page", 0) or 0)
    end = int(region.get("end_page", start) or start)
    signals = int(region.get("n_boundary_signals", 0) or 0)
    score = float(region.get("confidence_score", 0.0) or 0.0)
    late_start = start >= max(1, int(page_count * 0.70))
    late_end = end >= max(1, int(page_count * 0.80))
    sustained = end > start or signals >= 12 or (end == page_count and signals >= 6)
    return score >= 0.94 and signals >= 6 and late_start and late_end and sustained


def _fallback_segment_quality(records: Sequence[Dict], region: Dict) -> Dict:
    texts = [str(record.get("reference_text", "")).strip() for record in records]
    word_counts = [len(text.split()) for text in texts if text]
    evidence_count = sum(bool(YEAR_OR_SOURCE_RX.search(text)) for text in texts)
    evidence_ratio = evidence_count / max(len(texts), 1)
    giant_count = sum(value >= 500 for value in word_counts)
    median_words = median(word_counts) if word_counts else 0.0
    legal_or_structural = str(region.get("style_guess", "")) in {
        "legal_bulleted", "bullet", "numeric", "bracket_key"
    }
    accepted = (
        len(texts) >= 5
        and giant_count == 0
        and median_words <= 120
        and (evidence_ratio >= 0.55 or legal_or_structural)
    )
    score = min(
        0.99,
        0.42
        + min(len(texts), 20) * 0.015
        + evidence_ratio * 0.20
        + float(region.get("confidence_score", 0.0)) * 0.08,
    )
    return {
        "accepted": bool(accepted),
        "score": round(score, 3),
        "n_segments": len(texts),
        "evidence_ratio": round(evidence_ratio, 3),
        "median_words": round(float(median_words), 2),
        "n_giant_segments": giant_count,
    }



def _expanded_region_start_y(lines: Sequence[LayoutLine], region: Dict) -> float:
    """Conservatively include a reference paragraph whose year is wrapped below the inferred start."""
    page = int(region.get("start_page") or 1)
    start_y = float(region.get("start_y") or 0.0)
    page_lines = sorted([x for x in lines if int(x.page) == page], key=lambda x: (x.y0, x.x0))
    if not page_lines:
        return max(0.0, start_y - 3.0)
    below = next((x for x in page_lines if x.y0 >= start_y - 1.0), None)
    ref_x = float(below.x0) if below is not None else None
    year_rx = re.compile(r"\b(?:18|19|20)\d{2}\b")
    candidates = []
    for i, line in enumerate(page_lines):
        if line.y0 >= start_y or start_y - line.y0 > 130:
            continue
        text = str(line.text or "").strip()
        if not text or not text[:1].isupper():
            continue
        if ref_x is not None and abs(float(line.x0) - ref_x) > 35:
            continue
        joined = " ".join(str(x.text or "") for x in page_lines[i:i+4])
        authorish = bool(re.match(r"^[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+(?:\s+[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+){0,6}(?:\s*[,;:]|\s+(?:and|y|&))", text, re.I))
        if authorish and year_rx.search(joined[:360]):
            candidates.append(line)
    if not candidates:
        return max(0.0, start_y - 3.0)
    # Take the nearest plausible paragraph above the inferred region.
    candidate = max(candidates, key=lambda x: x.y0)
    return max(0.0, float(candidate.y0) - 3.0)

def _build_fallback_report(
    pdf_path: str | Path,
    scope: Scope,
    lines: Sequence[LayoutLine],
    region: Dict,
    stable_assessment: Dict,
    all_regions: List[Dict],
) -> Dict:
    start_y = _expanded_region_start_y(lines, region)
    spec = ManualZoneSpec(
        start_page=int(region["start_page"]),
        start_y=start_y,
        end_page=int(region["end_page"]),
        end_y=None,
        heading_text=str((region.get("heading_support") or {}).get("text") or "Zona inferida sin encabezado explícito"),
        note=(
            "Activada por evidencia conjunta de región bibliográfica y encabezado candidato."
            if region.get("heading_support")
            else "Activada por la capa conservadora de formato desconocido."
        ),
    )
    inferred = process_manual_zone(pdf_path, spec, lines, zone_id=1)
    quality = _fallback_segment_quality(inferred["records"], region)
    if not quality["accepted"]:
        raise ValueError("fallback_candidate_failed_quality_gate")

    records: List[Dict] = []
    for record in inferred["records"]:
        item = dict(record)
        item.update({
            "manual_zone": False,
            "accepted": True,
            "audit_status": "pending_review",
            "audit_note": "Zona inferida: confirmar visualmente.",
            "detection_method": "candidate_region_v2" if region.get("heading_support") else "inferred_unknown_style",
        })
        records.append(item)
    occurrences, duplicate_groups = _annotate_duplicates(records)
    selected = _select_scope(occurrences, scope, final_zone_id=1)

    zone = dict(inferred["zone"])
    zone.update({
        "termination_reason": "inferred_reference_density_end",
        "zone_completeness": "requires_confirmation",
        "combined_confidence_score": quality["score"],
        "combined_confidence_label": "medium",
        "manual_zone": False,
        "detection_method": "candidate_region_v2" if region.get("heading_support") else "inferred_unknown_style",
        "requires_confirmation": True,
        "inference_evidence": region.get("evidence", ""),
    })
    return {
        "software_version": FALLBACK_VERSION,
        "stable_engine_version": STABLE_ENGINE_VERSION,
        "pdf": str(pdf_path),
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_pdf_layout_lines": len(lines),
        "n_zones": 1,
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(group["occurrence_count"] for group in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(group["occurrence_count"] - 1 for group in duplicate_groups),
        "n_records_selected": len(selected),
        "zones": [zone],
        "duplicate_groups": duplicate_groups,
        "records": selected,
        "detection_decision": {
            "method": "candidate_region_v2" if region.get("heading_support") else "inferred_unknown_style",
            "stable_output_preserved": False,
            "requires_confirmation": True,
            "reason": (
                "stable_route_failed_and_candidate_region_passed_independent_evidence_gate"
                if region.get("heading_support")
                else "stable_route_failed_and_one_strong_late_region_passed_quality_gate"
            ),
            "stable_assessment": stable_assessment,
            "fallback_quality": quality,
        },
        "candidate_reference_regions": all_regions,
    }


def process_pdf_v06(
    pdf_path: str | Path,
    scope: Scope = "all_reference_sections",
    lines: Sequence[LayoutLine] | None = None,
) -> Dict:
    """Run stable extraction first; activate fallback only behind strict gates."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    shared_lines = list(lines) if lines is not None else extract_layout_lines(pdf_path)
    stable = process_pdf_stable(pdf_path, scope=scope, lines=shared_lines)
    assessment = assess_stable_result(stable)
    if assessment["preserve_stable_output"]:
        result = dict(stable)
        result["software_version"] = FALLBACK_VERSION
        result["stable_engine_version"] = STABLE_ENGINE_VERSION
        result["detection_decision"] = {
            "method": "stable_v0_5_3_route",
            "stable_output_preserved": True,
            "requires_confirmation": False,
            "reason": "stable_output_passed_quality_gate",
            "stable_assessment": assessment,
        }
        return result

    page_count = max((line.page for line in shared_lines), default=0)
    regions = detect_reference_like_regions(shared_lines, page_count)
    conservative = [
        region for region in regions
        if _region_is_conservative_candidate(region, page_count)
    ]
    heading_supported = _heading_supported_region(shared_lines, regions, page_count)
    selected_region = conservative[0] if len(conservative) == 1 else heading_supported

    if selected_region is not None:
        try:
            return _build_fallback_report(
                pdf_path, scope, shared_lines, selected_region, assessment, regions
            )
        except ValueError:
            pass

    result = dict(stable)
    result["software_version"] = FALLBACK_VERSION
    result["stable_engine_version"] = STABLE_ENGINE_VERSION
    result["detection_decision"] = {
        "method": "audit_required",
        "stable_output_preserved": True,
        "requires_confirmation": True,
        "reason": (
            "multiple_strong_unknown_regions"
            if len(conservative) > 1
            else "no_unknown_region_passed_all_quality_gates"
        ),
        "stable_assessment": assessment,
        "n_conservative_candidates": len(conservative),
    }
    result["candidate_reference_regions"] = regions
    return result
