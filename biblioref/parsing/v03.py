# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.3.

v0.3 is a conservative downstream parser revision derived from the external
v0.2 parser pilot.  It does **not** alter PDF detection or reference
segmentation.  The first five external theses used to diagnose v0.2 are now a
development/regression set for this parser; the three reserve theses remain
unseen until v0.3 is frozen.

Main changes over v0.2:
- explicit grammar for author-year references where the year is not parenthesized;
- explicit Vancouver-ish grammar (authors. title. journal. year;volume:pages);
- journal extraction preserves complete names with colons/subtitles instead of
  collapsing them to short contained aliases;
- support for article-number and ``p.123`` journal metadata tails;
- conservative structural publisher recovery for monographs/chapters;
- measurement instruments/manuals are distinguished from ordinary books,
  while DSM-style monographs are treated as books in the bibliometric taxonomy.

Raw citation text remains authoritative and every parsed field is downstream.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v02 as _v02
from .legacy import parse_reference as _legacy_parse
from .lexicons_v02 import JOURNAL_ALIASES, PUBLISHER_ALIASES

PARSER_VERSION = "biblioref-parser-v0.3"
PARSER_SCHEMA_VERSION = 3
PARSER_STATUS = "development_candidate"

_DOI_RE = re.compile(r'(10\.\d{4,9}/[^\s"<>]+)', re.I)
_YEAR_PAREN_RE = re.compile(r'\(\s*((?:18|19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)', re.I)
_YEAR_BARE_RE = re.compile(r'(?<![\w(])((?:18|19|20)\d{2})(?:[a-z])?\b', re.I)

# Journal metadata tails.  The patterns are ordered from most informative to
# most permissive.  They return the start of volume/issue/pages metadata.
_META_PATTERNS_V03 = [
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*\(\s*(?:\d+|suppl\.?\s*\d*|supl\.?\s*\d*)\s*\)\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d{1,7}(?:\s*[-–—]\s*[A-Za-z]?\d{1,7})?', re.I),
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d{1,7}(?:\s*[-–—]\s*[A-Za-z]?\d{1,7})', re.I),
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*[,;:]\s*p\.?\s*\d{1,7}\b', re.I),
    re.compile(r'\s*,?\s*(?:vol\.?\s*)?\d{1,4}\s*[,;:]\s*\d{5,9}\b', re.I),  # article number
    re.compile(r'\s*,?\s*(?:n[º°o]\.?\s*)?\d{1,4}\s*\(\s*\d+\s*\)', re.I),
    re.compile(r'\s+N[°ºo]\s*\d+\s*\(\s*\d+\s*\)', re.I),
]
_META_VOLUME_ONLY = re.compile(r'\s*,\s*\d{1,4}\s*\.?\s*$', re.I)

_JOURNAL_CUE_RE = re.compile(
    r'\b(journal|review|revista|psycholog|psychiatr|psychotherap|therapy|assessment|'
    r'behavior|behaviour|research|practice|frontiers|traumatolog|medicine|medical|'
    r'health|science|sciences|synthesis|bulletin|quarterly|annual|annals|anales|'
    r'cortex|neuro|development|education|work|police|personality)\b', re.I
)

_INSTRUMENT_RE = re.compile(
    r'\b(scale|scales|inventory|inventor(?:y|ies)|questionnaire|test battery|assessment\s+tool|'
    r'psycTests|database record|rating scales?|index\s*\([A-Z]{2,8}\))\b', re.I
)
_DSM_RE = re.compile(r'\bdiagnostic\s+and\s+statistical\s+manual\s+of\s+mental\s+disorders\b', re.I)


def _norm(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).casefold().replace("&", " and ")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_links(text: str) -> str:
    t = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|(?:doi\s*:?\s*)10\.\S+)', text, maxsplit=1, flags=re.I)[0]
    return t.strip()


def _find_first_meta(source: str):
    first = None
    for pat in _META_PATTERNS_V03:
        m = pat.search(source)
        if m and (first is None or m.start() < first.start()):
            first = m
    return first


def _canonicalize_journal(candidate: Optional[str]) -> Optional[str]:
    """Normalize only exact/full aliases; never collapse to a contained word.

    v0.2 could turn ``Clinical Psychology & Psychotherapy`` into
    ``Psychotherapy`` because that shorter alias occurred inside the candidate.
    v0.3 preserves the complete observed source unless an exact normalized alias
    explicitly repairs spelling/punctuation.
    """
    if not candidate:
        return None
    cand = re.sub(r"\s+", " ", candidate).strip(" .,:;")
    n = _norm(cand)
    if not n:
        return None
    canonical = JOURNAL_ALIASES.get(n)
    if canonical:
        return cand if _norm(canonical) == n else canonical
    return cand


