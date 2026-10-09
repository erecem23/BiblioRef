# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.7.

v0.7 is a conservative ABNT refinement over v0.6.  Development targets are
only the errors already exposed by the frozen v0.6 external holdout.

General changes:
- restore the schema contract ``author == first author`` while ``authors``
  carries the complete author block;
- recognise access markers such as ``Disponível:`` (without ``em``) before
  selecting the publication year, preventing URL path numbers from winning;
- accept ``(in)`` as an ``In:``-equivalent and distinguish journal vs book
  containers;
- remove ABNT volume/issue/page metadata from recovered journal titles,
  including textual values such as ``v. Eletrônico``;
- support compact/double-dot initials and conservative no-comma ABNT authors;
- remove author/editor, edition, reprint, extent and repeated-year descriptors
  from work titles;
- recover degree-granting universities as the source/publisher field for
  ``Tese`` / ``Dissertação`` references;
- preserve the v0.6/v0.5 fallback for all references that do not meet the
  stricter ABNT route.

No PDF/reference-boundary code is imported or modified here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v06 as _v06
from . import v05 as _v05
from . import v03 as _v03
from .lexicons_v02 import PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.7"
PARSER_SCHEMA_VERSION = 7
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ"
_LC = "a-záàâãéèêíìóòôõúùüçñ"
_YEAR_RE = re.compile(r"\b((?:18|19|20)\d{2})[a-z]?\b", re.I)
_ACCESS_RE = re.compile(
    r"\b(?:Dispon[ií]vel(?:\s+em)?|Disponivel(?:\s+em)?|Acesso\s+em|Acessado\s+em|"
    r"Consultado\s+em|Retrieved\s+(?:from|on)|Available\s+(?:at|from))\s*:?,?",
    re.I,
)
_THESIS_RE = re.compile(
    r"\b(?:tese(?:\s+de\s+doutorado)?|disserta[cç][aã]o(?:\s+de\s+mestrado)?|"
    r"monografia|doctoral\s+thesis|master'?s\s+thesis|doutorado|mestrado)\b",
    re.I,
)
_IN_RE = re.compile(r"^(?:(?:\(\s*in\s*\))|(?:In\.?|Em))\s*[:.]?\s+", re.I)
_EDITOR_PREFIX_RE = re.compile(
    r"^(?:\(\s*(?:orgs?\.?|eds?\.?|coords?\.?|comps?\.?)\s*\)\.?|"
    r"(?:orgs?\.?|eds?\.?|coords?\.?|comps?\.?)\s*)\s*",
    re.I,
)
_EDITION_PREFIX_RE = re.compile(
    r"^(?:(?:\d+\s*[ªaºo]?\s*(?:ed\.?|edi[cç][aã]o)|\d+\.\s*ed\.?|"
    r"\d+\.?\s*reimpress[aã]o|reimpress[aã]o|tradu[cç][aã]o(?:\s+de)?|trad\.?)"
    r"[^.]*\.?\s*)+",
    re.I,
)
_JOURNAL_META_BOUNDARY_RE = re.compile(
    r"[,;.]\s*(?=(?:v(?:ol)?\.?|n[º°o]?\.?|p{1,2}\.?|e-location|e\d)\s*[^,;.]*)",
    re.I,
)
_JOURNAL_CUE_RE = _v06._JOURNAL_CUE_RE
_ARTICLE_META_RE = re.compile(
    r"(?:\bv(?:ol)?\.?\s*\d|\bv(?:ol)?\.\s*[A-Za-zÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ]+\b|"
    r"\bn[º°o]?\.?\s*\d|\bn[º°o]?\.\s*[A-Za-zÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ]+\b|"
    r"\bp{1,2}\.?\s*\d|"
    r"\b\d{1,4}\s*\(\s*\d{1,4}\s*\)|\b\d{1,5}\s*[-–]\s*\d{1,5})",
    re.I,
)
_EDITOR_CUE_RE = _v06._EDITOR_CUE_RE
_PUBLISHER_CUE_RE = _v06._PUBLISHER_CUE_RE


def _norm(value: Any) -> str:
    return _v03._norm(value)


def _clean_person(person: str) -> str:
    s = re.sub(r"\s+", " ", person).strip(" ;")
    # OCR/typing often yields R.G.. at the author/title boundary.  Keep one
    # terminal full stop in the author value.
    s = re.sub(r"\.\.$", ".", s)
    return s


