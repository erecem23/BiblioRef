# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.6.

v0.6 extends the explicit ABNT-family route introduced in v0.5.  It is
strictly downstream from the validated PDF/reference segmentation engine.

Development targets are the 30 references already consumed by the v0.5 ABNT
external holdout.  They are regression/development material for v0.6, not
external validation.

General additions:
- ABNT authors written as ``SURNAME, Full Given Names`` or mixed initials and
  particles (e.g. ``ALMEIDA, S. L. de``);
- ``In:`` disambiguation: journal-like containers remain journal articles,
  while editor/author containers remain book chapters;
- explicit ``Tese`` / ``Dissertação`` / degree-work recognition;
- journal recovery from ABNT tails without a strict v./n./p. triple;
- conservative publisher recovery from colon, comma-place, explicit publisher
  words, or short known-imprint segments;
- publication year may be followed by page or thesis descriptors.

Raw citation text remains authoritative and no reference boundary logic is
modified here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v05 as _v05
from . import v04 as _v04
from . import v03 as _v03
from .lexicons_v02 import PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.6"
PARSER_SCHEMA_VERSION = 6
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ"
_LC = "a-záàâãéèêíìóòôõúùüçñ"
_SURNAME_RE = re.compile(rf"^(?P<surname>[{_UC}][{_UC}'’\- ]{{1,70}}),\s*(?P<after>.+)$")
_FULLNAME_WORD_RE = re.compile(rf"^(?:[{_UC}][{_LC}'’\-]+|[{_UC}]\.|de|da|do|dos|das|e)$", re.I)
_IMPLICIT_SECOND_AUTHOR_RE = re.compile(rf"\s+(?=[{_UC}]{{2,}}(?:\s+[{_UC}]{{2,}})*\s+[{_UC}][{_LC}])")
_YEAR_RE = re.compile(r"\b((?:18|19|20)\d{2})[a-z]?\b", re.I)
_ACCESS_RE = re.compile(
    r"\b(?:Dispon[ií]vel\s+em|Acesso\s+em|Acessado\s+em|Consultado\s+em|Retrieved\s+(?:from|on))\b",
    re.I,
)
_THESIS_RE = re.compile(
    r"\b(?:tese(?:\s+de\s+doutorado)?|disserta[cç][aã]o(?:\s+de\s+mestrado)?|"
    r"monografia|doctoral\s+thesis|master'?s\s+thesis|doutorado|mestrado)\b",
    re.I,
)
_IN_RE = re.compile(r"^(?:In\.?|Em)\s*[:.]?\s+", re.I)
_CONTAINER_AUTHOR_RE = re.compile(
    rf"^(?:[{_UC}][{_UC}'’\- ]{{1,60}},\s*(?:[{_UC}]\.?\s*){{1,5}}|"
    rf"[{_UC}][{_UC}'’\- ]{{1,60}},\s*[{_UC}][{_LC}])",
)
_EDITOR_CUE_RE = re.compile(r"\b(?:org\.?|orgs\.?|ed\.?|eds\.?|coord\.?|coords\.?|comp\.?|comps\.?)\b", re.I)
_ARTICLE_META_RE = re.compile(
    r"(?:\b(?:v(?:ol)?|n[º°o]?|p{1,2})\.?\s*\d|\b\d{1,4}\s*\(\s*\d{1,4}\s*\)|"
    r"\b\d{1,4}\s*,\s*(?:p{1,2}\.?\s*)?\d{1,5}(?:\s*[-–]\s*\d{1,5})?)",
    re.I,
)
_PAGE_RANGE_RE = re.compile(r"\b\d{1,5}\s*[-–]\s*\d{1,5}\b")
_JOURNAL_CUE_RE = re.compile(
    r"\b(?:revista|journal|review|bulletin|boletim|anales|annals|cadernos|arquivos|"
    r"estudos|psychology|psychological|psicologia|psican[aá]lise|sa[uú]de|educa[cç][aã]o|"
    r"ci[eê]ncia|ci[eê]ncias|sociedade|pesquisa|trabalho|feministas?|teias|calidosc[oó]pio)\b",
    re.I,
)
_PUBLISHER_CUE_RE = re.compile(
    r"\b(?:press|publishing|publications?|publishers?|verlag|ediciones?|editorial|editores?|editora|"
    r"livraria|letramento|bookman|zahar|recorde?|argos|nau|del\s+rey|artes\s+m[eé]dicas|"
    r"companhia\s+das\s+letras|edi[cç][oõ]es\s+\d+)\b",
    re.I,
)
_DESCRIPTOR_PREFIX_RE = re.compile(
    r"^(?:(?:Tradu[cç][aã]o|Trad\.?|Cole[cç][aã]o|\d+[aª]?\s*ed\.?|\d+\.\s*ed\.?|"
    r"Edi[cç][aã]o|Org\.?|Organiza[cç][aã]o)\b[^.]*\.\s*)+",
    re.I,
)


