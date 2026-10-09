# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.2.

The PDF extractor/segmenter remains authoritative.  This parser consumes one
already-segmented reference and structures internal metadata.  v0.2 improves
journal, publication type, publisher and author parsing while deliberately
reusing the v0.1 year/title/DOI outputs as no-regression invariants.

The bundled journal/publisher lexicons were derived from the project's
29,470-reference DEVELOPMENT corpus.  They are normalization aids, not an
external benchmark and never affect segmentation.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from .legacy import parse_reference as _legacy_parse
from .lexicons_v02 import JOURNAL_ALIASES, PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.2"
PARSER_SCHEMA_VERSION = 2
PARSER_STATUS = "development_candidate"

_DOI_RE = re.compile(r'(10\.\d{4,9}/[^\s"<>]+)', re.I)
_YEAR_PAREN_RE = re.compile(r'\(\s*((?:18|19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)', re.I)
_YEAR_BARE_RE = re.compile(r'\b(?:18|19|20)\d{2}[a-z]?\b', re.I)

THESIS_RE = re.compile(r'\b(tesis(?:\s+doctoral|\s+de\s+(?:maestr[ií]a|licenciatura))?|doctoral thesis|ph\.?d\.? thesis|dissertation|trabajo final|trabajo de grado)\b', re.I)
CONF_RE = re.compile(r'\b(congreso|conference|conferencia|simposio|symposium|jornadas|encuentro(?:\s+(?:nacional|internacional|argentino))?|annual meeting|proceedings\s+of)\b', re.I)
GUIDE_RE = re.compile(r'\b(manual|gu[ií]a|guideline|clasificaci[oó]n internacional|diagnostic and statistical manual|dsm[- ]?[ivx0-9]+|cie[- ]?\d+)\b', re.I)
REPORT_RE = re.compile(r'\b(report|informe|working paper|documento de trabajo|technical report|research report|policy brief)\b', re.I)
LEGAL_RE = re.compile(r'\b(ley\s*(?:n[°ºo]\.?\s*)?\d+|decreto\s*(?:n[°ºo]\.?\s*)?\d+|resoluci[oó]n\s*(?:n[°ºo]\.?\s*)?\d+|bolet[ií]n oficial)\b', re.I)
WEB_RE = re.compile(r'https?://|www\.', re.I)
CHAPTER_RE = re.compile(r'(?:^|[\.])\s*(?:En|In)\s+.+?(?:\(\s*(?:Ed\.?|Eds\.?|Comp\.?|Comps\.?|Dir\.?|Dirs\.?)\s*\)|\b(?:Ed\.?|Eds\.?|Comp\.?|Comps\.?|Coord\.?|Coords\.?)\b)', re.I)
PAGES_RE = re.compile(r'\bpp?\.?\s*\d{1,5}\s*[-–—]\s*\d{1,5}|\(\s*pp?\.?\s*\d', re.I)
BOOK_EDITOR_RE = re.compile(r'\b(ed\.|eds\.|comp\.|comps\.|coord\.|coords\.|dir\.|dirs\.)', re.I)
BOOK_CUE_RE = re.compile(r'\b(editorial|ediciones|editores|press|publishing|publishers?|verlag|paid[oó]s|amorrortu|siglo\s+xxi|routledge|springer|wiley|sage|gedisa|eudeba|alianza|anagrama|biblos|manantial|morata|trotta|guilford|erlbaum|pearson|mcgraw|fondo de cultura|c[aá]tedra)\b', re.I)
ARTICLE_WORD_RE = re.compile(r'\b(journal|revista|review|psychology|psychiatry|medicine|science|research|therapy|cortex|neuro|anales|anuario)\b', re.I)

_META_PATTERNS = [
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*\(\s*(?:\d+|suppl\.?\s*\d*|supl\.?\s*\d*)\s*\)\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d{1,5}(?:\s*[-–—]\s*[A-Za-z]?\d{1,5})?', re.I),
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d{1,5}(?:\s*[-–—]\s*[A-Za-z]?\d{1,5})', re.I),
    re.compile(r'\s*,?\s*(?:n[º°o]\.?\s*)?\d{1,4}\s*\(\s*\d+\s*\)', re.I),
    re.compile(r'\s+N[°ºo]\s*\d+\s*\(\s*\d+\s*\)', re.I),
]


