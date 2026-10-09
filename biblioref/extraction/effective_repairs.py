"""Selective rescue candidates derived from external holdout failures.

Every rescue is evidence-gated and document-generic. No repository, author or
thesis title is encoded here. These helpers have no authority on the default path.
"""
from __future__ import annotations

from dataclasses import replace
import re
import statistics
from typing import Dict, List, Sequence

from biblioref.adaptive.geometry import detect_repeated_decorations, is_repeated_decoration
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.detection.signals import (
    nearby_bibliographic_evidence, plausible_author_prefix,
    enhanced_start, page_start_margins,
)
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    YEAR_RX,
    SIN_FECHA_RX,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    segment_adaptive_layout_zone,
)

APPENDIX_RX = re.compile(r"^(?:appendix|appendices|anexo|anexos|ap[eé]ndice|ap[eé]ndices)\b", re.I)
AUTHOR_GUIDE_RX = re.compile(
    r"\b(?:author guidelines?|instructions? for authors?|preparing your paper|"
    r"manuscript guidelines?|submission guidelines?|style guidelines?)\b", re.I
)
CHAPTER_RX = re.compile(r"^(?:chapter|cap[ií]tulo)\s+(?:\d+|[ivxlcdm]+)\b", re.I)


def _quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(x.get("reference_text", "")).strip() for x in segments if str(x.get("reference_text", "")).strip()]
    words = [len(t.split()) for t in texts]
    evidence = sum(bool(YEAR_OR_SOURCE_RX.search(t)) for t in texts)
    return {
        "n_segments": len(texts),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "n_giant_segments": sum(w >= 500 for w in words),
        "evidence_ratio": round(evidence / max(len(texts), 1), 3),
    }


def clean_repeated_decorations(zone: AdaptiveLayoutZone, full_lines: Sequence[LayoutLine]) -> tuple[AdaptiveLayoutZone, Dict]:
    report = detect_repeated_decorations(full_lines)
    removed = [line for line in zone.lines if is_repeated_decoration(line, report)]
    if not removed:
        return zone, {"eligible": False, "n_removed_lines": 0}
    cleaned = [line for line in zone.lines if not is_repeated_decoration(line, report)]
    style = diagnose_adaptive_style([line.text for line in cleaned])
    layout = diagnose_adaptive_layout(cleaned, style)
    return replace(zone, lines=cleaned, style=style, layout=layout), {
        "eligible": True,
        "n_removed_lines": len(removed),
        "removed_pages": sorted({int(line.page) for line in removed}),
        "examples": list(dict.fromkeys(line.text.strip() for line in removed))[:5],
    }


def build_repeated_decoration_repair(zone: AdaptiveLayoutZone, full_lines: Sequence[LayoutLine], base_records: Sequence[Dict]) -> Dict:
    cleaned_zone, diag = clean_repeated_decorations(zone, full_lines)
    if not diag.get("eligible"):
        return {"accepted": False, "reason": "no_repeated_decoration_inside_zone", **diag}
    segments = segment_adaptive_layout_zone(cleaned_zone)
    q = _quality(segments)
    removed = int(diag.get("n_removed_lines", 0))
    base_n = len(base_records)
    new_n = len(segments)
    # Repeated running decorations can either become standalone false records or
    # get glued to a continuation.  Therefore a *lower* count is expected.  Do
    # not accept a collapse larger than the amount of repeated-page evidence.
    examples = [str(x).strip() for x in diag.get("examples", []) if str(x).strip()]
    base_contaminated = any(
        example and example.lower() in str(record.get("reference_text", "")).lower()
        for example in examples for record in base_records
    )
    accepted = bool(
        removed >= 3
        and new_n >= 5
        and (new_n < base_n or base_contaminated)
        and new_n <= base_n
        and base_n - new_n <= removed + 4
        and q["n_giant_segments"] == 0
        and q["evidence_ratio"] >= 0.75
        and 3 <= q["median_words"] <= 140
    )
    return {
        "accepted": accepted,
        "reason": "repeated_decoration_removed_and_resegmented" if accepted else "decoration_repair_failed_gate",
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        **diag,
        **q,
        "segments": segments,
    }