def _looks_next_person(s: str) -> bool:
    s = s.lstrip()
    return bool(
        re.match(rf"^[{_UC}][{_UC}'’\- ]{{1,70}},\s*(?:[{_UC}]\.?|[{_UC}][{_LC}])", s)
        or re.match(rf"^[{_UC}][{_UC}'’\- ]{{1,70}}\s+[{_UC}][{_LC}]", s)
    )


def _author_end_after_last_separator(text: str, start: int = 0, allow_initial_continuation: bool = False) -> Optional[int]:
    """Find the terminal full stop of an ABNT author block.

    The scan is permissive inside names but conservative at the boundary.  A
    full stop before a lower-case particle/name continuation is not terminal.
    """
    for m in re.finditer(r"\.{1,2}\s+", text[start:]):
        end = start + m.start()
        suffix = text[start + m.end():].lstrip()
        if not suffix:
            return end + (2 if text[end:end+2] == ".." else 1)
        # Initial followed by another given/family-name token is still inside
        # the author (e.g. Maria A. Viggiani; Celestino A. da Silva).
        prev = text[max(start, end - 2):end]
        nxt = re.match(r"([^\s,;.()]+)", suffix)
        token = nxt.group(1) if nxt else ""
        if allow_initial_continuation and re.fullmatch(rf"[{_UC}]", text[end-1:end]):
            # Continue only when what follows still looks like a compact name
            # continuation ending at punctuation, not a sentence-like title.
            name_cont = re.match(
                rf"^[{_UC}][{_LC}'’\-]+(?:\s+(?:de|da|do|dos|das|[{_UC}][{_LC}'’\-]+))*[.;]",
                suffix,
                re.I,
            )
            if token.casefold() in {"de", "da", "do", "dos", "das"} or name_cont:
                continue
        if _looks_next_person(suffix):
            continue
        return end + (2 if text[end:end+2] == ".." else 1)
    return None


def _split_authors(text: str) -> Optional[Tuple[str, str, str]]:
    """Return (first_author, all_authors, rest) for supported ABNT starts."""
    t = text.strip()

    # Uppercase surname + comma is the common personal-author family.
    m = re.match(rf"^(?P<surname>[{_UC}][{_UC}'’\- ]{{1,70}}),\s*", t)
    if m:
        # Compact initials may terminate in ``..`` at the author/title boundary.
        compact = re.match(
            rf"^(?P<person>[{_UC}][{_UC}'’\- ]{{1,70}},\s*(?:[{_UC}]\.?\s*){{1,6}})\.\s+",
            t,
        )
        if compact:
            person = _clean_person(compact.group("person"))
            return person, person, t[compact.end():].strip()

        # Find the complete author block.  The helper can cross initials and
        # semicolon-separated authors but stops at the first sentence-like
        # boundary.  This avoids mistaking semicolons later in an ``In:`` book
        # container for top-level authors.
        end = _author_end_after_last_separator(t, m.end(), allow_initial_continuation=True)
        if end:
            block = t[:end].strip()
            rest = t[end:].lstrip(" .")
            parts = [p.strip() for p in re.split(r"\s*;\s*|\s+&\s+", block) if p.strip()]
            first = _clean_person(parts[0] if parts else block)
            authors = " | ".join(_clean_person(p) for p in parts) if parts else first
            return first, authors, rest

    # Collective/two-surname author with no comma: ``BOGDAN & BIKLEN.``
    m = re.match(rf"^(?P<a>[{_UC}][{_UC}'’\-]*(?:\s+&\s+[{_UC}][{_UC}'’\-]*)+)\.\s+", t)
    if m:
        a = _clean_person(m.group("a"))
        return a, a, t[m.end():].strip()

    # Single uppercase author: ``ARISTÓTELES.``
    m = re.match(rf"^(?P<a>[{_UC}][{_UC}'’\-]{{2,}})\.\s+", t)
    if m:
        surname = m.group("a")
        rest = t[m.end():].strip()
        # Punctuation-loss variant ``ARENDT. Hannah. Title``.
        gm = re.match(rf"^(?P<given>[{_UC}][{_LC}'’\-]+(?:\s+[{_UC}][{_LC}'’\-]+)*)\.\s+", rest)
        if gm:
            author = f"{surname}. {gm.group('given')}"
            return author, author, rest[gm.end():].strip()
        # Plain ASCII all-caps tokens are more often institutional acronyms
        # (CONADEP, UNESCO, etc.) than personal surnames.  Preserve the older
        # route for those; accented lexical surnames such as ARISTÓTELES remain
        # eligible for the no-comma ABNT family.
        if re.fullmatch(r"[A-Z]{3,12}", surname):
            return None
        return surname, surname, rest

    # Fall back to v0.6 for older ABNT-initial families.
    old = _v06._author_boundary(t)
    if old:
        first, authors, rest = old
        # Enforce schema contract even if v0.6 returned the whole block in
        # author.  Split on explicit separators only.
        first = re.split(r"\s*;\s*|\s+&\s+", first, maxsplit=1)[0].strip()
        return _clean_person(first), authors, rest
    return None


