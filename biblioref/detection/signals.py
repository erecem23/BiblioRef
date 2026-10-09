"""Evidence signals used to repair under-segmented bibliography zones."""

import re
from collections import defaultdict
from typing import Dict, Sequence, Tuple

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import (
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    DOI_URL_AT_START_RX,
    NUMERIC_MARKER_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    LayoutLine,
    _is_footer,
    _is_reference_heading,
    _mode_cluster,
    AdaptiveLayoutZone,
    diagnose_adaptive_layout,
)


REPEATED_MARK_RX = re.compile(
    r"^(?:_{3,}|[-–—]{3,}|[\uF000-\uF8FF]{3,})\s*(?:,|\.)?\s*"
)
UNDATED_BARE_RX = re.compile(r"\b(?:forthcoming|in\s+press|en\s+prensa)\b", re.I)


def is_spaced_smallcaps_author(text: str) -> bool:
    """Recognize PDF-extracted small caps such as ``A LMEIDA``."""
    prefix = text.split(",", 1)[0].strip()
    if "," not in text or not prefix or len(prefix) > 100:
        return False
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ]+", prefix)
    letters = [char for token in tokens for char in token if char.isalpha()]
    if len(letters) < 5 or not any(len(token) == 1 for token in tokens):
        return False
    return sum(char.isupper() for char in letters) / len(letters) >= 0.82


def plausible_author_prefix(text: str) -> bool:
    """Reject wrapped prose that merely contains a comma and a later year."""
    if "," not in text:
        return False
    prefix = text.split(",", 1)[0].strip(" .;:'\"‘’“”")
    if not prefix or len(prefix) > 80 or not prefix[:1].isupper() or re.search(r"\d", prefix):
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+", prefix)
    return bool(words and len(words) <= 8)


def bare_author_year(text: str) -> bool:
    start = text.strip()[:300]
    return bool(
        plausible_author_prefix(start)
        and AUTHOR_COMMA_RX.match(start)
        and (YEAR_RX.search(start) or SIN_FECHA_RX.search(start) or UNDATED_BARE_RX.search(start))
        and not DOI_URL_AT_START_RX.match(start)
    )


def parenthetical_author_year(text: str) -> bool:
    start = text.strip()[:300]
    return bool(
        plausible_author_prefix(start)
        and AUTHOR_COMMA_RX.match(start)
        and re.search(
            r"\(\s*(?:(?:18|19|20)\d{2}[a-z]?|s\.?\s*(?:/\s*)?f\.?|n\.?\s*d\.?)",
            start,
            re.I,
        )
    )


#: 0.6.18: «Convergencia (1998)», «Etchvers Martín (2010)», «González. O.
#: (2016)», «Eribon, Didier et al. (2004)»: a short name run and then the year.
NAME_THEN_YEAR_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÑÜ][\wáéíóúñü'’\-]+\.?"
    r"(?:\s+(?:[A-ZÁÉÍÓÚÑÜ][\wáéíóúñü'’\-]*\.?|de|del|la|y|e|van|von|da|do|dos|et\s+al\.?|&)){0,5}"
    r"\s*\(\s*(?:(?:18|19|20)\d{2}[a-z]?|s\.?\s*(?:/\s*)?f\.?|n\.?\s*d\.?)\s*[)/\-–,]"
)
_CLOSED_LINE_RX = re.compile(r"[.)\]”\"'’:]\s*$")


def name_then_year_start(index: int, lines: Sequence[LayoutLine], margin: float) -> bool:
    """A commaless author at the start margin, below a line that ended a reference.

    The line above must be a hanging continuation (indented past the margin) or
    close with final punctuation; «…Estudio de caso en / Buenos Aires (2001) y»
    continues an open sentence and does not qualify.
    """
    text = lines[index].text.strip()
    if not NAME_THEN_YEAR_RX.match(text) or index == 0:
        return False
    previous = lines[index - 1]
    hanging = previous.x0 >= margin + 18
    return hanging or bool(_CLOSED_LINE_RX.search(previous.text.strip()))


def nearby_bibliographic_evidence(index: int, lines: Sequence[LayoutLine]) -> bool:
    page = lines[index].page
    text = " ".join(
        candidate.text
        for candidate in lines[index:index + 7]
        if candidate.page <= page + 1
    )
    return bool(YEAR_OR_SOURCE_RX.search(text) or SIN_FECHA_RX.search(text))


def raw_margin_candidate(index: int, lines: Sequence[LayoutLine]) -> bool:
    line = lines[index]
    text = line.text.strip()
    if not text or _is_footer(line) or _is_reference_heading(line):
        return False
    if NUMERIC_MARKER_RX.match(text) or BRACKET_KEY_RX.match(text):
        return True
    if parenthetical_author_year(text) or bare_author_year(text):
        return True
    if is_spaced_smallcaps_author(text) or REPEATED_MARK_RX.match(text):
        return nearby_bibliographic_evidence(index, lines)
    return False


