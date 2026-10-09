"""Robust per-zone length diagnostics for BiblioRef v0.8.5-e.

Length is surveillance evidence only.  It never creates, merges, removes or
splits records.  The profile is computed within a bibliography zone so that
short/long judgments are relative to the local documentary style.
"""
from __future__ import annotations

import math
import statistics
from typing import Dict, Sequence


def _percentile(values: Sequence[float], q: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * min(max(q, 0.0), 1.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _mad(values: Sequence[float], center: float | None = None) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return 0.0
    med = float(statistics.median(vals)) if center is None else float(center)
    return float(statistics.median(abs(v - med) for v in vals))


def _basic_metrics(segment: Dict) -> Dict:
    text = str(segment.get("reference_text", "")).strip()
    words = text.split()
    source_lines = list(segment.get("source_lines") or [])
    pages = {
        int(item.get("page")) for item in source_lines
        if item.get("page") is not None
    }
    if not pages:
        for key in ("reference_start_page", "reference_end_page"):
            if segment.get(key) is not None:
                pages.add(int(segment[key]))
    return {
        "n_chars": len(text),
        "n_words": len(words),
        "n_lines": int(segment.get("n_source_lines") or len(source_lines) or 1),
        "n_pages": int(segment.get("n_pages_spanned") or len(pages) or 1),
        "n_pdf_fragments": len(source_lines) if source_lines else int(segment.get("n_source_lines") or 0),
        "n_sentential_delimiters": sum(text.count(ch) for ch in (".", ";", ":")),
    }


def build_length_profile(segments: Sequence[Dict]) -> Dict:
    """Return robust zone-level and per-record length diagnostics."""
    rows = [_basic_metrics(seg) for seg in segments]
    words = [row["n_words"] for row in rows]
    logs = [math.log1p(v) for v in words]
    if words:
        median_words = float(statistics.median(words))
        median_log = float(statistics.median(logs))
        mad_words = _mad(words, median_words)
        mad_log = _mad(logs, median_log)
    else:
        median_words = median_log = mad_words = mad_log = 0.0

    q1 = _percentile(words, 0.25)
    q3 = _percentile(words, 0.75)
    p05 = _percentile(words, 0.05)
    p95 = _percentile(words, 0.95)

    enriched = []
    for i, row in enumerate(rows):
        n_words = row["n_words"]
        log_words = math.log1p(n_words)
        robust_z = 0.0
        if mad_log > 1e-9:
            robust_z = 0.6745 * (log_words - median_log) / mad_log
        prev_words = rows[i - 1]["n_words"] if i > 0 else None
        next_words = rows[i + 1]["n_words"] if i + 1 < len(rows) else None
        lo = max(0, i - 2)
        hi = min(len(rows), i + 3)
        local = [r["n_words"] for r in rows[lo:hi] if r["n_words"] >= 0]
        local_med = float(statistics.median(local)) if local else 0.0
        flags = []
        if n_words < 2:
            flags.append("very_short_absolute")
        if robust_z <= -3.5:
            flags.append("short_relative")
        if robust_z >= 3.5:
            flags.append("long_relative")
        if n_words >= 500:
            flags.append("giant_absolute")
        if row["n_pages"] > 1:
            flags.append("cross_page")
        # Ratio backstops are descriptive only, useful when MAD collapses.
        if median_words >= 8 and n_words <= max(3, 0.20 * median_words):
            flags.append("short_vs_zone_median")
        if median_words > 0 and n_words >= max(180, 4.0 * median_words):
            flags.append("long_vs_zone_median")
        enriched.append({
            "record_index": i,
            **row,
            "length_robust_z": round(float(robust_z), 3),
            "length_vs_zone_median": round(n_words / median_words, 3) if median_words else None,
            "length_vs_previous": round(n_words / prev_words, 3) if prev_words else None,
            "length_vs_next": round(n_words / next_words, 3) if next_words else None,
            "local_median_words_5": round(local_med, 2),
            "length_vs_local_median_5": round(n_words / local_med, 3) if local_med else None,
            "length_flags": list(dict.fromkeys(flags)),
        })

    return {
        "n_records": len(rows),
        "median_words": round(median_words, 2),
        "mad_words": round(mad_words, 2),
        "q1_words": round(q1, 2),
        "q3_words": round(q3, 2),
        "iqr_words": round(q3 - q1, 2),
        "p05_words": round(p05, 2),
        "p95_words": round(p95, 2),
        "min_words": min(words) if words else 0,
        "max_words": max(words) if words else 0,
        "records": enriched,
        "diagnostic_only": True,
        "auto_apply": False,
    }


__all__ = ["build_length_profile"]