def _plausible_journal(candidate: str, *, allow_single: bool = False) -> bool:
    c = re.sub(r"\s+", " ", candidate).strip(" .,:;")
    if not c or len(c) > 180:
        return False
    words = c.split()
    if len(words) > 18:
        return False
    if len(words) == 1 and not allow_single:
        # Single-word journals are allowed only when the word looks like a
        # source title rather than a generic tail.
        return bool(_norm(c) in JOURNAL_ALIASES or re.search(r'^(Assessment|Traumatology|Cortex|Brain|NeuroImage)$', c, re.I))
    if re.search(r'\b(?:pp?|vol|doi)\.?\b', c, re.I):
        return False
    return True


def _journal_split_score(prefix: str, candidate: str, sep: str) -> float:
    c = candidate.strip(" .,:;")
    p = prefix.strip(" .,:;")
    if not _plausible_journal(c, allow_single=True) or len(p.split()) < 3:
        return -999.0
    n = _norm(c)
    score = 0.0
    if n in JOURNAL_ALIASES:
        score += 6.0
    if _JOURNAL_CUE_RE.search(c):
        score += 3.0
    if 2 <= len(c.split()) <= 12:
        score += 1.5
    if len(p.split()) >= 6:
        score += 1.0
    if sep == ".":
        score += 1.0
    elif sep == ",":
        score += 0.2
    # Penalize obvious title-like sentence tails.
    if c and c[0].islower() and n not in JOURNAL_ALIASES:
        score -= 1.0
    if len(c.split()) == 1 and n not in JOURNAL_ALIASES:
        score -= 1.5
    return score


def _split_title_journal_before_meta(text_before_meta: str) -> Tuple[Optional[str], Optional[str]]:
    """Split ``title + journal`` without using colon as a delimiter."""
    s = re.sub(r"\s+", " ", text_before_meta).strip(" .,:;")
    if not s:
        return None, None

    candidates: List[Tuple[float, str, str]] = []
    # Sentence boundaries. Avoid periods internal to initials/abbreviations by
    # requiring the next token to begin with a letter and evaluating plausibility.
    for m in re.finditer(r'\.\s+(?=[A-Za-zÁÉÍÓÚÑ])', s):
        p, c = s[:m.start()], s[m.end():]
        candidates.append((_journal_split_score(p, c, "."), p, c))
    # Some British styles separate title and source with a comma.
    for m in re.finditer(r',\s+(?=[A-Za-zÁÉÍÓÚÑ])', s):
        p, c = s[:m.start()], s[m.end():]
        candidates.append((_journal_split_score(p, c, ","), p, c))

    if candidates:
        score, title, journal = max(candidates, key=lambda x: x[0])
        if score >= 2.5:
            return title.strip(" .,:;"), journal.strip(" .,:;")
    return None, None


