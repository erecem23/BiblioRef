"""Acceptance gates and logical grouping for segmentation repairs."""

import math
import re
from typing import Dict, List, Sequence

from biblioref.legacy.engine import _strip_heading_prefix


def repair_decision(
    base_records: Sequence[Dict], enhanced: Sequence[Dict], diagnostics: Dict
) -> Dict:
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


def logical_running_header_groups(zones: Sequence[Dict]) -> List[Dict]:
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
        numeric = (
            left_last is not None
            and right_first is not None
            and int(right_first) == int(left_last) + 1
        )
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


_repair_decision = repair_decision
_logical_running_header_groups = logical_running_header_groups
