# -*- coding: utf-8 -*-
"""BiblioRef v0.3 — layout-aware, auditable reference segmentation.

Version 0.3 keeps the adaptive style, scope and duplicate-reporting logic from
v0.2, but changes the PDF path in four consequential ways:

1. PDF fragments are merged and lines are sorted in visual reading order.
2. Reference boundaries combine text with a zone-specific left-margin model.
3. Footers and small-font footnotes are filtered relative to bibliography font.
4. A stop keyword closes a zone only when the line also looks like a heading.

The module deliberately remains a segmenter.  Full bibliographic field parsing
is outside this version's claims.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
from functools import lru_cache
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Tuple

from biblioref.ingestion.backend_context import pymupdf

from biblioref_v0_2 import (
    ANNOTATION_PROSE_RX,
    BRACKET_KEY_RX,
    NUMERIC_MARKER_RX,
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    StyleProfile,
    _annotate_duplicates,
    _select_scope,
    diagnose_style,
    is_ref_heading,
    norm_text,
)


Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]
YEAR_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
SIN_FECHA_RX = re.compile(r"\b(?:sin\s+fecha|s\.?\s*f\.?)\b", re.I)
DOI_URL_AT_START_RX = re.compile(r"^(?:https?://|www\.|doi\s*:)", re.I)
AUTHORISH_RX = re.compile(r"^[^\W\d_][^\s,;]{0,80}", re.UNICODE)
AUTHOR_INITIAL_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+)*"
    r",\s*(?:[A-ZÁÉÍÓÚÑÜ]\.(?:\s*[-–—]?\s*[A-ZÁÉÍÓÚÑÜ]\.)*|"
    r"[A-ZÁÉÍÓÚÑÜ]\s*[;,&y])",
)
MULTI_AUTHOR_NO_YEAR_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÑÜ][^\n]{0,220},\s*[A-ZÁÉÍÓÚÑÜ]\.\s*;",
)
INSTITUTIONAL_PREFIX_RX = re.compile(
    r"^(?:Ley\b|Decreto\b|Resoluci[oó]n\b|Ministerio\b|Universidad\b|"
    r"Biblioteca\b|Organizaci[oó]n\b|Asociaci[oó]n\b|Instituto\b|"
    r"OMS\b|OPS\b|WHO\b|UNESCO\b|UNICEF\b|CONICET\b|APA\b|"
    r"[A-ZÁÉÍÓÚÑÜ]{2,10}\s*\()",
    re.I,
)


@dataclass(frozen=True)
class LayoutLine:
    page: int
    page_height: float
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    median_font_size: float
    fragment_count: int = 1


@dataclass
class LayoutProfile:
    start_margin: float
    start_margin_tolerance: float
    bibliography_font_size: float
    continuation_margin: Optional[float]
    candidate_support: int
    hanging_indent_detected: bool


@dataclass
class LayoutZone:
    heading: LayoutLine
    lines: List[LayoutLine]
    start_page: int
    end_page: int
    style: StyleProfile
    layout: LayoutProfile
    termination_reason: str
    confidence_score: float
    confidence_label: str
    confidence_reasons: List[str]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _extract_layout_lines_uncached(pdf_path: str, y_tolerance: float) -> tuple[LayoutLine, ...]:
    """Extract visually ordered layout lines from one immutable PDF snapshot."""
    doc = pymupdf.open(pdf_path)
    output: List[LayoutLine] = []
    try:
        for page_number in range(1, doc.page_count + 1):
            page = doc[page_number - 1]
            fragments: List[dict] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = [s for s in line.get("spans", []) if str(s.get("text", "")).strip()]
                    if not spans:
                        continue
                    text = _clean_text(" ".join(str(s.get("text", "")) for s in spans))
                    if not text:
                        continue
                    box = pymupdf.Rect(
                        min(float(s["bbox"][0]) for s in spans),
                        min(float(s["bbox"][1]) for s in spans),
                        max(float(s["bbox"][2]) for s in spans),
                        max(float(s["bbox"][3]) for s in spans),
                    )
                    # 0.6.15: on a page with /Rotate the boxes come in unrotated
                    # space, where the lines read as columns; order them as seen.
                    if page.rotation:
                        box = box * page.rotation_matrix
                    fragments.append({
                        "text": text,
                        "x0": box.x0,
                        "y0": box.y0,
                        "x1": box.x1,
                        "y1": box.y1,
                        "sizes": [float(s.get("size", 0.0)) for s in spans],
                    })

            fragments.sort(key=lambda item: (item["y0"], item["x0"]))
            groups: List[List[dict]] = []
            for fragment in fragments:
                if groups:
                    baseline = statistics.median(x["y0"] for x in groups[-1])
                    if abs(fragment["y0"] - baseline) <= y_tolerance:
                        groups[-1].append(fragment)
                        continue
                groups.append([fragment])

            for group in groups:
                group.sort(key=lambda item: item["x0"])
                text = _clean_text(" ".join(item["text"] for item in group))
                sizes = [size for item in group for size in item["sizes"]]
                output.append(LayoutLine(
                    page=page_number,
                    page_height=float(page.rect.height),
                    text=text,
                    x0=min(item["x0"] for item in group),
                    y0=min(item["y0"] for item in group),
                    x1=max(item["x1"] for item in group),
                    y1=max(item["y1"] for item in group),
                    median_font_size=statistics.median(sizes),
                    fragment_count=len(group),
                ))
    finally:
        doc.close()
    return tuple(output)


@lru_cache(maxsize=2)
def _extract_layout_lines_cached(
    resolved_path: str,
    y_tolerance: float,
    size_bytes: int,
    mtime_ns: int,
) -> tuple[LayoutLine, ...]:
    # ``size_bytes`` and ``mtime_ns`` deliberately participate in the cache key
    # so replacing a PDF at the same path invalidates the snapshot.
    del size_bytes, mtime_ns
    return _extract_layout_lines_uncached(resolved_path, y_tolerance)


def extract_layout_lines(pdf_path: str | Path, y_tolerance: float = 0.9) -> List[LayoutLine]:
    """Return visually ordered lines, reusing the current PDF layout snapshot.

    BiblioRef's modular pipeline may request the same layout several times while
    stable, repair and shadow layers inspect one document.  Parsing every page
    again with ``page.get_text('dict')`` is pure duplicate I/O/CPU work.  The
    cache is intentionally tiny (two PDFs), returns a fresh list of immutable
    ``LayoutLine`` objects, and is invalidated by file size/mtime.
    """
    path = Path(pdf_path).expanduser().resolve()
    stat = path.stat()
    cached = _extract_layout_lines_cached(
        str(path),
        float(y_tolerance),
        int(stat.st_size),
        int(stat.st_mtime_ns),
    )
    return list(cached)


def clear_layout_line_cache() -> None:
    """Release cached PDF layout snapshots (mainly useful for long-lived UIs)."""
    _extract_layout_lines_cached.cache_clear()


#: 0.6.15: folios printed as «[303]», «- 24 -» or «-105-» are still folios.
#: Parentheses stay out: «(12)» alone can be a numbered-list marker.
_FOLIO_RX = re.compile(
    r"(?:\d+|[ivxlcdm]+)|\[\s?\d+\s?\]|[-–—]\s?\d+\s?[-–—]",
    flags=re.I,
)


def _is_footer(line: LayoutLine) -> bool:
    return (
        (line.y0 >= 0.91 * line.page_height or line.y0 <= 0.08 * line.page_height)
        and bool(_FOLIO_RX.fullmatch(line.text.strip()))
    )


#: v0.9.5 - vertical band where a chapter-titled bibliographic heading may open a
#: zone.  Above it sits the running header, which repeats the chapter title on
#: every page; below it sit table-of-contents entries and list items, which name
#: the chapter without starting it.  A heading that opens a section is neither.
CHAPTER_HEADING_BAND = (0.08, 0.80)


def _is_reference_heading(line: LayoutLine) -> bool:
    if len(line.text) > 150:
        return False
    # v0.9.5: "Chapter 7: References" is simultaneously a legitimate chapter-titled
    # bibliographic heading, the running header repeated on every page of that
    # chapter, and the table-of-contents entry that points at it.  The three are
    # the same string, so only geometry separates them, and getting it wrong opens
    # either one spurious zone per page or a zone that starts in the TOC.
    # Every other bibliographic form is unaffected by this band.
    page_height = float(getattr(line, "page_height", 0) or 0)
    if page_height > 0:
        rel = float(line.y0) / page_height
        allow_chapter_prefix = CHAPTER_HEADING_BAND[0] <= rel <= CHAPTER_HEADING_BAND[1]
    else:
        allow_chapter_prefix = True
    if is_ref_heading(line.text, allow_chapter_prefix=allow_chapter_prefix):
        return True
    return _is_heading_with_trailing_folio(line, allow_chapter_prefix)


#: v0.6.9: el folio impreso cae en la misma banda vertical que el titulo de la
#: seccion y ``extract_layout_lines`` los fusiona en una sola linea.  El test de
#: vocabulario esta anclado con ``re.fullmatch``, asi que "Referencias
#: bibliograficas 151" no matchea y la tesis entera queda sin zona.  Sacar el
#: numeral es seguro solo con dos guardarrailes, porque la misma cadena esta en
#: el indice: puntos conductores, y un numeral que apunta hacia adelante (en el
#: indice el numero es la pagina destino; en un encabezado es el folio de la
#: pagina que se esta leyendo).
_LEADER_DOTS_RX = re.compile(r"(?:\.\s?){4,}|…{2,}")
_TRAILING_FOLIO_RX = re.compile(r"[\s.…]*\b(\d{1,4})\s*\.?\s*$")


def _is_heading_with_trailing_folio(line: LayoutLine, allow_chapter_prefix: bool) -> bool:
    raw = str(line.text).strip()
    if _LEADER_DOTS_RX.search(raw):
        return False
    match = _TRAILING_FOLIO_RX.search(raw)
    if not match:
        return False
    if int(match.group(1)) > int(getattr(line, "page", 0) or 0):
        return False
    without_folio = _TRAILING_FOLIO_RX.sub("", raw).strip(" .-:")
    if not without_folio:
        return False
    return is_ref_heading(without_folio, allow_chapter_prefix=allow_chapter_prefix)


def _vertical_context(index: int, lines: List[LayoutLine]) -> Tuple[float, float]:
    current = lines[index]
    before = math.inf
    after = math.inf
    if index > 0 and lines[index - 1].page == current.page:
        before = current.y0 - lines[index - 1].y1
    if index + 1 < len(lines) and lines[index + 1].page == current.page:
        after = lines[index + 1].y0 - current.y1
    return before, after


def _is_structural_stop(index: int, lines: List[LayoutLine]) -> bool:
    """Require layout evidence before treating a stop keyword as a heading."""
    line = lines[index]
    text = line.text.strip()
    if len(text) > 120:
        return False
    lower = norm_text(text)
    explicit = bool(re.match(
        r"^(?:(?:\d+(?:\.\d+)*|[ivxlcdm]+)[\.\-:]?\s+)?"
        r"(?:capitulo|anexos?|apendices?|appendix|indice|conclusiones?|agradecimientos|"
        r"curriculum|"
        r"(?:primera|segunda|tercera|cuarta|quinta|sexta)\s+parte)\b",
        lower,
        flags=re.I,
    ))
    # Broader annex labels are safe only when they carry an explicit section
    # number.  Unnumbered words such as "Observaciones" can be publication
    # titles inside a bibliography.
    extended_numbered = bool(re.match(
        r"^(?:\d+(?:\.\d+)*|[ivxlcdm]+)[\.\-:]?\s+"
        r"(?:observaciones|entrevistas|matri(?:z|ces)|instrumentos?)\b",
        lower,
        flags=re.I,
    ))
    explicit = explicit or extended_numbered
    uppercase = sum(c.isupper() for c in text) >= max(4, sum(c.isalpha() for c in text) * 0.70)
    centered = line.x0 >= 150
    gap_before, gap_after = _vertical_context(index, lines)
    isolated = gap_before >= 12 or gap_after >= 12
    # A prose continuation such as "parte]. El Sigma..." fails these tests.
    return explicit and (
        centered or uppercase or isolated
        or (extended_numbered and line.median_font_size >= 10.5)
    )


def _textual_strong_candidate(text: str) -> bool:
    text = text.strip()
    if (
        not text
        or not text[:1].isupper()
        or DOI_URL_AT_START_RX.match(text)
        or not AUTHORISH_RX.match(text)
    ):
        return False
    if NUMERIC_MARKER_RX.match(text) or BRACKET_KEY_RX.match(text):
        return True
    return bool(YEAR_RX.search(text[:280]) or SIN_FECHA_RX.search(text[:280]))


def _mode_cluster(values: List[float], width: float = 7.0) -> Tuple[float, int]:
    if not values:
        return 0.0, 0
    best_members: List[float] = []
    for center in values:
        members = [value for value in values if abs(value - center) <= width]
        if len(members) > len(best_members):
            best_members = members
    return statistics.median(best_members), len(best_members)


def diagnose_layout(lines: Iterable[LayoutLine]) -> LayoutProfile:
    ls = [line for line in lines if not _is_footer(line)]
    strong = [line for line in ls if _textual_strong_candidate(line.text)]
    candidate_x = [line.x0 for line in strong]
    start_margin, support = _mode_cluster(candidate_x)
    if support < 2:
        # Lower x values are a safer fallback than the median because hanging
        # continuations usually lie to the right of starts.
        all_x = sorted(line.x0 for line in ls if line.text)
        start_margin = all_x[max(0, int(len(all_x) * 0.15) - 1)] if all_x else 0.0

    font_candidates = [
        line.median_font_size for line in strong
        if abs(line.x0 - start_margin) <= 12 and line.median_font_size > 0
    ]
    if not font_candidates:
        font_candidates = [line.median_font_size for line in ls if line.median_font_size > 0]
    bibliography_font = statistics.median(font_candidates) if font_candidates else 0.0

    continuation_x = [
        line.x0 for line in ls
        if start_margin + 18 <= line.x0 <= start_margin + 80
    ]
    continuation_margin, continuation_support = _mode_cluster(continuation_x)
    hanging = continuation_support >= 3 and continuation_margin >= start_margin + 18
    return LayoutProfile(
        start_margin=round(start_margin, 2),
        start_margin_tolerance=12.0,
        bibliography_font_size=round(bibliography_font, 2),
        continuation_margin=round(continuation_margin, 2) if hanging else None,
        candidate_support=support,
        hanging_indent_detected=hanging,
    )


def _is_small_font_noise(line: LayoutLine, layout: LayoutProfile) -> bool:
    if not layout.bibliography_font_size:
        return False
    return line.median_font_size < layout.bibliography_font_size - 0.8


def is_layout_reference_start(
    line: LayoutLine,
    style: StyleProfile,
    layout: LayoutProfile,
) -> Tuple[bool, str]:
    text = line.text.strip()
    if not text or _is_footer(line) or _is_small_font_noise(line, layout):
        return False, ""
    if _is_reference_heading(line) or DOI_URL_AT_START_RX.match(text):
        return False, ""
    at_margin = abs(line.x0 - layout.start_margin) <= layout.start_margin_tolerance

    if style.style == "numeric" and NUMERIC_MARKER_RX.match(text):
        return (at_margin, "numeric_marker+start_margin" if at_margin else "")
    if style.style == "bracket_key" and BRACKET_KEY_RX.match(text):
        return (at_margin, "bracket_key+start_margin" if at_margin else "")
    if not at_margin or not AUTHORISH_RX.match(text):
        return False, ""

    if YEAR_RX.search(text[:280]) or SIN_FECHA_RX.search(text[:280]):
        return True, "author_or_institution+date+start_margin"
    # Boundary detection must not require bibliographic completeness.  These
    # patterns cover yearless laws, conventional author-initial starts whose
    # date wraps to the following line, and institutional entries.
    if INSTITUTIONAL_PREFIX_RX.match(text):
        return True, "institution+start_margin"
    if AUTHOR_INITIAL_RX.match(text) or MULTI_AUTHOR_NO_YEAR_RX.match(text):
        return True, "author_initial+start_margin"
    return False, ""


def _provisional_boundaries(lines: List[LayoutLine], style: StyleProfile, layout: LayoutProfile) -> List[int]:
    return [
        index for index, line in enumerate(lines)
        if is_layout_reference_start(line, style, layout)[0]
    ]


def _trim_by_density(
    lines: List[LayoutLine],
    style: StyleProfile,
    layout: LayoutProfile,
) -> Tuple[List[LayoutLine], Optional[int]]:
    """Trim after two consecutive pages without starts once a zone has begun."""
    by_page: Dict[int, List[LayoutLine]] = defaultdict(list)
    for line in lines:
        by_page[line.page].append(line)
    seen = 0
    zero_pages: List[int] = []
    for page in sorted(by_page):
        starts = sum(is_layout_reference_start(line, style, layout)[0] for line in by_page[page])
        if starts:
            seen += starts
            zero_pages = []
        elif seen >= 3:
            zero_pages.append(page)
            if len(zero_pages) >= 2:
                cut_page = zero_pages[0]
                return [line for line in lines if line.page < cut_page], cut_page
    return lines, None


def detect_layout_zones(lines: List[LayoutLine], max_chapter_pages: int = 25) -> List[LayoutZone]:
    headings = [index for index, line in enumerate(lines) if _is_reference_heading(line)]
    zones: List[LayoutZone] = []
    for heading_position, heading_index in enumerate(headings):
        heading = lines[heading_index]
        next_heading_index = headings[heading_position + 1] if heading_position + 1 < len(headings) else len(lines)
        hard_limit_page = heading.page + max_chapter_pages
        stop_index = next_heading_index
        termination = "next_reference_heading" if next_heading_index < len(lines) else "end_of_document"
        for index in range(heading_index + 1, next_heading_index):
            line = lines[index]
            if line.page > hard_limit_page:
                stop_index = index
                termination = "max_chapter_pages"
                break
            if _is_structural_stop(index, lines):
                stop_index = index
                termination = "layout_confirmed_stop_heading"
                break

        body = [line for line in lines[heading_index + 1:stop_index] if not _is_footer(line)]
        if not body:
            continue
        # Diagnose text and layout together, then remove relative small-font noise.
        style = diagnose_style(line.text for line in body[:250])
        layout = diagnose_layout(body)
        body = [line for line in body if not _is_small_font_noise(line, layout)]
        style = diagnose_style(line.text for line in body)
        layout = diagnose_layout(body)

        if termination in {"next_reference_heading", "max_chapter_pages", "end_of_document"}:
            trimmed, cut_page = _trim_by_density(body, style, layout)
            if cut_page is not None:
                body = trimmed
                termination = "layout_reference_density_drop"
                style = diagnose_style(line.text for line in body)
                layout = diagnose_layout(body)
        if not body:
            continue

        n_boundaries = len(_provisional_boundaries(body, style, layout))
        reasons = [
            "explicit_reference_heading",
            "visual_reading_order",
            f"style_{style.style}",
            f"boundary_support_{n_boundaries}",
            f"start_margin_{layout.start_margin}",
            f"bibliography_font_{layout.bibliography_font_size}",
            f"terminated_by_{termination}",
        ]
        if layout.hanging_indent_detected:
            reasons.append("hanging_indent_detected")
        confidence = 0.48
        confidence += 0.16 if n_boundaries >= 5 else 0.08 if n_boundaries >= 2 else 0.0
        confidence += 0.12 if layout.candidate_support >= 5 else 0.06 if layout.candidate_support >= 2 else 0.0
        confidence += 0.10 if layout.hanging_indent_detected else 0.04
        confidence += 0.10 if termination in {"layout_confirmed_stop_heading", "next_reference_heading"} else 0.06
        confidence = round(min(confidence, 1.0), 3)
        label = "high" if confidence >= 0.80 else "medium" if confidence >= 0.60 else "low"
        zones.append(LayoutZone(
            heading=heading,
            lines=body,
            start_page=heading.page,
            end_page=max(line.page for line in body),
            style=style,
            layout=layout,
            termination_reason=termination,
            confidence_score=confidence,
            confidence_label=label,
            confidence_reasons=reasons,
        ))
    return zones


def _looks_complete(lines: List[LayoutLine]) -> bool:
    text = " ".join(line.text for line in lines)
    return bool(YEAR_RX.search(text) or SIN_FECHA_RX.search(text) or re.search(r"https?://|www\.", text, re.I))


def segment_layout_zone(zone: LayoutZone) -> List[dict]:
    segments: List[dict] = []
    current: List[LayoutLine] = []
    annotation: List[LayoutLine] = []
    boundary_evidence = ""

    def flush() -> None:
        nonlocal current, annotation, boundary_evidence
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
            "annotation_text": _clean_text(" ".join(line.text for line in annotation)),
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(current[0].x0, 2),
            "boundary_evidence": boundary_evidence,
            "audit_flags": ";".join(flags),
        })
        current = []
        annotation = []
        boundary_evidence = ""

    for line in zone.lines:
        start, evidence = is_layout_reference_start(line, zone.style, zone.layout)
        if start:
            flush()
            current = [line]
            boundary_evidence = evidence
            continue
        if not current:
            continue
        if zone.style.style == "bracket_key" and _looks_complete(current):
            if ANNOTATION_PROSE_RX.match(line.text) and not YEAR_RX.search(line.text[:80]):
                annotation.append(line)
                continue
            if annotation:
                annotation.append(line)
                continue
        current.append(line)
    flush()
    return segments


def process_pdf(pdf_path: str | Path, scope: Scope = "all_reference_sections") -> Dict:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    lines = extract_layout_lines(pdf_path)
    zones = detect_layout_zones(lines)
    records: List[dict] = []
    zone_summaries: List[dict] = []
    for zone_id, zone in enumerate(zones, 1):
        segments = segment_layout_zone(zone)
        for ref_in_zone, segment in enumerate(segments, 1):
            record = dict(segment)
            record.update({
                "zone_id": zone_id,
                "ref_in_zone": ref_in_zone,
                "zone_heading": zone.heading.text,
                "zone_start_page": zone.start_page,
                "zone_end_page": zone.end_page,
                "zone_confidence_score": zone.confidence_score,
                "zone_confidence_label": zone.confidence_label,
                "zone_confidence_kind": "layout_structural_evidence",
                "zone_termination_reason": zone.termination_reason,
            })
            records.append(record)
        zone_summaries.append({
            "zone_id": zone_id,
            "heading": zone.heading.text,
            "start_page": zone.start_page,
            "end_page": zone.end_page,
            "style": zone.style.style,
            "n_segments": len(segments),
            "termination_reason": zone.termination_reason,
            "confidence_score": zone.confidence_score,
            "confidence_label": zone.confidence_label,
            "confidence_kind": "layout_structural_evidence",
            "confidence_reasons": zone.confidence_reasons,
            **asdict(zone.layout),
            **{f"style_{key}": value for key, value in asdict(zone.style).items()},
        })

    occurrences, duplicate_groups = _annotate_duplicates(records)
    selected = _select_scope(occurrences, scope, final_zone_id=len(zones) if zones else None)
    return {
        "software_version": "0.3",
        "pdf": str(pdf_path),
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_pdf_layout_lines": len(lines),
        "n_zones": len(zones),
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(g["occurrence_count"] for g in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(g["occurrence_count"] - 1 for g in duplicate_groups),
        "n_records_selected": len(selected),
        "zones": zone_summaries,
        "duplicate_groups": duplicate_groups,
        "records": selected,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="BiblioRef v0.3 layout-aware reference segmenter")
    parser.add_argument("pdf", help="Input PDF")
    parser.add_argument("--json", dest="json_out", help="Output JSON")
    parser.add_argument("--csv", dest="csv_out", help="Output CSV")
    parser.add_argument(
        "--zones-csv", dest="zones_out", help="Optional bibliography-zone diagnostic CSV"
    )
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