def _norm(value: Any) -> str:
    return _v03._norm(value)


def _canonical_publisher(observed: Optional[str]) -> Optional[str]:
    if not observed:
        return None
    obs = re.sub(r"\s+", " ", observed).strip(" .;,:")
    obs = re.sub(r"\s+Ed\.?$", "", obs, flags=re.I).strip(" .;,:")
    return PUBLISHER_ALIASES.get(_norm(obs), obs) or None


def _core_before_access(text: str) -> str:
    m = _ACCESS_RE.search(text)
    return (text[:m.start()] if m else text).rstrip(" .;,")


def _author_boundary(text: str) -> Optional[Tuple[str, str, str]]:
    """Return (first_author, authors, rest) for common ABNT author blocks."""
    m = _SURNAME_RE.match(text)
    if not m:
        return None
    comma = text.find(",")
    after = text[comma + 1:].lstrip()

    # Full given-name style: ``ADICHIE, Chimamanda Ngozi. Title``.  Scan full
    # stops until the suffix no longer looks like another malformed author.
    if re.match(rf"^[{_UC}][{_LC}]", after):
        first_display = None
        author_chunks = []
        scan_from = comma + 1
        for dm in re.finditer(r"\.\s+", text[scan_from:]):
            end = scan_from + dm.start()
            prefix = text[:end].strip()
            suffix = text[end + 2:].lstrip()
            if first_display is None:
                first_display = prefix
                author_chunks.append(prefix)
            # A second author may be written as ``HARRIS, Paul.`` or, after
            # OCR/punctuation loss, ``MENEZES Marilda.``.
            next_author = bool(
                re.match(rf"^[{_UC}]{{2,}}(?:\s+[{_UC}]{{2,}})*,\s*[{_UC}][{_LC}]", suffix)
                or re.match(rf"^[{_UC}]{{2,}}(?:\s+[{_UC}]{{2,}})*\s+[{_UC}][{_LC}]", suffix)
            )
            if next_author:
                # Continue to the next full-stop boundary; do not let the
                # second author become the work title.
                continue
            return first_display.rstrip(" .;"), " | ".join(x.rstrip(" ;") for x in author_chunks), suffix
        return None

    # Missing final dot before semicolon: ``AGUIAR, W. M. J; OZELLA, S.``.
    semi = text.find(";")
    if 0 < semi < 120:
        first_given = text[comma + 1:semi].strip()
        initials_only = bool(re.fullmatch(
            rf"(?:[{_UC}]\.?\s*){{1,6}}(?:(?:de|da|do|dos|das)\.?)?",
            first_given,
            re.I,
        ))
        if initials_only:
            first = text[:semi].strip().rstrip(" .;")
            remainder = text[semi + 1:].lstrip()
            tail = _v05._split_abnt_author_block(remainder)
            if tail:
                authors = first + " | " + tail["authors"]
                return first, authors, tail["rest"]

    legacy = _v05._split_abnt_author_block(text)
    if legacy:
        author = legacy["author"]
        authors = legacy["authors"]
        rest = legacy["rest"]
        # Mixed initials + trailing particle: ``ALMEIDA, S. L. de. Title``.
        pm = re.match(r"^(de|da|do|dos|das)\.\s+", rest, re.I)
        if pm:
            particle = pm.group(1)
            author = f"{author} {particle}"
            authors = f"{authors} {particle}"
            rest = rest[pm.end():].strip()
        return author.rstrip(" ;"), authors.rstrip(" ;"), rest
    return None

