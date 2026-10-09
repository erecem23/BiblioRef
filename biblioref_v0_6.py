# -*- coding: utf-8 -*-
"""BiblioRef v0.6.0 — conservative fallback without stable-route regressions.

The v0.4.4 engine remains the authoritative first route.  This module does not
modify its zone detector or segmenter.  It only activates a second, explicitly
labelled route when the stable output is empty or structurally implausible.

The fallback is deliberately selective: it accepts only a dense, late-document
reference-like region with strong repeated boundary evidence.  Ambiguous cases
are returned for visual audit instead of silently replacing the stable output.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from statistics import median
from typing import Dict, List, Literal, Sequence

from biblioref_audit_core import (
    ManualZoneSpec,
    detect_reference_like_regions,
    process_manual_zone,
)
from biblioref_v0_2 import (
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    _annotate_duplicates,
    _select_scope,
)
from biblioref_v0_3 import LayoutLine, extract_layout_lines
from biblioref_v0_4 import process_pdf as process_pdf_stable


Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]
SOFTWARE_VERSION = "0.6.0"
STABLE_ENGINE_VERSION = "0.4.5"

YEAR_OR_SOURCE_RX = re.compile(
    r"(?:\b(?:18|19|20)\d{2}[a-z]?\b|https?://|www\.|\bdoi\s*:|"
    r"\b(?:ley|decreto|resoluci[oó]n|exp(?:te|ediente))\b)",
    re.I,
)


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
    # One short bibliography inside a document with several legitimate zones
    # is not enough to invalidate the established result (e.g. annex/program
    # bibliographies).  Sparse zones become blocking only when they dominate
    # the output or when there are at most two zones to assess.
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


def _build_fallback_report(
    pdf_path: str | Path,
    scope: Scope,
    lines: Sequence[LayoutLine],
    region: Dict,
    stable_assessment: Dict,
    all_regions: List[Dict],
) -> Dict:
    start_y = max(0.0, float(region.get("start_y", 0.0)) - 3.0)
    spec = ManualZoneSpec(
        start_page=int(region["start_page"]),
        start_y=start_y,
        end_page=int(region["end_page"]),
        end_y=None,
        heading_text="Zona inferida sin encabezado explícito",
        note="Activada por la capa conservadora de formato desconocido.",
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
            "detection_method": "inferred_unknown_style",
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
        "detection_method": "inferred_unknown_style",
        "requires_confirmation": True,
        "inference_evidence": region.get("evidence", ""),
    })
    return {
        "software_version": SOFTWARE_VERSION,
        "stable_engine_version": STABLE_ENGINE_VERSION,
        "pdf": str(pdf_path),
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_pdf_layout_lines": len(lines),
        "n_zones": 1,
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(g["occurrence_count"] for g in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(g["occurrence_count"] - 1 for g in duplicate_groups),
        "n_records_selected": len(selected),
        "zones": [zone],
        "duplicate_groups": duplicate_groups,
        "records": selected,
        "detection_decision": {
            "method": "inferred_unknown_style",
            "stable_output_preserved": False,
            "requires_confirmation": True,
            "reason": "stable_route_failed_and_one_strong_late_region_passed_quality_gate",
            "stable_assessment": stable_assessment,
            "fallback_quality": quality,
        },
        "candidate_reference_regions": all_regions,
    }


def process_pdf(pdf_path: str | Path, scope: Scope = "all_reference_sections") -> Dict:
    """Run stable extraction first; activate fallback only behind strict gates."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    stable = process_pdf_stable(pdf_path, scope=scope)
    assessment = assess_stable_result(stable)
    if assessment["preserve_stable_output"]:
        result = dict(stable)
        result["software_version"] = SOFTWARE_VERSION
        result["stable_engine_version"] = STABLE_ENGINE_VERSION
        result["detection_decision"] = {
            "method": "stable_v0_5_3_route",
            "stable_output_preserved": True,
            "requires_confirmation": False,
            "reason": "stable_output_passed_quality_gate",
            "stable_assessment": assessment,
        }
        return result

    lines = extract_layout_lines(pdf_path)
    page_count = max((line.page for line in lines), default=0)
    regions = detect_reference_like_regions(lines, page_count)
    conservative = [
        region for region in regions
        if _region_is_conservative_candidate(region, page_count)
    ]

    # More than one plausible unknown zone is inherently ambiguous.  The UI
    # receives all candidates but the program abstains from choosing silently.
    if len(conservative) == 1:
        try:
            return _build_fallback_report(
                pdf_path, scope, lines, conservative[0], assessment, regions
            )
        except ValueError:
            pass

    result = dict(stable)
    result["software_version"] = SOFTWARE_VERSION
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


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="BiblioRef v0.6.0 stable-first reference extractor"
    )
    parser.add_argument("pdf", help="Input PDF")
    parser.add_argument("--json", dest="json_out", help="Output JSON")
    parser.add_argument("--csv", dest="csv_out", help="Output references CSV")
    parser.add_argument("--zones-csv", dest="zones_out", help="Output zone diagnostics CSV")
    parser.add_argument("--scope", choices=sorted(VALID_SCOPES), default="all_reference_sections")
    args = parser.parse_args()

    result = process_pdf(args.pdf, scope=args.scope)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_out and result["records"]:
        with open(args.csv_out, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["records"][0]))
            writer.writeheader()
            writer.writerows(result["records"])
    if args.zones_out and result["zones"]:
        with open(args.zones_out, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["zones"][0]))
            writer.writeheader()
            writer.writerows(result["zones"])
    print(json.dumps(
        {key: value for key, value in result.items() if key not in {"records", "zones", "duplicate_groups"}},
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
