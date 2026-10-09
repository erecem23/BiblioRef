"""Relative geometry diagnostics for adaptive shadow segmentation.

No model is fitted and no probability is emitted.  All quantities are local to
the current zone/document: robust vertical gaps, x-position clusters, repeated
page decorations and local bibliographic density.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from typing import Dict, List, Sequence

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.legacy.engine import DOI_URL_AT_START_RX, LayoutLine, _is_reference_heading


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\d+", "#", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def median_mad(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    med = float(statistics.median(values))
    mad = float(statistics.median(abs(float(v) - med) for v in values))
    return med, mad


def vertical_gap_profile(lines: Sequence[LayoutLine]) -> Dict:
    ordered = list(lines)
    gaps: List[float] = []
    gap_by_index: Dict[int, float] = {}
    for index in range(1, len(ordered)):
        previous, current = ordered[index - 1], ordered[index]
        if int(previous.page) != int(current.page):
            continue
        gap = max(0.0, float(current.y0) - float(previous.y1))
        gaps.append(gap)
        gap_by_index[index] = gap
    med, mad = median_mad(gaps)
    fallback = max(3.0, med * 0.75)
    threshold = med + (3.0 * mad if mad > 0.25 else fallback)
    return {
        "median_gap": round(med, 3),
        "mad_gap": round(mad, 3),
        "adaptive_large_gap_threshold": round(threshold, 3),
        "gap_by_index": {str(k): round(v, 3) for k, v in gap_by_index.items()},
        "n_gaps": len(gaps),
    }


def _cluster_1d(values: Sequence[float], tolerance: float) -> List[Dict]:
    clusters: List[List[float]] = []
    for value in sorted(float(v) for v in values):
        placed = False
        for cluster in clusters:
            center = statistics.mean(cluster)
            if abs(value - center) <= tolerance:
                cluster.append(value)
                placed = True
                break
        if not placed:
            clusters.append([value])
    result = [
        {"center": round(float(statistics.mean(cluster)), 2), "count": len(cluster)}
        for cluster in clusters
    ]
    return sorted(result, key=lambda item: item["center"])


def x0_cluster_profile(lines: Sequence[LayoutLine]) -> Dict:
    usable = [
        line for line in lines
        if line.text.strip() and not _is_reference_heading(line) and len(line.text.strip()) >= 3
    ]
    if not usable:
        return {
            "clusters": [],
            "left_cluster_center": None,
            "continuation_cluster_center": None,
            "hanging_indent_detected": False,
            "tolerance": 0.0,
        }
    widths = [max(1.0, float(line.x1) - float(line.x0)) for line in usable]
    typical_width = float(statistics.median(widths))
    tolerance = max(4.0, min(14.0, 0.025 * typical_width))
    clusters = _cluster_1d([line.x0 for line in usable], tolerance)
    significant = [item for item in clusters if item["count"] >= max(2, int(len(usable) * 0.08))]
    left = significant[0] if significant else clusters[0]
    continuation = None
    for item in significant[1:]:
        if item["center"] - left["center"] >= max(10.0, 0.05 * typical_width):
            continuation = item
            break
    hanging = bool(continuation)
    return {
        "clusters": clusters,
        "significant_clusters": significant,
        "left_cluster_center": left["center"],
        "continuation_cluster_center": continuation["center"] if continuation else None,
        "hanging_indent_detected": hanging,
        "cluster_distance": round(continuation["center"] - left["center"], 2) if continuation else None,
        "typical_line_width": round(typical_width, 2),
        "tolerance": round(tolerance, 2),
    }


def detect_repeated_decorations(lines: Sequence[LayoutLine]) -> Dict:
    """Find repeated top/bottom strings in the same geometric band."""
    occurrences: Dict[tuple[str, str], List[LayoutLine]] = defaultdict(list)
    page_count = max((int(line.page) for line in lines), default=0)
    for line in lines:
        rel = float(line.y0) / max(float(line.page_height), 1.0)
        band = "top" if rel <= 0.12 else "bottom" if rel >= 0.88 else None
        if not band:
            continue
        text = line.text.strip()
        if not 2 <= len(text) <= 180:
            continue
        key = _norm(text)
        if not key:
            continue
        occurrences[(key, band)].append(line)

    minimum_pages = max(3, int(page_count * 0.20)) if page_count else 3
    repeated: List[Dict] = []
    keys = set()
    for (key, band), items in occurrences.items():
        pages = sorted({int(line.page) for line in items})
        if len(pages) < minimum_pages:
            continue
        keys.add((key, band))
        repeated.append({
            "normalized_text": key,
            "band": band,
            "page_count": len(pages),
            "pages": pages[:30],
            "example_text": items[0].text.strip(),
            "median_x0": round(float(statistics.median(line.x0 for line in items)), 2),
        })
    return {
        "minimum_pages": minimum_pages,
        "n_repeated_decorations": len(repeated),
        "items": repeated,
        "keys": keys,
    }


def is_repeated_decoration(line: LayoutLine, decoration_report: Dict) -> bool:
    rel = float(line.y0) / max(float(line.page_height), 1.0)
    band = "top" if rel <= 0.12 else "bottom" if rel >= 0.88 else None
    if not band:
        return False
    return (_norm(line.text.strip()), band) in decoration_report.get("keys", set())


def _bibliographic_line_signal(text: str) -> bool:
    stripped = text.strip()
    return bool(
        parenthetical_author_year(stripped)
        or bare_author_year(stripped)
        or YEAR_OR_SOURCE_RX.search(stripped)
        or DOI_URL_AT_START_RX.match(stripped)
        or re.search(r"\b(?:doi|isbn|issn|journal|revista|editorial|press|pp?\.)\b", stripped, re.I)
    )


def local_bibliographic_density(index: int, lines: Sequence[LayoutLine], radius: int = 3) -> float:
    if not lines:
        return 0.0
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    neighborhood = [line for line in lines[start:end] if line.text.strip()]
    if not neighborhood:
        return 0.0
    return sum(_bibliographic_line_signal(line.text) for line in neighborhood) / len(neighborhood)


def zone_geometry_diagnostics(lines: Sequence[LayoutLine]) -> Dict:
    gap = vertical_gap_profile(lines)
    x0 = x0_cluster_profile(lines)
    densities = [local_bibliographic_density(i, lines) for i in range(len(lines))]
    return {
        "gap_profile": gap,
        "x0_profile": x0,
        "local_density_median": round(float(statistics.median(densities)), 3) if densities else 0.0,
        "local_density_max": round(max(densities), 3) if densities else 0.0,
    }