def _strip_leading_author_descriptors(rest: str) -> str:
    s = rest.strip()
    while True:
        m = _EDITOR_PREFIX_RE.match(s)
        if not m or m.end() == 0:
            break
        s = s[m.end():].lstrip(" .")
    return s


def _core_before_access(text: str) -> str:
    m = _ACCESS_RE.search(text)
    if m:
        return text[:m.start()].rstrip(" .;,<")
    return text.rstrip(" .;,<")


def _publication_year(core: str, prefix_len: int, is_thesis: bool = False) -> Optional[re.Match[str]]:
    matches = [m for m in _YEAR_RE.finditer(core) if m.start() > prefix_len + 4]
    if not matches:
        return None
    if is_thesis:
        # Prefer a year immediately before an extent/degree descriptor.  This
        # handles repeated years while excluding URL path numbers.
        for m in matches:
            after = core[m.end():m.end()+80]
            if re.match(r"\s*\.\s*(?:\d+\s*f\.\s*)?(?:Tese|Disserta[cç][aã]o|Monografia)\b", after, re.I):
                return m
    # With access metadata already removed, the final late year is safest.
    for m in reversed(matches):
        if m.start() > max(prefix_len + 8, int(len(core) * 0.40)):
            return m
    return matches[-1]


def _split_title_tail(rest: str, year_match: re.Match[str], core_rest: str, is_thesis: bool) -> Optional[Tuple[str, str]]:
    before_year = core_rest[:year_match.start()].rstrip(" ;,")
    after_year = core_rest[year_match.end():].lstrip(" .;,")
    s = before_year.strip()

    # Thesis/dissertation: the first bibliographic year commonly sits directly
    # after the title, followed by extent and degree information.
    if is_thesis:
        title = re.sub(r"\s+", " ", s).strip(" .;,")
        tail = (year_match.group(0) + ". " + after_year).strip()
        return (title, tail) if title else None

    # Chapter source marker, including the common ``(in)`` variant.
    m = re.search(r"\.\s+(?=(?:\(\s*in\s*\)|In\.?|Em)\s*[:.]?\s+)", s, re.I)
    if m:
        return s[:m.start()].strip(" .;,"), s[m.end():].strip(" ;,")

    # Edition / reprint / translation descriptors belong to the source tail.
    m = re.search(
        r"\.\s+(?=(?:\d+\s*[ªaºo]?\s*(?:ed\.?|edi[cç][aã]o)|\d+\.\s*ed\.?|"
        r"\d+\.?\s*reimpress[aã]o|reimpress[aã]o|tradu[cç][aã]o|trad\.?))",
        s,
        re.I,
    )
    if m:
        return s[:m.start()].strip(" .;,"), s[m.end():].strip(" ;,")

    # Standard full-stop title/source boundary.
    split = _v06._split_title_tail(s)
    if split:
        return split

    # One-word titles are valid when the following tail has a strong place /
    # publisher structure (e.g. ``Confissões. Petrópolis, RJ: Editora Vozes``).
    m = re.match(r"^(?P<title>[^.]{2,80})\.\s+(?P<tail>.+)$", s)
    if m and (":" in m.group("tail") or _PUBLISHER_CUE_RE.search(m.group("tail"))):
        return m.group("title").strip(" .;,"), m.group("tail").strip(" ;,")

    # Colon-rich book references can omit the full stop before the imprint,
    # e.g. ``... nova ciência: EDUF, Juiz de Fora: Londrina: CEFIL``.  Only
    # activate when the suffix has multiple publisher/place colons.
    colons = [m.start() for m in re.finditer(r":\s*", s)]
    if len(colons) >= 3:
        for pos in colons[1:]:
            suffix = s[pos+1:].strip()
            if re.match(rf"^[{_UC}][{_UC}0-9]{{2,}}\b", suffix) and ":" in suffix:
                return s[:pos].strip(" .;,"), suffix
    return None


