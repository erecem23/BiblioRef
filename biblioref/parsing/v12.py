# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.

v0.12 keeps the validated reference segmentation untouched and strengthens the
bibliographic parser on two fronts:

1. conservative corrections for common APA-like ambiguities observed in field
   use (secondary/access years promoted to publication year, incomplete author
   blocks, title/journal boundary drift, chapter/article confusion and lexical
   publisher false positives);
2. an explicit uncertainty/audit layer.  The parser always emits its best
   interpretation, but when the raw reference contains competing evidence it
   also preserves candidates and review reasons instead of hiding uncertainty.

The audit fields are downstream metadata only.  They never alter PDF geometry,
reference boundaries or extraction provenance.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v11 as _v11

PARSER_VERSION = "biblioref-parser-v0.12"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇ"
_LC = "A-Za-zÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇáéíóúüñàâãèêìòôõùç"
_YEAR_ALL_RE = re.compile(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)")
_APA_HEAD_RE = re.compile(
    r"^(?P<head>.{1,280}?)\s*\(\s*(?P<year>(?:18|19|20)\d{2})[a-z]?"
    r"(?:\s*,[^)]*)?\)\s*\.?\s*(?P<rest>.+)$",
    re.I,
)
_APA_PERSON_RE = re.compile(
    rf"(?P<surname>[{_UC}][{_LC}'’´\- ]*?),\s*"
    rf"(?P<given>(?:[{_UC}]\.\s*){{1,5}})"
)
_ACCESS_RE = re.compile(r"\b(?:Retrieved|Extra[ií]d[oa]|Consultad[oa]|consultado|acceso)\b", re.I)
_URL_RE = re.compile(r"https?\s*:\s*/|www\.", re.I)
_ORG_HINT_RE = re.compile(
    r"\b(?:Universidad|University|UNICEF|Organization|Organisation|Ministerio|Ministry|"
    r"OMS|OPS|WHO|PAHO|Instituto|Institute|Gobierno|Government|Consejo|Council)\b",
    re.I,
)
_CHAPTER_RE = re.compile(r"^(?P<title>.+?)\.\s+(?P<marker>In|En)\s+(?P<container>.+)$", re.I)
_PAGE_MARK_RE = re.compile(r"\(\s*pp?\.\s*\d|\bpp?\.\s*\d", re.I)
_EXPLICIT_THESIS_RE = re.compile(
    r"\b(?:Tesis\s+(?:Doctoral|de\s+Doctorado|de\s+Maestr[ií]a|de\s+Licenciatura)|"
    r"Doctoral\s+Thesis|Ph\.?D\.?\s+Thesis|Dissertation)\b",
    re.I,
)

# Strong article metadata shapes.  These are intentionally anchored to the end
# of the citation so ordinary commas and dates in titles cannot license them.
_ARTICLE_META_PATTERNS = (
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:\d{1,4}|[IVXLCDM]{1,8})\s*"
        r"\(\s*[^)]{1,12}\s*\)\s*,\s*(?:pp?\.\s*)?"
        r"\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*\(\s*(?:\d{1,3}|[IVXLCDM]{1,8})\s*\)\s*,\s*"
        r"(?:pp?\.\s*)?\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:\d{1,4}|[IVXLCDM]{1,8})\s*,\s*"
        r"(?:pp?\.\s*)?\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:pp?\.\s*)?"
        r"\d{1,7}\s*[-–—]\s*\d{1,7}\s*\.?$",
        re.I,
    ),
)
_IN_JOURNAL_RE = re.compile(
    r"^(?P<title>.+?)\.\s+(?:In|En)\s+(?P<journal>.+?)\s*"
    r"\(\s*Vol\.?\s*\d{1,4}\s*,\s*No\.?\s*\d{1,4}\s*,\s*"
    r"pp?\.\s*\d{1,7}\s*[-–—]\s*\d{1,7}\s*\)",
    re.I,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _norm_cmp(value: Any) -> str:
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "", str(value or "").casefold())


