# -*- coding: utf-8 -*-
"""BiblioRef v0.2 — auditable adaptive bibliography extraction.

Development branch derived from the user's earlier V3.2.2 / integrated BiblioRef workflow.
This version focuses on four separable tasks:
  1) bibliography-zone detection,
  2) adaptive reference-boundary detection / segmentation.
  3) explicit extraction scope,
  4) conservative duplicate reporting and zone confidence.

It intentionally does NOT claim to solve full bibliographic field parsing yet.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Dict, Optional, Tuple, Literal

Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]
VALID_SCOPES = {"all_reference_sections", "final_reference_section", "unique_references"}
SCOPE_DEFINITIONS = {
    "all_reference_sections": "Every segmented occurrence from every explicit bibliography section.",
    "final_reference_section": "Only the last explicit bibliography section in document order; no claim that it is comprehensive.",
    "unique_references": "First occurrence of each conservative normalized fingerprint across all sections, with duplicate provenance retained.",
}

try:
    import pymupdf
except Exception:  # pragma: no cover
    pymupdf = None


# -----------------------------------------------------------------------------
# Normalization
# -----------------------------------------------------------------------------

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s))
        if not unicodedata.combining(c)
    )


def norm_text(s: str) -> str:
    s = strip_accents(str(s)).lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# -----------------------------------------------------------------------------
# Heading detection
# -----------------------------------------------------------------------------
REF_HEADING_RX = re.compile(
    r"\b(?:(?:otras\s+)?referencias(?:\s+(?:bibliograficas|citadas|consultadas))?|bibliografia|bibliography|references|"
    r"obras\s+citadas|fuentes\s+bibliograficas|fuentes\s+citadas|"
    r"literatura\s+(?:citada|consultada|citada\s+y\s+consultada)|"
    r"(?:cited\s+literature|literature\s+cited|works\s+cited))\b",
    re.I,
)

# Allows hierarchical prefixes such as "III.2.1. Bibliografía" and
# "CAPÍTULO V. ANEXO I" after normalization.
STOP_KEYWORDS = (
    "anexo", "anexos", "apendice", "appendix", "indice", "agradecimientos",
    "curriculum", "capitulo", "parte", "conclusiones", "conclusion"
)


# v0.9.7: hierarchical numbering is separated from the heading by a dot, a
# colon or a dash, and the dash is not always the ASCII hyphen.  Word
# processors autocorrect ``IV-5-`` into ``IV–5-``, so the whole Unicode dash
# block is accepted.  This widens the separator alphabet only; the
# ``re.fullmatch`` anchoring of the heading test itself is untouched.
_HEADING_NUM_SEP = "[\\.\\-\u2010-\u2015:]"


# 0.6.14 - every numeral level is a whole token.  The boundary used to guard
# only the first level, so in "5. Lista de referencias" the "Li" was taken as a
# second level and "sta de referencias" remained ("5. List of references",
# "5. Literatura citada" likewise).
_HEADING_NUMERAL = r"(?:[ivxlcdm]+|\d+)(?=\s|" + _HEADING_NUM_SEP + r"|$)"
_HEADING_PREFIX_RX = re.compile(
    r"^\s*" + _HEADING_NUMERAL
    + r"(?:\s*" + _HEADING_NUM_SEP + r"\s*" + _HEADING_NUMERAL + r")*\s*"
    + _HEADING_NUM_SEP + r"?\s*",
    re.I,
)

# 0.6.14 - enumerators closed by ")" ("7) Referencias", "G) BIBLIOGRAFIA
# GENERAL", T0137) and a single letter closed by "." ("A. Bibliografia").  Only
# the bibliographic heading test strips them: "10) Parte de la ley" is a numbered
# reference, and ``is_stop_heading`` must not read it as a "Parte" heading.  A
# letter needs its "." or ")", so "A la memoria de..." keeps its first word.
_HEADING_ENUMERATOR_RX = re.compile(r"^\s*(?:(?:\d+|[ivxlcdm]+|[a-z])\s*\)|[a-z]\s*\.)\s*", re.I)


def _strip_heading_prefix(t: str) -> str:
    t = norm_text(t)
    # roman / arabic hierarchical numbering: III.2.1., 5.2.3, IV., IV–5-, etc.
    # The boundary assertion prevents ordinary words beginning with Roman-
    # numeral letters (for example "literatura") from losing their prefix.
    t = _HEADING_PREFIX_RX.sub("", t)
    return t.strip()


# v0.9.5: a bibliographic heading may be titled as a chapter of its own
# ("Chapter 7: References", "Capítol 9. Referències").  The prefix is stripped
# ONLY for the bibliographic test below; ``_strip_heading_prefix`` is shared
# with ``is_stop_heading`` and must keep treating a chapter as a chapter.
_CHAPTER_PREFIX_RX = re.compile(
    r"^\s*(?:chapters?|chapitre|capitulos?|capitol|kapitel|hoofdstuk|cap)"
    r"\s*\.?\s*(?:[ivxlcdm]+|\d+)\s*[\.\-:)]*\s*",
    re.I,
)

# v0.9.5: some embedded fonts map the space character onto a printable glyph,
# so words arrive glued ("Chapterȱ7:ȱReferencesȱ").  Accent stripping would turn
# such a glyph into a letter, so the repair has to happen on the raw candidate.
# Only characters that cannot occur inside an ordinary word are considered.
_SUSPECT_SEPARATOR_RX = re.compile(r"[^\W\d_]", re.UNICODE)


def _strip_chapter_prefix(t: str) -> str:
    return _CHAPTER_PREFIX_RX.sub("", t).strip(" .-:")


def _separator_glyph_variants(raw: str):
    """Yield repairs for a heading whose spaces were replaced by a glyph.

    A candidate is produced by mapping one suspect glyph to a space.  Nothing is
    accepted here: the anchored vocabulary below still decides, so a repair can
    only succeed when it yields an exact bibliographic heading.
    """
    exotic = {
        ch for ch in set(raw)
        if ord(ch) > 0x7F and _SUSPECT_SEPARATOR_RX.match(ch)
        and strip_accents(ch).lower() != ch.lower()
    }
    for ch in exotic:
        if raw.count(ch) >= 2:
            yield raw.replace(ch, " ")


def _is_ref_heading_normalized(t: str) -> bool:
    """Anchored bibliographic vocabulary over an already normalized heading."""
    # Anchored patterns are essential: incidental prose such as
    # "algunas referencias a..." must not become a bibliography zone.
    # v0.6.9: ``bibliografia`` ya toleraba un calificador corto y ``referencias``
    # no.  "Referencias generales" dejaba una tesis entera sin zona.
    if re.fullmatch(
        r"(?:otras\s+)?referencias"
        r"(?:\s+(?:bibliograficas|citadas|consultadas|generales|documentales|finales))?",
        t,
        flags=re.I,
    ):
        return True
    if re.fullmatch(r"referencias\s+y\s+bibliografia", t, flags=re.I):
        return True
    # Bare ``Fuentes`` is intentionally excluded: in theses it is often a
    # methodology subsection rather than a cited-source list.  It remains an
    # audit candidate, while an annex or an explicit qualifier is strong enough
    # for automatic zone detection.
    if re.fullmatch(
        r"(?:(?:anexo|apendice)\s*:\s*fuentes"
        r"(?:\s+(?:juridicas|jurisprudenciales|normativas|documentales|consultadas|citadas))?"
        r"|fuentes\s+(?:juridicas|jurisprudenciales|normativas|documentales|consultadas|citadas))",
        t,
        flags=re.I,
    ):
        return True
    if re.fullmatch(
        r"(?:jurisprudencia|fallos|normativa|legislacion)\s+"
        r"(?:citad[oa]s?|consultad[oa]s?)",
        t,
        flags=re.I,
    ):
        return True
    # Tolerate a short OCR-corrupted qualifier after BIBLIOGRAFIA, e.g. CONSÜLÍADA.
    if re.fullmatch(r"bibliografia(?:\s+[a-z]{2,18}){0,2}", t, flags=re.I):
        return True
    if re.fullmatch(
        r"(?:bibliography|references|obras\s+citadas|fuentes\s+bibliograficas|"
        r"fuentes\s+citadas|literatura\s+(?:citada|consultada|citada\s+y\s+consultada)|"
        r"cited\s+literature|literature\s+cited|works\s+cited)",
        t,
        flags=re.I,
    ):
        return True
    # v0.9.5 - Catalan.  Accents are already stripped, so the surviving forms are
    # ``referencies`` / ``bibliografiques`` / ``citades`` / ``consultades``.
    # ``bibliografia`` needs no entry: it is spelled as in Spanish and is already
    # covered above.  Bare ``fonts`` is excluded for the same reason bare
    # ``fuentes`` is: in a thesis it is usually a methodology subsection.
    if re.fullmatch(
        r"(?:(?:altres\s+)?referencies(?:\s+(?:bibliografiques|citades|consultades))?"
        r"|obres\s+citades"
        r"|fonts\s+(?:i\s+bibliografia|bibliografiques|citades|consultades|documentals)"
        r"|literatura\s+(?:citada|consultada))",
        t,
        flags=re.I,
    ):
        return True
    # v0.9.5 - ordinary English variants that were missing.
    if re.fullmatch(r"(?:list\s+of\s+references|reference\s+list|list\s+of\s+works\s+cited)",
                    t, flags=re.I):
        return True
    # 0.6.12 - the Spanish counterparts ("Lista de Referencias", T0130).
    if re.fullmatch(r"(?:lista|listado)\s+de\s+(?:referencias(?:\s+bibliograficas)?|obras\s+citadas)",
                    t, flags=re.I):
        return True
    return False


def is_ref_heading(text: str, allow_chapter_prefix: bool = True) -> bool:
    raw = str(text).strip()
    if not raw or len(raw) > 150:
        return False

    def _normalize(candidate: str) -> str:
        t = _HEADING_ENUMERATOR_RX.sub("", _strip_heading_prefix(candidate))
        # Some embedded fonts expose an otherwise normal all-caps heading with a
        # spurious space after its first glyph: "R EFERENCIAS" or "O TRAS ...".
        # Repair only the beginning of a heading candidate; the anchored patterns
        # still decide whether the result is genuinely bibliographic.
        t = re.sub(r"^([a-z])\s+(?=[a-z]{3})", r"\1", t, flags=re.I)
        return t.strip(" .-:")

    for candidate in (raw, *_separator_glyph_variants(raw)):
        t = _normalize(candidate)
        if _is_ref_heading_normalized(t):
            return True
        # v0.9.5: "Chapter 7: References" and friends.  Guarded, because the very
        # same string is what a running header looks like on every page of the
        # bibliography it heads; callers with geometry pass allow_chapter_prefix=False
        # inside the decoration band so a repeated header cannot open a zone.
        if allow_chapter_prefix:
            chapterless = _strip_chapter_prefix(t)
            if chapterless != t and _is_ref_heading_normalized(chapterless):
                return True
    return False


def is_stop_heading(text: str) -> bool:
    raw = str(text).strip()
    if not raw or len(raw) > 180:
        return False
    t = _strip_heading_prefix(raw)
    # v0.9.5: a chapter whose title IS the bibliography ("Capítulo 7:
    # Referencias") must not close the zone it opens.  Checked before the
    # chapter rule below so the ordinary "capitulo v. anexo i" case is unaffected.
    if is_ref_heading(raw):
        return False
    # catch "capitulo v. anexo i" before prefix stripping can remove only V
    if re.match(r"^capitulo\b", t):
        return True
    return any(re.match(rf"^{re.escape(k)}\b", t) for k in STOP_KEYWORDS)


# -----------------------------------------------------------------------------
# Reference-start families
# -----------------------------------------------------------------------------
YEAR = r"(?:18|19|20)\d{2}[a-z]?"
YEAR_RX = re.compile(rf"\b{YEAR}\b", re.I)
YEAR_PAREN_RX = re.compile(rf"\({YEAR}(?:\s*[/\-]\s*{YEAR})?[a-z]?\)", re.I)

# v0.9.7: a numbered reference marker is often glued to a dash instead of a
# space (``[1]-N.M. Bertero``, ``[23]- O.S. Alexeev``).  Requiring whitespace
# made those bibliographies invisible to the numeric style diagnosis, which
# then fell back to author-year boundaries and merged whole runs of
# references into one record.
NUMERIC_MARKER_RX = re.compile(
    r"^\s*(?:\[\s?(\d{1,4})\s?\]|\(\s?(\d{1,4})\s?\)|(\d{1,4})[\.)])"
    r"(?:\s+|\s*[\-\u2010-\u2015]\s*)"
)
BRACKET_KEY_RX = re.compile(r"^\s*\[([A-Za-z][A-Za-z0-9 _\-]{0,18}|www\d{1,4})\]\s+", re.I)

# Conventional surname-comma styles.
AUTHOR_COMMA_RX = re.compile(
    r"^\s*[^\W\d_][^,\n]{0,100}\s*,",
    re.UNICODE,
)

# Styles such as "Altieri M & C Nicholls (1999)" / "Aizen M, Garibaldi L & M Dondo (2009)".
AUTHOR_INITIAL_NO_COMMA_RX = re.compile(
    rf"^\s*[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+"
    rf"(?:\s+[A-ZÁÉÍÓÚÑÜ](?:\.|\b)|\s+[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+)"
    rf".{{0,180}}\({YEAR}(?:\s*[/\-]\s*{YEAR})?[a-z]?\)",
    re.UNICODE,
)

INSTITUTIONAL_RX = re.compile(
    r"^\s*(?:Ministerio|Universidad|Organizaci[oó]n|Asociaci[oó]n|OMS|OPS|UNESCO|APA|CONICET|ONU|UNICEF|IICA|INTA|WHO)\b",
    re.I,
)

REPEATED_AUTHOR_DASH_RX = re.compile(rf"^\s*-{{3,}}\s*(?:\({YEAR}\)|{YEAR})")
# Includes common Unicode bullets and the private-use range emitted when old
# Wingdings bullets are extracted from Word/PDF (for example U+F071/U+F0A8).
# Dashes used as bibliography markers are sometimes attached directly to the
# surname (``-Alonso``).  Accept that form only before an uppercase letter so a
# wrapped continuation such as ``-el_espacio`` is not split as a new record.
BULLET_RX = re.compile(
    r"^\s*(?:(?:[-–—](?=\s|[A-ZÁÉÍÓÚÑÜ]))|"
    r"[•·*▪◦●○◆♦‣⁃\uF000-\uF8FF]+)\s*"
)
DOI_URL_RX = re.compile(r"(?:\b10\.\d{4,9}/\S+|https?://|www\.)", re.I)


@dataclass
class StyleProfile:
    style: str
    n_lines: int
    numeric_starts: int = 0
    bracket_key_starts: int = 0
    author_comma_year_starts: int = 0
    author_initial_year_starts: int = 0
    institutional_year_starts: int = 0
    bullet_starts: int = 0
    numeric_sequence_score: float = 0.0


def _numeric_marker_value(text: str) -> Optional[int]:
    m = NUMERIC_MARKER_RX.match(str(text))
    if not m:
        return None
    for g in m.groups():
        if g is not None:
            try:
                return int(g)
            except ValueError:
                return None
    return None


def _numeric_sequence_score(values: List[int]) -> float:
    if len(values) < 2:
        return 0.0
    good = 0
    total = 0
    for a, b in zip(values, values[1:]):
        total += 1
        # allow occasional skipped number / OCR loss; reject years behaving as list numbers.
        if 1 <= (b - a) <= 3 and a <= 1200 and b <= 1200:
            good += 1
    return good / max(total, 1)


#: Estilos que se activan por un marcador explícito al principio de la línea.
_MARKER_STYLES = ("bracket_key", "numeric", "bulleted")


def _demote_unsupported_marker(
    style: str,
    n_key: int,
    n_numeric: int,
    n_bullet: int,
    n_comma: int,
    n_initial: int,
    n_inst: int,
    seq: float,
) -> str:
    """Un marcador anecdótico no puede ganarle a la evidencia autor-año.

    v0.6.10: "repeated evidence" son dos ocurrencias, sin comparar contra nada.
    Dos líneas que empiezan con ``[on-line] en:`` o ``[Recuperado] 15 de junio
    de 2015`` convertían una bibliografía autor-año entera en ``bracket_key``:
    el margen se calculaba sobre esas dos líneas —que son continuaciones— y
    todas las referencias quedaban fuera de tolerancia.  Con menos de cuatro
    líneas marcadas, un marcador pierde contra una alternativa que tenga al
    menos cinco veces más evidencia.
    """
    counts = {"bracket_key": n_key, "numeric": n_numeric, "bulleted": n_bullet}
    if style == "bulleted" and n_bullet >= 4:
        # v0.6.20 (T0145): a scan whose OCR read every «———» as «·» has 19 «bullets»
        # and 75 «Apellido, N.» starts. In a real bulleted list the name follows the
        # bullet, so bare author starts are rare; three times more of them means the
        # «bullets» are something else.
        author = max(n_comma, n_initial)
        if author >= 3 * n_bullet:
            return "author_initial" if n_initial > n_comma else "author_year_comma"
        return style
    if style not in counts or counts[style] >= 4:
        return style
    alternatives = {
        "bracket_key": n_key,
        "numeric": n_numeric,
        "bulleted": n_bullet,
        "author_initial": n_initial,
        "author_year_comma": n_comma,
        "institutional": n_inst,
    }
    alternatives.pop(style, None)
    name, support = max(alternatives.items(), key=lambda item: item[1])
    if support < max(5 * counts[style], 5):
        return style
    if name == "numeric" and seq < 0.45:
        return style
    return name


def diagnose_style(lines: Iterable[str]) -> StyleProfile:
    ls = [str(x).strip() for x in lines if str(x).strip()]
    numeric_values: List[int] = []
    n_key = n_comma = n_initial = n_inst = n_bullet = 0

    for line in ls:
        nv = _numeric_marker_value(line)
        if nv is not None:
            numeric_values.append(nv)
        if BRACKET_KEY_RX.match(line) and not re.match(r"^\s*\[\d+\]", line):
            n_key += 1
        if BULLET_RX.match(line):
            n_bullet += 1
        no_marker = NUMERIC_MARKER_RX.sub("", line)
        no_marker = BRACKET_KEY_RX.sub("", no_marker)
        if AUTHOR_COMMA_RX.match(no_marker) and YEAR_RX.search(no_marker[:260]):
            n_comma += 1
        if AUTHOR_INITIAL_NO_COMMA_RX.match(no_marker):
            n_initial += 1
        if INSTITUTIONAL_RX.match(no_marker) and YEAR_RX.search(no_marker[:260]):
            n_inst += 1

    n_numeric = len(numeric_values)
    seq = _numeric_sequence_score(numeric_values)

    # Activate structural markers only with repeated evidence. This prevents lines like
    # "1999. Capítulo..." from being treated as reference number 1999.
    if n_key >= 2:
        style = "bracket_key"
    elif n_numeric >= 2 and seq >= 0.45:
        style = "numeric"
    elif n_bullet >= 2:
        style = "bulleted"
    elif n_initial >= 2 and n_initial >= n_comma:
        style = "author_initial"
    elif n_comma >= 2:
        style = "author_year_comma"
    elif n_inst >= 2:
        style = "institutional"
    else:
        style = "mixed"

    style = _demote_unsupported_marker(
        style, n_key, n_numeric, n_bullet, n_comma, n_initial, n_inst, seq
    )

    return StyleProfile(
        style=style,
        n_lines=len(ls),
        numeric_starts=n_numeric,
        bracket_key_starts=n_key,
        author_comma_year_starts=n_comma,
        author_initial_year_starts=n_initial,
        institutional_year_starts=n_inst,
        bullet_starts=n_bullet,
        numeric_sequence_score=round(seq, 3),
    )


def is_reference_start(text: str, profile: Optional[StyleProfile] = None) -> bool:
    raw = str(text).strip()
    if not raw or is_ref_heading(raw) or is_stop_heading(raw):
        return False
    if DOI_URL_RX.match(raw):
        return False

    profile = profile or StyleProfile("mixed", 0)

    # Strong structural families are enabled only when diagnosed at zone level.
    if profile.style == "bracket_key":
        return bool(BRACKET_KEY_RX.match(raw))
    if profile.style == "numeric":
        return bool(NUMERIC_MARKER_RX.match(raw))

    clean = NUMERIC_MARKER_RX.sub("", raw)
    clean = BRACKET_KEY_RX.sub("", clean)
    clean = BULLET_RX.sub("", clean)

    if AUTHOR_COMMA_RX.match(clean) and YEAR_RX.search(clean[:280]):
        return True
    if AUTHOR_INITIAL_NO_COMMA_RX.match(clean):
        return True
    if INSTITUTIONAL_RX.match(clean) and YEAR_RX.search(clean[:280]):
        return True
    if REPEATED_AUTHOR_DASH_RX.match(raw):
        return True

    # Mixed mode keeps structural markers only if they look bibliographic, rather than
    # accepting every number in the document.
    if profile.style == "mixed":
        if BRACKET_KEY_RX.match(raw):
            return True
        if NUMERIC_MARKER_RX.match(raw):
            # A marker plus author-like uppercase/name or title-like content is acceptable.
            tail = NUMERIC_MARKER_RX.sub("", raw)
            if re.match(r"^[A-ZÁÉÍÓÚÑÜ]", tail) and len(tail) >= 8:
                return True
    return False


# -----------------------------------------------------------------------------
# Segmentation
# -----------------------------------------------------------------------------
ANNOTATION_PROSE_RX = re.compile(
    r"^(?:se trata|este |esta |en este|en esta|es un |es una |introduce |presenta |describe |permite |cubre |da un enfoque)",
    re.I,
)


def _looks_bibliographically_complete(lines: List[str]) -> bool:
    text = " ".join(lines)
    return bool(YEAR_RX.search(text) or DOI_URL_RX.search(text)) and len(text) >= 25


def segment_lines(lines: Iterable[str], profile: Optional[StyleProfile] = None) -> List[Dict[str, str]]:
    ls = [str(x).strip() for x in lines if str(x).strip()]
    profile = profile or diagnose_style(ls)
    segments: List[Dict[str, str]] = []
    current: List[str] = []
    annotation: List[str] = []

    def flush():
        nonlocal current, annotation
        if current:
            segments.append({
                "reference_text": re.sub(r"\s+", " ", " ".join(current)).strip(),
                "annotation_text": re.sub(r"\s+", " ", " ".join(annotation)).strip(),
                "style": profile.style,
            })
        current, annotation = [], []

    for line in ls:
        if is_ref_heading(line):
            continue
        if is_stop_heading(line):
            flush()
            break

        start = is_reference_start(line, profile)
        if start:
            flush()
            current = [line]
            continue

        if not current:
            continue

        # Annotated bibliographies (common in older computing theses): once a record
        # is bibliographically complete, prose-like commentary is kept separately.
        if profile.style == "bracket_key" and _looks_bibliographically_complete(current):
            if ANNOTATION_PROSE_RX.match(line) and not YEAR_RX.search(line[:80]):
                annotation.append(line)
                continue
            if annotation:
                annotation.append(line)
                continue

        current.append(line)

    flush()
    return segments


# -----------------------------------------------------------------------------
# PDF extraction + bibliography zones
# -----------------------------------------------------------------------------
@dataclass
class PDFLine:
    page: int
    text: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


@dataclass
class Zone:
    heading_page: int
    heading_text: str
    start_page: int
    end_page: int
    lines: List[PDFLine]
    style: Optional[StyleProfile] = None
    termination_reason: str = "unknown"
    confidence_score: float = 0.0
    confidence_label: str = "low"
    confidence_reasons: Optional[List[str]] = None


def extract_pdf_lines(pdf_path: str | Path) -> List[PDFLine]:
    if pymupdf is None:
        raise ImportError("PyMuPDF is required: pip install pymupdf")
    doc = pymupdf.open(str(pdf_path))
    out: List[PDFLine] = []
    for pno in range(doc.page_count):
        page = doc.load_page(pno)
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = " ".join(str(s.get("text", "")) for s in spans)
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue
                boxes = [s.get("bbox") for s in spans if s.get("bbox")]
                if boxes:
                    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
                    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
                else:
                    x0 = y0 = x1 = y1 = 0.0
                out.append(PDFLine(pno + 1, text, x0, y0, x1, y1))
    doc.close()
    return out


def _is_heading_like(line: PDFLine) -> bool:
    t = line.text.strip()
    # Bibliography headings are usually short. This also filters incidental mentions.
    return len(t) <= 140 and is_ref_heading(t)


def _heading_quality(text: str) -> Tuple[float, str]:
    """Return conservative heading evidence without using downstream counts."""
    t = _strip_heading_prefix(text)
    exact = {
        "referencias", "referencias bibliograficas", "bibliografia",
        "bibliography", "references", "obras citadas", "fuentes bibliograficas",
    }
    if t in exact:
        return 1.0, "exact_reference_heading"
    return 0.78, "ocr_or_qualified_reference_heading"


def _style_support(profile: StyleProfile) -> int:
    if profile.style == "numeric":
        return profile.numeric_starts
    if profile.style == "bracket_key":
        return profile.bracket_key_starts
    if profile.style == "author_initial":
        return profile.author_initial_year_starts
    if profile.style == "author_year_comma":
        return profile.author_comma_year_starts
    if profile.style == "institutional":
        return profile.institutional_year_starts
    return max(
        profile.numeric_starts, profile.bracket_key_starts,
        profile.author_comma_year_starts, profile.author_initial_year_starts,
        profile.institutional_year_starts,
    )


def _zone_confidence(
    heading_text: str,
    profile: StyleProfile,
    n_segments: int,
    termination_reason: str,
) -> Tuple[float, str, List[str]]:
    """Score zone evidence; this is diagnostic confidence, not empirical accuracy."""
    heading_score, heading_reason = _heading_quality(heading_text)
    support = _style_support(profile)
    repeated_start_score = min(support / 5.0, 1.0)
    segment_score = min(n_segments / 5.0, 1.0)
    style_score = 0.55 if profile.style == "mixed" else 1.0
    termination_scores = {
        "next_reference_heading": 1.0,
        "explicit_stop_heading": 1.0,
        "density_drop": 0.82,
        "max_chapter_pages": 0.68,
        "end_of_document": 0.78,
    }
    termination_score = termination_scores.get(termination_reason, 0.55)
    score = (
        0.28 * heading_score
        + 0.24 * repeated_start_score
        + 0.20 * segment_score
        + 0.14 * style_score
        + 0.14 * termination_score
    )
    score = round(max(0.0, min(score, 1.0)), 3)
    label = "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"
    reasons = [
        heading_reason,
        f"style_{profile.style}",
        f"style_support_{support}",
        f"segments_{n_segments}",
        f"terminated_by_{termination_reason}",
    ]
    if profile.style == "mixed":
        reasons.append("mixed_style_penalty")
    if support < 3:
        reasons.append("limited_repeated_boundary_evidence")
    return score, label, reasons


def detect_zones(pdf_lines: List[PDFLine], max_chapter_pages: int = 25) -> List[Zone]:
    """Detect explicit bibliography zones and trim over-capture by reference density.

    A critical lesson from the development corpus is that an explicit bibliography heading
    does not imply that the zone runs until the next chapter heading. Some theses place a
    short bibliography and then immediately resume prose without a structural stop heading.
    Therefore, after detecting a heading we also watch page-level reference starts and close
    the zone after two consecutive pages with no new starts once references have begun.
    """
    if not pdf_lines:
        return []
    headings = [i for i, ln in enumerate(pdf_lines) if _is_heading_like(ln)]
    heading_set = set(headings)
    zones: List[Zone] = []
    max_page = max(x.page for x in pdf_lines)

    for hi, idx in enumerate(headings):
        h = pdf_lines[idx]
        stop_idx = None
        termination_reason = "end_of_document"

        for j in range(idx + 1, len(pdf_lines)):
            ln = pdf_lines[j]
            if j in heading_set:
                stop_idx = j
                termination_reason = "next_reference_heading"
                break
            if is_stop_heading(ln.text):
                stop_idx = j
                termination_reason = "explicit_stop_heading"
                break
            if h.page / max(max_page, 1) < 0.60 and ln.page > h.page + max_chapter_pages:
                stop_idx = j
                termination_reason = "max_chapter_pages"
                break

        if stop_idx is None:
            stop_idx = len(pdf_lines)

        body = [ln for ln in pdf_lines[idx + 1:stop_idx] if ln.page >= h.page]
        body = [ln for ln in body if not _is_heading_like(ln)]
        if not body:
            continue

        # Diagnose the bibliography style from the first few pages after the heading,
        # reducing contamination by later prose when the zone endpoint is unclear.
        preview_end = h.page + 4
        preview = [ln.text for ln in body if ln.page <= preview_end]
        style = diagnose_style(preview if preview else [x.text for x in body])

        # Page-density trim: after references have actually started, two consecutive
        # pages with zero new reference starts signal that bibliography likely ended.
        page_order = []
        page_lines: Dict[int, List[PDFLine]] = {}
        for ln in body:
            if ln.page not in page_lines:
                page_order.append(ln.page)
                page_lines[ln.page] = []
            page_lines[ln.page].append(ln)

        seen_starts = 0
        zero_run: List[int] = []
        cut_page = None
        for p in page_order:
            nstarts = sum(is_reference_start(x.text, style) for x in page_lines[p])
            if nstarts > 0:
                seen_starts += nstarts
                zero_run = []
            elif seen_starts >= 3:
                zero_run.append(p)
                if len(zero_run) >= 2:
                    cut_page = zero_run[0]
                    break

        if cut_page is not None:
            body = [ln for ln in body if ln.page < cut_page]
            termination_reason = "density_drop"

        if not body:
            continue

        # Re-diagnose on the trimmed zone.
        style = diagnose_style([x.text for x in body])
        segments_for_confidence = segment_lines([x.text for x in body], style)
        conf_score, conf_label, conf_reasons = _zone_confidence(
            h.text, style, len(segments_for_confidence), termination_reason
        )
        zones.append(Zone(
            heading_page=h.page,
            heading_text=h.text,
            start_page=h.page,
            end_page=max(x.page for x in body),
            lines=body,
            style=style,
            termination_reason=termination_reason,
            confidence_score=conf_score,
            confidence_label=conf_label,
            confidence_reasons=conf_reasons,
        ))
    return zones


def reference_fingerprint(reference_text: str) -> str:
    """Conservative punctuation-insensitive identity key for exact duplicate reporting."""
    normalized = norm_text(reference_text)
    normalized = re.sub(r"https?\s*:\s*/\s*/", "http", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _annotate_duplicates(records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    by_fp: Dict[str, List[int]] = {}
    for i, rec in enumerate(records):
        fp = reference_fingerprint(rec.get("reference_text", ""))
        rec["reference_fingerprint"] = fp
        if fp:
            by_fp.setdefault(fp, []).append(i)

    reports: List[Dict] = []
    group_no = 0
    for fp, indices in by_fp.items():
        if len(indices) < 2:
            continue
        group_no += 1
        gid = f"DUP{group_no:04d}"
        zone_ids = sorted({int(records[i]["zone_id"]) for i in indices})
        pages = sorted({int(records[i]["zone_start_page"]) for i in indices})
        for i in indices:
            records[i].update({
                "duplicate_group_id": gid,
                "duplicate_occurrence_count": len(indices),
                "duplicate_zone_ids": ";".join(map(str, zone_ids)),
                "is_repeated_across_zones": len(zone_ids) > 1,
            })
        reports.append({
            "duplicate_group_id": gid,
            "reference_fingerprint": fp,
            "occurrence_count": len(indices),
            "zone_ids": zone_ids,
            "zone_start_pages": pages,
            "canonical_reference_text": records[indices[0]]["reference_text"],
        })

    for rec in records:
        rec.setdefault("duplicate_group_id", "")
        rec.setdefault("duplicate_occurrence_count", 1)
        rec.setdefault("duplicate_zone_ids", str(rec.get("zone_id", "")))
        rec.setdefault("is_repeated_across_zones", False)
    return records, reports


def _select_scope(records: List[Dict], scope: Scope, final_zone_id: Optional[int] = None) -> List[Dict]:
    if scope == "all_reference_sections":
        return [dict(r) for r in records]
    if scope == "final_reference_section":
        if final_zone_id is None and not records:
            return []
        final_zone = final_zone_id if final_zone_id is not None else max(int(r["zone_id"]) for r in records)
        return [dict(r) for r in records if int(r["zone_id"]) == final_zone]
    # unique_references: retain the first occurrence and carry provenance forward.
    seen = set()
    selected = []
    for rec in records:
        fp = rec.get("reference_fingerprint", "")
        identity = fp or f"record:{rec.get('zone_id')}:{rec.get('ref_in_zone')}"
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(dict(rec))
    return selected


def process_pdf(pdf_path: str | Path, scope: Scope = "all_reference_sections") -> Dict:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}; choose one of {sorted(VALID_SCOPES)}")
    lines = extract_pdf_lines(pdf_path)
    zones = detect_zones(lines)
    records = []
    zone_summaries = []
    for zi, z in enumerate(zones, start=1):
        segs = segment_lines([x.text for x in z.lines], z.style)
        for ri, s in enumerate(segs, start=1):
            s = dict(s)
            s.update({
                "zone_id": zi,
                "ref_in_zone": ri,
                "zone_heading": z.heading_text,
                "zone_start_page": z.start_page,
                "zone_end_page": z.end_page,
                "zone_confidence_score": z.confidence_score,
                "zone_confidence_label": z.confidence_label,
                "zone_confidence_kind": "rule_based_structural_evidence",
                "zone_termination_reason": z.termination_reason,
            })
            records.append(s)
        zone_summaries.append({
            "zone_id": zi,
            "heading": z.heading_text,
            "start_page": z.start_page,
            "end_page": z.end_page,
            "style": z.style.style if z.style else None,
            "n_segments": len(segs),
            "termination_reason": z.termination_reason,
            "confidence_score": z.confidence_score,
            "confidence_label": z.confidence_label,
            "confidence_kind": "rule_based_structural_evidence",
            "confidence_reasons": z.confidence_reasons or [],
            **(asdict(z.style) if z.style else {}),
        })
    occurrences, duplicate_groups = _annotate_duplicates(records)
    selected_records = _select_scope(occurrences, scope, final_zone_id=len(zones) if zones else None)
    return {
        "pdf": str(pdf_path),
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_pdf_lines": len(lines),
        "n_zones": len(zones),
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(g["occurrence_count"] for g in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(g["occurrence_count"] - 1 for g in duplicate_groups),
        "n_records_selected": len(selected_records),
        "zones": zone_summaries,
        "duplicate_groups": duplicate_groups,
        "records": selected_records,
    }


if __name__ == "__main__":
    import argparse, json, csv
    ap = argparse.ArgumentParser(description="BiblioRef v0.2 auditable adaptive reference segmenter")
    ap.add_argument("pdf", help="Input PDF")
    ap.add_argument("--json", dest="json_out", help="Output JSON")
    ap.add_argument("--csv", dest="csv_out", help="Output CSV")
    ap.add_argument(
        "--scope", choices=sorted(VALID_SCOPES), default="all_reference_sections",
        help="Reference universe to return; all occurrences and duplicate provenance remain auditable.",
    )
    args = ap.parse_args()
    result = process_pdf(args.pdf, scope=args.scope)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_out:
        rows = result["records"]
        if rows:
            with open(args.csv_out, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader(); w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ("records", "duplicate_groups")}, ensure_ascii=False, indent=2))