def _strip_in(tail: str) -> Tuple[str, bool]:
    s = tail.strip()
    m = _IN_RE.match(s)
    return (s[m.end():].strip(), True) if m else (s, False)


def _looks_chapter_container(container: str) -> bool:
    c = container[:220]
    if _EDITOR_CUE_RE.search(c[:160]):
        return True
    # Surname/name container with multiple contributors/editors.
    if re.match(rf"^[{_UC}A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ][^.;]{{0,120}}[,;]", c):
        # Strong periodical metadata wins only when it appears before any book
        # title/editor cue.
        if not _ARTICLE_META_RE.search(c[:100]):
            return True
    return _v06._looks_chapter_container(c)


def _looks_article_container(container: str) -> bool:
    c = container.strip()
    if _ARTICLE_META_RE.search(c):
        return True
    if _JOURNAL_CUE_RE.search(c[:180]):
        return True
    # A place/publisher colon without independent periodical evidence is a
    # monograph signal.  Do not delegate it to v0.6, whose broad ``p`` pattern
    # can mistake words such as Petrópolis/Paulo for page metadata.
    if ":" in c:
        return False
    return _v06._looks_article_container(c)


def _journal_from_tail(tail: str) -> Optional[str]:
    c, _ = _strip_in(tail)
    c = _v06._strip_source_descriptors(c)
    c = re.sub(r"\s+", " ", c).strip(" .;,")
    if not c:
        return None

    # Cut before any ABNT v./n./p. metadata, including textual values such as
    # ``v. Eletrônico`` and compact forms such as ``v1``.
    m = re.search(r"[,;.]\s*(?=(?:v(?:ol)?\.?|n[º°o]?\.?|p{1,2}\.?)\s*[^,;.]+)", c, re.I)
    if m:
        candidate = c[:m.start()].strip(" .;,")
    else:
        candidate = c
        # Compact comma-free metadata fallback.
        m2 = re.search(r"\s+(?=(?:v(?:ol)?\.?|n[º°o]?\.?|p{1,2}\.?)\s*\d)", c, re.I)
        if m2:
            candidate = c[:m2.start()].strip(" .;,")

    # Remove a short location segment only if the preceding source is already
    # independently journal-like.
    parts = [p.strip() for p in candidate.split(",")]
    if len(parts) >= 2 and _JOURNAL_CUE_RE.search(", ".join(parts[:-1])):
        last = parts[-1]
        if 1 <= len(last.split()) <= 4 and not _JOURNAL_CUE_RE.search(last):
            candidate = ", ".join(parts[:-1])
    return candidate.strip(" .;,") or None


def _canonical_publisher(observed: Optional[str]) -> Optional[str]:
    if not observed:
        return None
    obs = re.sub(r"\s+", " ", observed).strip(" .;,:<>")
    obs = re.sub(r",?\s*(?:Ltda\.?|LTDA\.?|Inc\.?|S\.A\.?)$", "", obs, flags=re.I).strip(" .;,:<>")
    obs = re.sub(r"\s+Ed\.?$", "", obs, flags=re.I).strip(" .;,:<>")
    # One conservative OCR/spelling normalization in an institutional phrase.
    obs = re.sub(r"\bUniversidade\s+de\s+S[aã]o\s+Pulo\b", "Universidade de São Paulo", obs, flags=re.I)
    return PUBLISHER_ALIASES.get(_norm(obs), obs) or None