def _parse_bare_year(text: str) -> Optional[Dict[str, Any]]:
    """Parse author-year references with a non-parenthesized year.

    Examples include Harvard-style references such as ``Smith, J. 2020. Title.
    Journal, 12(2), 1-10``.  The rule abstains when the year is parenthesized or
    occurs too late to plausibly terminate the author block.
    """
    if _YEAR_PAREN_RE.search(text[:260]):
        return None
    m = _YEAR_BARE_RE.search(text[:320])
    if not m or m.start() < 3:
        return None
    before = text[:m.start()].strip(" ,.;:")
    if len(before) > 260 or not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', before):
        return None
    # Reject years occurring inside/after a title or container. A genuine
    # Harvard author block is mostly surnames/initials plus short connectors;
    # sentence-like lowercase words or title punctuation indicate that the year
    # is bibliographic metadata later in the reference, not the author/year
    # boundary.
    if re.search(r'[():«»“”"]', before):
        return None
    lower_words = [w for w in re.findall(r'\b[a-záéíóúñ]{4,}\b', before) if w not in {"with"}]
    if lower_words:
        return None
    # Require personal/institutional author structure and a boundary after year.
    if not ("," in before or re.search(r'\b(?:association|university|organisation|organization|institute|ministerio)\b', before, re.I)):
        return None
    after = text[m.end():]
    if after and not re.match(r'^[a-z]?\s*[.,;:]?\s*', after, re.I):
        return None
    tail = re.sub(r'^[a-z]?\s*[.,;:]?\s*', '', after, count=1, flags=re.I)
    tail = _strip_links(tail)
    if len(tail.split()) < 4:
        return None

    first_author = _v02._first_author_from_block(before)
    if not first_author:
        # Harvard blocks sometimes omit punctuation after initials; recover only
        # the leading surname/initials conservatively.
        mfa = re.match(r'^([^,]{2,80}),\s*([A-Z](?:\.?\s*[A-Z]\.?){0,3})', before)
        if mfa:
            first_author = f"{mfa.group(1).strip()}, {_v02._format_initials(mfa.group(2))}"

    # Reuse v0.2's author-list parser by creating a temporary parenthesized form.
    fake = f"{before} ({m.group(1)}). X."
    _, authors = _v02.extract_authors(fake, "")

    meta = _find_first_meta(tail)
    before_meta = tail[:meta.start()].strip(" .,:;") if meta else tail.strip(" .,:;")
    title, journal = _split_title_journal_before_meta(before_meta)
    # Volume-only articles such as ``British Medical Journal, 368.``
    if not journal:
        vm = _META_VOLUME_ONLY.search(tail)
        if vm:
            title, journal = _split_title_journal_before_meta(tail[:vm.start()].strip(" .,:;"))
    if not title:
        # Conservative fallback: first sentence after year is the title.
        sm = re.search(r'\.\s+(?=[A-Za-zÁÉÍÓÚÑ])', tail)
        if sm:
            title = tail[:sm.start()].strip(" .,:;")
    return {
        "author": first_author,
        "authors": authors,
        "year": m.group(1),
        "title": title,
        "journal": _canonicalize_journal(journal),
    }


def _parse_vancouverish(text: str) -> Optional[Dict[str, Any]]:
    """Parse common Vancouver-ish ``authors. title. journal. year;vol:pages``."""
    t = _strip_links(re.sub(r"\s+", " ", text).strip())
    ym = re.search(r'\b((?:18|19|20)\d{2})\s*;\s*\d{1,4}(?:\s*\([^)]*\))?\s*:\s*[A-Za-z]?\d{1,7}', t)
    if not ym:
        return None
    left = t[:ym.start()].rstrip(" .;,")
    # Journal is the final period-delimited segment before year.
    jsep = left.rfind(". ")
    if jsep < 0:
        return None
    journal = left[jsep + 2:].strip(" .,:;")
    pre = left[:jsep].rstrip(" .")
    tsep = pre.rfind(". ")
    if tsep < 0:
        return None
    author_block = pre[:tsep].strip(" .,:;")
    title = pre[tsep + 2:].strip(" .,:;")
    if not (author_block and title and _plausible_journal(journal, allow_single=True)):
        return None
    # Vancouver authors frequently look like ``Barker TH, Habibi N``.
    first_piece = re.split(r',|\bet\s+al\.?', author_block, maxsplit=1, flags=re.I)[0].strip()
    first_author = first_piece or None
    authors_parts = [p.strip(" ,.") for p in re.split(r',\s*', re.sub(r',?\s*et\s+al\.?', '', author_block, flags=re.I)) if p.strip(" ,.")]
    authors = " | ".join(authors_parts)
    return {
        "author": first_author,
        "authors": authors,
        "year": ym.group(1),
        "title": title,
        "journal": _canonicalize_journal(journal),
    }


def _journal_from_parenthetical(text: str, title: str) -> Optional[str]:
    """v0.2-style source extraction with wider metadata and no alias collapse."""
    if _v02._is_chapter(text):
        return None
    t = _v02._strip_auth_year(text)
    t = _strip_links(t)
    source = t
    title = str(title or "").strip()
    title_removed = False
    if title:
        # Exact textual title removal first.
        pos = source.casefold().find(title.casefold())
        if 0 <= pos <= 8:
            source = source[pos + len(title):].lstrip(" .,:;")
            title_removed = True
        else:
            # v0.1 may include trailing edition/database descriptors. Try a
            # normalized prefix only when it is very close to the start.
            ns, nt = _norm(source), _norm(title)
            if nt and ns.startswith(nt):
                # keep the original string untouched if we cannot map lengths;
                # exact removal is safer than approximate slicing.
                pass
    meta = _find_first_meta(source)
    if not meta:
        vm = _META_VOLUME_ONLY.search(source)
        if vm:
            cand0 = source[:vm.start()].strip(" .,:;")
            if _JOURNAL_CUE_RE.search(cand0) or _norm(cand0) in JOURNAL_ALIASES:
                meta = vm
    if not meta:
        return None
    candidate = source[:meta.start()].strip(" .,:;")
    if not title_removed:
        # Split title and source directly rather than trimming at the last period,
        # which is unsafe for initials and abbreviations.
        _, cand = _split_title_journal_before_meta(candidate)
        candidate = cand or candidate
    candidate = re.sub(r'^(?:In|En)\s+', '', candidate, flags=re.I).strip()
    if not _plausible_journal(candidate, allow_single=True):
        return None
    return _canonicalize_journal(candidate)