def _publication_year(core: str, author_end: int = 0) -> Optional[re.Match[str]]:
    matches = list(_YEAR_RE.finditer(core))
    if not matches:
        return None
    # Last year is the safest ABNT publication-year candidate after access
    # metadata has been removed.  It must still occur in the latter half-ish of
    # the reference to avoid years embedded solely inside titles.
    for m in reversed(matches):
        if m.start() > max(author_end + 8, int(len(core) * 0.42)):
            return m
    return None


def _split_title_tail(rest_before_year: str) -> Optional[Tuple[str, str]]:
    s = rest_before_year.strip(" ;,")
    # Question/exclamation can terminate the title when followed by a strong
    # source/descriptor cue (e.g. ``Interseccionalidade? Coleção ...``).
    for m in re.finditer(r"[?!]\s+", s):
        suffix = s[m.end():]
        if re.match(r"(?:Cole[cç][aã]o|Tradu[cç][aã]o|Trad\.?|Revista|Journal|Estudos|Cadernos|Editora|Editorial)\b", suffix, re.I):
            return s[:m.start()+1].strip(" .;,"), suffix.strip(" ;,")
    # Otherwise the first full-stop sentence boundary separates title/source.
    for m in re.finditer(r"\.\s+(?=[(\"“'A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ])", s):
        title = s[:m.start()].strip(" .;,")
        tail = s[m.end():].strip(" ;,")
        if len(title) >= 3 and len(title.split()) >= 2 and tail:
            return title, tail
    return None


def _strip_in(tail: str) -> Tuple[str, bool]:
    m = _IN_RE.match(tail.strip())
    if not m:
        return tail.strip(), False
    return tail.strip()[m.end():].strip(), True


def _strip_source_descriptors(container: str) -> str:
    c = container.strip()
    # Translation/edition/collection descriptors precede the actual source in
    # many ABNT references and must not become part of a journal name.
    while True:
        m = re.match(
            r"^(?:Tradu[cç][aã]o(?:\s+de)?|Trad\.?|\d+[aª]?\s*ed\.?|\d+\.\s*ed\.?|"
            r"Cole[cç][aã]o)\b[^.]*\.\s*",
            c,
            re.I,
        )
        if not m:
            break
        c = c[m.end():].strip()
    return c


def _looks_chapter_container(container: str) -> bool:
    head = container[:180]
    return bool(_CONTAINER_AUTHOR_RE.match(head) or _EDITOR_CUE_RE.search(head[:120]))


def _looks_article_container(container: str) -> bool:
    c = container.strip()
    if _ARTICLE_META_RE.search(c) or _JOURNAL_CUE_RE.search(c[:180]):
        return True
    # Journal title + city + page range, without v./n. metadata.
    if _PAGE_RANGE_RE.search(c) and len(c.split(",", 1)[0].split()) <= 14:
        return True
    return False


def _journal_from_tail(tail: str) -> Optional[str]:
    c, _ = _strip_in(tail)
    c = _strip_source_descriptors(c)
    c = re.sub(r"\s+", " ", c).strip(" .;,")
    if not c:
        return None

    # ``Calidoscópio. Vol. 3`` style.
    m = re.search(r"\.\s*(?=(?:v(?:ol)?|n[º°o]?|p{1,2})\.?)", c, re.I)
    if m:
        candidate = c[:m.start()].strip(" .;,")
        return candidate or None

    # Standard comma before explicit volume/issue/page metadata.
    patterns = [
        r",\s*(?=(?:v(?:ol)?|n[º°o]?|p{1,2})\.?\s*\d)",
        r",\s*(?=\d{1,4}\s*\(\s*\d{1,4}\s*\))",
        r",\s*(?=\d{1,4}\s*,\s*(?:p{1,2}\.?\s*)?\d{1,5}(?:\s*[-–]\s*\d{1,5})?)",
    ]
    for pat in patterns:
        m = re.search(pat, c, re.I)
        if m:
            candidate = c[:m.start()].strip(" .;,")
            # ``Journal, City, v.``: remove short city segment only when the
            # preceding source is independently journal-like.
            parts = [x.strip() for x in candidate.split(",")]
            if len(parts) >= 2 and _JOURNAL_CUE_RE.search(", ".join(parts[:-1])):
                last = parts[-1]
                if 1 <= len(last.split()) <= 4 and not _JOURNAL_CUE_RE.search(last):
                    candidate = ", ".join(parts[:-1])
            return candidate.strip(" .;,") or None

    # ``Estudos Feministas, Florianópolis: 229-235``.
    if _PAGE_RANGE_RE.search(c) and "," in c:
        first = c.split(",", 1)[0].strip(" .;,")
        if _JOURNAL_CUE_RE.search(first):
            return first

    # Explicit journal cue can stand alone before later place/publisher noise.
    if _JOURNAL_CUE_RE.search(c):
        first = c.split(",", 1)[0].strip(" .;,")
        if 1 <= len(first.split()) <= 18:
            return first
    return None