def _add_unique(values: List[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _candidate_pair(old: Any, new: Any) -> str:
    vals: List[str] = []
    if old not in (None, ""):
        _add_unique(vals, str(old))
    if new not in (None, ""):
        _add_unique(vals, str(new))
    return " || ".join(vals)


def _apa_authors(head: str) -> List[str]:
    matches = list(_APA_PERSON_RE.finditer(head))
    if matches:
        out: List[str] = []
        for m in matches:
            surname = re.sub(r"\s+", " ", m.group("surname")).strip(" ,;&")
            given = re.sub(r"\s+", " ", m.group("given")).strip()
            if surname and given:
                out.append(f"{surname}, {given}")
        return out
    corporate = head.strip(" .")
    if corporate and "," not in corporate and len(corporate.split()) <= 16:
        return [corporate]
    return []


def _year_evidence(text: str, apa_match: Optional[re.Match[str]]) -> Tuple[List[str], Dict[str, List[str]]]:
    publication_year = apa_match.group("year") if apa_match else None
    access_match = _ACCESS_RE.search(text)
    url_match = _URL_RE.search(text)
    access_start = access_match.start() if access_match else None
    url_start = url_match.start() if url_match else None
    values: List[str] = []
    roles: Dict[str, List[str]] = {}
    for m in _YEAR_ALL_RE.finditer(text):
        year = m.group(1)
        _add_unique(values, year)
        role = "text"
        if apa_match and publication_year == year and m.start() <= apa_match.end("year") + 2:
            role = "publication"
        elif access_start is not None and m.start() >= access_start and (url_start is None or m.start() < url_start):
            role = "access"
        elif url_start is not None and m.start() >= url_start:
            role = "url"
        roles.setdefault(year, [])
        if role not in roles[year]:
            roles[year].append(role)
    return values, roles


def _split_article(rest: str) -> Optional[Tuple[str, str]]:
    s = _clean(rest)

    # Some exports write journal articles as ``Title. In Journal (Vol..., pp...)``.
    m_in = _IN_JOURNAL_RE.match(s)
    if m_in:
        return m_in.group("title").strip(" ."), m_in.group("journal").strip(" .,:;")

    # A genuine book chapter marker blocks the generic page-tail route below.
    if re.search(r"\.\s+(?:In|En)\s+", s, re.I):
        return None

    prefix = None
    for pattern in _ARTICLE_META_PATTERNS:
        m = pattern.match(s)
        if m:
            prefix = m.group("prefix").strip(" ,.")
            break
    if not prefix:
        return None

    boundaries = [m.start() for m in re.finditer(r"\.\s+(?=[A-ZÁÉÍÓÚÜÑ])", prefix)]
    if not boundaries:
        return None
    pos = boundaries[-1]
    title = prefix[:pos].strip(" .")
    journal = prefix[pos + 1 :].strip(" .,:;")
    if not title or not journal or len(journal.split()) > 16:
        return None
    if re.match(r"^(?:Editorial|Ediciones?|Press|Publishing)\b", journal, re.I):
        return None
    return title, journal


def _split_chapter(rest: str) -> Optional[Tuple[str, str]]:
    s = _clean(rest)
    m = _CHAPTER_RE.match(s)
    if not m:
        return None
    container = m.group("container")
    if not _PAGE_MARK_RE.search(container):
        return None
    # Journal-style ``In ... (Vol., No., pp.)`` was handled by _split_article.
    if re.search(r"\(\s*Vol\.", container, re.I):
        return None
    return m.group("title").strip(" ."), container


def _chapter_publisher(container: str) -> Optional[str]:
    # Explicit publisher label, stopping before ISBN/DOI noise.
    m = re.search(
        r"\b(Editorial\s+[A-ZÁÉÍÓÚÜÑ][^.;]{1,70}?)(?=\s+ISBN\b|[.;]|$)",
        container,
        re.I,
    )
    if m:
        return m.group(1).strip(" .,:;")

    # Conventional ``Place: Publisher`` tail.
    core = container.strip().rstrip(" .")
    m = re.search(r":\s*([^:.;]{2,70})$", core)
    if m:
        candidate = m.group(1).strip(" .,:;")
        if candidate and len(candidate.split()) <= 10 and not re.search(r"\bpp?\.", candidate, re.I):
            return candidate
    return None


def _terminal_publisher_book(rest: str) -> Optional[Tuple[str, str]]:
    core = _clean(rest).rstrip(" .")
    if "." not in core:
        return None
    before, last = core.rsplit(".", 1)
    publisher = last.strip(" ,;:")
    if not publisher or len(publisher.split()) > 5 or re.search(r"\d", publisher):
        return None
    if publisher.isupper() or re.match(r"^(?:Editorial|Ediciones?|Press|Publishing)\b", publisher, re.I):
        return before.strip(" ."), publisher
    return None


def _web_title(rest: str, author: Any) -> Tuple[Optional[str], List[str], bool]:
    parts = _ACCESS_RE.split(rest, maxsplit=1)
    before = parts[0].strip(" .") if parts else ""
    after = parts[1] if len(parts) > 1 else ""
    m = re.search(r"\bfrom\b\s+(.+?)(?=https?\s*:|www\.)", after, re.I)
    if not m:
        m = re.search(r"\bdesde\b\s+(.+?)(?=https?\s*:|www\.)", after, re.I)
    after_title = m.group(1).strip(" .:") if m else ""
    candidates = [x for x in (before, after_title) if x]
    ambiguous = len(candidates) >= 2 and _norm_cmp(candidates[0]) != _norm_cmp(candidates[1])

    selected = before or after_title or None
    if after_title:
        if author and _norm_cmp(before) == _norm_cmp(author):
            selected = after_title
        elif _ORG_HINT_RE.search(before) and len(after_title.split()) > len(before.split()) + 1:
            selected = after_title
        elif author and _norm_cmp(after_title) == _norm_cmp(author):
            selected = before
        elif len(after_title.split()) >= 5 and len(before.split()) <= 4:
            selected = after_title
    return selected, candidates, ambiguous


def _count_authors(value: Any) -> int:
    if not value:
        return 0
    return len([x for x in str(value).split("|") if x.strip()])


def _review_overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    notes: List[str] = []
    review: List[str] = []
    candidate_values: Dict[str, str] = {
        "year": "",
        "author": "",
        "title": "",
        "journal": "",
        "type": "",
        "publisher": "",
    }

    apa = _APA_HEAD_RE.match(text)
    years, year_roles = _year_evidence(text, apa)
    if len(years) > 1:
        review.append("multiple_year_mentions")
        candidate_values["year"] = " | ".join(
            f"{year} [{' / '.join(year_roles.get(year, ['text']))}]" for year in years
        )

    if apa:
        publication_year = apa.group("year")
        if str(out.get("year") or "") != publication_year:
            candidate_values["year"] = candidate_values["year"] or _candidate_pair(out.get("year"), publication_year)
            out["year"] = publication_year
            notes.append("year_primary_parenthetical_recovered")

        parsed_authors = _apa_authors(apa.group("head"))
        if parsed_authors:
            authors_joined = " | ".join(parsed_authors)
            if _norm_cmp(out.get("authors")) != _norm_cmp(authors_joined):
                candidate_values["author"] = _candidate_pair(out.get("authors"), authors_joined)
                out["author"] = parsed_authors[0]
                out["authors"] = authors_joined
                notes.append("apa_author_block_recovered")
        elif re.search(r"(?:&|\sy\s)", apa.group("head"), re.I):
            review.append("author_boundary_ambiguous")

        rest = apa.group("rest")
        article = _split_article(rest)
        chapter = None if article else _split_chapter(rest)

        if article:
            title, journal = article
            if _norm_cmp(out.get("title")) != _norm_cmp(title):
                candidate_values["title"] = _candidate_pair(out.get("title"), title)
                notes.append("title_journal_boundary_recovered")
            if _norm_cmp(out.get("journal")) != _norm_cmp(journal):
                candidate_values["journal"] = _candidate_pair(out.get("journal"), journal)
                notes.append("journal_boundary_recovered" if out.get("journal") else "journal_recovered")
            if out.get("publication_type") != "articulo_revista":
                candidate_values["type"] = _candidate_pair(out.get("publication_type"), "articulo_revista")
                notes.append("document_type_article_recovered")
            if out.get("publisher"):
                candidate_values["publisher"] = _candidate_pair(out.get("publisher"), "(none: journal article)")
                notes.append("publisher_journal_conflict_removed")
            out["title"] = title
            out["journal"] = journal
            out["publication_type"] = "articulo_revista"
            out["publisher"] = None
            out["publisher_observed"] = None
            out["source_publisher"] = None

        elif chapter:
            title, container = chapter
            if _norm_cmp(out.get("title")) != _norm_cmp(title):
                candidate_values["title"] = _candidate_pair(out.get("title"), title)
            if out.get("publication_type") != "capitulo_libro":
                candidate_values["type"] = _candidate_pair(out.get("publication_type"), "capitulo_libro")
            out["title"] = title
            out["publication_type"] = "capitulo_libro"
            out["journal"] = None
            pub = _chapter_publisher(container)
            if pub and _norm_cmp(out.get("publisher")) != _norm_cmp(pub):
                candidate_values["publisher"] = _candidate_pair(out.get("publisher"), pub)
                out["publisher"] = pub
                out["publisher_observed"] = pub
                out["source_publisher"] = pub
            notes.append("chapter_container_recovered")

        # Access-language + URL is strong web evidence, but title/source order is
        # frequently inconsistent.  Select the best title and retain both candidates.
        if _ACCESS_RE.search(rest) and _URL_RE.search(rest) and not _EXPLICIT_THESIS_RE.search(text):
            selected_title, title_candidates, ambiguous = _web_title(rest, out.get("author"))
            if out.get("publication_type") != "material_web":
                candidate_values["type"] = _candidate_pair(out.get("publication_type"), "material_web")
                out["publication_type"] = "material_web"
                notes.append("web_access_pattern_recovered")
            if selected_title and _norm_cmp(out.get("title")) != _norm_cmp(selected_title):
                candidate_values["title"] = " || ".join(title_candidates) or _candidate_pair(out.get("title"), selected_title)
                out["title"] = selected_title
                notes.append("web_title_recovered")
            elif title_candidates and not candidate_values["title"]:
                candidate_values["title"] = " || ".join(title_candidates)
            if ambiguous:
                review.append("web_title_source_ambiguous")

        if out.get("publication_type") == "sin_clasificar":
            book = _terminal_publisher_book(rest)
            if book:
                title, publisher = book
                candidate_values["type"] = _candidate_pair(out.get("publication_type"), "libro")
                candidate_values["publisher"] = _candidate_pair(out.get("publisher"), publisher)
                if _norm_cmp(out.get("title")) != _norm_cmp(title):
                    candidate_values["title"] = _candidate_pair(out.get("title"), title)
                out["title"] = title
                out["publisher"] = publisher
                out["publisher_observed"] = publisher
                out["source_publisher"] = publisher
                out["publication_type"] = "libro"
                notes.append("short_terminal_publisher_book_recovered")

    # General safety net: unresolved type should be visible, not silently blank.
    if out.get("publication_type") in (None, "", "sin_clasificar"):
        review.append("document_type_unresolved")

    # A publisher token that lives inside the selected title is suspicious when
    # it is not supported by a monograph/chapter route.
    publisher = str(out.get("publisher") or "").strip()
    title = str(out.get("title") or "").strip()
    if publisher and title and _norm_cmp(publisher) in _norm_cmp(title) and out.get("publication_type") not in {"libro", "capitulo_libro"}:
        review.append("publisher_inside_title")
        candidate_values["publisher"] = candidate_values["publisher"] or _candidate_pair(publisher, "(review)")

    # De-duplicate while preserving deterministic order.
    review = list(dict.fromkeys(review))
    notes = list(dict.fromkeys(notes))
    confidence = 1.0
    penalties = {
        "multiple_year_mentions": 0.10,
        "web_title_source_ambiguous": 0.15,
        "author_boundary_ambiguous": 0.20,
        "document_type_unresolved": 0.20,
        "publisher_inside_title": 0.15,
    }
    for reason in review:
        confidence -= penalties.get(reason, 0.05)
    confidence = max(0.20, round(confidence, 2))

    out["needs_review"] = bool(review)
    out["review_reasons"] = ";".join(review)
    out["parser_notes"] = ";".join(notes)
    out["parser_confidence"] = confidence
    out["year_candidates"] = candidate_values["year"]
    out["author_candidates"] = candidate_values["author"]
    out["title_candidates"] = candidate_values["title"]
    out["journal_candidates"] = candidate_values["journal"]
    out["type_candidates"] = candidate_values["type"]
    out["publisher_candidates"] = candidate_values["publisher"]
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    out = dict(_v11.parse_reference(text))
    out = _review_overlay(text, out)
    style = str(out.get("parse_style") or "")
    if out.get("parser_notes"):
        out["parse_style"] = "+".join([x for x in (style, "v12_robust_audit") if x])
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


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
        "publication_type", "title", "journal", "publisher", "publisher_observed",
        "source_publisher", "doi", "needs_review", "review_reasons", "parser_notes",
        "parser_confidence", "year_candidates", "author_candidates", "title_candidates",
        "journal_candidates", "type_candidates", "publisher_candidates",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