def _norm(s: Any) -> str:
    if s is None:
        return ""
    text = str(s).casefold().replace("&", " and ")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_auth_year(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    m = _YEAR_PAREN_RE.search(t)
    if m and m.start() < 220:
        return t[m.end():].lstrip(" .,:;")
    m = _YEAR_BARE_RE.search(t)
    if m and m.start() < 180:
        return t[m.end():].lstrip(" .,:;)")
    return t


def _is_chapter(text: str) -> bool:
    return bool(CHAPTER_RE.search(text) and (PAGES_RE.search(text) or BOOK_EDITOR_RE.search(text)))


def _canonicalize_candidate(candidate: Optional[str], aliases: Dict[str, str]) -> Optional[str]:
    if not candidate:
        return None
    n = _norm(candidate)
    if not n:
        return None
    if n in aliases:
        canonical = aliases[n]
        # If the lexicon only differs in punctuation/capitalization, preserve
        # the document's own journal spelling. Use the canonical label only
        # when it actually repairs a lexical variant/typo.
        if _norm(canonical) == n:
            return candidate.strip(" .,:;")
        return canonical
    padded = f" {n} "
    best: Optional[tuple[int, str]] = None
    # Candidate strings are short, so a linear scan is acceptable and keeps the
    # lexicon transparent.  Exact normalized candidates are handled above.
    for alias, canonical in aliases.items():
        if len(alias) < 5:
            continue
        if f" {alias} " in padded:
            score = len(alias)
            if best is None or score > best[0]:
                best = (score, canonical)
    return best[1] if best else candidate.strip(" .,:;")


def _journal_candidate(text: str, legacy_title: str) -> Optional[str]:
    if _is_chapter(text):
        return None
    t = _strip_auth_year(text)
    t = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)', t, maxsplit=1, flags=re.I)[0].strip()
    title = str(legacy_title or "").strip()
    source = t
    title_removed = False
    if title and _norm(t).startswith(_norm(title)):
        pos = t.casefold().find(title.casefold())
        if pos >= 0:
            tail = t[pos + len(title):].lstrip(" .,:;")
            if tail:
                source = tail
                title_removed = True
    first_meta = None
    for pat in _META_PATTERNS:
        m = pat.search(source)
        if m and (first_meta is None or m.start() < first_meta.start()):
            first_meta = m
    if not first_meta:
        return None
    candidate = source[:first_meta.start()].strip(" .,:;")
    if not title_removed:
        boundaries = list(re.finditer(r"[.!?]\s+(?=[A-ZÁÉÍÓÚÑ])", candidate))
        if boundaries:
            candidate = candidate[boundaries[-1].end():].strip(" .,:;")
    candidate = re.sub(r"^(?:In|En)\s+", "", candidate, flags=re.I).strip()
    if not (2 <= len(candidate) <= 180 and len(candidate.split()) <= 18):
        return None
    return candidate


def extract_journal(text: str, legacy_title: str) -> Optional[str]:
    return _canonicalize_candidate(_journal_candidate(text, legacy_title), JOURNAL_ALIASES)


def _publisher_source_tail(text: str, legacy_source: str) -> str:
    # v0.1's source field is often noisy but usefully starts after the title.
    # It is used only as a search window; the returned publisher is isolated.
    source = str(legacy_source or "").strip()
    return source if source else _strip_auth_year(text)


def extract_publisher(text: str, legacy_source: str) -> Optional[str]:
    source = _publisher_source_tail(text, legacy_source)
    n = _norm(source)
    if not n:
        return None
    padded = f" {n} "
    best: Optional[tuple[int, str]] = None
    for alias, canonical in PUBLISHER_ALIASES.items():
        if f" {alias} " in padded:
            score = len(alias)
            if best is None or score > best[0]:
                best = (score, canonical)
    if best:
        return best[1]
    # General unseen-publisher fallbacks.  These are deliberately conservative.
    patterns = [
        r"\b((?:The\s+)?(?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'’.-]*\s+){0,5}(?:University\s+Press|Press|Publishing|Publishers|Verlag))\b",
        r"\b((?:Editorial|Ediciones?)\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'’.-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'’.-]*){0,5})\b",
    ]
    for pat in patterns:
        m = re.search(pat, source)
        if m:
            cand = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;")
            if 4 <= len(cand) <= 100:
                return cand
    return None


