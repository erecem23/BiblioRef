"""Pre-BiblioRef visual-only stress profiling for human-gold source selection.

The profiler renders a small, deterministic set of pages with PDFium and uses
only raster geometry/density. It never opens a text page and never imports or
executes BiblioRef.
"""

from __future__ import annotations

import hashlib
import statistics
from pathlib import Path

_METHOD = "pdfium_raster_geometry_v1"


def _number(profile: dict, field: str) -> float:
    value = profile.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid visual profile field: {field}")
    return float(value)


def visual_labels(profile: dict) -> list[str]:
    labels = []
    page_count = _number(profile, "page_count")
    if page_count >= 500:
        labels.append("very_long_document")
    elif page_count >= 250:
        labels.append("long_document")
    if _number(profile, "landscape_share") >= 0.2:
        labels.append("landscape_pages")
    if _number(profile, "aspect_ratio_span") >= 0.15:
        labels.append("mixed_page_geometry")
    median_ink = _number(profile, "median_ink_fraction")
    if median_ink >= 0.20:
        labels.append("dense_render")
    elif median_ink <= 0.035:
        labels.append("sparse_render")
    if _number(profile, "ink_fraction_span") >= 0.12:
        labels.append("mixed_render_density")
    if _number(profile, "two_column_like_share") >= 0.4:
        labels.append("two_column_like")
    return labels


def difficulty_score(profile: dict) -> float:
    """Continuous visual-only score used solely to rank the stress partition."""
    pages = min(_number(profile, "page_count"), 600.0) / 120.0
    landscape = min(_number(profile, "landscape_share"), 1.0) * 2.5
    geometry = min(_number(profile, "aspect_ratio_span"), 0.5) * 8.0
    density_span = min(_number(profile, "ink_fraction_span"), 0.4) * 5.0
    two_column = min(_number(profile, "two_column_like_share"), 1.0) * 4.0
    median_ink = _number(profile, "median_ink_fraction")
    density_extreme = max(0.0, median_ink - 0.18) * 8.0 + max(0.0, 0.04 - median_ink) * 8.0
    return round(pages + landscape + geometry + density_span + two_column + density_extreme, 8)


def rank_stress_profiles(rows: list[dict], profiles: dict[str, dict], *, n: int, selection_seed: int) -> list[dict]:
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("stress n must be a non-negative integer")
    ranked = []
    seen = set()
    for row in rows:
        document_id = row.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("stress row requires document_id")
        if document_id in seen:
            raise ValueError(f"duplicate stress document_id: {document_id}")
        seen.add(document_id)
        profile = profiles.get(document_id)
        if not isinstance(profile, dict):
            raise ValueError(f"missing visual profile: {document_id}")
        score = difficulty_score(profile)
        tie = hashlib.sha256(f"{selection_seed}|{document_id}".encode("utf-8")).hexdigest()
        ranked.append((-score, tie, document_id, row, profile))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(ranked) < n:
        raise ValueError("insufficient visual profiles for stress selection")
    result = []
    for negative_score, _, _, row, profile in ranked[:n]:
        selected = dict(row)
        labels = visual_labels(profile)
        if not labels:
            labels = ["high_visual_difficulty_rank"]
        selected["visual_difficulty_labels"] = labels
        selected["visual_difficulty_score"] = -negative_score
        selected["visual_difficulty_profile"] = dict(profile)
        selected["visual_profile_method"] = _METHOD
        selected["selected_before_biblioref_run"] = True
        result.append(selected)
    return result


def _sample_indices(page_count: int, max_samples: int = 5) -> list[int]:
    if page_count < 1:
        return []
    if page_count <= max_samples:
        return list(range(page_count))
    points = {0, page_count - 1}
    for numerator in range(1, max_samples - 1):
        points.add(round((page_count - 1) * numerator / (max_samples - 1)))
    return sorted(points)


def _raster_features(image) -> dict:
    gray = image.convert("L")
    width, height = gray.size
    histogram = gray.histogram()
    total = max(1, width * height)
    ink = sum(histogram[:230]) / total

    pixels = gray.load()
    gutter_left = int(width * 0.46)
    gutter_right = max(gutter_left + 1, int(width * 0.54))
    side_margin = int(width * 0.08)
    left_end = int(width * 0.44)
    right_start = int(width * 0.56)

    def region_fraction(predicate, x0, x1):
        x0 = max(0, min(width, x0))
        x1 = max(x0 + 1, min(width, x1))
        count = 0
        region_total = (x1 - x0) * height
        for x in range(x0, x1):
            for y in range(height):
                if predicate(pixels[x, y]):
                    count += 1
        return count / max(1, region_total)

    gutter_white = region_fraction(lambda value: value >= 245, gutter_left, gutter_right)
    left_ink = region_fraction(lambda value: value < 230, side_margin, left_end)
    right_ink = region_fraction(lambda value: value < 230, right_start, width - side_margin)
    two_column_like = gutter_white >= 0.93 and left_ink >= 0.035 and right_ink >= 0.035
    return {
        "width": width,
        "height": height,
        "aspect_ratio": width / max(1, height),
        "ink_fraction": ink,
        "two_column_like": two_column_like,
    }


def profile_pdf(path: Path, *, scale: float = 0.35, max_samples: int = 5) -> dict:
    """Render deterministic pages and return visual-only geometry/density features."""
    import pypdfium2 as pdfium

    path = Path(path)
    document = pdfium.PdfDocument(str(path))
    try:
        page_count = len(document)
        indices = _sample_indices(page_count, max_samples=max_samples)
        rows = []
        for index in indices:
            page = document[index]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    rows.append(_raster_features(image))
                finally:
                    try:
                        bitmap.close()
                    except Exception:
                        pass
            finally:
                try:
                    page.close()
                except Exception:
                    pass
    finally:
        document.close()
    if not rows:
        raise ValueError(f"PDF has no renderable sampled pages: {path}")
    aspects = [row["aspect_ratio"] for row in rows]
    inks = [row["ink_fraction"] for row in rows]
    return {
        "page_count": page_count,
        "sample_count": len(rows),
        "sample_page_indices": indices,
        "landscape_share": sum(row["width"] > row["height"] for row in rows) / len(rows),
        "aspect_ratio_span": max(aspects) - min(aspects),
        "median_ink_fraction": statistics.median(inks),
        "ink_fraction_span": max(inks) - min(inks),
        "two_column_like_share": sum(bool(row["two_column_like"]) for row in rows) / len(rows),
    }
