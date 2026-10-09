# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.5.

v0.5 adds an explicit, conservative ABNT-family route downstream from the
validated extraction/segmentation engine.  The route was developed from the
10 USP/Pizzimenti references already consumed by the v0.4 external holdout;
those rows are therefore development/regression data for v0.5, never external
validation.

The new route is structural rather than repository-specific.  It requires:
- an uppercase surname + initials author block at the beginning;
- no parenthesized author-year prefix;
- a bibliographic year near the end of the citation (before retrieval/access
  metadata when present);
- an independently delimited title followed by a source/publisher tail.

Supported ABNT families include:
- AUTHOR. Title. Place: Publisher, YEAR.
- AUTHOR. Title. Journal, [Place,] v. N, n. N, p. N-N, YEAR.
- AUTHOR. Chapter title. In./In: Container ... Place: Publisher, YEAR.

Raw citation text remains authoritative.  No PDF/reference boundary logic is
changed by this module.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from . import v04 as _v04
from . import v03 as _v03
from .lexicons_v02 import PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.5"
PARSER_SCHEMA_VERSION = 5
PARSER_STATUS = "development_candidate"

# One ABNT personal author: SILVA, A. B. / D'ÁVILA, M. / DE SOUZA, J.
_ABNT_SURNAME = r"[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ][A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ'’\- ]{1,70}"
_ABNT_INITIALS = r"(?:[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ]\.\s*){1,5}"
_ABNT_PERSON = rf"{_ABNT_SURNAME},\s*{_ABNT_INITIALS}"
_ABNT_AUTHORS_RE = re.compile(
    rf"^(?P<authors>{_ABNT_PERSON}(?:\s*;\s*{_ABNT_PERSON})*)\s+",
    re.UNICODE,
)
_ABNT_YEAR_RE = re.compile(r"\b((?:18|19|20)\d{2})[a-z]?\b", re.I)
_ABNT_ACCESS_RE = re.compile(
    r"\b(?:Dispon[ií]vel\s+em|Acesso\s+em|Acessado\s+em|Consultado\s+em|Retrieved\s+(?:from|on))\b",
    re.I,
)
_ABNT_CHAPTER_RE = re.compile(r"^(?:In\.?|Em)\s*[:.]?\s+", re.I)
_ABNT_ARTICLE_META_RE = re.compile(
    r",\s*(?:v(?:ol)?\.?\s*\d+|n[º°o]?\.?\s*\d+|p{1,2}\.?\s*[A-Za-z]?\d+|e\d{4,})\b",
    re.I,
)
_ABNT_RETRIEVAL_RE = re.compile(r"\s+(?:Dispon[ií]vel\s+em|Acesso\s+em|Acessado\s+em|Consultado\s+em)\s*:?.*$", re.I)
_ABNT_JOURNAL_CUE_RE = re.compile(
    r"\b(?:revista|journal|review|anales|annals|boletim|bulletin|cadernos|arquivos|"
    r"psicologia|psican[aá]lise|sa[uú]de|educa[cç][aã]o|ci[eê]ncia|ci[eê]ncias|"
    r"sociedade|estudos|pesquisa|trabalho)\b",
    re.I,
)


def _norm(value: Any) -> str:
    return _v03._norm(value)


def _split_abnt_author_block(text: str) -> Optional[Dict[str, str]]:
    m = _ABNT_AUTHORS_RE.match(text)
    if not m:
        return None
    block = re.sub(r"\s+", " ", m.group("authors")).strip(" .;")
    persons = [re.sub(r"\s+", " ", x).strip(" .;") for x in re.split(r"\s*;\s*", block) if x.strip()]
    if not persons:
        return None
    # Keep terminal periods on initials in the human-readable author fields.
    # The regex consumes the punctuation, so normalize only spacing here.
    first_raw = re.split(r"\s*;\s*", m.group("authors"))[0].strip()
    all_raw = [x.strip() for x in re.split(r"\s*;\s*", m.group("authors")) if x.strip()]
    return {
        "author": first_raw.rstrip(" ;"),
        "authors": " | ".join(x.rstrip(" ;") for x in all_raw),
        "rest": text[m.end():].strip(),
    }


def _abnt_core_before_access(text: str) -> str:
    m = _ABNT_ACCESS_RE.search(text)
    return text[:m.start()].rstrip(" .;,") if m else text.rstrip(" .;,")


def _abnt_year(core: str) -> Optional[re.Match[str]]:
    matches = list(_ABNT_YEAR_RE.finditer(core))
    if not matches:
        return None
    m = matches[-1]
    # ABNT publication year should be late in the reference.  This rejects
    # uppercase-author strings that merely mention a year inside a title.
    if m.start() < max(12, int(len(core) * 0.55)):
        return None
    # Only punctuation/short month text may follow publication year in the core.
    after = core[m.end():].strip(" .;,)")
    if len(after) > 12:
        return None
    return m


def _split_abnt_title(rest_before_year: str) -> Optional[Dict[str, str]]:
    """Split the first full-stop-delimited work title from its source tail."""
    s = rest_before_year.strip(" ;,")
    # A title can contain colons, dashes and question marks.  ABNT source begins
    # after the first full stop followed by whitespace and an uppercase/source
    # token.  Avoid single-letter abbreviation boundaries.
    for m in re.finditer(r"\.\s+(?=[(A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ])", s):
        title = s[:m.start()].strip(" .;,")
        tail = s[m.end():].strip(" ;,")
        if len(title) < 3 or len(title.split()) < 2 or not tail:
            continue
        # ``Trad.`` / ``Org.`` immediately after title are descriptors, not the
        # source boundary.  The title itself is still valid; descriptors stay in
        # the tail where publisher extraction can ignore them.
        return {"title": title, "tail": tail}
    return None