def classify_document(text: str, journal: Optional[str], publisher: Optional[str]) -> str:
    t = str(text or "")
    if LEGAL_RE.search(t):
        return "documento_legal"
    if THESIS_RE.search(t):
        return "tesis"
    if _is_chapter(t):
        return "capitulo_libro"
    if CONF_RE.search(t):
        return "conference_paper"
    if journal:
        return "articulo_revista"
    if re.search(r"\b\d{1,4}\s*\(\s*\d+\s*\)\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d", t):
        return "articulo_revista"
    if re.search(r"\b\d{1,4}\s*[,;:]\s*\d{1,5}\s*[-–—]\s*\d{1,5}\b", t) and not BOOK_CUE_RE.search(t):
        return "articulo_revista"
    if _DOI_RE.search(t) and ARTICLE_WORD_RE.search(t):
        return "articulo_revista"
    if GUIDE_RE.search(t):
        return "documento_guia_manual"
    if REPORT_RE.search(t):
        return "informe_documento"
    if publisher or BOOK_CUE_RE.search(t) or re.search(r"\b[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .-]{2,40}:\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ &.-]{2,80}\.?\s*$", t):
        return "libro"
    if WEB_RE.search(t):
        return "material_web"
    return "sin_clasificar"


def _format_initials(value: str) -> str:
    s = re.sub(r"\s+", " ", value.strip(" ,.;:"))
    if not s:
        return s
    # Compact initials: MJ / M.J. / M J -> M. J.
    compact = re.sub(r"[.\s-]", "", s)
    if compact.isalpha() and compact.upper() == compact and 1 <= len(compact) <= 4:
        return " ".join(ch + "." for ch in compact)
    return s


def _first_author_from_block(block: str) -> Optional[str]:
    """Extract only the leading author conservatively.

    Handles APA-like ``Surname, S.`` as well as compact OCR initials such as
    ``Surname, LI,`` without needing to solve the full author-list grammar.
    """
    b = re.sub(r"\s+", " ", str(block or "")).strip(" ,;:")
    if not b:
        return None
    # Surname, initials.  The look-ahead prevents consuming the next surname.
    m = re.match(
        r"^([^,]{2,80}),\s*((?:[A-ZÁÉÍÓÚÑ](?:\.)?\s*){1,4}|[A-ZÁÉÍÓÚÑ]{1,4})(?=\s*(?:,|;|&|\by\b|\band\b|$))",
        b,
    )
    if m:
        surname = m.group(1).strip()
        initials = _format_initials(m.group(2))
        return f"{surname}, {initials}".strip()
    # Full given name after comma, e.g. ``Lacan, Jacques``.
    m = re.match(r"^([^,]{2,80}),\s*([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]{2,35})(?=\s*(?:,|;|&|\by\b|\band\b|$))", b)
    if m:
        return f"{m.group(1).strip()}, {m.group(2).strip()}"
    return None


