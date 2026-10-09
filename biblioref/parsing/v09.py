# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.9.

v0.9 attacks the two failure families left open by the frozen v0.8 holdouts.
Development targets are only references already consumed by those holdouts,
which are therefore development/regression material here, not validation.

The diagnosis that motivates the release: most of the journal errors reported
for v0.8 were not journal errors.  They were author-block errors.  When
``ALMEIDA, R. S.; BOURLIATAUX-LAJOINIE, S.; MARTINS, M.`` was cut after the
first initial, the remainder of the author list became the title and the real
title became the journal.  Fixing the boundary repairs author, authors, title
and journal at once.

General changes:
- replace the ABNT author boundary with an explicit token scan over the author
  grammar (surname, given part, separator) instead of a full-stop search, so a
  given part made of several initials, particles or full names no longer ends
  the block;
- recognise ``et al.`` and equivalent truncation markers as an explicit
  terminator of the author block rather than as a name;
- recognise a surname followed directly by initials without a comma
  (``DONABEDIAN A.``) as a personal author;
- classify the source container using periodical metadata that appears after
  the publication year (``1966, 44: 166-206``), not only before it;
- cut journal candidates before compact article metadata written without
  ``v.``/``n.``/``p.`` (``31(1):11-25``, ``44: 166-206``, ``e25314``);
- drop a corporate publishing entity appended to a journal name
  (``..., Institute of Electrical and Electronics Engineers (IEEE), v. 128``);
- drop a publication place appended to a journal name with a comma or a full
  stop, and stop dropping a trailing segment that is itself journal-like
  (``Trabalho, Educação e Saúde`` is no longer truncated to ``Trabalho``);
- recover an APA journal when the base route abstained because the volume/issue
  block is not purely numeric (``7(MAR)``, ``43, e25314``, ``19.``,
  ``(online)``), under explicit periodical evidence and monograph exclusions;
- preserve the v0.8 result for every reference that does not meet these routes.

No PDF/reference-boundary code is imported or modified here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v08 as _v08
from . import v06 as _v06
from . import v03 as _v03
from . import v02 as _v02

PARSER_VERSION = "biblioref-parser-v0.9"
PARSER_SCHEMA_VERSION = 9
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ"
_LC = "a-záàâãéèêíìóòôõúùüçñ"

_YEAR_RE = _v08._YEAR_RE
_THESIS_RE = _v08._THESIS_RE
_JOURNAL_CUE_RE = _v08._JOURNAL_CUE_RE
_ARTICLE_META_RE = _v08._ARTICLE_META_RE
_PUBLISHER_CUE_RE = _v08._PUBLISHER_CUE_RE

# --------------------------------------------------------------------------
# Author block grammar
# --------------------------------------------------------------------------
# An ABNT author block is a sequence of persons separated by explicit
# separators.  Each person is a surname plus an optional given part.  The block
# ends at a truncation marker, at an editor marker, or at a full stop that is
# not followed by another person.

_MAX_AUTHOR_BLOCK = 320