def _abnt_journal(tail: str) -> Optional[str]:
    """Recover journal name before ABNT v./n./p. metadata."""
    m = _ABNT_ARTICLE_META_RE.search(tail)
    if not m:
        return None
    prefix = tail[:m.start()].strip(" .;,")
    if not prefix:
        return None

    # ABNT commonly inserts city between journal and volume:
    # ``A Peste: Revista ..., São Paulo, v. 1``.  Remove the last comma segment
    # only when the preceding source has an explicit journal cue and the final
    # segment looks like a short proper-name location.
    parts = [p.strip() for p in prefix.split(",")]
    if len(parts) >= 2:
        last = parts[-1]
        before = ", ".join(parts[:-1]).strip()
        location_like = (
            1 <= len(last.split()) <= 4
            and not _ABNT_JOURNAL_CUE_RE.search(last)
            and bool(re.fullmatch(r"[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ][\wÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑáàâãéèêíìóòôõúùüçñ .'-]{1,50}", last))
        )
        if location_like and _ABNT_JOURNAL_CUE_RE.search(before):
            prefix = before

    if len(prefix) > 200 or len(prefix.split()) > 20:
        return None
    return prefix.strip(" .;,") or None


def _abnt_publisher(tail: str) -> tuple[Optional[str], Optional[str]]:
    """Return (canonical, observed) publisher from ``Place: Publisher`` tail."""
    cleaned = _ABNT_RETRIEVAL_RE.sub("", tail).strip(" ,;")
    # Ignore translation/editor descriptors that may precede place.
    cleaned = re.sub(r"^\((?:Trad\.|Tradu[cç][aã]o|Org\.|Organiza[cç][aã]o)[^)]*\)\.\s*", "", cleaned, flags=re.I)
    if ":" not in cleaned:
        return None, None
    raw_observed = cleaned.rsplit(":", 1)[1].strip(" ,;")
    keep_abbrev_period = bool(re.search(r"\bEd\.\s*$", raw_observed, re.I))
    observed = raw_observed if keep_abbrev_period else raw_observed.rstrip(".")
    if not observed or len(observed) > 140 or len(observed.split()) > 14 or re.search(r"https?://", observed, re.I):
        return None, None
    # Reject location/date fragments mistaken for publishers.
    if re.search(r"\b(?:v|n|p)\.?\s*\d", observed, re.I):
        return None, None

    canonical = observed
    # ``Jorge Zahar Ed.`` is an abbreviated imprint suffix.  Preserve it in
    # publisher_observed while canonical publisher strips only this terminal
    # abbreviation; full words Editora/Editorial remain part of the imprint.
    canonical = re.sub(r"\s+Ed\.?$", "", canonical, flags=re.I).strip(" .;,")
    alias = PUBLISHER_ALIASES.get(_norm(canonical))
    if alias:
        canonical = alias
    return canonical or observed, observed


def _parse_abnt(text: str) -> Optional[Dict[str, Any]]:
    """Parse a structurally supported ABNT-family reference, otherwise abstain."""
    if not text or _v03._YEAR_PAREN_RE.search(text[:280]):
        return None
    ab = _split_abnt_author_block(text)
    if not ab:
        return None

    core = _abnt_core_before_access(text)
    ym = _abnt_year(core)
    if not ym:
        return None

    # Recompute rest/core coordinates after the author block so the publication
    # year can be stripped without relying on repository-specific punctuation.
    prefix_len = len(text) - len(ab["rest"])
    if ym.start() <= prefix_len:
        return None
    rest_before_year = core[prefix_len:ym.start()].rstrip(" ;,")
    split = _split_abnt_title(rest_before_year)
    if not split:
        return None
    title, tail = split["title"], split["tail"]

    is_chapter = bool(_ABNT_CHAPTER_RE.match(tail))
    journal = None if is_chapter else _abnt_journal(tail)
    if journal:
        publication_type = "articulo_revista"
        publisher = publisher_observed = None
    else:
        publisher, publisher_observed = _abnt_publisher(tail)
        publication_type = "capitulo_libro" if is_chapter else ("libro" if publisher else "sin_clasificar")

    # Web access metadata does not override a structurally identified article.
    return {
        "author": ab["author"],
        "authors": ab["authors"],
        "year": ym.group(1),
        "title": title,
        "journal": journal,
        "publication_type": publication_type,
        "publisher": publisher,
        "publisher_observed": publisher_observed,
    }


def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    base = _v04.parse_reference(text)
    abnt = _parse_abnt(text)
    if not abnt:
        out = dict(base)
        out["schema_version"] = PARSER_SCHEMA_VERSION
        out["parser_version"] = PARSER_VERSION
        out["parser_status"] = PARSER_STATUS
        return out

    # DOI remains the mature downstream extraction inherited from v0.4.
    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "parser_status": PARSER_STATUS,
        "parse_style": "abnt_author_title_year_end",
        "author": abnt.get("author") or base.get("author"),
        "authors": abnt.get("authors") or base.get("authors"),
        "year": abnt.get("year") or base.get("year"),
        "publication_type": abnt.get("publication_type") or base.get("publication_type"),
        "title": abnt.get("title") or base.get("title"),
        "journal": abnt.get("journal"),
        "publisher": abnt.get("publisher"),
        "publisher_observed": abnt.get("publisher_observed") or abnt.get("publisher"),
        "source_publisher": abnt.get("publisher"),
        "doi": base.get("doi"),
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
        "parser_version", "parser_status", "parse_style", "author", "authors", "year",
        "publication_type", "title", "journal", "publisher", "publisher_observed", "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
