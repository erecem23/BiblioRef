"""BiblioRef algorithm 0.6.7 structural repair layer.

Ports the evidence-gated UNR28/UNR30 repairs from the frozen v0.9.10-rc1
candidate without overwriting the preserved v0.6.5 pipeline or the independent
v0.6.6 dominant-margin (Cabrera) reconciliation. RC1 also called its changes
algorithm 0.6.6; the combined line is therefore identified as 0.6.7.
"""
from __future__ import annotations

from pathlib import Path
import re
import statistics
from typing import Dict, List, Sequence

from biblioref.ingestion.backend_context import pymupdf

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.detection.signals import plausible_author_prefix, nearby_bibliographic_evidence
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine
from biblioref.extraction.boundary_reconciliation import (
    _clean_zone_lines,
    _segment,
    _quality,
    _first_record_head_missing,
)
from biblioref.extraction.column_reflow import (
    _clean,
    _coalesce_reflow_order,
    _is_page_number_line,
    _low_mode,
    _raw_page_lines,
    _column_geometry,
    _segment_quality,
    reflow_two_column_zone,
    build_column_reflow_repair_v2 as _baseline_column_reflow_v2,
)

INTEGRATED_ALGORITHM_VERSION = "0.6.7"
RC1_ORIGIN = "v0.9.10-rc1 / algorithm-0.6.6"


def _x_mode_clusters(lines: Sequence[LayoutLine], merge_tolerance: float = 4.5) -> List[Dict]:
    values = sorted(float(line.x0) for line in lines)
    clusters: List[List[float]] = []
    for value in values:
        if not clusters or value - statistics.median(clusters[-1]) > merge_tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [{"center": float(statistics.median(group)), "support": len(group), "min": min(group), "max": max(group)} for group in clusters]


def _infer_dominant_hanging_indent(lines: Sequence[LayoutLine]) -> Dict:
    if len(lines) < 40:
        return {"eligible": False, "reason": "too_few_lines_for_raw_x_geometry"}
    clusters = _x_mode_clusters(lines)
    if len(clusters) < 2:
        return {"eligible": False, "reason": "fewer_than_two_x_modes"}
    top = sorted(clusters, key=lambda item: item["support"], reverse=True)[:4]
    best = None
    for left in top:
        for right in top:
            if left is right or right["center"] <= left["center"]:
                continue
            separation = float(right["center"] - left["center"])
            if not 14.0 <= separation <= 90.0:
                continue
            combined = int(left["support"] + right["support"])
            balance = min(left["support"], right["support"]) / max(left["support"], right["support"])
            score = combined * (0.75 + 0.25 * balance)
            candidate = (score, left, right, separation, balance)
            if best is None or score > best[0]:
                best = candidate
    if best is None:
        return {"eligible": False, "reason": "no_plausible_start_continuation_pair"}
    _, start, continuation, separation, balance = best
    total = max(len(lines), 1)
    combined_share = (start["support"] + continuation["support"]) / total
    minimum_support = max(12, int(round(total * 0.10)))
    eligible = bool(start["support"] >= minimum_support and continuation["support"] >= minimum_support and combined_share >= 0.70 and balance >= 0.35)
    return {
        "eligible": eligible,
        "reason": "dominant_raw_hanging_indent_geometry" if eligible else "raw_x_modes_failed_support_gate",
        "start_margin": round(float(start["center"]), 2),
        "continuation_margin": round(float(continuation["center"]), 2),
        "margin_separation": round(float(separation), 2),
        "start_support": int(start["support"]),
        "continuation_support": int(continuation["support"]),
        "mode_balance": round(float(balance), 3),
        "combined_mode_share": round(float(combined_share), 3),
        "n_x_clusters": len(clusters),
    }


