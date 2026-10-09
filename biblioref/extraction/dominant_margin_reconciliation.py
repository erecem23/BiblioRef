"""Dominant-margin post-segmentation reconciliation (algorithm v0.6.6 candidate).

This repair is intentionally narrow. It addresses author-year bibliographies
where the baseline segmentation already demonstrates an overwhelmingly stable
first-line x margin, but an isolated false boundary and an isolated missed
boundary can cancel each other numerically. It also rebuilds each accepted
record from the *physical document lines*, preserving continuation-only URL
lines that a text-evidence segmenter may have dropped.

The repair does not change bibliography-zone detection and never parses
bibliographic metadata. It only replaces record boundaries when independent
geometry and local year/source evidence agree under conservative gates.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, YEAR_RX, SIN_FECHA_RX
from biblioref_page_decorations import detect_running_headers

DOMINANT_MARGIN_RECONCILIATION_VERSION = "0.6.6-dominant-margin-topology1"

_NORMALIZE_RX = re.compile(r"\s+")
_PAGE_NUMBER_RX = re.compile(r"^\s*(?:\[?\d{1,4}\]?|[-–—]?\s*\d{1,4}\s*[-–—]?)\s*$")
_AUTHOR_LEAD_RX = re.compile(r"^[A-ZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇ0-9][^\n]{2,}")


def _norm(text: str) -> str:
    return _NORMALIZE_RX.sub(" ", str(text or "")).strip().casefold()


def _head_signature(text: str, size: int = 40) -> str:
    return _norm(text)[:size]


def _local_repeated_decorations(lines: Sequence[LayoutLine]) -> set[Tuple[str, str]]:
    by_key: Dict[Tuple[str, str], set[int]] = {}
    for line in lines:
        text = _norm(line.text)
        if not text or len(text) > 180:
            continue
        height = max(float(getattr(line, "page_height", 0.0) or 0.0), 1.0)
        rel = float(line.y0) / height
        band = "top" if rel <= 0.075 else "bottom" if rel >= 0.90 else ""
        if not band:
            continue
        by_key.setdefault((text, band), set()).add(int(line.page))
    return {key for key, pages in by_key.items() if len(pages) >= 3}


def _is_decoration(line: LayoutLine, keys: set[Tuple[str, str]]) -> bool:
    height = max(float(getattr(line, "page_height", 0.0) or 0.0), 1.0)
    rel = float(line.y0) / height
    band = "top" if rel <= 0.075 else "bottom" if rel >= 0.90 else ""
    return bool(band and (_norm(line.text), band) in keys)


def _physical_zone_lines(document_lines: Sequence[LayoutLine], zone: AdaptiveLayoutZone) -> List[LayoutLine]:
    selected: List[LayoutLine] = []
    for line in document_lines:
        page = int(line.page)
        if page < int(zone.start_page) or page > int(zone.end_page):
            continue
        text = str(line.text or "").strip()
        if not text:
            continue
        if page == int(zone.start_page) and float(line.y0) <= float(zone.heading.y1) + 2.0:
            continue
        selected.append(line)

    decorations = _local_repeated_decorations(selected)
    # 0.6.18: a running header just below the 7.5 % band (a signature at 7.8 %)
    # repeats at the same height on every page; same rule as the zone filter.
    running = {id(line) for line in detect_running_headers(selected)}
    out: List[LayoutLine] = []
    for line in selected:
        text = str(line.text or "").strip()
        if _is_decoration(line, decorations) or id(line) in running:
            continue
        if _PAGE_NUMBER_RX.fullmatch(text):
            continue
        out.append(line)
    return out


def _dominant_start_margin(base_records: Sequence[Dict], cluster_tol: float = 3.0) -> Dict:
    xs: List[float] = []
    for record in base_records:
        try:
            xs.append(float(record.get("reference_start_x")))
        except (TypeError, ValueError):
            continue
    if not xs:
        return {"margin": None, "support": 0.0, "n": 0, "n_off_margin": 0}

    # Baseline starts are normally quantized by PDF layout. Choose the observed
    # x value whose ±cluster_tol neighbourhood has maximal support; median of
    # that neighbourhood stabilizes small floating-point variation.
    best_members: List[float] = []
    for x in xs:
        members = [v for v in xs if abs(v - x) <= cluster_tol]
        if len(members) > len(best_members):
            best_members = members
    margin = float(statistics.median(best_members))
    support = len(best_members) / len(xs)
    return {
        "margin": margin,
        "support": support,
        "n": len(xs),
        "n_off_margin": len(xs) - len(best_members),
    }


def _candidate_author_shape(text: str) -> bool:
    text = str(text or "").strip()
    if not text or len(text) < 4 or len(text) > 360:
        return False
    if _PAGE_NUMBER_RX.fullmatch(text):
        return False
    return bool(_AUTHOR_LEAD_RX.match(text))


def _near_margin(line: LayoutLine, margin: float, tolerance: float) -> bool:
    return abs(float(line.x0) - margin) <= tolerance


def _window_has_evidence(lines: Sequence[LayoutLine], start: int, stop: int) -> bool:
    probe = " ".join(str(lines[i].text or "").strip() for i in range(start, min(stop, start + 3)))
    probe = _NORMALIZE_RX.sub(" ", probe).strip()
    if not probe:
        return False
    return bool(YEAR_RX.search(probe[:700]) or SIN_FECHA_RX.search(probe[:700]) or YEAR_OR_SOURCE_RX.search(probe[:700]))


def _candidate_starts(lines: Sequence[LayoutLine], margin: float, tolerance: float) -> tuple[List[int], int, int]:
    raw = [
        i for i, line in enumerate(lines)
        if _near_margin(line, margin, tolerance) and _candidate_author_shape(line.text)
    ]
    accepted: List[int] = []
    rejected = 0
    for pos, index in enumerate(raw):
        stop = raw[pos + 1] if pos + 1 < len(raw) else len(lines)
        if _window_has_evidence(lines, index, stop):
            accepted.append(index)
        else:
            rejected += 1
    return accepted, len(raw), rejected


def _segment(lines: Sequence[LayoutLine], starts: Sequence[int], style: str) -> List[Dict]:
    out: List[Dict] = []
    for pos, start in enumerate(starts):
        stop = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        source = list(lines[start:stop])
        text = _NORMALIZE_RX.sub(
            " ", " ".join(str(line.text or "").strip() for line in source if str(line.text or "").strip())
        ).strip()
        if not text:
            continue
        pages = sorted({int(line.page) for line in source})
        out.append({
            "reference_text": text,
            "annotation_text": "",
            "style": style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(float(source[0].x0), 2),
            "boundary_evidence": "dominant_baseline_start_margin+local_bibliographic_evidence",
            "audit_flags": "cross_page" if len(pages) > 1 else "",
            "dominant_margin_reconciliation_version": DOMINANT_MARGIN_RECONCILIATION_VERSION,
        })
    return out


def _quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(s.get("reference_text") or "").strip() for s in segments]
    words = [len(t.split()) for t in texts if t]
    evidence = sum(bool(YEAR_RX.search(t[:700]) or SIN_FECHA_RX.search(t[:700]) or YEAR_OR_SOURCE_RX.search(t[:700])) for t in texts)
    return {
        "n_segments": len(texts),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "max_words": max(words) if words else 0,
        "n_giant_segments": sum(w >= 500 for w in words),
        "evidence_ratio": round(evidence / max(len(texts), 1), 3),
    }


def _topology_delta(base_records: Sequence[Dict], candidate: Sequence[Dict]) -> Dict:
    base = [_head_signature(r.get("reference_text", "")) for r in base_records]
    cand = [_head_signature(r.get("reference_text", "")) for r in candidate]
    base_counts = Counter(x for x in base if x)
    cand_counts = Counter(x for x in cand if x)
    removed = list((base_counts - cand_counts).elements())
    added = list((cand_counts - base_counts).elements())
    return {
        "n_removed_start_signatures": len(removed),
        "n_added_start_signatures": len(added),
        "removed_start_signatures": removed[:12],
        "added_start_signatures": added[:12],
    }


def _text_gain(base_records: Sequence[Dict], candidate: Sequence[Dict]) -> Dict:
    # Compare aligned head signatures only. Longer candidate text is useful
    # evidence that continuation-only lines (especially URLs) were preserved.
    base_by_head = {_head_signature(r.get("reference_text", "")): str(r.get("reference_text") or "") for r in base_records}
    gained = 0
    chars = 0
    for c in candidate:
        sig = _head_signature(c.get("reference_text", ""))
        old = base_by_head.get(sig)
        new = str(c.get("reference_text") or "")
        if old is not None and len(new) > len(old) + 8 and _norm(new).startswith(_norm(old)):
            gained += 1
            chars += len(new) - len(old)
    return {"n_records_with_continuation_text_gain": gained, "continuation_chars_recovered": chars}


def build_dominant_margin_repair(
    document_lines: Sequence[LayoutLine],
    zone: AdaptiveLayoutZone,
    base_records: Sequence[Dict],
) -> Dict:
    base_records = list(base_records or [])
    base_n = len(base_records)
    style = str(zone.style.style)
    if style in {"numeric", "bracket_key", "bulleted"}:
        return {"accepted": False, "reason": "dominant_margin_not_author_year_like"}
    if base_n < 20:
        return {"accepted": False, "reason": "too_few_baseline_records", "n_base_segments": base_n}

    dom = _dominant_start_margin(base_records)
    margin = dom.get("margin")
    if margin is None or float(dom.get("support") or 0.0) < 0.95:
        return {"accepted": False, "reason": "baseline_start_margin_not_dominant", **dom}

    tolerance = 4.0
    physical = _physical_zone_lines(document_lines, zone)
    starts, n_raw, n_rejected = _candidate_starts(physical, float(margin), tolerance)
    segments = _segment(physical, starts, style)
    q = _quality(segments)
    topo = _topology_delta(base_records, segments)
    gain = _text_gain(base_records, segments)

    new_n = len(segments)
    delta = new_n - base_n
    changes = topo["n_removed_start_signatures"] + topo["n_added_start_signatures"]
    max_topology_changes = max(2, int(round(base_n * 0.03)))
    purity = new_n / max(n_raw, 1)

    common = bool(
        new_n >= 20
        and purity >= 0.97
        and q["evidence_ratio"] >= 0.94
        and q["n_giant_segments"] == 0
        and 3 <= q["median_words"] <= 180
        and q["max_words"] < 500
    )

    # Same-count topology swaps are the principal v0.6.6 use case. Require an
    # off-margin baseline start, exactly balanced add/remove boundaries, and a
    # very small change set. This prevents count equality from masking a false
    # split + missed start pair.
    same_count_swap = bool(
        common
        and delta == 0
        and dom["support"] >= 0.98
        and dom["n_off_margin"] >= 1
        and topo["n_removed_start_signatures"] >= 1
        and topo["n_removed_start_signatures"] == topo["n_added_start_signatures"]
        and changes <= max_topology_changes
    )

    # A small positive delta can also recover missed dominant-margin starts, but
    # only when virtually every baseline start already belongs to that margin.
    missed_only = bool(
        common
        and 1 <= delta <= max(2, int(round(base_n * 0.02)))
        and dom["support"] >= 0.98
        and topo["n_removed_start_signatures"] == 0
        and topo["n_added_start_signatures"] == delta
    )

    accepted = same_count_swap or missed_only
    return {
        "accepted": accepted,
        "reason": (
            "dominant_margin_same_count_topology_reconciled" if same_count_swap else
            "dominant_margin_missing_boundaries_reconciled" if missed_only else
            "dominant_margin_reconciliation_failed_gate"
        ),
        "version": DOMINANT_MARGIN_RECONCILIATION_VERSION,
        "n_base_segments": base_n,
        "n_reconciled_segments": new_n,
        "delta": delta,
        "dominant_start_margin": round(float(margin), 2),
        "dominant_start_margin_support": round(float(dom["support"]), 3),
        "n_baseline_start_x": dom["n"],
        "n_baseline_off_margin_starts": dom["n_off_margin"],
        "start_margin_tolerance_effective": tolerance,
        "n_physical_zone_lines": len(physical),
        "n_raw_geometric_candidates": n_raw,
        "n_candidates_rejected_without_local_evidence": n_rejected,
        "candidate_evidence_purity": round(purity, 3),
        "max_allowed_topology_changes": max_topology_changes,
        **topo,
        **gain,
        **q,
        "segments": segments,
    }