# Each component of an upper-case surname must be a complete upper-case word.
# Without the lookahead, ``MENEZES Marilda`` would yield the surname
# ``MENEZES M`` and lose the given name.
_CAPS_WORD = rf"[{_UC}][{_UC}'’]*(?![{_LC}])"
_SURNAME_CAPS_RE = re.compile(rf"{_CAPS_WORD}(?:[\s\-]{_CAPS_WORD})*")
_SURNAME_TITLE_RE = re.compile(
    rf"[{_UC}][{_LC}'’\-]+(?:\s+(?:de|da|do|dos|das|del|van|von|di|du|la|le)\s+[{_UC}][{_LC}'’\-]+"
    rf"|\s+[{_UC}][{_LC}'’\-]+)*"
)
_INITIAL_RUN_RE = re.compile(rf"(?:[{_UC}]\s*\.)(?:\s*[{_UC}]\s*\.)*")
_NAME_WORD_RE = re.compile(rf"[{_UC}][{_LC}'’\-]{{1,24}}")
_PARTICLE_RE = re.compile(r"(?:de|da|do|dos|das|del|van|von|der|di|du|la|le)(?![A-Za-z])", re.I)
# A dotless initial is only recognised where the next token cannot be a title
# word: before a separator, at the end, or before a name particle.
_BARE_INITIAL_RE = re.compile(rf"[{_UC}](?=\s*[;,&]|\s*$|\s+(?:de|da|do|dos|das)\b)")
_TRUNCATION_RE = re.compile(r"et\.?\s*al(?:ii|\.|\b)\.?|e\s+(?:outros|colaboradores)\b|and\s+others\b", re.I)
_EDITOR_MARK_RE = re.compile(
    r"\(\s*(?:orgs?|eds?|coords?|comps?|dirs?|orgs?\.|eds?\.)\s*\.?\s*\)\.?", re.I
)
_NEXT_PERSON_RE = re.compile(
    rf"[{_UC}][{_UC}'’\- ]{{1,70}},\s*(?:[{_UC}]\.?|[{_UC}][{_LC}])"
    rf"|[{_UC}][{_LC}'’\-]+(?:\s+[{_UC}][{_LC}'’\-]+)*,\s*(?:[{_UC}]\.?|[{_UC}][{_LC}])"
)
# Punctuation loss between authors: ``ALBUQUERQUE, Else de F. MENEZES Marilda.``
_LOST_SEPARATOR_PERSON_RE = re.compile(
    rf"[{_UC}]{{2,}}(?:\s+[{_UC}]{{2,}})*(?:,\s*|\s+)[{_UC}][{_LC}]"
)
_SEPARATOR_RE = re.compile(
    r"\s*(?:[;,]\s*)?(?:&|\be\b|\by\b|\band\b)\s*|\s*;\s*|\s*,\s*", re.I
)


_STRONG_SEP_RE = re.compile(rf"\s*(?:;|,\s*&|&|\s+e\s+(?=[{_UC}]))")


def _given_tokens_end(text: str, pos: int) -> int:
    """Greedy end of a run of name/initial/particle tokens (lookahead only)."""
    i = pos
    while i < len(text):
        j = i
        while j < len(text) and text[j] == " ":
            j += 1
        for rx in (_INITIAL_RUN_RE, _NAME_WORD_RE, _PARTICLE_RE):
            m = rx.match(text, j)
            if m and m.end() > j:
                i = m.end()
                break
        else:
            break
    return i


def _scan_given_part(text: str, pos: int, allow_full_names: bool = True) -> int:
    """Consume initials, given names and particles; return the new position.

    A full given name that follows an abbreviation dot is ambiguous: it is a
    further given name in ``BICUDO, Maria A. Viggiani; ...`` and the first word
    of the title in ``ALBUQUERQUE, P. P. Autogestão. In: ...``.  The two are
    separated by what closes the run: an author-list separator keeps it inside
    the block, anything else ends the block at the dot.
    """
    i = pos
    after_dot = False
    while i < len(text):
        j = i
        while j < len(text) and text[j] == " ":
            j += 1
        m = _INITIAL_RUN_RE.match(text, j)
        if m and m.end() > j:
            i = m.end()
            after_dot = text[:i].rstrip().endswith(".")
            continue
        m = _NAME_WORD_RE.match(text, j)
        if m:
            if not allow_full_names:
                break
            if after_dot and not _STRONG_SEP_RE.match(text, _given_tokens_end(text, j)):
                break
            i = m.end()
            after_dot = False
            continue
        m = _PARTICLE_RE.match(text, j)
        if m:
            i = m.end()
            after_dot = text[:i].rstrip().endswith(".")
            continue
        m = _BARE_INITIAL_RE.match(text, j)
        if m:
            i = m.end()
            after_dot = False
            continue
        break
    return i


