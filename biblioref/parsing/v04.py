# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.4.

v0.4 is a conservative refinement of parser v0.3. It is downstream from the
validated PDF/reference segmentation engine and never changes extraction
boundaries or raw reference strings.

The v0.3 strict reserve is development/regression data for this revision. The
rules below target general residual families observed there:
- title continuation after question/exclamation marks when the journal boundary
  is independently observable;
- edition statements separated from monograph titles;
- expansion of overly-short contained journal aliases to the complete observed
  journal name;
- preservation of explicit publisher forms (Publishing/Publications/etc.) when
  v0.2/v0.3 canonical aliases collapsed them;
- conservative one-word publisher recovery after chapter page ranges.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from . import v03 as _v03
from . import v02 as _v02
from .lexicons_v02 import PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.4"
PARSER_SCHEMA_VERSION = 4
PARSER_STATUS = "development_candidate"

_EDITION_SUFFIX_RE = re.compile(
    r"\s*[\[(]\s*(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:rev(?:ised)?\.?\s+)?(?:ed(?:ition|n)?\.?|ed\.)\s*[\])]\s*$",
    re.I,
)
_PUBLISHER_WORD_RE = re.compile(
    r"\b(?:Press|Publishing|Publications?|Publishers?|Verlag|Ediciones?|Editorial|Editores?|Books?)\b",
    re.I,
)


def _norm(value: Any) -> str:
    return _v03._norm(value)


def _strip_edition_from_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return title
    t = str(title).strip()
    # Common forms: (2nd ed.), (3rd edition), [2nd ed.], (rev. ed.).
    t2 = _EDITION_SUFFIX_RE.sub("", t).strip(" .,:;")
    return t2 or t