def page_start_margins(zone: AdaptiveLayoutZone) -> Tuple[Dict[int, float], float]:
    by_page: Dict[int, list[float]] = defaultdict(list)
    all_x: list[float] = []
    for index, line in enumerate(zone.lines):
        if raw_margin_candidate(index, zone.lines):
            by_page[line.page].append(line.x0)
            all_x.append(line.x0)
    global_margin, _ = _mode_cluster(all_x)
    if not all_x:
        global_margin = diagnose_adaptive_layout(zone.lines, zone.style).start_margin
    margins = PageMargins()
    for page, values in by_page.items():
        margin, support = _mode_cluster(values)
        margins[page] = margin if support else global_margin
    for page in sorted({line.page for line in zone.lines}):
        starts = local_hanging_starts([line for line in zone.lines if line.page == page],
                                      margins.get(page, global_margin))
        if starts:
            margins.local_starts.update(id(line) for line in starts)
            margins.local_pages.add(page)
    return margins, global_margin


class PageMargins(dict):
    """Start margin per page, plus the pages read by local geometry (0.6.20)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_pages: set = set()
        self.local_starts: set = set()


#: «· (1896):», «- (1905)»: a «———» repeated-author mark misread by OCR, then the date.
_DATE_AFTER_MARK_RX = re.compile(r"^[·•\-–—=:]{1,3}\s*\(\s*\d{4}")
_LINE_OPENING_RX = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ(·•\-–—=:]")


def local_hanging_starts(page_lines: Sequence[LayoutLine], margin: float) -> list:
    """Starts of a hanging-indent page whose margin moves (0.6.20, T0145).

    A scanned book shifts its margin from page to page and the page itself may be
    tilted (starts drifting from x=98 to x=77), and when the year closes the entry
    the dated lines that fix ``margin`` are continuations. Here a line starts an
    entry when no nearby line sits further left and an indented continuation sits
    nearby. Used only when that geometry disagrees with ``margin`` (shifted by an
    indent, or starts spread over more than the margin tolerance) and the lines it
    finds open like entries: «Apellido, N.» or a misread repeated-author mark.
    """
    body = [
        line for line in page_lines
        if len(line.text.strip()) >= 12 and _LINE_OPENING_RX.match(line.text.strip())
        and not _is_footer(line) and not _is_reference_heading(line)
    ]
    if len(body) < 8:
        return []
    starts = []
    for line in body:
        near = [other for other in body if other is not line and abs(other.y0 - line.y0) <= 80]
        if any(other.x0 <= line.x0 - 14 for other in near):
            continue
        if any(line.x0 + 14 <= other.x0 <= line.x0 + 60 for other in near):
            starts.append(line)
    if len(starts) < 4:
        return []
    entry_like = sum(
        1 for line in starts
        if (AUTHOR_COMMA_RX.match(line.text.strip()) and plausible_author_prefix(line.text.strip()[:300]))
        or _DATE_AFTER_MARK_RX.match(line.text.strip())
    )
    if entry_like < 3 or entry_like * 5 < len(starts) * 3:
        return []
    xs = sorted(line.x0 for line in starts)
    shifted = margin - xs[len(xs) // 2] >= 14
    spread = xs[-1] - xs[0] > 12
    return starts if shifted or spread else []


def enhanced_start(
    index: int,
    zone: AdaptiveLayoutZone,
    page_margins: Dict[int, float],
    global_margin: float,
) -> Tuple[bool, str]:
    line = zone.lines[index]
    text = line.text.strip()
    if not text or _is_footer(line) or _is_reference_heading(line):
        return False, ""
    margin = page_margins.get(line.page, global_margin)
    at_margin = abs(line.x0 - margin) <= 12.0
    if line.page in getattr(page_margins, "local_pages", ()):
        # 0.6.20: on a shifted or tilted page the local geometry decides.
        if id(line) in page_margins.local_starts:
            return True, "hanging_indent+local_margin"
        if not NUMERIC_MARKER_RX.match(text):
            return False, ""

    # v0.6.11: un marcador numérico vale como borde explícito aunque la primera
    # página de la zona use otro margen, pero sólo en una bibliografía numerada.
    # En una zona autor-año, "60. https://doi.org/…" es el número de página de la
    # línea de continuación, y promoverlo parte en dos la referencia de arriba.
    if NUMERIC_MARKER_RX.match(text):
        if at_margin or str(zone.style.style) == "numeric":
            return True, "numeric_marker"
    if BRACKET_KEY_RX.match(text) and at_margin:
        return True, "bracket_key+page_margin"
    if not at_margin:
        return False, ""
    if parenthetical_author_year(text):
        return True, "author+parenthetical_date+page_margin"
    if bare_author_year(text):
        return True, "author+bare_date+page_margin"
    if name_then_year_start(index, zone.lines, margin):
        return True, "commaless_author+parenthetical_date+page_margin"
    if is_spaced_smallcaps_author(text) and nearby_bibliographic_evidence(index, zone.lines):
        return True, "spaced_smallcaps_author+nearby_date+page_margin"
    if REPEATED_MARK_RX.match(text) and nearby_bibliographic_evidence(index, zone.lines):
        return True, "repeated_author_mark+nearby_date+page_margin"
    return False, ""


# Compatibility aliases ease comparison with the v0.6.1 implementation.
_is_spaced_smallcaps_author = is_spaced_smallcaps_author
_plausible_author_prefix = plausible_author_prefix
_bare_author_year = bare_author_year
_parenthetical_author_year = parenthetical_author_year
_nearby_bibliographic_evidence = nearby_bibliographic_evidence
_raw_margin_candidate = raw_margin_candidate
_page_start_margins = page_start_margins
_enhanced_start = enhanced_start