def _scan_person(text: str, pos: int) -> Optional[int]:
    """Match one person starting at ``pos``; return the end position."""
    m = _SURNAME_CAPS_RE.match(text, pos)
    caps = bool(m) and (m.end() - pos) >= 2
    if not caps:
        m = _SURNAME_TITLE_RE.match(text, pos)
    if not m or m.end() == pos:
        return None
    end = m.end()
    if end < len(text) and text[end] == ",":
        # A title-case surname is only admitted with an initials-only given
        # part.  ``Laplanche, Jean. La cubeta. ... Buenos Aires: Amorrortu,
        # 1987`` is a Chicago-style monograph, not an ABNT author block, and
        # admitting it would turn its subtitle into a journal.
        given_end = _scan_given_part(text, end + 1, allow_full_names=caps)
        if given_end > end + 1:
            return given_end
        return None
    # No comma: only a caps surname followed by initials, or a caps surname
    # followed by a title-case given name after punctuation loss.
    if caps:
        given_end = _scan_given_part(text, end)
        if given_end > end:
            return given_end
        return end
    return None


def _author_block(text: str) -> Optional[Tuple[List[str], str, bool]]:
    """Return (persons, rest, truncated) for an ABNT-like author block.

    The block is read person by person.  An explicit separator continues the
    list; a terminal full stop closes it unless another person follows, which
    is what keeps ``AMBROSE, Gavin. HARRIS, Paul. Design Thinking`` from losing
    its second author.  A scan that reaches a title word with no boundary at
    all abstains, so the v0.8 route keeps the reference.
    """
    head = text[:_MAX_AUTHOR_BLOCK]
    persons: List[str] = []
    pos = 0
    while True:
        end = _scan_person(head, pos)
        if end is None:
            return None
        person = head[pos:end].strip(" ,;")
        if not person:
            return None
        persons.append(person)

        sm = _SEPARATOR_RE.match(head, end)
        if sm and sm.end() > end and _scan_person(head, sm.end()) is not None:
            pos = sm.end()
            continue

        k = end
        dots = 0
        while k < len(head) and head[k] == "." and dots < 2:
            k += 1
            dots += 1
        had_dot = dots > 0 or person.endswith(".")
        j = k
        while j < len(head) and head[j] in " \t":
            j += 1
        if not had_dot or (j == k and j < len(head)):
            return None

        tm = _TRUNCATION_RE.match(head, j)
        if tm:
            rest = text[_skip(head, tm.end(), " .,;"):].strip()
            return (persons, rest, True) if rest else None
        em = _EDITOR_MARK_RE.match(head, j)
        if em:
            rest = text[_skip(head, em.end(), " .,;"):].strip()
            return (persons, rest, False) if rest else None
        suffix = head[j:]
        if _NEXT_PERSON_RE.match(suffix) or _LOST_SEPARATOR_PERSON_RE.match(suffix):
            pos = j
            continue
        rest = text[j:].strip()
        return (persons, rest, False) if rest else None


def _skip(text: str, pos: int, chars: str) -> int:
    while pos < len(text) and text[pos] in chars:
        pos += 1
    return pos


def _clean_person(person: str) -> str:
    return _v08._clean_person(person)


_COLLECTIVE_AUTHOR_RE = re.compile(
    rf"^(?P<a>[{_UC}][{_UC}'’\-]*(?:\s+&\s+[{_UC}][{_UC}'’\-]*)+)\.\s+"
)