def build_long_segment_raw_hanging_indent_repair(zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    """Recover strongly under-segmented hanging-indent bibliographies."""
    base_records = list(base_records or [])
    base_words = [len(str(record.get("reference_text", "")).split()) for record in base_records]
    long_base = sum(value >= 180 for value in base_words)
    if long_base < 2:
        return {"accepted": False, "reason": "fewer_than_two_moderately_long_base_segments", "n_base_segments": len(base_records), "n_base_segments_ge_180": long_base}
    if str(zone.style.style) in {"numeric", "bracket_key", "bulleted"}:
        return {"accepted": False, "reason": "raw_hanging_indent_not_author_year_like", "n_base_segments": len(base_records), "n_base_segments_ge_180": long_base}
    lines = _clean_zone_lines(zone)
    geom = _infer_dominant_hanging_indent(lines)
    if not geom.get("eligible"):
        return {"accepted": False, "n_base_segments": len(base_records), "n_base_segments_ge_180": long_base, **geom}
    start_margin = float(geom["start_margin"])
    tolerance = min(5.5, max(2.5, float(geom["margin_separation"]) * 0.16))
    starts = [index for index, line in enumerate(lines) if abs(float(line.x0) - start_margin) <= tolerance]
    segments = _segment(lines, starts, str(zone.style.style))
    q = _quality(segments)
    words = [len(str(item.get("reference_text", "")).split()) for item in segments]
    base_n = len(base_records)
    new_n = len(segments)
    gain = new_n - base_n
    minimum_gain = max(10, int(round(max(base_n, 1) * 0.25)))
    head_missing = _first_record_head_missing(base_records, segments)
    accepted = bool(new_n >= 20 and gain >= minimum_gain and q["evidence_ratio"] >= 0.90 and q["n_giant_segments"] == 0 and 3 <= q["median_words"] <= 100 and (max(words) if words else 0) < 180)
    return {
        **geom,
        "accepted": accepted,
        "reason": "raw_hanging_indent_recovers_moderate_long_undersegmentation" if accepted else "raw_hanging_indent_repair_failed_quality_gate",
        "version": "0.6.7-raw-hanging-indent-long-segment",
        "rc1_origin": RC1_ORIGIN,
        "n_base_segments": base_n,
        "n_reconciled_segments": new_n,
        "delta": gain,
        "minimum_gain": minimum_gain,
        "n_base_segments_ge_180": long_base,
        "base_max_words": max(base_words) if base_words else 0,
        "candidate_max_words": max(words) if words else 0,
        "start_margin_tolerance_effective": round(tolerance, 2),
        "first_reference_head_recovered": bool(head_missing and accepted),
        **q,
        "segments": segments,
    }


def _column_hanging_indent_segments(lines: Sequence[LayoutLine]) -> tuple[List[Dict], Dict]:
    visual = [line for line in _coalesce_reflow_order(lines) if not _is_page_number_line(line)]
    if len(visual) < 16:
        return [], {"eligible": False, "reason": "too_few_reflow_lines"}
    xs = [float(line.x0) for line in visual]
    start_margin = _low_mode(xs)
    start_tolerance = 5.5
    continuation_x = [float(line.x0) for line in visual if start_margin + 14.0 <= float(line.x0) <= start_margin + 90.0]
    if len(continuation_x) < 5:
        return [], {"eligible": False, "reason": "no_continuation_margin_cluster", "start_margin": round(start_margin, 2), "n_continuation_lines": len(continuation_x)}
    continuation_margin = _low_mode(continuation_x)
    separation = continuation_margin - start_margin
    continuation_support = sum(abs(x - continuation_margin) <= 6.0 for x in continuation_x)
    if separation < 14.0 or continuation_support < 5:
        return [], {"eligible": False, "reason": "weak_hanging_indent_geometry", "start_margin": round(start_margin, 2), "continuation_margin": round(continuation_margin, 2), "margin_separation": round(separation, 2), "continuation_support": continuation_support}
    starts: List[int] = []
    rejected_without_evidence = 0
    for index, line in enumerate(visual):
        if abs(float(line.x0) - start_margin) > start_tolerance:
            continue
        text = str(line.text or "").strip()
        if not plausible_author_prefix(text):
            continue
        if nearby_bibliographic_evidence(index, visual):
            starts.append(index)
        else:
            rejected_without_evidence += 1
    starts = sorted(set(starts))
    if len(starts) < 8:
        return [], {"eligible": False, "reason": "too_few_margin_author_starts", "start_margin": round(start_margin, 2), "continuation_margin": round(continuation_margin, 2), "margin_separation": round(separation, 2), "continuation_support": continuation_support, "n_start_candidates": len(starts), "n_rejected_without_local_evidence": rejected_without_evidence}
    segments: List[Dict] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(visual)
        chunk = visual[start:end]
        if not chunk:
            continue
        text = _clean(" ".join(str(line.text or "") for line in chunk if str(line.text or "").strip()))
        if not text:
            continue
        pages = sorted({int(line.page) for line in chunk})
        segments.append({"reference_text": text, "annotation_text": "", "style": "author_year_layout", "reference_start_page": int(chunk[0].page), "reference_end_page": int(pages[-1]), "reference_start_x": round(float(chunk[0].x0), 2), "boundary_evidence": "two_column_reflow+hanging_indent_start_margin+local_bibliographic_evidence", "audit_flags": "column_hanging_indent_v0_6_7"})
    return segments, {"eligible": True, "reason": "strong_reflow_hanging_indent_geometry", "start_margin": round(start_margin, 2), "continuation_margin": round(continuation_margin, 2), "margin_separation": round(separation, 2), "continuation_support": continuation_support, "n_start_candidates": len(starts), "n_rejected_without_local_evidence": rejected_without_evidence}


def _local_x0_clusters(lines: Sequence[LayoutLine], tolerance: float = 2.6) -> List[tuple[float, int]]:
    values = sorted(float(line.x0) for line in lines if not _is_page_number_line(line))
    groups: List[List[float]] = []
    for value in values:
        if not groups or abs(value - statistics.median(groups[-1])) > tolerance:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [(float(statistics.median(group)), len(group)) for group in groups]


def _local_hanging_pair(lines: Sequence[LayoutLine]) -> Dict | None:
    clusters = _local_x0_clusters(lines)
    best = None
    for i, left in enumerate(clusters):
        for right in clusters[i + 1:]:
            separation = float(right[0] - left[0])
            if not 8.0 <= separation <= 20.0 or int(left[1]) < 3 or int(right[1]) < 3:
                continue
            score = int(left[1]) + int(right[1]) - 0.8 * abs(separation - 12.0)
            candidate = {"start_margin": float(left[0]), "continuation_margin": float(right[0]), "start_support": int(left[1]), "continuation_support": int(right[1]), "margin_separation": separation, "pair_support": int(left[1]) + int(right[1]), "score": float(score)}
            if best is None or candidate["score"] > best["score"]:
                best = candidate
    return best


def _numbered_layout_heading(text: str) -> bool:
    clean = _clean(text)
    if len(clean.split()) > 7 or YEAR_OR_SOURCE_RX.search(clean):
        return False
    return bool(re.match(r"^\d+(?:\.\d+)*\.\s+\S", clean))


def _drop_numbered_heading_chunks(chunks: Sequence[Sequence[LayoutLine]]) -> tuple[List[List[LayoutLine]], int]:
    kept: List[List[LayoutLine]] = []
    heading_tail = False
    dropped = 0
    for raw_chunk in chunks:
        chunk = list(raw_chunk)
        if not chunk:
            continue
        text = _clean(" ".join(str(line.text or "") for line in chunk))
        if not text:
            continue
        if _numbered_layout_heading(text):
            heading_tail = True
            dropped += 1
            continue
        if heading_tail:
            words = len(text.split())
            sentence_ending = bool(re.search(r"[.!?;:]\s*$", text))
            if words <= 5 and not sentence_ending:
                dropped += 1
                continue
            heading_tail = False
        kept.append(chunk)
    return kept, dropped


def _page_column_hanging_indent_segments(pdf_path: str | Path, zone: AdaptiveLayoutZone) -> tuple[List[Dict], Dict]:
    ordered: List[tuple[LayoutLine, bool]] = []
    column_diags: List[Dict] = []
    strong_pages = 0
    top_margin_lines_recovered = 0
    with pymupdf.open(str(pdf_path)) as doc:
        stop = min(int(zone.end_page), int(doc.page_count))
        for page_number in range(int(zone.start_page), stop + 1):
            page = doc[page_number - 1]
            raw = _raw_page_lines(page, page_number)
            geometry = _column_geometry(raw, float(page.rect.width))
            if not geometry.get("strong"):
                continue
            strong_pages += 1
            for side in ("left", "right"):
                local = _local_hanging_pair(geometry.get(side, []))
                if local is None:
                    continue
                start_margin = float(local["start_margin"])
                continuation_margin = float(local["continuation_margin"])
                tolerance = 3.3
                selected: List[tuple[LayoutLine, bool]] = []
                for line in raw:
                    if _is_page_number_line(line):
                        continue
                    if not (0.025 * float(line.page_height) <= float(line.y0) <= 0.94 * float(line.page_height)):
                        continue
                    d_start = abs(float(line.x0) - start_margin)
                    d_cont = abs(float(line.x0) - continuation_margin)
                    if min(d_start, d_cont) > tolerance:
                        continue
                    selected.append((line, d_start <= d_cont))
                    if float(line.y0) < 0.06 * float(line.page_height):
                        top_margin_lines_recovered += 1
                selected.sort(key=lambda pair: (float(pair[0].y0), float(pair[0].x0)))
                ordered.extend(selected)
                side_lines = list(geometry.get(side, []))
                support_ratio = float(local["pair_support"]) / max(len(side_lines), 1)
                column_diags.append({"page": int(page_number), "side": side, "start_margin": round(start_margin, 2), "continuation_margin": round(continuation_margin, 2), "margin_separation": round(float(local["margin_separation"]), 2), "start_support": int(local["start_support"]), "continuation_support": int(local["continuation_support"]), "pair_support_ratio": round(support_ratio, 3), "selected_lines": len(selected)})
    expected_columns = strong_pages * 2
    profiled_columns = len(column_diags)
    if expected_columns < 4 or profiled_columns < 4:
        return [], {"eligible": False, "reason": "too_few_profiled_page_columns", "n_strong_pages": strong_pages, "n_expected_columns": expected_columns, "n_profiled_columns": profiled_columns}
    profile_ratio = profiled_columns / max(expected_columns, 1)
    separations = [float(item["margin_separation"]) for item in column_diags]
    supports = [float(item["pair_support_ratio"]) for item in column_diags]
    median_separation = float(statistics.median(separations)) if separations else 0.0
    separation_spread = (max(separations) - min(separations)) if separations else 999.0
    median_support = float(statistics.median(supports)) if supports else 0.0
    if not (profile_ratio >= 0.90 and 8.0 <= median_separation <= 20.0 and separation_spread <= 5.0 and median_support >= 0.90):
        return [], {"eligible": False, "reason": "weak_page_column_hanging_geometry", "n_strong_pages": strong_pages, "n_expected_columns": expected_columns, "n_profiled_columns": profiled_columns, "profiled_column_ratio": round(profile_ratio, 3), "median_margin_separation": round(median_separation, 2), "margin_separation_spread": round(separation_spread, 2), "median_pair_support_ratio": round(median_support, 3)}
    chunks: List[List[LayoutLine]] = []
    current: List[LayoutLine] = []
    for line, is_start in ordered:
        if is_start:
            if current:
                chunks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        chunks.append(current)
    chunks, n_heading_chunks = _drop_numbered_heading_chunks(chunks)
    segments: List[Dict] = []
    for chunk in chunks:
        text = _clean(" ".join(str(line.text or "") for line in chunk if str(line.text or "").strip()))
        if not text:
            continue
        pages = sorted({int(line.page) for line in chunk})
        segments.append({"reference_text": text, "annotation_text": "", "style": "author_year_layout", "reference_start_page": int(chunk[0].page), "reference_end_page": int(pages[-1]), "reference_start_x": round(float(chunk[0].x0), 2), "boundary_evidence": "two_column+page_column_local_hanging_indent", "audit_flags": "column_local_hanging_indent_v0_6_7"})
    return segments, {"eligible": True, "reason": "strong_page_column_hanging_geometry", "n_strong_pages": strong_pages, "n_expected_columns": expected_columns, "n_profiled_columns": profiled_columns, "profiled_column_ratio": round(profile_ratio, 3), "median_margin_separation": round(median_separation, 2), "margin_separation_spread": round(separation_spread, 2), "median_pair_support_ratio": round(median_support, 3), "top_margin_lines_recovered": int(top_margin_lines_recovered), "n_numbered_heading_chunks_excluded": int(n_heading_chunks), "column_profiles": column_diags}


def build_column_reflow_repair_v067(pdf_path: str | Path, zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    """Preserve v0.6.5 first; use RC1 candidates only after safe abstention."""
    baseline = _baseline_column_reflow_v2(pdf_path, zone, base_records)
    if baseline.get("accepted"):
        return baseline
    reflowed, geometry = reflow_two_column_zone(pdf_path, zone)
    if not geometry.get("eligible") or len(reflowed) < 8:
        return baseline
    hanging_candidate, hanging_diag = _column_hanging_indent_segments(reflowed)
    if hanging_candidate:
        q = _segment_quality(hanging_candidate)
        words = [len(str(item.get("reference_text", "")).split()) for item in hanging_candidate]
        base_n, new_n = len(base_records), len(hanging_candidate)
        minimum_gain = max(3, int(round(max(1, base_n) * 0.05))) if base_n >= 5 else 0
        if hanging_diag.get("eligible") and new_n >= 8 and (base_n < 5 or new_n >= base_n + minimum_gain) and q["n_giant_segments"] == 0 and q["evidence_ratio"] >= 0.92 and 3 <= q["median_words"] <= 140 and (max(words) if words else 0) < 250:
            return {**geometry, **hanging_diag, "accepted": True, "reason": "two_column_hanging_indent_recovered_v0_6_7", "rc1_origin": RC1_ORIGIN, "candidate_style": "author_year_layout", "n_base_segments": base_n, "n_enhanced_segments": new_n, "minimum_gain": minimum_gain, "max_words": max(words) if words else 0, **q, "segments": hanging_candidate}
    local_candidate, local_diag = _page_column_hanging_indent_segments(pdf_path, zone)
    if local_candidate:
        q = _segment_quality(local_candidate)
        words = [len(str(item.get("reference_text", "")).split()) for item in local_candidate]
        base_n, new_n = len(base_records), len(local_candidate)
        minimum_gain = max(8, int(round(max(1, base_n) * 0.15))) if base_n >= 5 else 0
        if local_diag.get("eligible") and new_n >= 20 and (base_n < 5 or new_n >= base_n + minimum_gain) and q["n_giant_segments"] == 0 and q["evidence_ratio"] >= 0.80 and 3 <= q["median_words"] <= 100 and (max(words) if words else 0) < 120:
            return {**geometry, **local_diag, "accepted": True, "reason": "two_column_page_local_hanging_indent_recovered_v0_6_7", "rc1_origin": RC1_ORIGIN, "candidate_style": "mixed_author_year_layout", "n_base_segments": base_n, "n_enhanced_segments": new_n, "minimum_gain": minimum_gain, "max_words": max(words) if words else 0, **q, "segments": local_candidate}
    enriched = dict(baseline)
    enriched.update({"hanging_indent_candidate_segments": len(hanging_candidate), "hanging_indent_candidate": hanging_diag, "page_column_hanging_candidate_segments": len(local_candidate), "page_column_hanging_candidate": local_diag, "rc1_origin": RC1_ORIGIN})
    return enriched
