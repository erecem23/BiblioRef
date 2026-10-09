"""Conservative shadow discovery for documents where the stable route abstains.

This does not create extraction output.  It searches for repeated layout plus
bibliographic-evidence patterns so the audit interface/report can point to a
region worth inspecting.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Dict, List, Sequence

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.adaptive.continuity import backward_expansion_start
from biblioref.adaptive.geometry import detect_repeated_decorations, is_repeated_decoration, median_mad
from biblioref.adaptive.input_hygiene import detect_input_decorations, decoration_status
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    SIN_FECHA_RX,
    _mode_cluster,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
)


def discover_shadow_regions(lines: Sequence[LayoutLine], page_count: int) -> List[Dict]:
    """Find pages with repeated bibliographic-looking starts at a shared margin.

    The returned support score is an explicit 0-10 checklist summary, not a
    probability.  Regions are only suggestions for shadow analysis.
    """
    decorations = detect_repeated_decorations(lines)
    input_decorations = detect_input_decorations(lines)
    by_page: Dict[int, List[LayoutLine]] = defaultdict(list)
    for line in lines:
        if is_repeated_decoration(line, decorations) or decoration_status(line, input_decorations) == "DECORATION_CONFIRMED":
            continue
        if 0.10 * line.page_height <= line.y0 <= 0.94 * line.page_height:
            by_page[int(line.page)].append(line)

    page_profiles: Dict[int, Dict] = {}
    for page, page_lines in by_page.items():
        evidence_lines = [
            line for line in page_lines
            if 12 <= len(line.text.strip()) <= 700
            and (YEAR_OR_SOURCE_RX.search(line.text) or SIN_FECHA_RX.search(line.text))
        ]
        if len(evidence_lines) < 3:
            continue
        margin, support = _mode_cluster([float(line.x0) for line in evidence_lines])
        typical_width = statistics.median(max(1.0, float(line.x1) - float(line.x0)) for line in evidence_lines)
        margin_tolerance = max(6.0, min(18.0, 0.035 * float(typical_width)))
        aligned = [
            line for line in evidence_lines
            if abs(float(line.x0) - float(margin)) <= margin_tolerance
        ]
        if len(aligned) < 3:
            continue
        aligned = sorted(aligned, key=lambda line: (line.y0, line.x0))
        gaps = [
            max(0.0, float(right.y0) - float(left.y1))
            for left, right in zip(aligned, aligned[1:])
        ]
        median_gap = float(statistics.median(gaps)) if gaps else 0.0
        _, mad_gap = median_mad(gaps)
        alignment_ratio = len(aligned) / max(len(evidence_lines), 1)
        near_end = page >= max(1, int(page_count * 0.60))

        points = 0.0
        components = []
        for condition, value, label in (
            (len(aligned) >= 3, 2.0, "at_least_3_aligned_evidence_lines"),
            (len(aligned) >= 5, 2.0, "at_least_5_aligned_evidence_lines"),
            (alignment_ratio >= 0.60, 2.0, "alignment_ratio>=0.60"),
            (median_gap >= 5.0, 1.5, "vertical_separation_present"),
            (near_end, 1.0, "late_document_location"),
            (support >= 3, 1.5, "stable_margin_cluster"),
        ):
            if condition:
                points += value
                components.append({"check": label, "points": value})

        if points < 5.0:
            continue
        page_profiles[page] = {
            "page": page,
            "start_y": round(min(line.y0 for line in aligned), 2),
            "end_y": round(max(line.y1 for line in aligned), 2),
            "start_margin": round(float(margin), 2),
            "n_evidence_lines": len(evidence_lines),
            "n_aligned_evidence_lines": len(aligned),
            "alignment_ratio": round(alignment_ratio, 3),
            "median_vertical_gap": round(median_gap, 2),
            "mad_vertical_gap": round(float(mad_gap), 2),
            "margin_tolerance": round(float(margin_tolerance), 2),
            "support_score_0_10": round(min(points, 10.0), 2),
            "score_components": components,
        }

    if not page_profiles:
        return []

    pages = sorted(page_profiles)
    groups: List[List[int]] = [[pages[0]]]
    for page in pages[1:]:
        if page - groups[-1][-1] <= 1:
            groups[-1].append(page)
        else:
            groups.append([page])

    regions: List[Dict] = []
    for region_id, group in enumerate(groups, 1):
        first, last = group[0], group[-1]
        total_aligned = sum(page_profiles[p]["n_aligned_evidence_lines"] for p in group)
        mean_score = statistics.mean(page_profiles[p]["support_score_0_10"] for p in group)
        regions.append({
            "region_id": region_id,
            "start_page": first,
            "start_y": page_profiles[first]["start_y"],
            "end_page": last,
            "end_y": None,
            "n_aligned_evidence_lines": total_aligned,
            "support_score_0_10": round(float(mean_score), 2),
            "page_profiles": [page_profiles[p] for p in group],
            "requires_review": True,
        })
    return regions


def build_shadow_zone_from_region(
    lines: Sequence[LayoutLine],
    region: Dict,
) -> AdaptiveLayoutZone:
    """Build an in-memory zone solely for non-destructive shadow analysis."""
    start_page = int(region["start_page"])
    end_page = int(region["end_page"])
    original_start_y = float(region.get("start_y", 0.0) or 0.0)
    expansion = backward_expansion_start(lines, start_page, original_start_y)
    start_y = float(expansion.get("start_y", original_start_y))
    body = [
        line for line in lines
        if start_page <= int(line.page) <= end_page
        and not (int(line.page) == start_page and float(line.y0) < start_y - 4.0)
    ]
    if not body:
        raise ValueError("shadow_region_has_no_lines")
    style = diagnose_adaptive_style([line.text for line in body[:400]])
    layout = diagnose_adaptive_layout(body[:400], style)
    first = body[0]
    heading = LayoutLine(
        page=start_page,
        page_height=first.page_height,
        text="Zona candidata adaptativa (shadow)",
        x0=first.x0,
        y0=max(0.0, start_y - 12.0),
        x1=first.x1,
        y1=max(1.0, start_y - 2.0),
        median_font_size=first.median_font_size,
        fragment_count=1,
    )
    span = end_page - start_page + 1
    return AdaptiveLayoutZone(
        heading=heading,
        lines=body,
        start_page=start_page,
        end_page=end_page,
        style=style,
        layout=layout,
        termination_reason="adaptive_shadow_region",
        confidence_score=0.0,
        confidence_label="shadow_only",
        confidence_reasons=["layout_and_bibliographic_evidence_discovery"],
        start_confidence_score=0.0,
        start_confidence_label="shadow_only",
        start_confidence_reasons=["not_accepted_as_automatic_zone"],
        end_confidence_score=0.0,
        end_confidence_label="shadow_only",
        end_confidence_reasons=["not_accepted_as_automatic_zone"],
        zone_completeness="shadow_candidate",
        adaptive_soft_limit_pages=0,
        zone_span_pages=span,
        adaptive_limit_exceeded=False,
    )