def _parse_comma_author_pairs(piece: str) -> List[str]:
    """Parse repeated ``Surname, initials`` pairs inside one separator block."""
    parts = [p.strip() for p in piece.split(",") if p.strip()]
    if len(parts) < 2 or len(parts) % 2:
        return []
    out: List[str] = []
    for i in range(0, len(parts), 2):
        surname, given = parts[i], parts[i + 1]
        if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", surname):
            return []
        compact = re.sub(r"[.\s-]", "", given)
        is_initials = bool(compact and compact.isalpha() and compact.upper() == compact and len(compact) <= 4)
        is_given = bool(re.fullmatch(r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]{2,35}", given))
        if not (is_initials or is_given):
            return []
        out.append(f"{surname}, {_format_initials(given) if is_initials else given}")
    return out


def extract_authors(text: str, legacy_authors: str) -> tuple[Optional[str], str]:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    t = re.sub(r"^[\d.\-\s\[\]]+", "", t)
    m = _YEAR_PAREN_RE.search(t)
    block = t[:m.start()].strip(" ,.;:") if m and m.start() < 240 else ""
    if not block:
        # Older styles: "Lacan, Jacques: Title..., 1973" or "Laplanche, Jean. Title... 1980".
        m2 = re.match(r"^([^:]{2,80}?,\s*[^:.,]{1,40})(?:[:.]\s+)", t)
        if m2:
            block = m2.group(1).strip()
    if not block:
        legacy_first = (legacy_authors or "").split("|")[0].strip(" ,.")
        return (legacy_first or None), legacy_authors or ""

    # Institutional author without personal-name punctuation.
    if "," not in block and re.search(r"\b(organization|organisation|association|society|ministerio|universidad|university|instituto|institute|who|oms|ops|unesco|unicef)\b", block, re.I):
        return block, block

    # Split strong separators first.  Commas remain inside "Surname, Initials".
    pieces = [p.strip(" ,.") for p in re.split(r"\s*(?:;|&|\by\b|\band\b)\s*", block, flags=re.I) if p.strip(" ,.")]
    expanded: List[str] = []
    for piece in pieces:
        pairs = _parse_comma_author_pairs(piece)
        if pairs:
            expanded.extend(pairs)
            continue
        # Parse repeated APA pairs inside a comma-separated piece.
        matches = list(re.finditer(r"(?:^|,\s*)([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\- ]{1,45}),\s*((?:[A-ZÁÉÍÓÚÑ](?:\.|\b)\s*){1,4}|[A-ZÁÉÍÓÚÑ][a-záéíóúñ'’\-]+)(?=,\s*[A-ZÁÉÍÓÚÑ]|$)", piece))
        if matches:
            expanded.extend((m.group(1).strip() + ", " + _format_initials(m.group(2))) for m in matches)
        else:
            # Common single personal author.
            m3 = re.match(r"^([^,]{2,60}),\s*(.{1,40})$", piece)
            if m3:
                expanded.append(m3.group(1).strip() + ", " + _format_initials(m3.group(2)))
            else:
                expanded.append(piece)
    # Deduplicate while preserving order.
    clean: List[str] = []
    for a in expanded:
        a = re.sub(r"\b(et al\.?|eds?\.?|comps?\.?|dirs?\.?|orgs?\.?)\b", "", a, flags=re.I)
        a = re.sub(r"\s+", " ", a).strip(" ,")
        if len(a) > 2 and a not in clean:
            clean.append(a)
    if not clean:
        legacy_first = (legacy_authors or "").split("|")[0].strip(" ,.")
        return (legacy_first or None), legacy_authors or ""
    first = _first_author_from_block(block) or clean[0]
    return first, " | ".join(clean)


def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    old = _legacy_parse(text)

    journal = extract_journal(text, old.get("title") or "")
    # Publisher lexicon is consulted before type classification; publisher output
    # is suppressed for article references afterward.
    publisher = extract_publisher(text, old.get("source_publisher") or "")
    publication_type = classify_document(text, journal, publisher)
    if publication_type != "articulo_revista":
        journal = None
    if publication_type == "articulo_revista":
        publisher = None
    elif publication_type not in {"libro", "capitulo_libro"}:
        # Preserve the v2 pipeline invariant: publisher is asserted only for
        # monographic references. Other source organizations stay in raw text.
        publisher = None
    author, authors = extract_authors(text, old.get("authors") or "")

    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "parser_status": PARSER_STATUS,
        "author": author,
        "authors": authors,
        # Invariants: these three values come directly from the v0.1 parser.
        "year": old.get("year"),
        "publication_type": publication_type,
        "title": old.get("title"),
        "journal": journal,
        "publisher": publisher,
        "source_publisher": publisher,
        "doi": old.get("doi"),
    }


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    parsed = parsed or {}
    fields = (
        "parser_version", "parser_status", "author", "authors", "year",
        "publication_type", "title", "journal", "publisher", "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