def _within_page_gaps(lines: Sequence[LayoutLine]) -> List[float]:
    gaps: List[float] = []
    for prev, cur in zip(lines, lines[1:]):
        if int(prev.page) == int(cur.page):
            gaps.append(max(0.0, float(cur.y0) - float(prev.y1)))
    return gaps


def _gap_threshold(lines: Sequence[LayoutLine]) -> float:
    gaps = _within_page_gaps(lines)
    if not gaps:
        return 9999.0
    med = float(statistics.median(gaps))
    mad = float(statistics.median(abs(g - med) for g in gaps))
    return max(5.0, med + max(4.0 * mad, med * 0.35))


def _author_list_without_year(text: str) -> bool:
    # Wrapped author lists often postpone the date to the next line.  Require
    # strong author punctuation/initial evidence so journal-title continuations
    # such as ``Personality and Individual Differences, 48, ...`` are rejected.
    initials = len(re.findall(r"\b[A-ZÁÉÍÓÚÑÜ]\.", text))
    return bool(initials >= 2 or re.search(r"(?:&|\. \. \.)\s*[^,]{0,35},?\s*$", text))


def _gap_start(index: int, lines: Sequence[LayoutLine], threshold: float) -> bool:
    if index == 0:
        return False
    cur, prev = lines[index], lines[index - 1]
    if int(cur.page) != int(prev.page):
        return False
    gap = max(0.0, float(cur.y0) - float(prev.y1))
    if gap < threshold:
        return False
    text = cur.text.strip()
    if not plausible_author_prefix(text):
        return False
    if YEAR_RX.search(text[:320]) or SIN_FECHA_RX.search(text[:320]):
        return True
    return bool(_author_list_without_year(text) and nearby_bibliographic_evidence(index, lines))


def _segment_pure_gap_zone(zone: AdaptiveLayoutZone) -> tuple[List[Dict], Dict]:
    lines = list(zone.lines)
    threshold = _gap_threshold(lines)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    starts = 0

    def flush():
        nonlocal current
        if not current:
            return
        pages = sorted({int(line.page) for line in current})
        text = re.sub(r"\s+", " ", " ".join(line.text.strip() for line in current if line.text.strip())).strip()
        segments.append({
            "reference_text": text, "annotation_text": "", "style": zone.style.style,
            "reference_start_page": pages[0], "reference_end_page": pages[-1],
            "reference_start_x": round(float(current[0].x0), 2),
            "boundary_evidence": "large_vertical_gap+author_evidence",
            "audit_flags": "cross_page" if len(pages) > 1 else "",
        })
        current = []

    for index, line in enumerate(lines):
        text = line.text.strip()
        if not text:
            continue
        if _gap_start(index, lines, threshold):
            starts += 1
            flush(); current = [line]
        elif current:
            current.append(line)
        elif plausible_author_prefix(text) and nearby_bibliographic_evidence(index, lines):
            current = [line]
    flush()
    q = _quality(segments)
    q.update({"gap_threshold": round(threshold, 3), "n_gap_only_starts": starts, "n_explicit_starts": 0, "gap_mode": "pure"})
    return segments, q


def _segment_gap_zone(zone: AdaptiveLayoutZone) -> tuple[List[Dict], Dict]:
    lines = list(zone.lines)
    threshold = _gap_threshold(lines)
    page_margins, global_margin = page_start_margins(zone)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    gap_starts = 0
    explicit_starts = 0

    def flush():
        nonlocal current
        if not current:
            return
        pages = sorted({int(line.page) for line in current})
        text = " ".join(line.text.strip() for line in current if line.text.strip())
        text = re.sub(r"\s+", " ", text).strip()
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(float(current[0].x0), 2),
            "boundary_evidence": "hybrid_explicit_or_vertical_gap",
            "audit_flags": "cross_page" if len(pages) > 1 else "",
        })
        current = []

    for index, line in enumerate(lines):
        text = line.text.strip()
        if not text:
            continue
        explicit, _ = enhanced_start(index, zone, page_margins, global_margin)
        gap_start = _gap_start(index, lines, threshold)
        start_here = explicit or gap_start
        if start_here:
            explicit_starts += int(bool(explicit))
            gap_starts += int(bool(gap_start and not explicit))
            flush()
            current = [line]
        elif current:
            current.append(line)
        else:
            if plausible_author_prefix(text) and nearby_bibliographic_evidence(index, lines):
                current = [line]
    flush()
    q = _quality(segments)
    q.update({
        "gap_threshold": round(threshold, 3),
        "n_gap_only_starts": gap_starts,
        "n_explicit_starts": explicit_starts,
    })
    return segments, q