def _split_authors_v09(text: str) -> Optional[Tuple[str, str, str]]:
    # Bare caps surnames joined by ``&`` are a single collective author
    # (``BOGDAN & BIKLEN.``), not an author list.  Keep the v0.8 reading.
    cm = _COLLECTIVE_AUTHOR_RE.match(text)
    if cm:
        a = _clean_person(cm.group("a"))
        rest = text[cm.end():].strip()
        return (a, a, rest) if a and rest else None

    block = _author_block(text)
    if not block:
        return None
    persons, rest, truncated = block
    persons = [_clean_person(p) for p in persons if _clean_person(p)]
    if not persons or not rest:
        return None
    first = persons[0]
    # A lone surname without a comma is a personal author only when initials
    # follow it.  A plain-ASCII all-caps token, or a multiword caps string with
    # no initials, is more often an institution; the v0.8 route keeps those.
    if len(persons) == 1 and "," not in first:
        if re.fullmatch(r"[A-Z]{3,12}", first):
            return None
        if len(first.split()) > 1 and not re.search(rf"\s[{_UC}]\.?$", first):
            return None
    authors = " | ".join(persons)
    if truncated:
        authors = authors + " et al."
    return first, authors, rest


# --------------------------------------------------------------------------
# Journal candidate cleanup
# --------------------------------------------------------------------------

_COMPACT_META_RE = re.compile(
    r"[,;.]\s*(?="
    r"\d{1,4}\s*\(\s*[^)]{1,14}\s*\)\s*[:,;]"        # 31(1):11-25
    r"|\d{1,4}\s*:\s*\d{1,5}"                         # 44: 166-206
    r"|(?:19|20)\d{2}\s*,\s*\d{1,4}\s*[:,]\s*\d"      # 1966, 44: 166
    r"|e\d{3,8}\b"                                    # e25314
    r")",
    re.I,
)
_CORPORATE_TAIL_RE = re.compile(
    r"\b(?:institute|institution|institut|society|association|academy|council|"
    r"federation|foundation|press|publish(?:ing|ers?)|elsevier|springer|wiley|"
    r"routledge|sage|taylor\s*&?\s*francis|emerald|ieee|acm|inc\.?|ltda?\.?|llc|"
    r"editora|ediciones|editorial|universidade|university)\b",
    re.I,
)
_PLACE_TAIL_RE = re.compile(
    r"\[?\s*S\.?\s*l\.?\s*\]?"
    r"|(?:Rio\s+de\s+Janeiro|S[ãa]o\s+Paulo|S[ãa]o\s+Carlos|Curitiba|Bras[ií]lia|Porto\s+Alegre|"
    r"Florian[oó]polis|Belo\s+Horizonte|Recife|Salvador|Fortaleza|Campinas|Goi[aâ]nia|"
    r"Vit[oó]ria|Natal|Manaus|Bel[eé]m|Jo[aã]o\s+Pessoa|Macei[oó]|Teresina|S[ãa]o\s+Lu[ií]s|"
    r"Cuiab[aá]|Campo\s+Grande|Aracaju|Palmas|Boa\s+Vista|Porto\s+Velho|Rio\s+Branco|Macap[aá]|"
    r"Santa\s+Catarina|Minas\s+Gerais|Rio\s+Grande\s+do\s+Sul|Paran[aá]|Bahia|Pernambuco|"
    r"Buenos\s+Aires|Montevideo|Santiago|Bogot[aá]|Lima|Madrid|Barcelona|M[eé]xico|Lisboa|Porto)",
    re.I,
)


def _strip_corporate_tail(candidate: str) -> str:
    parts = [p.strip() for p in candidate.split(",")]
    while len(parts) >= 2:
        last = parts[-1]
        if _CORPORATE_TAIL_RE.search(last) and not _JOURNAL_CUE_RE.search(last):
            parts = parts[:-1]
            continue
        break
    return ", ".join(parts).strip(" .;,")


