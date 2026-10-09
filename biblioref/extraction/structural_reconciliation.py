"""Optional document-structure reconciliation for BiblioRef v0.9.3.

The stable extractor remains authoritative by default.  This module only builds
an explicit comparison candidate when detected reference zones conflict with
strong document structure (e.g. a table-of-contents occurrence or a subsequent
chapter opening inside an overextended zone).
"""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Dict, List, Sequence

from biblioref.adaptive.context import classify_document_pages
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    segment_adaptive_layout_zone,
)


_EXPLICIT_CHAPTER_RX = re.compile(
    r"^(?:chapter|cap[ií]tulo)\s+(?:\d+|[ivxlcdm]+)\b", re.I
)
_NUMERIC_TOP_SECTION_RX = re.compile(
    r"^(?P<num>\d{1,2})(?:\.(?P<sub>\d+(?:\.\d+)*))?[.)]?\s+(?P<title>[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü].*)$"
)


def _strong_section_heading(text: str) -> bool:
    """Return True only when *this line itself* is a strong new-section heading.

    Page-level ``chapter_open`` evidence is intentionally insufficient: embedded
    articles often have a chapter-like running header while ordinary body/reference
    lines occupy the same top region.  Numeric section headings are limited to one
    or two leading digits to avoid treating page-number prefixes such as
    ``110 B. ...`` as document structure.  Reference/bibliography headings are
    never treated as closing boundaries.
    """
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    lowered = value.lower()
    if re.search(r"\b(?:references?|bibliograph(?:y|ies)|referencias?|bibliograf[ií]a)\b", lowered):
        return False
    if _EXPLICIT_CHAPTER_RX.match(value):
        return True
    match = _NUMERIC_TOP_SECTION_RX.match(value)
    if not match:
        return False
    number = int(match.group("num"))
    # Top-level thesis chapters/sections in the observed corpus are small; a
    # very large leading number is much more likely to be a page/OCR artifact.
    return 1 <= number <= 30


def _toc_like_page(lines: Sequence[LayoutLine], page: int) -> bool:
    texts = [line.text.strip() for line in lines if int(line.page) == int(page) and line.text.strip()]
    if len(texts) < 6:
        return False
    trailing_page = sum(bool(re.search(r"(?:\.{2,}|…{2,})\s*\d{1,4}\s*$", text)) for text in texts)
    chapterish = sum(bool(re.match(r"^(?:cap[ií]tulo|chapter|\d+(?:\.\d+)+)\b", text, re.I)) for text in texts)
    return trailing_page >= 6 or (trailing_page >= 4 and chapterish >= 2)


def _top_level_number(text: str) -> int | None:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    m = re.match(r"^(?:chapter|cap[ií]tulo)\s+(\d{1,2})\b", value, re.I)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d{1,2})(?:\.\d+)+\b", value)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d{1,2})[.)]?\s+[A-ZÁÉÍÓÚÑÜ]", value)
    return int(m.group(1)) if m else None


def _first_strong_section_boundary(zone: AdaptiveLayoutZone, full_lines: Sequence[LayoutLine], page_roles: Dict[int, Dict], effective_end_page: int | None = None) -> Dict | None:
    candidates: List[LayoutLine] = []
    for line in full_lines:
        page = int(line.page)
        end_page = int(effective_end_page if effective_end_page is not None else zone.end_page)
        if page <= int(zone.start_page) or page > end_page:
            continue
        text = line.text.strip()
        role = page_roles.get(page, {}).get("role")
        # Both signals are required.  A page classified as chapter_open is only
        # context; the candidate boundary line must itself be a strong heading.
        if role == "chapter_open" and _strong_section_heading(text):
            current_top = _top_level_number(zone.heading.text)
            candidate_top = _top_level_number(text)
            # A repeated chapter running header inside that chapter is not a
            # new structural boundary.  When both sides are numbered, require
            # the natural next top-level section (Adan/Sandhu/Morton).
            if current_top is not None and candidate_top is not None:
                if candidate_top != current_top + 1:
                    continue
            candidates.append(line)
    if not candidates:
        return None
    boundary = min(candidates, key=lambda line: (int(line.page), float(line.y0), float(line.x0)))
    return {
        "page": int(boundary.page),
        "y0": float(boundary.y0),
        "page_height": float(boundary.page_height),
        "text": boundary.text.strip(),
        "top_fraction": round(float(boundary.y0) / max(1.0, float(boundary.page_height)), 4),
    }


def structural_reconciliation_plan(
    layout_zones: Sequence[AdaptiveLayoutZone],
    stable_zones: Sequence[Dict],
    full_lines: Sequence[LayoutLine],
) -> Dict:
    roles = classify_document_pages(full_lines)
    drop_ids: List[int] = []
    trim: Dict[int, Dict] = {}
    evidence: List[Dict] = []

    for zone_id, zone in enumerate(layout_zones, 1):
        start_page = int(zone.start_page)
        role = roles.get(start_page, {}).get("role", "unknown")
        if role == "toc" or _toc_like_page(full_lines, start_page):
            drop_ids.append(zone_id)
            evidence.append({
                "zone_id": zone_id,
                "action": "drop",
                "reason": "reference_heading_inside_table_of_contents",
                "start_page": start_page,
                "heading": zone.heading.text,
            })
            continue
        effective_end_page = None
        if zone_id - 1 < len(stable_zones):
            try:
                effective_end_page = int(stable_zones[zone_id - 1].get("end_page", zone.end_page))
            except (TypeError, ValueError, AttributeError):
                effective_end_page = int(zone.end_page)
        boundary = _first_strong_section_boundary(zone, full_lines, roles, effective_end_page=effective_end_page)
        if boundary:
            # Check that at least some reference-like evidence precedes the new
            # section; otherwise this may simply be a false zone better handled
            # by another rescue.
            before = [
                line for line in zone.lines
                if (int(line.page), float(line.y0)) < (int(boundary["page"]), float(boundary["y0"]))
            ]
            evidence_lines = sum(bool(YEAR_OR_SOURCE_RX.search(line.text)) for line in before)
            if evidence_lines >= 3:
                trim[zone_id] = boundary
                evidence.append({
                    "zone_id": zone_id,
                    "action": "trim",
                    "reason": "strong_new_chapter_inside_detected_reference_zone",
                    "heading": zone.heading.text,
                    "boundary": boundary,
                    "reference_like_lines_before_boundary": evidence_lines,
                })

    return {
        "eligible": bool(drop_ids or trim),
        "drop_zone_ids": drop_ids,
        "trim_zones": trim,
        "evidence": evidence,
        "page_roles": roles,
    }


def build_trimmed_zone(zone: AdaptiveLayoutZone, boundary: Dict) -> tuple[AdaptiveLayoutZone, List[Dict]]:
    boundary_key = (int(boundary["page"]), float(boundary["y0"]))
    kept = [line for line in zone.lines if (int(line.page), float(line.y0)) < boundary_key]
    if not kept:
        return zone, []
    style = diagnose_adaptive_style([line.text for line in kept])
    layout = diagnose_adaptive_layout(kept, style)
    end_page = max(int(line.page) for line in kept)
    candidate = replace(
        zone,
        lines=kept,
        end_page=end_page,
        style=style,
        layout=layout,
        termination_reason="selective_rescue_structural_new_section",
        zone_span_pages=end_page - int(zone.start_page) + 1,
    )
    return candidate, segment_adaptive_layout_zone(candidate)