def build_vertical_gap_repair(zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    if zone.style.style not in {"author_year_comma", "author_year_bare", "mixed"}:
        return {"accepted": False, "reason": "style_not_gap_candidate"}
    # When there is no hanging indent and the vertical paragraph separation is
    # itself strong, gap-only segmentation is safer than author syntax (which
    # can mistake wrapped final authors for new entries).  Otherwise use a
    # hybrid of explicit starts plus gap-only evidence.
    if not zone.layout.hanging_indent_detected and _gap_threshold(zone.lines) >= 8.0:
        segments, q = _segment_pure_gap_zone(zone)
    else:
        segments, q = _segment_gap_zone(zone)
    base_n, new_n = len(base_records), len(segments)
    gain = new_n - base_n
    minimum_gain = 1 if base_n <= 20 else max(2, int(base_n * 0.01))
    accepted = bool(
        q.get("n_gap_only_starts", 0) >= 1
        and new_n >= 5
        and gain >= minimum_gain
        and gain <= max(20, int(base_n * 0.12) + 2)
        and q["n_giant_segments"] == 0
        and q["evidence_ratio"] >= 0.80
        and 3 <= q["median_words"] <= 140
        and q["gap_threshold"] >= 5.0
    )
    return {
        "accepted": accepted,
        "reason": "same_margin_vertical_gap_boundaries_recovered" if accepted else "vertical_gap_repair_failed_gate",
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        **q,
        "segments": segments,
    }


def strong_appendix_guideline_conflict(zone: AdaptiveLayoutZone, full_lines: Sequence[LayoutLine]) -> Dict:
    """Block a References heading embedded in appendix author instructions.

    Search backwards through the current appendix block (up to 25 pages) and
    stop if a real chapter heading is encountered.  Both appendix evidence and
    author/submission-guideline vocabulary are required.
    """
    heading_page = int(zone.heading.page)
    nearby: List[LayoutLine] = []
    for page in range(heading_page, max(0, heading_page - 25), -1):
        page_lines = [line for line in full_lines if int(line.page) == page and line.text.strip()]
        texts = [line.text.strip() for line in page_lines]
        if page < heading_page and any(CHAPTER_RX.search(t) for t in texts):
            break
        nearby.extend(page_lines)
        if any(APPENDIX_RX.search(t) for t in texts) and any(AUTHOR_GUIDE_RX.search(t) for t in texts):
            break
    texts = [line.text.strip() for line in nearby]
    appendix_hits = [t for t in texts if APPENDIX_RX.search(t)]
    guide_hits = [t for t in texts if AUTHOR_GUIDE_RX.search(t)]
    blocked = bool(appendix_hits and guide_hits)
    return {
        "blocked": blocked,
        "reason": "appendix_author_guidelines_context" if blocked else "no_strong_appendix_guideline_conflict",
        "appendix_evidence": appendix_hits[:3],
        "guideline_evidence": guide_hits[:3],
    }


def toc_reference_coverage(lines: Sequence[LayoutLine], zones: Sequence[Dict]) -> Dict:
    """Diagnostic only: compare TOC reference labels with detected zone headings."""
    toc_candidates = []
    for line in lines:
        text = line.text.strip()
        low = text.lower()
        if len(text) <= 180 and ("referenc" in low or "bibliograf" in low):
            if re.search(r"\.{3,}|\s\d{1,4}\s*$", text) or re.match(r"^\d+[a-z]?(?:[ivxlcdm]+|\d+)", low):
                toc_candidates.append({"page": int(line.page), "text": text})
    zone_heads = [str(z.get("heading", "")) for z in zones]
    return {
        "n_toc_reference_candidates": len(toc_candidates),
        "toc_reference_candidates": toc_candidates[:20],
        "n_detected_reference_zones": len(zones),
        "detected_headings": zone_heads,
        "possible_incomplete_coverage": bool(toc_candidates and not zones),
    }

# --- Selective rescue helpers (v0.8.6) -------------------------------------

def _guarded_enhanced_start(index: int, zone: AdaptiveLayoutZone, page_margins: Dict[int, float], global_margin: float):
    """Use v0.6.1 start evidence but suppress bare numeric starts in author-year zones."""
    start, evidence = enhanced_start(index, zone, page_margins, global_margin)
    if start and evidence == "numeric_marker" and zone.style.style not in {"numeric", "bracket_key"}:
        return False, ""
    return start, evidence


def _segment_numeric_guard_zone(zone: AdaptiveLayoutZone) -> tuple[List[Dict], Dict]:
    from biblioref.extraction.resegmentation import DATE_ONLY_ENTRY_RX
    page_margins, global_margin = page_start_margins(zone)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    boundary_evidence = ""
    suppressed_numeric = 0

    def flush():
        nonlocal current, boundary_evidence
        if not current:
            return
        pages = sorted({int(line.page) for line in current})
        text = re.sub(r"\s+", " ", " ".join(line.text.strip() for line in current if line.text.strip())).strip()
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(float(current[0].x0), 2),
            "boundary_evidence": boundary_evidence,
            "audit_flags": "cross_page" if len(pages) > 1 else "",
        })
        current = []
        boundary_evidence = ""

    for index, line in enumerate(zone.lines):
        text = line.text.strip()
        if not text:
            continue
        original_start, original_evidence = enhanced_start(index, zone, page_margins, global_margin)
        start, evidence = _guarded_enhanced_start(index, zone, page_margins, global_margin)
        if original_start and original_evidence == "numeric_marker" and not start:
            suppressed_numeric += 1
        if not start and current and DATE_ONLY_ENTRY_RX.match(text):
            current_text = " ".join(item.text for item in current)
            page_margin = page_margins.get(line.page, global_margin)
            inherited_indent = line.x0 >= page_margin + 18
            if inherited_indent and (YEAR_RX.search(current_text) or SIN_FECHA_RX.search(current_text)):
                start = True
                evidence = "inherited_author+date_only_entry"
        if start:
            flush()
            current = [line]
            boundary_evidence = evidence
        elif current:
            current.append(line)
    flush()
    q = _quality(segments)
    q["n_suppressed_numeric_starts"] = suppressed_numeric
    return segments, q