def _strip_place_tail(candidate: str) -> str:
    # Comma-separated place: ``Journal, Curitiba`` / ``Journal, [S.l.]``.
    parts = [p.strip() for p in candidate.split(",")]
    if len(parts) >= 2:
        last = parts[-1]
        head = ", ".join(parts[:-1])
        journal_like_tail = bool(_JOURNAL_CUE_RE.search(last))
        placeish = bool(_PLACE_TAIL_RE.fullmatch(last))
        if not journal_like_tail and (
            placeish or (_JOURNAL_CUE_RE.search(head) and 1 <= len(last.split()) <= 4)
        ):
            candidate = head
    # Full-stop separated place: ``Arq Catarinense de Medicina. Santa Catarina``.
    dot_parts = re.split(r"\.\s+", candidate)
    if len(dot_parts) >= 2 and _PLACE_TAIL_RE.fullmatch(dot_parts[-1].strip(" .;,")):
        candidate = ". ".join(dot_parts[:-1])
    return candidate.strip(" .;,")


def _journal_from_tail_v09(tail: str) -> Optional[str]:
    c, _ = _v08._strip_in(tail)
    c = _v06._strip_source_descriptors(c)
    c = re.sub(r"\s+", " ", c).strip(" .;,")
    if not c:
        return None

    cut = None
    m = re.search(r"[,;.]\s*(?=(?:v(?:ol)?\.?|n[º°o]?\.?|p{1,2}\.?)\s*[^,;.]+)", c, re.I)
    if m:
        cut = m.start()
    m2 = _COMPACT_META_RE.search(c)
    if m2 and (cut is None or m2.start() < cut):
        cut = m2.start()
    if cut is None:
        m3 = re.search(r"\s+(?=(?:v(?:ol)?\.?|n[º°o]?\.?|p{1,2}\.?)\s*\d)", c, re.I)
        if m3:
            cut = m3.start()
    candidate = c[:cut].strip(" .;,") if cut is not None else c

    candidate = re.sub(
        r"\s*\[(?:[^\]]*(?:SciELO|Scientific\s+Electronic|Online|Index|Database)[^\]]*)\]\s*$",
        "", candidate, flags=re.I,
    ).strip(" .;,")
    candidate = _strip_corporate_tail(candidate)
    candidate = _strip_place_tail(candidate)
    return candidate.strip(" .;,") or None


def _looks_article_container_v09(container: str, after_year: str = "") -> bool:
    c = container.strip()
    if _ARTICLE_META_RE.search(c):
        return True
    if _JOURNAL_CUE_RE.search(c[:180]):
        return True
    if _COMPACT_META_RE.search(c):
        return True
    # Periodical metadata may follow the publication year in less regular ABNT
    # styles: ``... Quarterly, 1966, 44: 166-206``.
    tail = str(after_year or "").strip()
    if tail and ":" not in c:
        if _ARTICLE_META_RE.search(tail) or re.match(r"^\d{1,4}\s*[:,]\s*\d", tail):
            return True
    if ":" in c:
        return False
    return _v06._looks_article_container(c)


# --------------------------------------------------------------------------
# ABNT route
# --------------------------------------------------------------------------

# Any parenthesis carrying a four-digit year in the head of the reference is
# author-year evidence, including Spanish/Portuguese long dates such as
# ``(28 de agosto de 2014)`` that the bare year-parenthesis pattern misses.
_PAREN_YEAR_RE = re.compile(r"\([^)]{0,60}\b(?:18|19|20)\d{2}\b[^)]{0,20}\)")


