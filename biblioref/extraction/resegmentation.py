"""Evidence-gated second segmentation from the validated v0.6.1 algorithm."""

import re
import statistics
from typing import Dict, List, Tuple

from biblioref.core.patterns import AUTHOR_LIST_TAIL_RX, YEAR_OR_SOURCE_RX
from biblioref.detection.signals import enhanced_start, page_start_margins
from biblioref.legacy.engine import (
    INTERNAL_BIBLIOGRAPHY_HEADING_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    AdaptiveLayoutZone,
    LayoutLine,
    _clean_text,
    _is_reference_heading,
)


DATE_ONLY_ENTRY_RX = re.compile(
    r"^\(\s*(?:18|19|20)\d{2}[a-z]?(?:\s*\[[^\]]+\])?\s*\)", re.I
)


def segment_enhanced_zone(zone: AdaptiveLayoutZone) -> Tuple[List[Dict], Dict]:
    page_margins, global_margin = page_start_margins(zone)
    segments: List[Dict] = []
    current: List[LayoutLine] = []
    boundary_evidence = ""
    inherited_date_starts = 0
    explicit_starts = 0

    def flush() -> None:
        nonlocal current, boundary_evidence
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
            "annotation_text": "",
            "style": zone.style.style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(current[0].x0, 2),
            "boundary_evidence": boundary_evidence,
            "audit_flags": ";".join(flags),
        })
        current = []
        boundary_evidence = ""

    for index, line in enumerate(zone.lines):
        text = line.text.strip()
        if INTERNAL_BIBLIOGRAPHY_HEADING_RX.fullmatch(text) or _is_reference_heading(line):
            continue

        start, evidence = enhanced_start(index, zone, page_margins, global_margin)
        if not start and current and DATE_ONLY_ENTRY_RX.match(text):
            current_text = " ".join(item.text for item in current)
            page_margin = page_margins.get(line.page, global_margin)
            inherited_indent = line.x0 >= page_margin + 18
            # v0.6.11: "(2017). Effect of…" hereda el autor de arriba sólo si el
            # de arriba ya es una referencia. Cuando la lista de autores ocupa
            # toda la primera línea y el año se va a la siguiente, el de arriba
            # termina en "& Apellido, X." y esto es su continuación, no un
            # registro nuevo.
            if (
                inherited_indent
                and (YEAR_RX.search(current_text) or SIN_FECHA_RX.search(current_text))
                and not AUTHOR_LIST_TAIL_RX.search(current_text.strip())
            ):
                start = True
                evidence = "inherited_author+date_only_entry"
                inherited_date_starts += 1

        if start:
            explicit_starts += 1
            flush()
            current = [line]
            boundary_evidence = evidence
        elif current:
            current.append(line)
    flush()

    word_counts = [len(item["reference_text"].split()) for item in segments]
    evidence_count = sum(bool(YEAR_OR_SOURCE_RX.search(item["reference_text"])) for item in segments)
    diagnostics = {
        "n_enhanced_segments": len(segments),
        "n_explicit_starts": explicit_starts,
        "n_inherited_date_starts": inherited_date_starts,
        "n_giant_segments": sum(value >= 500 for value in word_counts),
        "median_words": round(float(statistics.median(word_counts)), 2) if word_counts else 0.0,
        "evidence_ratio": round(evidence_count / max(len(segments), 1), 3),
        "page_start_margins": {
            str(key): round(value, 2) for key, value in sorted(page_margins.items())
        },
    }
    return segments, diagnostics


_segment_enhanced_zone = segment_enhanced_zone