def _publisher_from_tail(tail: str) -> Tuple[Optional[str], Optional[str]]:
    c, _ = _strip_in(tail)
    c = re.sub(r"\s+", " ", c).strip(" .;,")
    c = _DESCRIPTOR_PREFIX_RE.sub("", c).strip(" .;,")
    old_can, old_obs = _v05._abnt_publisher(c)
    if old_obs:
        return old_can, old_obs

    # Prefer an explicit publisher-bearing segment anywhere in the tail.
    segments = [s.strip(" .;,") for s in re.split(r"\.\s+|;\s+", c) if s.strip(" .;,")]
    explicit = [s for s in segments if _PUBLISHER_CUE_RE.search(s)]
    if explicit:
        obs = explicit[-1]
        # If segment is ``São Paulo, Companhia das Letras`` retain only imprint.
        if "," in obs:
            bits = [b.strip() for b in obs.split(",") if b.strip()]
            if len(bits) >= 2 and _PUBLISHER_CUE_RE.search(bits[-1]):
                obs = bits[-1]
        return _canonical_publisher(obs), obs

    # ``São Paulo, Companhia das Letras`` without explicit publisher token in
    # a generic lexicon; the final comma segment must be a known imprint.
    bits = [b.strip(" .;,") for b in c.split(",") if b.strip(" .;,")]
    if len(bits) >= 2:
        last = bits[-1]
        can = _canonical_publisher(last)
        if _norm(last) in PUBLISHER_ALIASES or (can and can != last):
            return can, last

    # ``Bookman. Porto Alegre.``: short first segment is a known imprint.
    if segments:
        first = segments[0]
        if _norm(first) in PUBLISHER_ALIASES or _PUBLISHER_CUE_RE.search(first):
            return _canonical_publisher(first), first
    return None, None


def _parse_abnt_v06(text: str) -> Optional[Dict[str, Any]]:
    if not text or _v03._YEAR_PAREN_RE.search(text[:280]):
        return None
    ab = _author_boundary(text)
    if not ab:
        return None
    author, authors, rest = ab
    core = _core_before_access(text)
    prefix_len = len(text) - len(rest)
    ym = _publication_year(core, prefix_len)
    if not ym or ym.start() <= prefix_len:
        return None
    before_year = core[prefix_len:ym.start()].rstrip(" ;,")
    split = _split_title_tail(before_year)
    if not split:
        return None
    title, tail = split
    container, had_in = _strip_in(tail)

    if _THESIS_RE.search(text):
        publication_type = "tesis"
        journal = None
        publisher, publisher_observed = _publisher_from_tail(tail)
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
            elif re.search(r"\b(?:ed\.|edi[cç][aã]o|cole[cç][aã]o)\b", tail, re.I):
                publication_type = "libro"
            else:
                publication_type = "sin_clasificar"

    style = "abnt_fullname_year_end" if re.search(rf",\s*[{_UC}][{_LC}]", author) else "abnt_enhanced_year_end"
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
    base = _v05.parse_reference(text)
    abnt = _parse_abnt_v06(text)
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