def _parse_abnt_v09(text: str) -> Optional[Dict[str, Any]]:
    if not text or _v03._YEAR_PAREN_RE.search(text[:280]):
        return None
    if _PAREN_YEAR_RE.search(text[:280]):
        return None
    ab = _split_authors_v09(text)
    if not ab:
        return None
    author, authors, rest = ab
    rest = _v08._strip_leading_author_descriptors(rest)
    core = _v08._core_before_access(text)
    idx = text.find(rest)
    prefix_len = idx if idx >= 0 else len(text) - len(rest)
    core_rest = core[prefix_len:].strip() if prefix_len < len(core) else ""
    is_thesis = bool(_THESIS_RE.search(core_rest))
    ym = _v08._publication_year(core, prefix_len, is_thesis=is_thesis)
    if not ym or ym.start() <= prefix_len:
        return None
    local_target = max(0, ym.start() - prefix_len)
    local_matches = list(re.finditer(re.escape(ym.group(0)), core_rest))
    if not local_matches:
        return None
    local_year = min(local_matches, key=lambda m: abs(m.start() - local_target))
    split = _v08._split_title_tail(rest, local_year, core_rest, is_thesis)
    if not split:
        return None
    title, tail = split
    title = re.sub(r"\s+", " ", title).strip(" .;,")
    title = re.sub(
        r"\s*\[(?:jan(?:eiro)?|fev(?:ereiro)?|mar(?:[cç]o)?|abr(?:il)?|mai(?:o)?|jun(?:ho)?|"
        r"jul(?:ho)?|ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|dez(?:embro)?)"
        r"(?:\s+de)?\s+(?:19|20)\d{2}\]$", "", title, flags=re.I).strip(" .;,")
    if not title:
        return None
    after_year = core_rest[local_year.end():].lstrip(" .;,")
    container, had_in = _v08._strip_in(tail)
    has_url = bool(re.search(r"https?://|www\.", text, re.I))
    interview_like = bool(re.search(r"\bEntrevistador(?:a|es)?\b|\bentrevista\b", tail, re.I))

    if interview_like and has_url:
        publication_type = "recurso_web"
        journal = None
        publisher, publisher_observed = _v08._publisher_from_tail(tail)
    elif is_thesis:
        publication_type = "tesis"
        journal = None
        institution = _v08._thesis_institution(core_rest)
        publisher = institution
        publisher_observed = institution
    else:
        chapter_like = had_in and _v08._looks_chapter_container(container)
        article_like = (not chapter_like) and _looks_article_container_v09(container, after_year)
        journal = _journal_from_tail_v09(tail) if article_like and not chapter_like else None
        if journal:
            publication_type = "articulo_revista"
            publisher = publisher_observed = None
        elif chapter_like:
            publication_type = "capitulo_libro"
            publisher, publisher_observed = _v08._publisher_from_tail(tail)
        else:
            publisher, publisher_observed = _v08._publisher_from_tail(tail)
            if publisher:
                publication_type = "libro"
            elif article_like:
                publication_type = "articulo_revista"
            elif re.search(r"\b(?:ed\.?|edi[cç][aã]o|reimpress[aã]o|cole[cç][aã]o)\b", tail, re.I):
                publication_type = "libro"
            else:
                publication_type = "sin_clasificar"

    if "," in author:
        style = "abnt_v09_personal_year_end"
    elif "&" in author:
        style = "abnt_v09_collective_year_end"
    else:
        style = "abnt_v09_nocomma_year_end"
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


# --------------------------------------------------------------------------
# APA journal rescue
# --------------------------------------------------------------------------

_APA_META_V09 = [
    re.compile(r",\s*(?:vol\.?\s*)?\d{1,4}\s*\(\s*[^)]{1,14}\s*\)", re.I),
    re.compile(r",\s*(?:vol\.?\s*)?\d{1,4}\s*,\s*[A-Za-z]?\d", re.I),
    re.compile(r",\s*e\d{3,8}\b", re.I),
    re.compile(r",\s*\(?\s*(?:online|no\s+prelo|in\s+press|ahead\s+of\s+print)\s*\)?", re.I),
    re.compile(r",\s*(?:vol\.?\s*)?\d{1,4}\s*\.?\s*$", re.I),
]
_APA_EVIDENCE_RE = re.compile(
    r"(?:doi\s*:?\s*10\.|h?ttps?://(?:dx\.)?doi\.org/|"
    r",\s*\d{1,4}\s*\(\s*[^)]{1,14}\s*\)|,\s*e\d{3,8}\b|"
    r",\s*\(?\s*(?:online|no\s+prelo|in\s+press|ahead\s+of\s+print)\s*\)?)",
    re.I,
)
_APA_LINK_SPLIT_RE = re.compile(
    r"\s*(?:h?ttps?://|www\.|doi\s*:\s*10\.|Retrieved\b|Recuperado\b|Recuperada\b|"
    r"Dispon[ií]vel\b|Acesso\b)",
    re.I,
)
_BRACKET_DESCRIPTOR_RE = re.compile(r"\[[^\]]{0,200}\]")