def build_author_year_numeric_guard_repair(zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    if zone.style.style in {"numeric", "bracket_key", "bulleted"}:
        return {"accepted": False, "reason": "numeric_guard_not_applicable_to_numeric_style"}
    suspicious_records = [
        r for r in base_records
        if re.match(r"^\s*\d{1,4}\s*[.)]\s+", str(r.get("reference_text", "")))
    ]
    if len(suspicious_records) < 2:
        return {"accepted": False, "reason": "too_few_suspicious_numeric_boundaries", "n_suspicious": len(suspicious_records)}
    segments, q = _segment_numeric_guard_zone(zone)
    base_n, new_n = len(base_records), len(segments)
    reduction = base_n - new_n
    accepted = bool(
        q.get("n_suppressed_numeric_starts", 0) >= 2
        and 1 <= reduction <= len(suspicious_records) + 4
        and new_n >= 5
        and q["n_giant_segments"] == 0
        and q["evidence_ratio"] >= 0.78
        and 3 <= q["median_words"] <= 150
    )
    return {
        "accepted": accepted,
        "reason": "author_year_numeric_continuations_rejoined" if accepted else "numeric_guard_failed_gate",
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        "n_suspicious": len(suspicious_records),
        **q,
        "segments": segments,
    }

def _segment_guarded_gap_zone(zone: AdaptiveLayoutZone) -> tuple[List[Dict], Dict]:
    """Hybrid author-year segmentation: guarded explicit starts + strong vertical gaps."""
    from biblioref.extraction.resegmentation import DATE_ONLY_ENTRY_RX
    lines = list(zone.lines)
    threshold = _gap_threshold(lines)
    page_margins, global_margin = page_start_margins(zone)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    boundary_evidence = ""
    suppressed_numeric = 0
    gap_only = 0
    explicit = 0

    def flush():
        nonlocal current, boundary_evidence
        if not current:
            return
        pages = sorted({int(line.page) for line in current})
        text = re.sub(r"\s+", " ", " ".join(line.text.strip() for line in current if line.text.strip())).strip()
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(float(current[0].x0), 2),
            "boundary_evidence": boundary_evidence,
            "audit_flags": "cross_page" if len(pages) > 1 else "",
        })
        current = []
        boundary_evidence = ""

    for index, line in enumerate(lines):
        text = line.text.strip()
        if not text:
            continue
        original_start, original_evidence = enhanced_start(index, zone, page_margins, global_margin)
        start, evidence = _guarded_enhanced_start(index, zone, page_margins, global_margin)
        if original_start and original_evidence == "numeric_marker" and not start:
            suppressed_numeric += 1
        gap_start = _gap_start(index, lines, threshold)
        if not start and gap_start:
            start = True
            evidence = "large_vertical_gap+author_evidence"
            gap_only += 1
        elif start:
            explicit += 1
        if not start and current and DATE_ONLY_ENTRY_RX.match(text):
            current_text = " ".join(item.text for item in current)
            page_margin = page_margins.get(line.page, global_margin)
            inherited_indent = line.x0 >= page_margin + 18
            if inherited_indent and (YEAR_RX.search(current_text) or SIN_FECHA_RX.search(current_text)):
                start = True
                evidence = "inherited_author+date_only_entry"
                explicit += 1
        if start:
            flush()
            current = [line]
            boundary_evidence = evidence
        elif current:
            current.append(line)
        elif plausible_author_prefix(text) and nearby_bibliographic_evidence(index, lines):
            current = [line]
            boundary_evidence = "initial_author_evidence"
    flush()
    q = _quality(segments)
    q.update({
        "gap_threshold": round(threshold, 3),
        "n_gap_only_starts": gap_only,
        "n_explicit_starts": explicit,
        "n_suppressed_numeric_starts": suppressed_numeric,
    })
    return segments, q


