# -*- coding: utf-8 -*-
"""BiblioRef v0.4.5 — adaptive bibliography-zone closure and segmentation.

Version 0.4 extends the layout-aware v0.3 engine with three changes motivated
by full-thesis stress tests:

1. A bibliography zone is no longer closed after a fixed number of pages.
2. Start, end and completeness confidence are reported separately.
3. Weak author/institution boundaries need local layout support, reducing the
   chance that wrapped source or publisher lines become new references.

The program remains an auditable reference segmenter. It does not claim full
bibliographic field parsing.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from biblioref_v0_2 import (
    ANNOTATION_PROSE_RX,
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    BULLET_RX,
    NUMERIC_MARKER_RX,
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    StyleProfile,
    _annotate_duplicates,
    _numeric_marker_value,
    _select_scope,
    _strip_heading_prefix,
    diagnose_style,
)
from biblioref_paragraph_flow import profile_paragraph_flow, is_paragraph_start
from biblioref_page_decorations import filter_repeated_page_decorations

from biblioref_v0_3 import (
    AUTHORISH_RX,
    AUTHOR_INITIAL_RX,
    DOI_URL_AT_START_RX,
    INSTITUTIONAL_PREFIX_RX,
    MULTI_AUTHOR_NO_YEAR_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    LayoutLine,
    LayoutProfile,
    _clean_text,
    _is_footer,
    _is_reference_heading,
    _is_small_font_noise,
    _is_structural_stop,
    _mode_cluster,
    diagnose_layout,
    extract_layout_lines,
)


Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]

# Author-year references normally place the bibliographic date at the start of
# a parenthesis. This deliberately rejects continuation fragments such as
# "Papers, No. 2013/4" and "Argentina 1974-1975".
PAREN_DATE_RX = re.compile(
    r"\(\s*(?:"
    r"(?:\d{1,2}\s*[-/]\s*\d{1,2}\s*[-/]\s*)|"
    r"(?:\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+\s*(?:de|,)\s*)|"
    r"(?:[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+\s*(?:de|,)\s*)|"
    r"(?:/\s*)"
    r")?(?:18|19|20)\d{2}",
    re.I,
)
PAREN_UNDATED_RX = re.compile(
    r"\(\s*(?:s\.?\s*(?:/\s*)?f\.?|sin\s+fecha|en\s+prensa|forthcoming)\s*\)",
    re.I,
)
LEGAL_START_RX = re.compile(r"^(?:Ley|Decreto|Resoluci[oó]n|Ordenanza)\b", re.I)
#: Partícula nobiliaria en minúscula al frente del apellido: "van Dijk, J.",
#: "de Asúa, M.", "del Valle, M. V.".  Se exige que el apellido que sigue sí
#: empiece con mayúscula, para no confundirla con prosa que arranca en "de la".
SURNAME_PARTICLE_RX = re.compile(
    r"^(?:de\s+la|de\s+los|van\s+der|van\s+den|de|del|da|das|do|dos|van|von|di|della|le|ten|ter)\s+"
    r"[A-ZÁÉÍÓÚÑÜ]"
)
WEAK_EVIDENCE = {"institution+start_margin", "author_initial+start_margin"}
REPEATED_AUTHOR_MARK_RX = re.compile(r"^(?:_{3,}|[-–—]{3,})\s*")
NAMED_WEB_SOURCE_RX = re.compile(
    r"^(?:[^:]{2,100}:\s*(?:(?i:https?)://|www\.)\S+|"
    r"[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+){0,4}:\s*)$"
)
#: 0.6.15: «Recuperado de: http://…» ends the previous reference; its label is
#: an access phrase, not the name of a web source.
ACCESS_LABEL_RX = re.compile(
    r"(?:^|\W)(?:recuperad[oa]s?(?:\s+(?:de|desde|en))?|disponible(?:\s+en)?|retrieved(?:\s+from)?|"
    r"available(?:\s+(?:at|from|on))?|consultad[oa](?:\s+en)?|obtenid[oa](?:\s+de)?|"
    r"accesible\s+en|en\s+l[ií]nea|online|url|link|enlace|acceso|dispon[ií]vel\s+em)\s*$",
    re.I,
)
#: A surname is followed by an initial or a given name, never by a number.
AUTHOR_THEN_NAME_RX = re.compile(r"^[^\W\d_][^,\n]{0,100}?,\s*[^\W\d_]", re.UNICODE)


#: 0.6.15: a line that opens with the access phrase is the tail of a reference.
ACCESS_START_RX = re.compile(
    r"^(?:recuperad[oa]s?|disponible|retrieved|available|consultad[oa]|obtenid[oa]|"
    r"dispon[ií]vel|accesible)\b",
    re.I,
)


def _is_named_web_source(text: str) -> bool:
    if not NAMED_WEB_SOURCE_RX.match(text):
        return False
    label = text.split(":", 1)[0].strip()
    # A source is named: "Alberto Goldenstein: http://…", never "de: http://…".
    return label[:1].isupper() and not ACCESS_LABEL_RX.search(label)


INTERNAL_BIBLIOGRAPHY_HEADING_RX = re.compile(
    r"^(?:fuentes|sites?|sitios?(?:\s+web)?|p[aá]ginas?\s+web\s+de\s+los\s+artistas|"
    r"otros\s+sitios\s+consultados)\s*$",
    re.I,
)
WEB_SECTION_HEADING_RX = re.compile(
    r"^(?:sites?|sitios?(?:\s+web)?|p[aá]ginas?\s+web\s+de\s+los\s+artistas|"
    r"otros\s+sitios\s+consultados)\s*$",
    re.I,
)
ABNT_START_TEXT_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜ]{2,}(?:[-'’][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜ]{2,})*"
    r"(?:\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜ]{2,}(?:[-'’][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜ]{2,})*){0,8}"
    r"(?:\s*,|\s*\.|\s*;|\s*$)|_{3,}|[-–—]{3,})"
)


def _looks_abnt_upper_start_text(text: str) -> bool:
    text = text.strip()
    if ABNT_START_TEXT_RX.match(text):
        return True
    letters = [char for char in text if char.isalpha()]
    return bool(
        len(letters) >= 5
        and letters[0].isupper()
        and sum(char.isupper() for char in letters) / len(letters) >= 0.88
    )


def _abnt_dominant_texts(lines: List[str]) -> bool:
    abnt_like = sum(_looks_abnt_upper_start_text(line) for line in lines)
    parenthetical = sum(_has_early_bibliographic_date(line) for line in lines)
    return abnt_like >= 5 and abnt_like >= parenthetical


@dataclass
class AdaptiveLayoutZone:
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
    start_confidence_score: float
    start_confidence_label: str
    start_confidence_reasons: List[str]
    end_confidence_score: float
    end_confidence_label: str
    end_confidence_reasons: List[str]
    zone_completeness: str
    adaptive_soft_limit_pages: int
    zone_span_pages: int
    adaptive_limit_exceeded: bool


def _label(score: float) -> str:
    return "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"


def _has_early_bibliographic_date(text: str) -> bool:
    start = text.strip()[:220]
    return bool(PAREN_DATE_RX.search(start) or PAREN_UNDATED_RX.search(start))


def _has_bare_author_year(text: str) -> bool:
    """Detect author–year styles where the year is not parenthesized."""
    start = text.strip()[:260]
    if (
        not start
        or not start[:1].isupper()
        or not AUTHORISH_RX.match(start)
        or not AUTHOR_COMMA_RX.match(start)
        or _has_early_bibliographic_date(start)
    ):
        return False
    match = YEAR_RX.search(start)
    if not match:
        return False
    before = start[max(0, match.start() - 2):match.start()]
    return "(" not in before and "/" not in before


#: 0.6.15: in a numbered list every entry carries its marker, so markers cannot
#: be fewer than a quarter of the author-year starts. Ten numbered lines (an
#: annex list, "2001." lines of a law) beside 283 author-year starts are noise.
NUMERIC_MIN_SHARE_OF_AUTHOR_STARTS = 0.25
NUMERIC_DEMOTION_MIN_AUTHOR_STARTS = 20


def _demote_minor_numeric(base: StyleProfile) -> StyleProfile:
    if base.style != "numeric":
        return base
    comma, initial = base.author_comma_year_starts, base.author_initial_year_starts
    author = comma + initial
    if author < NUMERIC_DEMOTION_MIN_AUTHOR_STARTS or base.numeric_starts >= NUMERIC_MIN_SHARE_OF_AUTHOR_STARTS * author:
        return base
    return replace(base, style="author_initial" if initial > comma else "author_year_comma")


def diagnose_adaptive_style(lines: List[str]) -> StyleProfile:
    base = _demote_minor_numeric(diagnose_style(lines))
    if base.style in {"numeric", "bracket_key"}:
        return base
    bare = sum(_has_bare_author_year(line) for line in lines)
    parenthetical = sum(_has_early_bibliographic_date(line) for line in lines)
    abnt_like = sum(_looks_abnt_upper_start_text(line) for line in lines)
    abnt_dominant = abnt_like >= 5 and abnt_like >= parenthetical
    # A few en/em dashes inside an ABNT entry must not turn a whole bibliography
    # into a bulleted list.  ABNT commonly uses uppercase surnames, bare years
    # near the end and underscores to repeat the previous author.
    abnt_override = (
        base.style == "bulleted"
        and base.bullet_starts <= 2
        and (bare >= 2 or abnt_dominant)
    )
    if base.style == "bulleted" and not abnt_override:
        return base
    if (bare >= 2 and bare >= parenthetical) or abnt_override or abnt_dominant:
        return StyleProfile(
            style="author_year_bare",
            n_lines=base.n_lines,
            numeric_starts=base.numeric_starts,
            bracket_key_starts=base.bracket_key_starts,
            author_comma_year_starts=base.author_comma_year_starts,
            author_initial_year_starts=base.author_initial_year_starts,
            institutional_year_starts=base.institutional_year_starts,
            bullet_starts=base.bullet_starts,
            numeric_sequence_score=base.numeric_sequence_score,
        )
    return base


def _contextual_abnt_start(
    index: int,
    lines: List[LayoutLine],
    style: StyleProfile,
) -> bool:
    """Recognize ABNT starts using uppercase text, whitespace and nearby dates."""
    if style.style not in {"author_year_bare", "author_year_comma"}:
        return False
    line = lines[index]
    text = line.text.strip()
    if not _looks_abnt_upper_start_text(text):
        return False

    page_lines = [candidate for candidate in lines if candidate.page == line.page and not _is_footer(candidate)]
    if not page_lines:
        return False
    page_left = min(candidate.x0 for candidate in page_lines)
    if line.x0 > page_left + 4:
        return False
    # 0.6.18: with a reverse indent the dated starts sit to the right and the
    # left margin belongs to continuations («MERCOSUR, Facultad…», «UBA.»).
    dated_x = [c.x0 for c in page_lines if _has_early_bibliographic_date(c.text.strip()[:60])]
    dated_left = sum(1 for x in dated_x if x <= page_left + 4)
    if len(dated_x) >= 3 and dated_left * 4 <= len(dated_x):
        return False

    previous = lines[index - 1] if index else None
    at_page_start = previous is None or previous.page != line.page or _is_footer(previous)
    gap_before = math.inf if at_page_start else line.y0 - previous.y1
    if not at_page_start and gap_before < 5.0:
        return False

    nearby = " ".join(
        candidate.text for candidate in lines[index:index + 9]
        if candidate.page <= line.page + 1
    )
    return bool(YEAR_RX.search(nearby) or SIN_FECHA_RX.search(nearby))


def diagnose_adaptive_layout(
    lines: List[LayoutLine],
    style: StyleProfile,
) -> LayoutProfile:
    """Diagnose margins, including marker-only numeric and bracket styles."""
    base = diagnose_layout(lines)
    if style.style == "numeric":
        candidates = [line for line in lines if NUMERIC_MARKER_RX.match(line.text.strip())]
    elif style.style == "bracket_key":
        candidates = [line for line in lines if BRACKET_KEY_RX.match(line.text.strip())]
    elif style.style == "bulleted":
        candidates = [line for line in lines if BULLET_RX.match(line.text.strip())]
    else:
        return base
    if len(candidates) < 2:
        return base

    start_margin, support = _mode_cluster([line.x0 for line in candidates])
    fonts = [line.median_font_size for line in candidates if line.median_font_size > 0]
    bibliography_font = statistics.median(fonts) if fonts else base.bibliography_font_size
    continuation_x = [
        line.x0 for line in lines
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


def is_adaptive_reference_start(
    line: LayoutLine,
    style: StyleProfile,
    layout: LayoutProfile,
) -> Tuple[bool, str]:
    """Return a boundary candidate and auditable evidence label."""
    text = line.text.strip()
    if not text or _is_footer(line):
        return False, ""
    if _is_reference_heading(line) or DOI_URL_AT_START_RX.match(text) or ACCESS_START_RX.match(text):
        return False, ""
    at_margin = abs(line.x0 - layout.start_margin) <= layout.start_margin_tolerance

    # Explicit structural markers outrank font-size heuristics.  Some long
    # theses alternate 9.5pt and 11pt entries inside the very same bibliography.
    if style.style == "numeric" and NUMERIC_MARKER_RX.match(text):
        # 0.6.15: "(2005) 1." continues "[6]-P. Mäki-Arvela; Appl. Catal. A:";
        # a year is not a list number.
        if not 1500 <= (_numeric_marker_value(text) or 0) <= 2099:
            # Numeric markers remain explicit boundaries even if the first page of
            # a zone uses a different left margin than subsequent pages.
            return True, "numeric_marker"
        return False, ""
    if style.style == "bracket_key" and BRACKET_KEY_RX.match(text):
        return (at_margin, "bracket_key+start_margin" if at_margin else "")
    if style.style == "bulleted" and BULLET_RX.match(text):
        return True, "bullet_marker"
    if style.style == "bulleted" and _is_named_web_source(text):
        return True, "named_web_source"
    if _is_small_font_noise(line, layout):
        return False, ""
    if style.style == "author_year_bare" and REPEATED_AUTHOR_MARK_RX.match(text):
        return (at_margin, "repeated_author_mark+start_margin" if at_margin else "")
    # v0.6.11: "van Dijk, J.", "de Asúa, M.", "del Valle, M. V." abren registro
    # igual que cualquier otro apellido, pero no empiezan con mayúscula y
    # quedaban pegados a la referencia anterior.
    opens_with_particle = bool(SURNAME_PARTICLE_RX.match(text))
    if not at_margin or not (text[:1].isupper() or opens_with_particle) or not AUTHORISH_RX.match(text):
        return False, ""

    if _has_early_bibliographic_date(text):
        return True, "author_or_institution+parenthetical_date+start_margin"
    if (
        style.style == "bulleted"
        and AUTHOR_THEN_NAME_RX.match(text)
        and re.search(r"\b(?:recuperado|disponible|consultado)\b", text, re.I)
    ):
        return True, "author+retrieval_statement+start_margin"
    if style.style == "author_year_bare" and _has_bare_author_year(text):
        return True, "author+bare_year+start_margin"
    if LEGAL_START_RX.match(text):
        return True, "legal_instrument+start_margin"
    if INSTITUTIONAL_PREFIX_RX.match(text):
        return True, "institution+start_margin"
    if AUTHOR_INITIAL_RX.match(text) or MULTI_AUTHOR_NO_YEAR_RX.match(text):
        return True, "author_initial+start_margin"
    return False, ""


def _at_start_margin(line: LayoutLine, layout: LayoutProfile) -> bool:
    return abs(line.x0 - layout.start_margin) <= layout.start_margin_tolerance


def _hanging_indent_opens_new_record(
    line: LayoutLine,
    previous_line: LayoutLine,
    layout: LayoutProfile,
) -> bool:
    """True cuando la geometría ya distingue un registro nuevo.

    v0.6.9: con sangría francesa, un borde en el margen de inicio cuya línea
    anterior está sangrada a la derecha es inequívocamente un registro nuevo,
    y la línea de arriba es la continuación de la referencia previa —que casi
    siempre abre con el nombre de la revista: "Sciences,", "Neurobiology,".
    """
    if not layout.hanging_indent_detected:
        return False
    at_margin = abs(line.x0 - layout.start_margin) <= layout.start_margin_tolerance
    previous_indented = previous_line.x0 >= line.x0 + 6.0
    return at_margin and previous_indented


def _reverse_indent_regime(lines: List[LayoutLine], layout: LayoutProfile) -> bool:
    """True en bibliografias con sangria de PRIMERA linea.

    v0.6.9: el apoyo geometrico asumia sangria francesa, o sea la continuacion a
    la derecha del margen de inicio.  Cuando la sangrada es la primera linea, el
    registro arranca a 120.5 y la continuacion cae a 85.1: el apoyo se negaba
    siempre y se descartaban bordes correctos.
    """
    left = sum(
        1 for line in lines
        if layout.start_margin - 80 <= line.x0 <= layout.start_margin - 14
    )
    right = sum(
        1 for line in lines
        if layout.start_margin + 14 <= line.x0 <= layout.start_margin + 80
    )
    return left >= 3 and left > right


def _weak_boundary_supported(
    index: int,
    lines: List[LayoutLine],
    layout: LayoutProfile,
    paragraph_profile=None,
) -> bool:
    """Support a year-wrapped weak start by hanging indent or paragraph geometry."""
    candidate = lines[index]
    reverse_indent = _reverse_indent_regime(lines, layout)
    paragraph_open = bool(paragraph_profile and is_paragraph_start(index, lines, paragraph_profile))
    for follower in lines[index + 1:index + 3]:
        if follower.page > candidate.page + 1:
            break
        if reverse_indent:
            indented = follower.x0 <= layout.start_margin - 14
        else:
            indented = follower.x0 >= layout.start_margin + 14
        if not indented and not paragraph_open:
            if follower.page == candidate.page:
                break
        if _has_early_bibliographic_date(follower.text) or YEAR_RX.search(follower.text[:120]):
            return bool(indented or paragraph_open)
    return False


def _continues_marked_entry(text: str, evidence: str, style: StyleProfile, marked_open: bool) -> bool:
    """0.6.15: in a list of [n] markers without hanging indent every line sits
    at the margin; "Chem. 184 (2002) 431." continues the marked entry above.
    While a marked entry is open, only an explicit "Surname, I." opens another.
    """
    return (
        style.style == "numeric"
        and marked_open
        and evidence != "numeric_marker"
        and not AUTHOR_INITIAL_RX.match(text.strip())
    )


def _deferred_author_year_start(index: int, lines: List[LayoutLine], layout: LayoutProfile, paragraph_profile=None) -> bool:
    """Author/editor opening whose year is delayed to one of the next two physical lines."""
    if not (0 <= index < len(lines)):
        return False
    line = lines[index]
    text = line.text.strip()
    if not text or not text[:1].isupper() or YEAR_RX.search(text[:260]) or _has_early_bibliographic_date(text) or _has_bare_author_year(text):
        return False
    if ACCESS_START_RX.match(text):
        return False
    at_margin = abs(line.x0 - layout.start_margin) <= layout.start_margin_tolerance
    authorish = bool(AUTHORISH_RX.match(text) or AUTHOR_INITIAL_RX.match(text) or MULTI_AUTHOR_NO_YEAR_RX.match(text) or re.search(r"\b(?:eds?\.?|editors?|coords?\.?|comp(?:s|iladores?)?\.?)\b", text, re.I))
    if not (authorish and at_margin):
        return False
    nearby = " ".join(x.text for x in lines[index + 1:index + 3] if x.page <= line.page + 1)
    if not YEAR_RX.search(nearby[:260]):
        return False
    paragraph_open = bool(paragraph_profile and is_paragraph_start(index, lines, paragraph_profile))
    page_open = index == 0 or lines[index - 1].page != line.page
    return paragraph_open or page_open


def _accepted_boundaries(
    lines: List[LayoutLine],
    style: StyleProfile,
    layout: LayoutProfile,
) -> List[int]:
    accepted: List[int] = []
    paragraph_profile = profile_paragraph_flow(lines)
    abnt_mode = style.style == "author_year_bare" and _abnt_dominant_texts(
        [line.text for line in lines]
    )
    marked_open = False
    for index, line in enumerate(lines):
        if _contextual_abnt_start(index, lines, style):
            accepted.append(index)
            marked_open = False
            continue
        start, evidence = is_adaptive_reference_start(line, style, layout)
        if not start and style.style not in {"author_year_bare", "numeric", "bracket_key", "bulleted"} and _has_bare_author_year(line.text):
            if not re.match(r"^(?:En|In|Press|Editorial|University|Universidad|Vol\.?|No\.?|N[º°])\b", line.text.strip(), re.I):
                # v0.6.11: ``hanging_indent_detected`` es del documento, no de
                # la linea. Sin mirar el x0, cualquier continuacion con forma de
                # "revista, numero, anio" abria registro propio y partia en dos
                # la referencia de arriba.
                if _at_start_margin(line, layout) and (
                    layout.hanging_indent_detected
                    or is_paragraph_start(index, lines, paragraph_profile)
                ):
                    start, evidence = True, "author+bare_year+local_geometry"
        if not start:
            continue
        if abnt_mode and evidence == "author+bare_year+start_margin":
            continue
        if evidence == "author+bare_year+start_margin" and style.style != "author_year_bare":
            local_ok = bool(layout.hanging_indent_detected or is_paragraph_start(index, lines, paragraph_profile))
            if not local_ok:
                continue
        if evidence in WEAK_EVIDENCE and not _weak_boundary_supported(index, lines, layout, paragraph_profile):
            continue
        if _continues_marked_entry(line.text, evidence, style, marked_open):
            continue
        accepted.append(index)
        marked_open = evidence == "numeric_marker"
    return accepted


def _adaptive_trim_by_density(
    lines: List[LayoutLine],
    style: StyleProfile,
    layout: LayoutProfile,
    terminal_reason: str,
) -> Tuple[List[LayoutLine], Optional[int], str, Dict[int, int]]:
    """Close after two empty pages; remove one trailing empty page at EOF."""
    # Explicit structural closure outranks a temporary density drop when the
    # bibliography itself announces a web/source subsection.  Such lists often
    # omit years and author punctuation but still end cleanly at an annex.
    if terminal_reason == "layout_confirmed_stop_heading" and any(
        WEB_SECTION_HEADING_RX.fullmatch(line.text.strip()) for line in lines
    ):
        return lines, None, terminal_reason, {}
    by_page: Dict[int, List[LayoutLine]] = defaultdict(list)
    for line in lines:
        by_page[line.page].append(line)
    page_counts: Dict[int, int] = {}
    seen = 0
    zero_pages: List[int] = []
    for page in sorted(by_page):
        page_lines = by_page[page]
        starts = len(_accepted_boundaries(page_lines, style, layout))
        page_counts[page] = starts
        if starts:
            seen += starts
            zero_pages = []
        elif seen >= 3:
            zero_pages.append(page)
            if len(zero_pages) >= 2:
                cut_page = zero_pages[0]
                return (
                    [line for line in lines if line.page < cut_page],
                    cut_page,
                    "layout_reference_density_drop",
                    page_counts,
                )

    # At the physical end of a PDF, a single non-bibliographic page (for
    # example a back cover) is enough to trim because no later references can
    # resume.
    if terminal_reason == "end_of_document" and seen >= 3 and zero_pages:
        cut_page = zero_pages[0]
        return (
            [line for line in lines if line.page < cut_page],
            cut_page,
            "trailing_reference_density_drop",
            page_counts,
        )
    return lines, None, terminal_reason, page_counts


def _confidence_for_start(n_boundaries: int, layout: LayoutProfile) -> Tuple[float, List[str]]:
    reasons = ["explicit_reference_heading", f"boundary_support_{n_boundaries}"]
    score = 0.55
    if n_boundaries >= 5:
        score += 0.20
    elif n_boundaries >= 2:
        score += 0.10
    if layout.candidate_support >= 5:
        score += 0.12
        reasons.append("stable_start_margin")
    elif layout.candidate_support >= 2:
        score += 0.06
    if layout.hanging_indent_detected:
        score += 0.08
        reasons.append("hanging_indent_detected")
    return round(min(score, 1.0), 3), reasons


def _confidence_for_end(
    termination: str,
    n_boundaries: int,
    limit_exceeded: bool,
) -> Tuple[float, str, List[str]]:
    if termination == "layout_confirmed_stop_heading":
        score, completeness = 0.96, "complete"
    elif termination == "next_reference_heading":
        score, completeness = 0.92, "complete"
    elif termination == "layout_reference_density_drop":
        score, completeness = 0.88, "complete"
    elif termination == "trailing_reference_density_drop":
        score, completeness = 0.86, "probably_complete"
    elif termination == "end_of_document" and n_boundaries >= 3:
        score, completeness = 0.90, "complete"
    elif termination == "end_of_document":
        score, completeness = 0.58, "indeterminate"
    else:
        score, completeness = 0.45, "possibly_truncated"
    reasons = [f"terminated_by_{termination}"]
    if limit_exceeded:
        reasons.append("adaptive_soft_limit_exceeded_but_extraction_continued")
    return score, completeness, reasons


_SENTENCE_END_RX = re.compile(r"[.:;!?»”\"')\]]\s*$")
_FOLIO_ONLY_RX = re.compile(r"^[\s\-–—]*(?:\d{1,4}|[ivxlcdm]{1,6})[\s\-–—]*$", re.I)


def _is_prose_tail(index: int, lines: List[LayoutLine]) -> bool:
    """0.6.15: «... no ha sido reportado en la / bibliografía.» is a sentence end.

    A heading never starts in lowercase in the middle of an open sentence: the
    line just above, in the same paragraph, has no closing punctuation.
    """
    text = lines[index].text.strip()
    first = next((c for c in text if c.isalpha()), "")
    if not first or not first.islower() or index == 0:
        return False
    previous = lines[index - 1]
    if previous.page != lines[index].page:
        return False
    height = max(1.0, lines[index].y1 - lines[index].y0)
    gap = lines[index].y0 - previous.y1
    return gap <= 1.5 * height and not _SENTENCE_END_RX.search(previous.text.strip())


def _is_table_cell(index: int, lines: List[LayoutLine]) -> bool:
    """0.6.15: a heading word that shares its row with two or more other cells."""
    current = lines[index]
    cells = 0
    for other in lines[max(0, index - 12):index + 13]:
        if other is current or other.page != current.page:
            continue
        text = other.text.strip()
        # A cell holds a word or a number; «·», «|», «E» at the edge of a scan do not.
        if sum(c.isalnum() for c in text) < 2 or _FOLIO_ONLY_RX.match(text):
            continue
        same_band = other.y0 < current.y1 and current.y0 < other.y1
        disjoint = other.x1 <= current.x0 or current.x1 <= other.x0
        if same_band and disjoint:
            if len(text) > 40:
                return False
            cells += 1
    return cells >= 2


def _is_divider_before(start: int, end: int, lines: List[LayoutLine]) -> bool:
    """Only a few title words ("y Anexos") and no dated line between two headings."""
    between = [line.text.strip() for line in lines[start + 1:end] if not _is_footer(line)]
    return (
        len(between) <= 3
        and sum(len(text) for text in between) < 40
        and not any(re.search(r"\b(?:1[5-9]|20)\d{2}\b", text) for text in between)
    )


#: 0.6.18: a hyperlink set in a smaller font («Disponible en: / http://…») is
#: part of its reference; so is the rest of the address on the next line.
_SMALL_URL_RX = re.compile(r"^(?:https?\s*:\s*/|www\.|doi\s*:|10\.\d{4,9}/)", re.I)
_URL_TAIL_RX = re.compile(r"^\S+$")


def _drop_small_font_noise(body: List[LayoutLine], style: StyleProfile, layout: LayoutProfile) -> List[LayoutLine]:
    kept: List[LayoutLine] = []
    previous_url = False
    for line in body:
        text = line.text.strip()
        small = _is_small_font_noise(line, layout)
        url = bool(_SMALL_URL_RX.match(text))
        url_tail = previous_url and bool(_URL_TAIL_RX.match(text)) and ("/" in text or "." in text)
        if (
            not small
            or url or url_tail
            or (style.style == "numeric" and NUMERIC_MARKER_RX.match(text))
            or (style.style == "bracket_key" and BRACKET_KEY_RX.match(text))
            or (style.style == "bulleted" and BULLET_RX.match(text))
        ):
            kept.append(line)
        previous_url = small and (url or url_tail)
    return kept


def detect_adaptive_layout_zones(lines: List[LayoutLine]) -> List[AdaptiveLayoutZone]:
    headings = [
        index for index, line in enumerate(lines)
        if _is_reference_heading(line)
        and not _is_prose_tail(index, lines)
        and not _is_table_cell(index, lines)
    ]
    total_pages = max((line.page for line in lines), default=0)
    # A table of contents may repeat an actual late-document heading.  Suppress
    # only the early duplicate, preserving repeated real bibliographies by
    # chapter elsewhere in the document.
    heading_keys: Dict[str, List[int]] = defaultdict(list)
    for index in headings:
        key = re.sub(r"[^a-z0-9]+", " ", _strip_heading_prefix(lines[index].text)).strip()
        heading_keys[key].append(index)
    def in_numbered_contents_cluster(index: int) -> bool:
        page = lines[index].page
        previous = [
            line.text.strip()
            for line in lines[max(0, index - 20):index]
            if line.page == page
        ]
        numbered = sum(bool(re.match(
            r"^(?:(?:[ivxlcdm]+|\d+)(?:[\.\-:]|\s))",
            text,
            flags=re.I,
        )) for text in previous)
        return numbered >= 4

    toc_duplicates = {
        indexes[0]
        for indexes in heading_keys.values()
        if len(indexes) >= 2
        and lines[indexes[-1]].page >= lines[indexes[0]].page + 3
        and in_numbered_contents_cluster(indexes[0])
    }
    headings = [index for index in headings if index not in toc_duplicates]
    # Page headers such as "254 REFERENCIAS", "255 REFERENCIAS" repeat the
    # same section label on every page.  Keep only the first heading in a run;
    # real chapter bibliographies separated by several pages remain distinct.
    deduplicated_headings: List[int] = []
    previous_key = ""
    previous_page = -999
    for index in headings:
        key = re.sub(r"[^a-z0-9]+", " ", _strip_heading_prefix(lines[index].text)).strip()
        repeated_page_header = (
            key == previous_key
            and lines[index].page <= previous_page + 3
            and lines[index].y0 <= 120
        )
        if not repeated_page_header:
            deduplicated_headings.append(index)
        elif deduplicated_headings and _is_divider_before(deduplicated_headings[-1], index, lines):
            # 0.6.15: nothing but "y Anexos" since the previous one, so that one
            # was a divider page and this is the heading that opens the list.
            deduplicated_headings[-1] = index
        previous_key = key
        previous_page = lines[index].page
    headings = deduplicated_headings
    adaptive_soft_limit = max(25, int(math.ceil(total_pages * 0.15)))
    zones: List[AdaptiveLayoutZone] = []

    for position, heading_index in enumerate(headings):
        heading = lines[heading_index]
        next_heading_index = headings[position + 1] if position + 1 < len(headings) else len(lines)
        stop_index = next_heading_index
        terminal_reason = "next_reference_heading" if next_heading_index < len(lines) else "end_of_document"

        for index in range(heading_index + 1, next_heading_index):
            if _is_structural_stop(index, lines):
                stop_index = index
                terminal_reason = "layout_confirmed_stop_heading"
                break

        body = [line for line in lines[heading_index + 1:stop_index] if not _is_footer(line)]
        if not body:
            continue

        # Diagnose from the beginning of the candidate zone so later prose does
        # not redefine its margin or bibliographic style before density trimming.
        sample = body[:400]
        style = diagnose_adaptive_style([line.text for line in sample])
        layout = diagnose_adaptive_layout(sample, style)
        body = _drop_small_font_noise(body, style, layout)
        body, _, termination, page_counts = _adaptive_trim_by_density(
            body, style, layout, terminal_reason
        )
        if not body:
            continue

        style = diagnose_adaptive_style([line.text for line in body])
        layout = diagnose_adaptive_layout(body, style)
        untrimmed, untrimmed_termination = body, termination
        # Re-run the trim after the final profile is known.
        body, _, termination, page_counts = _adaptive_trim_by_density(
            body, style, layout, termination
        )
        if not body:
            continue

        # 0.6.15: the style above was read on a body that still held the annex
        # (numbered lists) and the trim cut with it. If the lines that remain
        # read otherwise, trim again from the same body with their style.
        trimmed_style = diagnose_adaptive_style([line.text for line in body])
        if trimmed_style.style != style.style:
            trimmed_layout = diagnose_adaptive_layout(body, trimmed_style)
            retrimmed, _, retermination, recounts = _adaptive_trim_by_density(
                untrimmed, trimmed_style, trimmed_layout, untrimmed_termination
            )
            if retrimmed:
                body, style, layout = retrimmed, trimmed_style, trimmed_layout
                termination, page_counts = retermination, recounts

        boundaries = _accepted_boundaries(body, style, layout)
        n_boundaries = len(boundaries)
        end_page = max(line.page for line in body)
        span = end_page - heading.page + 1
        exceeded = span > adaptive_soft_limit
        start_score, start_reasons = _confidence_for_start(n_boundaries, layout)
        end_score, completeness, end_reasons = _confidence_for_end(
            termination, n_boundaries, exceeded
        )
        combined = round(min(start_score, end_score), 3)
        reasons = [
            *start_reasons,
            *end_reasons,
            "visual_reading_order",
            f"style_{style.style}",
            f"start_margin_{layout.start_margin}",
            f"bibliography_font_{layout.bibliography_font_size}",
            f"zone_pages_{span}",
            f"adaptive_soft_limit_pages_{adaptive_soft_limit}",
        ]
        zones.append(AdaptiveLayoutZone(
            heading=heading,
            lines=body,
            start_page=heading.page,
            end_page=end_page,
            style=style,
            layout=layout,
            termination_reason=termination,
            confidence_score=combined,
            confidence_label=_label(combined),
            confidence_reasons=reasons,
            start_confidence_score=start_score,
            start_confidence_label=_label(start_score),
            start_confidence_reasons=start_reasons,
            end_confidence_score=end_score,
            end_confidence_label=_label(end_score),
            end_confidence_reasons=end_reasons,
            zone_completeness=completeness,
            adaptive_soft_limit_pages=adaptive_soft_limit,
            zone_span_pages=span,
            adaptive_limit_exceeded=exceeded,
        ))
    return zones


def _looks_complete(lines: List[LayoutLine]) -> bool:
    text = " ".join(line.text for line in lines)
    return bool(YEAR_RX.search(text) or SIN_FECHA_RX.search(text) or re.search(r"https?://|www\.", text, re.I))


def segment_adaptive_layout_zone(zone: AdaptiveLayoutZone) -> List[dict]:
    segments: List[dict] = []
    current: List[LayoutLine] = []
    annotation: List[LayoutLine] = []
    boundary_evidence = ""
    in_web_section = False
    marked_open = False

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

    effective_lines, removed_decorations = filter_repeated_page_decorations(zone.lines)
    effective_layout = diagnose_adaptive_layout(effective_lines, zone.style)
    paragraph_profile = profile_paragraph_flow(effective_lines)
    abnt_mode = zone.style.style == "author_year_bare" and _abnt_dominant_texts(
        [line.text for line in effective_lines]
    )
    for index, line in enumerate(effective_lines):
        if INTERNAL_BIBLIOGRAPHY_HEADING_RX.fullmatch(line.text.strip()):
            flush()
            if WEB_SECTION_HEADING_RX.fullmatch(line.text.strip()):
                in_web_section = True
            continue
        contextual_abnt = _contextual_abnt_start(index, effective_lines, zone.style)
        start, evidence = is_adaptive_reference_start(line, zone.style, effective_layout)
        if not start and zone.style.style not in {"author_year_bare", "numeric", "bracket_key", "bulleted"} and _has_bare_author_year(line.text):
            if not re.match(r"^(?:En|In|Press|Editorial|University|Universidad|Vol\.?|No\.?|N[º°])\b", line.text.strip(), re.I):
                if _at_start_margin(line, effective_layout) and (
                    effective_layout.hanging_indent_detected
                    or is_paragraph_start(index, effective_lines, paragraph_profile)
                ):
                    start, evidence = True, "author+bare_year+local_geometry"
        if not start and _deferred_author_year_start(index, effective_lines, effective_layout, paragraph_profile):
            start, evidence = True, "deferred_author_year+local_geometry"
        if contextual_abnt:
            start, evidence = True, "abnt_uppercase+blank_gap"
        elif abnt_mode and evidence == "author+bare_year+start_margin":
            start, evidence = False, ""
        if start and evidence == "author+bare_year+start_margin" and zone.style.style != "author_year_bare":
            start = bool(effective_layout.hanging_indent_detected or is_paragraph_start(index, effective_lines, paragraph_profile))
        if start and evidence in WEAK_EVIDENCE:
            start = _weak_boundary_supported(index, effective_lines, effective_layout, paragraph_profile)
        # In block bibliographies, a year appearing on line 2 belongs to the paragraph
        # opened immediately above; it must not split that reference in half.
        if start and index > 0 and effective_lines[index - 1].page == line.page and not is_paragraph_start(index, effective_lines, paragraph_profile) and paragraph_profile.separated:
            if evidence in {"author_or_institution+parenthetical_date+start_margin", "author+bare_year+start_margin"}:
                previous_line = effective_lines[index - 1]
                prev = previous_line.text.strip()
                # v0.6.9: cancelar un borde que la geometría ya distingue pegaba
                # dos y tres referencias en un solo registro.
                hanging_new_record = _hanging_indent_opens_new_record(
                    line, previous_line, effective_layout
                )
                if (
                    prev
                    and prev[:1].isupper()
                    and not YEAR_RX.search(prev)
                    and not hanging_new_record
                ):
                    start, evidence = False, ""
        if start and _continues_marked_entry(line.text, evidence, zone.style, marked_open):
            start, evidence = False, ""
        if in_web_section and not current and not start:
            start, evidence = True, "web_section_first_source"
        if in_web_section and current and not start:
            previous = effective_lines[index - 1] if index else None
            page_break = previous is None or previous.page != line.page
            gap_before = math.inf if page_break else line.y0 - previous.y1
            current_text = " ".join(item.text for item in current)
            at_left = abs(line.x0 - effective_layout.start_margin) <= effective_layout.start_margin_tolerance
            if at_left and (gap_before >= 8.0 or (page_break and _looks_complete(current))):
                start, evidence = True, "web_source_blank_gap"
            elif (
                at_left
                and _looks_complete(current)
                and re.search(
                    r"\ben\s+la\s+siguiente\s+direcci[oó]n\s*:?",
                    line.text,
                    re.I,
                )
            ):
                start, evidence = True, "web_source_retrieval_label"
        if start:
            flush()
            current = [line]
            boundary_evidence = evidence
            marked_open = evidence == "numeric_marker"
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


def classify_zone_role(heading_text: str) -> str:
    """Classify the documentary function of a bibliography-like zone."""
    text = _strip_heading_prefix(heading_text)
    text = re.sub(r"^([a-z])\s+(?=[a-z]{3})", r"\1", text, flags=re.I).strip(" .-:")
    if re.search(r"\b(?:anexo\s*:\s*fuentes|fuentes\s+(?:juridicas|jurisprudenciales|normativas)|jurisprudencia|fallos|normativa|legislacion)\b", text, re.I):
        return "legal_sources"
    if re.search(r"\b(?:otras\s+referencias|consultad[ao]s?)\b", text, re.I):
        return "consulted_sources"
    if re.search(r"\b(?:literatura|obras|fuentes)\s+citad[ao]s?\b", text, re.I):
        return "cited_literature"
    return "primary_references"


def _numeric_sequence_diagnostics(segments: List[dict]) -> Dict:
    values = [
        value for value in (
            _numeric_marker_value(segment.get("reference_text", "")) for segment in segments
        ) if value is not None
    ]
    if not values:
        return {
            "numeric_first_marker": None,
            "numeric_last_marker": None,
            "numeric_missing_markers": "",
            "numeric_duplicate_markers": "",
            "numeric_sequence_warning": "",
        }
    seen = set(values)
    missing = [value for value in range(min(values), max(values) + 1) if value not in seen]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    warnings: List[str] = []
    if values[0] != 1:
        warnings.append(f"first_detected_marker_is_{values[0]}")
    if missing:
        warnings.append(f"missing_{len(missing)}_markers")
    if duplicates:
        warnings.append(f"duplicate_{len(duplicates)}_markers")
    return {
        "numeric_first_marker": values[0],
        "numeric_last_marker": values[-1],
        "numeric_missing_markers": ";".join(map(str, missing)),
        "numeric_duplicate_markers": ";".join(map(str, duplicates)),
        "numeric_sequence_warning": ";".join(warnings),
    }


def process_pdf(
    pdf_path: str | Path,
    scope: Scope = "all_reference_sections",
    lines: Optional[Sequence[LayoutLine]] = None,
) -> Dict:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    lines = list(lines) if lines is not None else extract_layout_lines(pdf_path)
    zones = detect_adaptive_layout_zones(lines)
    records: List[dict] = []
    zone_summaries: List[dict] = []

    for zone_id, zone in enumerate(zones, 1):
        segments = segment_adaptive_layout_zone(zone)
        zone_role = classify_zone_role(zone.heading.text)
        numeric_diagnostics = _numeric_sequence_diagnostics(segments)
        for ref_in_zone, segment in enumerate(segments, 1):
            record = dict(segment)
            record.update({
                "zone_id": zone_id,
                "ref_in_zone": ref_in_zone,
                "zone_heading": zone.heading.text,
                "zone_role": zone_role,
                "zone_start_page": zone.start_page,
                "zone_end_page": zone.end_page,
                "zone_start_confidence_score": zone.start_confidence_score,
                "zone_start_confidence_label": zone.start_confidence_label,
                "zone_end_confidence_score": zone.end_confidence_score,
                "zone_end_confidence_label": zone.end_confidence_label,
                "zone_completeness": zone.zone_completeness,
                "zone_termination_reason": zone.termination_reason,
                "zone_adaptive_limit_exceeded": zone.adaptive_limit_exceeded,
            })
            records.append(record)

        zone_summaries.append({
            "zone_id": zone_id,
            "heading": zone.heading.text,
            "zone_role": zone_role,
            "start_page": zone.start_page,
            "end_page": zone.end_page,
            "style": zone.style.style,
            "n_segments": len(segments),
            "termination_reason": zone.termination_reason,
            "zone_completeness": zone.zone_completeness,
            "start_confidence_score": zone.start_confidence_score,
            "start_confidence_label": zone.start_confidence_label,
            "start_confidence_reasons": zone.start_confidence_reasons,
            "end_confidence_score": zone.end_confidence_score,
            "end_confidence_label": zone.end_confidence_label,
            "end_confidence_reasons": zone.end_confidence_reasons,
            "combined_confidence_score": zone.confidence_score,
            "combined_confidence_label": zone.confidence_label,
            "adaptive_soft_limit_pages": zone.adaptive_soft_limit_pages,
            "zone_span_pages": zone.zone_span_pages,
            "adaptive_limit_exceeded": zone.adaptive_limit_exceeded,
            "confidence_reasons": zone.confidence_reasons,
            **numeric_diagnostics,
            **asdict(zone.layout),
            **{f"style_{key}": value for key, value in asdict(zone.style).items()},
        })

    occurrences, duplicate_groups = _annotate_duplicates(records)
    selected = _select_scope(occurrences, scope, final_zone_id=len(zones) if zones else None)
    return {
        "software_version": "0.4.5",
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

    parser = argparse.ArgumentParser(description="BiblioRef v0.4.5 adaptive reference segmenter")
    parser.add_argument("pdf", help="Input PDF")
    parser.add_argument("--json", dest="json_out", help="Output JSON")
    parser.add_argument("--csv", dest="csv_out", help="Output references CSV")
    parser.add_argument("--zones-csv", dest="zones_out", help="Output zone diagnostics CSV")
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