def _apa_first_meta(source: str):
    first = None
    for pat in _APA_META_V09:
        m = pat.search(source)
        if m and (first is None or m.start() < first.start()):
            first = m
    return first


def _plausible_journal_v09(candidate: str) -> bool:
    c = re.sub(r"\s+", " ", candidate).strip(" .,:;")
    if not (2 <= len(c) <= 160):
        return False
    words = c.split()
    if not (1 <= len(words) <= 14):
        return False
    if not re.match(rf"^[{_UC}A-Z(]", c):
        return False
    if re.search(r"\b(?:pp?|vol|doi|ed|eds)\.", c, re.I):
        return False
    # Sentence-like tails are titles, not sources.
    if re.search(r"\.\s+[a-z]", c):
        return False
    if _v02.BOOK_EDITOR_RE.search(c) or _BRACKET_DESCRIPTOR_RE.search(c):
        return False
    return True


def _apa_journal_rescue(text: str, base: Dict[str, Any]) -> Optional[str]:
    """Recover an APA journal when the base route produced none.

    The route is gated on explicit periodical evidence and on the absence of
    monograph/chapter/thesis evidence, so it can only add a source where the
    parser previously abstained.
    """
    if base.get("journal"):
        return None
    if not _v03._YEAR_PAREN_RE.search(text[:260]):
        return None
    if not _APA_EVIDENCE_RE.search(text):
        return None
    if _v02._is_chapter(text) or _v02.THESIS_RE.search(text) or _THESIS_RE.search(text):
        return None
    if _v02.BOOK_CUE_RE.search(text) or _v02.CONF_RE.search(text) or _v02.LEGAL_RE.search(text):
        return None
    if base.get("publisher"):
        return None
    if re.search(r"\[[^\]]*(?:tese|disserta|thesis|dissertation|tesis)[^\]]*\]", text, re.I):
        return None

    source = _v02._strip_auth_year(text)
    source = _APA_LINK_SPLIT_RE.split(source, maxsplit=1)[0].strip()
    if not source:
        return None
    title = str(base.get("title") or "").strip()
    title_removed = False
    if title:
        pos = source.casefold().find(title.casefold())
        if 0 <= pos <= 8:
            source = source[pos + len(title):].lstrip(" .,:;")
            title_removed = True
    meta = _apa_first_meta(source)
    if not meta:
        return None
    candidate = source[:meta.start()].strip(" .,:;")
    # Removing the parsed title can leave a residual subtitle sentence glued to
    # the source (``Un análisis para su estudio e investigación. Revista
    # Signos``).  The scored split is applied in both branches; it refuses to
    # cut after a one-word prefix, which protects abbreviated journal names
    # such as ``Cad. Saúde Pública``.
    _, cand = _v03._split_title_journal_before_meta(candidate)
    if cand:
        candidate = cand
    elif not title_removed:
        return None
    candidate = re.sub(r"^(?:In|En)\s+", "", candidate, flags=re.I).strip(" .,:;")
    if not _plausible_journal_v09(candidate):
        return None
    return _v03._canonicalize_journal(candidate)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    base = _v08.parse_reference(text)
    abnt = _parse_abnt_v09(text)
    if abnt:
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

    out = dict(base)
    rescued = _apa_journal_rescue(text, base)
    if rescued:
        out["journal"] = rescued
        out["publication_type"] = "articulo_revista"
        out["publisher"] = None
        out["source_publisher"] = None
        out["parse_style"] = str(base.get("parse_style") or "") + "+v09_journal_rescue"
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
        "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