def _strip_title_descriptors(title: Optional[str]) -> Optional[str]:
    if not title:
        return title
    t = str(title).strip()
    # Non-content catalog descriptors are safe to exclude from a title field.
    t = re.sub(r'\s*\[(?:Database record|Data set|Dataset|Measurement instrument)\]\s*$', '', t, flags=re.I)
    return t.strip(" .")


def _structural_publisher(text: str, title: str, author: Optional[str], publication_type: str) -> Optional[str]:
    if publication_type not in {"libro", "capitulo_libro", "documento_guia_manual"}:
        return None
    t = _strip_links(re.sub(r"\s+", " ", text).strip())
    # Start after parenthesized/bare year.
    pm = _YEAR_PAREN_RE.search(t[:260])
    if pm:
        tail = t[pm.end():].lstrip(" .,:;")
    else:
        bm = _YEAR_BARE_RE.search(t[:320])
        tail = t[bm.end():].lstrip(" a-z.,:;",) if bm else t
    # Prefer text after the parsed title when it occurs literally.
    if title:
        pos = tail.casefold().find(str(title).casefold())
        if 0 <= pos <= 20:
            tail = tail[pos + len(str(title)):].lstrip(" .,:;")
    # For chapters, discard book container through page range.
    if publication_type == "capitulo_libro":
        mp = re.search(r'\(\s*pp?\.?\s*\d{1,5}\s*[-–—]\s*\d{1,5}\s*\)\.?\s*', tail, re.I)
        if mp:
            tail = tail[mp.end():].lstrip(" .,:;")
    tail = re.sub(r'^\([^)]*(?:ed\.|edition)[^)]*\)\.?\s*', '', tail, flags=re.I)
    tail = tail.strip(" .")
    if not tail:
        return None

    # Institutional ``Author`` means the work's corporate author is publisher.
    if re.search(r'(?:^|[:.]\s*)Author\.?$', tail, re.I) and author and re.search(r'association|organization|organisation|university|institute', author, re.I):
        return author

    # Remove a leading place before a colon: ``New York: Guilford Press``.
    if ":" in tail:
        left, right = tail.rsplit(":", 1)
        if right.strip() and len(right.strip().split()) <= 12:
            # For co-publisher strings like ``Kluwer Academic: Plenum Publishers``
            # the right side is a valid publisher in its own right.
            tail = right.strip()

    # Clean catalog/edition tails but preserve parenthetical abbreviations (MHS).
    tail = re.split(r'(?i)\s+(?:https?://|Retrieved\b|Recuperado\b)', tail, maxsplit=1)[0]
    cand = tail.strip(" .,:;")
    if not cand or len(cand) > 140 or len(cand.split()) > 16:
        return None

    # High-confidence publisher shapes, including organizations and test houses.
    if re.search(r'\b(?:Press|Publishing|Publishers?|Verlag|Ediciones?|Editorial|Sons|PsycTests|Systems?\s+Incorporated|Association)\b', cand, re.I):
        n = _norm(cand)
        exact = PUBLISHER_ALIASES.get(n)
        # Preserve the observed full name when the lexicon would collapse it to
        # a strict substring (e.g. John Wiley & Sons -> Wiley).
        if exact and _norm(exact) == n:
            return cand
        if exact and len(_norm(exact)) >= 0.75 * len(n):
            return exact
        return cand
    return None