def _source_after_year(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    pm = _v03._YEAR_PAREN_RE.search(t[:280])
    if pm:
        return _v03._strip_links(t[pm.end():].lstrip(" .,:;"))
    bm = _v03._YEAR_BARE_RE.search(t[:340])
    if bm:
        return _v03._strip_links(t[bm.end():].lstrip(" abcdefghijklmnopqrstuvwxyz.,:;"))
    return _v03._strip_links(t)


def _observed_journal(text: str, title: Optional[str], base_journal: Optional[str]) -> Optional[str]:
    """Return a fuller observed journal only with independent structural support."""
    expanded = None
    if _v03._YEAR_PAREN_RE.search(str(text)[:280]):
        expanded = _v03._journal_from_parenthetical(str(text), title or "")
    if not expanded:
        return base_journal
    if not base_journal:
        return expanded

    nb, ne = _norm(base_journal), _norm(expanded)
    if not nb or not ne or nb == ne:
        return expanded if ne else base_journal

    # v0.3 already handled a fixed list of generic tails. v0.4 generalizes the
    # rule: a one-word source such as "Criminology" can be expanded to
    # "The British Journal of Criminology" only when it is a complete token
    # inside the structurally recovered source and the latter contains a strong
    # journal cue. This does not expand arbitrary multiword aliases.
    if len(nb.split()) == 1 and re.search(rf"\b{re.escape(nb)}\b", ne):
        if len(ne.split()) >= 3 and _v03._JOURNAL_CUE_RE.search(expanded):
            return expanded

    # Preserve v0.3's generic-tail protection for other cases.
    generic = {
        "psychotherapy", "psychology", "therapy", "research", "review",
        "journal", "assessment", "psychiatry", "medicine",
    }
    if nb in ne and nb in generic and len(ne) > len(nb):
        return expanded
    return base_journal


def _recover_article_title(text: str, current_title: Optional[str], journal: Optional[str]) -> Optional[str]:
    """Recover title text up to an independently identified journal boundary.

    This fixes titles with internal ``?``/``!`` or more than one sentence
    without changing ordinary one-sentence titles. The recovery is accepted only
    when the observed journal string occurs literally after the year.
    """
    current = _strip_edition_from_title(current_title)
    if not journal:
        return current
    source = _source_after_year(text)
    if not source:
        return current
    pos = source.casefold().find(str(journal).casefold())
    if pos <= 0:
        return current
    candidate = source[:pos].strip(" .,:;")
    candidate = _strip_edition_from_title(candidate)
    if not candidate or len(candidate) > 500 or len(candidate.split()) < 2:
        return current
    if not current:
        return candidate
    nc, nr = _norm(current), _norm(candidate)
    # Only lengthen a title if the old title is a normalized prefix of the
    # observed candidate; never replace it with a conflicting parse.
    if nc and nr.startswith(nc) and len(nr) > len(nc):
        return candidate
    return current


def _publisher_family(value: Optional[str]) -> str:
    n = _norm(value)
    if not n:
        return ""
    canon = PUBLISHER_ALIASES.get(n)
    return _norm(canon) if canon else n


def _publisher_tail(text: str, title: Optional[str], publication_type: str) -> Optional[str]:
    """Recover an observed publisher token/string from the monographic tail."""
    if publication_type not in {"libro", "capitulo_libro", "documento_guia_manual"}:
        return None
    tail = _source_after_year(text)
    if title:
        pos = tail.casefold().find(str(title).casefold())
        if 0 <= pos <= 30:
            tail = tail[pos + len(str(title)):].lstrip(" .,:;")
    # Edition statements belong neither to title nor publisher.
    tail = re.sub(
        r"^[\[(]\s*(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:rev(?:ised)?\.?\s+)?(?:ed(?:ition|n)?\.?|ed\.)\s*[\])]\s*[.,;:]?\s*",
        "", tail, flags=re.I,
    )
    if publication_type == "capitulo_libro":
        # For a chapter, the publisher begins after the container's page range.
        pages = list(re.finditer(r"\(\s*pp?\.?\s*\d{1,6}\s*[-–—]\s*\d{1,6}\s*\)\s*[.,;:]?\s*", tail, re.I))
        if pages:
            tail = tail[pages[-1].end():]
    tail = _v03._strip_links(tail).strip(" .,:;")
    if not tail:
        return None

    # Place: Publisher -> keep the right-hand observed form.
    if ":" in tail:
        right = tail.rsplit(":", 1)[1].strip(" .,:;")
        if right and len(right.split()) <= 14:
            tail = right

    # Stop before retrieval/catalog noise.
    tail = re.split(r"\s+(?:Retrieved|Recuperado|Disponible\s+en)\b", tail, maxsplit=1, flags=re.I)[0]
    cand = tail.strip(" .,:;")
    if not cand or len(cand) > 150 or len(cand.split()) > 16 or re.search(r"\d{3,}", cand):
        return None

    if _PUBLISHER_WORD_RE.search(cand):
        return cand

    # One-word publishers (e.g. Willan, Routledge, Springer) after an explicit
    # chapter page range are structurally strong even without the word Press.
    # Restrict this to chapters and a single capitalized alphabetic token.
    if publication_type == "capitulo_libro" and re.fullmatch(r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’.-]{3,35}", cand):
        return cand
    return None


def _choose_publisher(base_publisher: Optional[str], observed: Optional[str]) -> Optional[str]:
    # Backward-compatible normalized/canonical field. If v0.3 already has a
    # publisher, keep it. The richer literal form is exposed separately as
    # ``publisher_observed`` instead of overwriting the bibliometric field.
    if base_publisher:
        return base_publisher
    return observed


def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    base = _v03.parse_reference(text)

    journal = _observed_journal(text, base.get("title"), base.get("journal"))
    publication_type = base.get("publication_type") or "sin_clasificar"
    if publication_type != "articulo_revista":
        journal = None

    title = _strip_edition_from_title(base.get("title"))
    if publication_type == "articulo_revista":
        title = _recover_article_title(text, title, journal)

    observed_publisher = _publisher_tail(text, title, publication_type)
    publisher = _choose_publisher(base.get("publisher"), observed_publisher)
    if publication_type == "articulo_revista":
        publisher = None
    elif publication_type not in {"libro", "capitulo_libro", "documento_guia_manual"}:
        publisher = None

    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "parser_status": PARSER_STATUS,
        "parse_style": base.get("parse_style"),
        "author": base.get("author"),
        "authors": base.get("authors"),
        "year": base.get("year"),
        "publication_type": publication_type,
        "title": title,
        "journal": journal,
        "publisher": publisher,
        "publisher_observed": observed_publisher or publisher,
        "source_publisher": publisher,
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