def _publisher_from_tail(tail: str) -> Tuple[Optional[str], Optional[str]]:
    can, obs = _v06._publisher_from_tail(tail)
    if obs:
        return _canonical_publisher(obs), re.sub(r"\s+", " ", obs).strip(" .;,")
    c, _ = _strip_in(tail)
    c = re.sub(r"\s+", " ", c).strip(" .;,")
    # Final colon segment is a strong publisher cue in colon-rich ABNT books.
    if ":" in c:
        obs2 = c.rsplit(":", 1)[1].strip(" .;,")
        if 1 <= len(obs2.split()) <= 12 and not re.search(r"https?://|\b(?:v|n|p)\.?\s*\d", obs2, re.I):
            return _canonical_publisher(obs2), obs2
    # ``Porto Editora, LTDA`` / other explicit publisher segment without city colon.
    segs = [x.strip(" .;,") for x in re.split(r"\.\s+|;\s+", c) if x.strip(" .;,")]
    for seg in reversed(segs):
        if _PUBLISHER_CUE_RE.search(seg):
            return _canonical_publisher(seg), seg
    return None, None


def _thesis_institution(text: str) -> Optional[str]:
    matches = re.findall(
        r"\b(?:Pontif[ií]cia\s+)?Universidade\b[^,.;<>–—-]{2,110}",
        text,
        flags=re.I,
    )
    if not matches:
        return None
    inst = re.sub(r"\s+", " ", matches[-1]).strip(" .;,-–—")
    return inst or None


def _parse_abnt_v07(text: str) -> Optional[Dict[str, Any]]:
    if not text or _v03._YEAR_PAREN_RE.search(text[:280]):
        return None
    ab = _split_authors(text)
    if not ab:
        return None
    author, authors, rest = ab
    rest = _strip_leading_author_descriptors(rest)
    prefix_len = len(text) - len(rest)
    core = _core_before_access(text)
    # Rebuild coordinates from the actual rest substring after descriptor
    # removal when possible.
    idx = text.find(rest)
    if idx >= 0:
        prefix_len = idx
    core_rest = core[prefix_len:].strip() if prefix_len < len(core) else ""
    is_thesis = bool(_THESIS_RE.search(core_rest))
    ym = _publication_year(core, prefix_len, is_thesis=is_thesis)
    if not ym or ym.start() <= prefix_len:
        return None
    local_year = re.search(re.escape(ym.group(0)), core_rest)
    if not local_year:
        return None
    split = _split_title_tail(rest, local_year, core_rest, is_thesis)
    if not split:
        return None
    title, tail = split
    title = re.sub(r"\s+", " ", title).strip(" .;,")
    if not title:
        return None
    container, had_in = _strip_in(tail)

    if is_thesis:
        publication_type = "tesis"
        journal = None
        institution = _thesis_institution(core_rest)
        publisher = institution
        publisher_observed = institution
    else:
        chapter_like = had_in and _looks_chapter_container(container)
        article_like = (not chapter_like) and _looks_article_container(container)
        journal = _journal_from_tail(tail) if article_like and not chapter_like else None
        if journal:
            publication_type = "articulo_revista"
            publisher = publisher_observed = None
        elif chapter_like:
            publication_type = "capitulo_libro"
            publisher, publisher_observed = _publisher_from_tail(tail)
        else:
            publisher, publisher_observed = _publisher_from_tail(tail)
            if publisher:
                publication_type = "libro"
            elif article_like:
                publication_type = "articulo_revista"
            elif re.search(r"\b(?:ed\.?|edi[cç][aã]o|reimpress[aã]o|cole[cç][aã]o)\b", tail, re.I):
                publication_type = "libro"
            else:
                publication_type = "sin_clasificar"

    if "," in author:
        style = "abnt_v07_personal_year_end"
    elif "&" in author:
        style = "abnt_v07_collective_year_end"
    else:
        style = "abnt_v07_nocomma_year_end"
    return {
        "parse_style": style,
        "author": author,
        "authors": authors,
        "year": ym.group(1),
        "title": title,
        "journal": journal,
        "publication_type": publication_type,
        "publisher": publisher,
        "publisher_observed": publisher_observed,
    }


def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    base = _v06.parse_reference(text)
    abnt = _parse_abnt_v07(text)
    if not abnt:
        out = dict(base)
        out["schema_version"] = PARSER_SCHEMA_VERSION
        out["parser_version"] = PARSER_VERSION
        out["parser_status"] = PARSER_STATUS
        return out
    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "parser_status": PARSER_STATUS,
        "parse_style": abnt.get("parse_style"),
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
