# -*- coding: utf-8 -*-
"""BiblioRef v0.6.1 — evidence-gated repair of under-segmented zones.

Version 0.6.1 keeps the v0.6 stable-first route intact.  A bibliography zone
is re-segmented only when its own layout exposes substantially more credible
reference starts than the established output, giant merged segments, or a
repeated pattern of date-only entries inheriting the previous author.

The repair rules describe document structures, never repositories or countries:
mirrored page margins, bare author-year dates, letter-spaced small caps,
repeated-author marks, and running bibliography headers.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Literal, Sequence, Tuple

from biblioref_v0_2 import (
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    NUMERIC_MARKER_RX,
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    _annotate_duplicates,
    _select_scope,
    _strip_heading_prefix,
)
from biblioref_v0_3 import (
    DOI_URL_AT_START_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    LayoutLine,
    _clean_text,
    _is_footer,
    _is_reference_heading,
    _mode_cluster,
    extract_layout_lines,
)
from biblioref_v0_4 import (
    AdaptiveLayoutZone,
    INTERNAL_BIBLIOGRAPHY_HEADING_RX,
    diagnose_adaptive_layout,
    detect_adaptive_layout_zones,
)
from biblioref_v0_6 import YEAR_OR_SOURCE_RX, process_pdf as process_pdf_v06


Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]
SOFTWARE_VERSION = "0.6.1"
BASE_VERSION = "0.6.0"
STABLE_ENGINE_VERSION = "0.4.5"

DATE_ONLY_ENTRY_RX = re.compile(
    r"^\(\s*(?:18|19|20)\d{2}[a-z]?(?:\s*\[[^\]]+\])?\s*\)", re.I
)
REPEATED_MARK_RX = re.compile(
    r"^(?:_{3,}|[-–—]{3,}|[\uF000-\uF8FF]{3,})\s*(?:,|\.)?\s*"
)
UNDATED_BARE_RX = re.compile(r"\b(?:forthcoming|in\s+press|en\s+prensa)\b", re.I)
DUPLICATE_FIELDS = {
    "reference_fingerprint",
    "duplicate_group_id",
    "duplicate_occurrence_count",
    "duplicate_zone_ids",
    "is_repeated_across_zones",
}


def _is_spaced_smallcaps_author(text: str) -> bool:
    """Recognize PDF-extracted small caps such as ``A LMEIDA``."""
    prefix = text.split(",", 1)[0].strip()
    if "," not in text or not prefix or len(prefix) > 100:
        return False
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ]+", prefix)
    letters = [char for token in tokens for char in token if char.isalpha()]
    if len(letters) < 5 or not any(len(token) == 1 for token in tokens):
        return False
    return sum(char.isupper() for char in letters) / len(letters) >= 0.82


def _plausible_author_prefix(text: str) -> bool:
    """Reject wrapped prose that merely contains a comma and a later year."""
    if "," not in text:
        return False
    prefix = text.split(",", 1)[0].strip(" .;:'\"‘’“”")
    if not prefix or len(prefix) > 80 or not prefix[:1].isupper() or re.search(r"\d", prefix):
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+", prefix)
    return bool(words and len(words) <= 8)


def _bare_author_year(text: str) -> bool:
    start = text.strip()[:300]
    return bool(
        _plausible_author_prefix(start)
        and
        AUTHOR_COMMA_RX.match(start)
        and (YEAR_RX.search(start) or SIN_FECHA_RX.search(start) or UNDATED_BARE_RX.search(start))
        and not DOI_URL_AT_START_RX.match(start)
    )


def _parenthetical_author_year(text: str) -> bool:
    start = text.strip()[:300]
    return bool(
        _plausible_author_prefix(start)
        and
        AUTHOR_COMMA_RX.match(start)
        and re.search(
            r"\(\s*(?:(?:18|19|20)\d{2}[a-z]?|s\.?\s*(?:/\s*)?f\.?|n\.?\s*d\.?)",
            start,
            re.I,
        )
    )


def _nearby_bibliographic_evidence(index: int, lines: Sequence[LayoutLine]) -> bool:
    page = lines[index].page
    text = " ".join(
        candidate.text
        for candidate in lines[index:index + 7]
        if candidate.page <= page + 1
    )
    return bool(YEAR_OR_SOURCE_RX.search(text) or SIN_FECHA_RX.search(text))


def _raw_margin_candidate(index: int, lines: Sequence[LayoutLine]) -> bool:
    line = lines[index]
    text = line.text.strip()
    if not text or _is_footer(line) or _is_reference_heading(line):
        return False
    if NUMERIC_MARKER_RX.match(text) or BRACKET_KEY_RX.match(text):
        return True
    if _parenthetical_author_year(text) or _bare_author_year(text):
        return True
    if _is_spaced_smallcaps_author(text) or REPEATED_MARK_RX.match(text):
        return _nearby_bibliographic_evidence(index, lines)
    return False


def _page_start_margins(zone: AdaptiveLayoutZone) -> Tuple[Dict[int, float], float]:
    by_page: Dict[int, List[float]] = defaultdict(list)
    all_x: List[float] = []
    for index, line in enumerate(zone.lines):
        if _raw_margin_candidate(index, zone.lines):
            by_page[line.page].append(line.x0)
            all_x.append(line.x0)
    global_margin, _ = _mode_cluster(all_x)
    if not all_x:
        global_margin = diagnose_adaptive_layout(zone.lines, zone.style).start_margin
    margins: Dict[int, float] = {}
    for page, values in by_page.items():
        margin, support = _mode_cluster(values)
        margins[page] = margin if support else global_margin
    return margins, global_margin


def _enhanced_start(
    index: int,
    zone: AdaptiveLayoutZone,
    page_margins: Dict[int, float],
    global_margin: float,
) -> Tuple[bool, str]:
    line = zone.lines[index]
    text = line.text.strip()
    if not text or _is_footer(line) or _is_reference_heading(line):
        return False, ""
    margin = page_margins.get(line.page, global_margin)
    at_margin = abs(line.x0 - margin) <= 12.0

    if NUMERIC_MARKER_RX.match(text):
        return True, "numeric_marker"
    if BRACKET_KEY_RX.match(text) and at_margin:
        return True, "bracket_key+page_margin"
    if not at_margin:
        return False, ""
    if _parenthetical_author_year(text):
        return True, "author+parenthetical_date+page_margin"
    if _bare_author_year(text):
        return True, "author+bare_date+page_margin"
    if _is_spaced_smallcaps_author(text) and _nearby_bibliographic_evidence(index, zone.lines):
        return True, "spaced_smallcaps_author+nearby_date+page_margin"
    if REPEATED_MARK_RX.match(text) and _nearby_bibliographic_evidence(index, zone.lines):
        return True, "repeated_author_mark+nearby_date+page_margin"

    return False, ""


def _segment_enhanced_zone(zone: AdaptiveLayoutZone) -> Tuple[List[Dict], Dict]:
    page_margins, global_margin = _page_start_margins(zone)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    boundary_evidence = ""
    inherited_date_starts = 0
    explicit_starts = 0

    def flush() -> None:
        nonlocal current, boundary_evidence
        if not current:
            return
        pages = sorted({line.page for line in current})
        flags: List[str] = []
        if len(pages) > 1:
            flags.append("cross_page")
        if any(line.fragment_count > 1 for line in current):
            flags.append("merged_pdf_fragments")
        text = _clean_text(" ".join(line.text for line in current))
        if not YEAR_RX.search(text) and not SIN_FECHA_RX.search(text):
            flags.append("no_year")
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(current[0].x0, 2),
            "boundary_evidence": boundary_evidence,
            "audit_flags": ";".join(flags),
        })
        current = []
        boundary_evidence = ""

    for index, line in enumerate(zone.lines):
        text = line.text.strip()
        if INTERNAL_BIBLIOGRAPHY_HEADING_RX.fullmatch(text) or _is_reference_heading(line):
            continue

        start, evidence = _enhanced_start(index, zone, page_margins, global_margin)
        if not start and current and DATE_ONLY_ENTRY_RX.match(text):
            current_text = " ".join(item.text for item in current)
            page_margin = page_margins.get(line.page, global_margin)
            inherited_indent = line.x0 >= page_margin + 18
            if inherited_indent and (YEAR_RX.search(current_text) or SIN_FECHA_RX.search(current_text)):
                start = True
                evidence = "inherited_author+date_only_entry"
                inherited_date_starts += 1

        if start:
            explicit_starts += 1
            flush()
            current = [line]
            boundary_evidence = evidence
        elif current:
            current.append(line)
    flush()

    word_counts = [len(item["reference_text"].split()) for item in segments]
    evidence_count = sum(bool(YEAR_OR_SOURCE_RX.search(item["reference_text"])) for item in segments)
    diagnostics = {
        "n_enhanced_segments": len(segments),
        "n_explicit_starts": explicit_starts,
        "n_inherited_date_starts": inherited_date_starts,
        "n_giant_segments": sum(value >= 500 for value in word_counts),
        "median_words": round(float(statistics.median(word_counts)), 2) if word_counts else 0.0,
        "evidence_ratio": round(evidence_count / max(len(segments), 1), 3),
        "page_start_margins": {str(key): round(value, 2) for key, value in sorted(page_margins.items())},
    }
    return segments, diagnostics


def _repair_decision(base_records: Sequence[Dict], enhanced: Sequence[Dict], diagnostics: Dict) -> Dict:
    base_words = [len(str(item.get("reference_text", "")).split()) for item in base_records]
    enhanced_words = [len(str(item.get("reference_text", "")).split()) for item in enhanced]
    n_base = len(base_records)
    n_new = len(enhanced)
    base_giant = sum(value >= 250 for value in base_words)
    ratio = n_new / max(n_base, 1)
    inherited = int(diagnostics.get("n_inherited_date_starts", 0) or 0)

    trigger_reasons: List[str] = []
    if n_new >= max(n_base + 5, math.ceil(n_base * 1.55)):
        trigger_reasons.append("candidate_to_segment_gap")
    if base_giant and n_new >= n_base + 3:
        trigger_reasons.append("giant_merged_segments")
    if inherited >= 2 and n_new >= n_base + 2:
        trigger_reasons.append("repeated_inherited_author_entries")

    accepted = bool(
        trigger_reasons
        and n_new >= n_base + 2
        and diagnostics.get("n_giant_segments", 0) == 0
        and 3 <= diagnostics.get("median_words", 0) <= 140
        and diagnostics.get("evidence_ratio", 0) >= 0.55
    )
    return {
        "accepted": accepted,
        "trigger_reasons": trigger_reasons,
        "n_base_segments": n_base,
        "n_enhanced_segments": n_new,
        "segment_ratio": round(ratio, 3),
        "n_base_giant_segments_250_words": base_giant,
        "n_enhanced_giant_segments_500_words": sum(value >= 500 for value in enhanced_words),
        **diagnostics,
    }


def _logical_running_header_groups(zones: Sequence[Dict]) -> List[Dict]:
    groups: List[Dict] = []
    current: List[Dict] = []

    def key(zone: Dict) -> str:
        text = _strip_heading_prefix(str(zone.get("heading", "")))
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def continuous(left: Dict, right: Dict) -> bool:
        same_heading = key(left) == key(right) and bool(key(left))
        adjacent = int(right.get("start_page", 0)) <= int(left.get("end_page", 0)) + 1
        left_last = left.get("numeric_last_marker")
        right_first = right.get("numeric_first_marker")
        numeric = left_last is not None and right_first is not None and int(right_first) == int(left_last) + 1
        return same_heading and adjacent and numeric

    def flush() -> None:
        nonlocal current
        if len(current) >= 2:
            groups.append({
                "logical_zone_group_id": f"LZG{len(groups) + 1:03d}",
                "zone_ids": [int(zone["zone_id"]) for zone in current],
                "heading": _strip_heading_prefix(str(current[0].get("heading", ""))),
                "start_page": int(current[0]["start_page"]),
                "end_page": int(current[-1]["end_page"]),
                "reason": "running_heading_with_continuous_numeric_sequence",
            })
        current = []

    for zone in zones:
        if not current or continuous(current[-1], zone):
            current.append(zone)
        else:
            flush()
            current = [zone]
    flush()
    return groups


def _record_with_zone_metadata(segment: Dict, zone_id: int, ref_in_zone: int, summary: Dict) -> Dict:
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


def process_pdf(pdf_path: str | Path, scope: Scope = "all_reference_sections") -> Dict:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")

    base_all = process_pdf_v06(pdf_path, scope="all_reference_sections")
    if base_all.get("detection_decision", {}).get("method") != "stable_v0_5_3_route":
        result = process_pdf_v06(pdf_path, scope=scope)
        result["software_version"] = SOFTWARE_VERSION
        result["base_version"] = BASE_VERSION
        return result

    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(zone) for zone in base_all.get("zones", [])]
    base_records = base_all.get("records", [])
    by_zone: Dict[int, List[Dict]] = defaultdict(list)
    for record in base_records:
        by_zone[int(record["zone_id"])].append(record)

    replacements: Dict[int, List[Dict]] = {}
    repair_reports: List[Dict] = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        # Exact numbered and bracket-key boundaries are already stronger than
        # the inferred author-year repair route.
        if summary.get("style") in {"numeric", "bracket_key"}:
            continue
        enhanced, diagnostics = _segment_enhanced_zone(layout_zone)
        decision = _repair_decision(by_zone.get(zone_id, []), enhanced, diagnostics)
        if not decision["accepted"]:
            continue
        replacements[zone_id] = [
            _record_with_zone_metadata(segment, zone_id, index, summary)
            for index, segment in enumerate(enhanced, 1)
        ]
        repair_reports.append({
            "zone_id": zone_id,
            "heading": summary.get("heading", ""),
            **decision,
        })

    logical_groups = _logical_running_header_groups(summaries)
    if not replacements:
        result = process_pdf_v06(pdf_path, scope=scope)
        result["software_version"] = SOFTWARE_VERSION
        result["base_version"] = BASE_VERSION
        result["logical_zone_groups"] = logical_groups
        if logical_groups:
            result["detection_decision"] = dict(result["detection_decision"])
            result["detection_decision"]["structural_warnings"] = ["running_heading_fragmentation"]
        return result

    combined: List[Dict] = []
    for zone_id in range(1, len(summaries) + 1):
        records = replacements.get(zone_id, by_zone.get(zone_id, []))
        for record in records:
            clean = {key: value for key, value in dict(record).items() if key not in DUPLICATE_FIELDS}
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
        summary["segmentation_method"] = (
            "evidence_gated_v0_6_1_repair" if zone_id in repaired_ids else "stable_v0_4_4"
        )
        summary["n_segments"] = len(replacements.get(zone_id, by_zone.get(zone_id, [])))

    return {
        **{key: value for key, value in base_all.items() if key not in {
            "records", "zones", "duplicate_groups", "scope", "scope_definition",
            "n_occurrences_all_zones", "n_unique_references", "n_duplicate_groups",
            "n_occurrences_in_duplicate_groups", "n_repeated_occurrences_beyond_first",
            "n_records_selected", "detection_decision", "software_version",
        }},
        "software_version": SOFTWARE_VERSION,
        "base_version": BASE_VERSION,
        "stable_engine_version": STABLE_ENGINE_VERSION,
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_zones": len(summaries),
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(group["occurrence_count"] for group in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(group["occurrence_count"] - 1 for group in duplicate_groups),
        "n_records_selected": len(selected),
        "zones": summaries,
        "duplicate_groups": duplicate_groups,
        "records": selected,
        "logical_zone_groups": logical_groups,
        "segmentation_repairs": repair_reports,
        "detection_decision": {
            "method": "stable_zone_resegmentation_v0_6_1",
            "stable_output_preserved": False,
            "zone_detection_preserved": True,
            "requires_confirmation": True,
            "reason": "stable_zones_preserved_but_undersegmentation_evidence_triggered_repair",
            "repaired_zone_ids": sorted(repaired_ids),
            "base_decision": base_all.get("detection_decision", {}),
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="BiblioRef v0.6.1 stable-first reference extractor")
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