def build_author_year_boundary_repair(zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    """Repair mixed false numeric splits and missed same-margin author-year starts."""
    if zone.style.style not in {"author_year_comma", "author_year_bare", "mixed"}:
        return {"accepted": False, "reason": "author_year_boundary_not_applicable"}
    suspicious = sum(
        bool(re.match(r"^\s*\d{1,4}\s*[.)]\s+", str(r.get("reference_text", ""))))
        for r in base_records
    )
    segments, q = _segment_guarded_gap_zone(zone)
    base_n, new_n = len(base_records), len(segments)
    delta = new_n - base_n
    # This profile is intentionally narrow: it is useful when at least two
    # numeric-looking starts were observed OR multiple strong gap-only starts
    # appear. Candidate size must remain close to the stable result.
    accepted = bool(
        (suspicious >= 2 or q.get("n_gap_only_starts", 0) >= 2)
        and new_n >= 5
        and abs(delta) <= max(20, int(base_n * 0.10) + 2)
        and q["n_giant_segments"] == 0
        and q["evidence_ratio"] >= 0.80
        and 3 <= q["median_words"] <= 150
    )
    return {
        "accepted": accepted,
        "reason": "author_year_boundaries_recomputed_with_numeric_guard_and_gap_evidence" if accepted else "author_year_boundary_repair_failed_gate",
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        "delta": delta,
        "n_suspicious_numeric_starts": suspicious,
        **q,
        "segments": segments,
    }