def _classify_v03(text: str, journal: Optional[str], publisher: Optional[str], title: Optional[str], base_type: str) -> str:
    t = str(text or "")
    if _v02.LEGAL_RE.search(t):
        return "documento_legal"
    if _v02.THESIS_RE.search(t):
        return "tesis"
    if _v02._is_chapter(t):
        return "capitulo_libro"
    if _v02.CONF_RE.search(t):
        return "conference_paper"
    if journal:
        return "articulo_revista"
    # DSM is treated as a monograph in the bibliometric document taxonomy,
    # despite the word "Manual" in its title.
    if _DSM_RE.search(t):
        return "libro"
    if _INSTRUMENT_RE.search(t) or re.search(r'\b(?:BDI-II|CAARS|PAS)\b', t, re.I):
        return "documento_guia_manual"
    # Preserve a v0.2 monograph decision unless a stronger v0.3 grammar above
    # has already identified chapter, conference, journal, DSM or instrument.
    # This prevents generic numeric tails inside books from being promoted to
    # articles and protects development-tested publisher assignments.
    if base_type in {"libro", "capitulo_libro"}:
        return base_type
    # Keep v0.2's remaining precedence and cues.
    if re.search(r'\b\d{1,4}\s*\(\s*\d+\s*\)\s*[,;:]\s*(?:pp?\.?\s*)?[A-Za-z]?\d', t):
        return "articulo_revista"
    if re.search(r'\b\d{1,4}\s*[,;:]\s*(?:pp?\.?\s*)?\d{1,7}(?:\s*[-–—]\s*\d{1,7})\b', t) and not _v02.BOOK_CUE_RE.search(t):
        return "articulo_revista"
    if _DOI_RE.search(t) and _v02.ARTICLE_WORD_RE.search(t):
        return "articulo_revista"
    if _v02.GUIDE_RE.search(t):
        return "documento_guia_manual"
    if _v02.REPORT_RE.search(t):
        return "informe_documento"
    if publisher or _v02.BOOK_CUE_RE.search(t):
        return "libro"
    if _v02.WEB_RE.search(t):
        return "material_web"
    return base_type or "sin_clasificar"


def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    old = _legacy_parse(text)
    base = _v02.parse_reference(text)

    # Style-specific overrides. Vancouver is tested first because its year is
    # near the end and should not be mistaken for a Harvard author-year prefix.
    style = _parse_vancouverish(text)
    style_name = "vancouverish" if style else None
    if not style:
        style = _parse_bare_year(text)
        style_name = "bare_year" if style else None

    author = (style or {}).get("author") or base.get("author")
    authors = (style or {}).get("authors") or base.get("authors")
    year = (style or {}).get("year") or base.get("year")
    title = (style or {}).get("title") or base.get("title")
    title = _strip_title_descriptors(title)

    if style and style.get("journal"):
        journal = style.get("journal")
    else:
        base_journal = base.get("journal")
        # A development-tested monograph publisher is negative evidence for
        # journal rescue. This blocks book/chapter tails such as
        # ``Harvard University Press, 174`` from being reinterpreted as a
        # volume-only journal source.
        base_monograph = bool(base.get("publisher")) and base.get("publication_type") in {"libro", "capitulo_libro"}
        expanded_journal = (_journal_from_parenthetical(text, title or "")
                            if _YEAR_PAREN_RE.search(text[:260]) and not base_monograph else None)
        if base_journal and expanded_journal:
            nb, ne = _norm(base_journal), _norm(expanded_journal)
            # Keep v0.2's canonical label unless it is clearly just a generic
            # contained tail of the fuller observed source (Psychotherapy,
            # Psychology, etc.).
            generic_tail = nb in {
                "psychotherapy", "psychology", "therapy", "research", "review",
                "journal", "assessment", "psychiatry", "medicine"
            }
            if nb and nb in ne and generic_tail and len(ne) > len(nb):
                journal = expanded_journal
            else:
                journal = base_journal
        else:
            journal = expanded_journal or base_journal

    # First-pass type without publisher lets us select a monographic tail.
    provisional_type = _classify_v03(text, journal, None, title, base.get("publication_type") or "")
    structural_pub = _structural_publisher(text, title or "", author, provisional_type)
    # Preserve v0.2's development-tested canonical publisher whenever it
    # exists; structural recovery is primarily a coverage rescue for cases
    # where v0.2 abstained.
    publisher = base.get("publisher") or structural_pub
    publication_type = _classify_v03(text, journal, publisher, title, base.get("publication_type") or "")

    if publication_type != "articulo_revista":
        journal = None
    if publication_type == "articulo_revista":
        publisher = None
    elif publication_type not in {"libro", "capitulo_libro", "documento_guia_manual"}:
        publisher = None

    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "parser_status": PARSER_STATUS,
        "parse_style": style_name or "legacy_parenthetical_or_fallback",
        "author": author,
        "authors": authors,
        "year": year,
        "publication_type": publication_type,
        "title": title,
        "journal": journal,
        "publisher": publisher,
        "source_publisher": publisher,
        "doi": old.get("doi"),  # DOI remains the legacy exact extraction path.
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
        "publication_type", "title", "journal", "publisher", "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
