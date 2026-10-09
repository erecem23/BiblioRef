# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.11.

v0.11 adds a conservative route for legacy Ibero-American humanities/legal
references whose publication year is normally placed at the end of the entry
rather than immediately after the author block.  The development trigger came
from a 322-reference Sociology dissertation (Universidad de Belgrano) where
segmentation was exact but v0.10 left most authors/sources unparsed.

Design constraints
------------------
* v0.10 is the base and remains unchanged for references outside the new route.
* Leading list bullets are presentation noise and are stripped before parsing.
* A URL is treated as access evidence, not automatically as publication type.
* ``tesis`` is only assigned on explicit document-form evidence (``Tesis
  Doctoral``, dissertation, etc.), never because the title or publisher happens
  to contain the word ``tesis``.
* The route abstains on ordinary parenthetical author-year/APA/ABNT references.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v10 as _v10
from . import v03 as _v03
from . import v02 as _v02

PARSER_VERSION = "biblioref-parser-v0.11"
PARSER_SCHEMA_VERSION = 11
PARSER_STATUS = "development_candidate"

_BULLET_RE = re.compile(r"^\s*(?:[\u25a0-\u25ff\u2022\u2023\u2043\u2219\uf000-\uf8ff]+|[-–—*])\s*")
_YEAR_RE = re.compile(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)")
_ACCESS_TAIL_RE = re.compile(r"\s*[;,]?\s*(?:última\s+visita|ultima\s+visita|consultad[oa]|acceso)\s*:\s*.*$", re.I)
_URL_RE = re.compile(r"https?://|www\.", re.I)
_PARENTHESES_YEAR_EARLY_RE = re.compile(r"\(\s*(?:18|19|20)\d{2}[a-z]?\s*\)", re.I)

_PERSON_WORD = r"[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’´.-]*"
_SURNAME = rf"{_PERSON_WORD}(?:\s+(?:de|del|de\s+la|de\s+los|da|do|dos|das|van|von|y)?\s*{_PERSON_WORD}){{0,4}}"
_GIVEN = rf"(?:{_PERSON_WORD}|[A-ZÁÉÍÓÚÜÑ]\.)+(?:\s+(?:{_PERSON_WORD}|[A-ZÁÉÍÓÚÜÑ]\.)){{0,5}}"
_ROLE = r"(?:Compiladores?|Compiladoras?|Coordinadores?|Coordinadoras?|Directores?|Directoras?(?:\s+de\s+Investigaci[oó]n)?|Editor(?:es)?|Editoras?|Autor\s*[–-]\s*Coordinador|Relator\s*[–-]\s*Compilador|Pr[oó]logo|Autores?|Coords?|Comps?|Dirs?)"

_CORP_CUE_RE = re.compile(
    r"^(?:ARGENJUS|UNESCO|PNUD|PROJUS|FORES|Banco\b|Corte\b|Consejo\b|Instituto\b|"
    r"Asociaci[oó]n\b|Corporaci[oó]n\b|Fundaci[oó]n\b|Ministerio\b|Universidad\b|Convenio\b|Foro\b|Junta\b|Mesa\b|Programa\b|Unidos\s+por\s+la\s+Justicia\b|National\s+Center\b|"
    r"Naciones\s+Unidas\b|Comisi[oó]n\b|Centro\b|Colegio\b|Gobierno\b|Diccionario\b)", re.I
)
_PUBLISHER_RE = re.compile(
    r"\b(?:Editorial|Ediciones?|Editores?|Press|Publishing|Publishers?|Fondo\s+de\s+Cultura\s+Econ[oó]mica|"
    r"Siglo\s+Veintiuno|Siglo\s+XXI|Paid[oó]s|Gedisa|Kapelusz|Rubinzal|Culzoni|Tecnos|Taurus|"
    r"Sudamericana|Planeta|Emec[eé]|Lumiere|CLACSO\s+Libros|Nueva\s+Visi[oó]n|Nuevo\s+Estilo|"
    r"La\s+Ley|Astrea|Depalma|Granica|Alianza|Aique|UNSAM|UNAM|Universidad\s+[A-ZÁÉÍÓÚÜÑ])\b", re.I
)
_JOURNAL_WORD_RE = re.compile(
    r"\b(?:Revista|Journal|Law\s+Review|Review|Anales|Bolet[ií]n|Jurisprudencia\s+Argentina|"
    r"Estudios\s+Constitucionales|La\s+Ley|Noticias\s+Jur[ií]dicas|Working\s+Paper)\b", re.I
)
_CONF_RE = re.compile(r"\b(?:trabajo\s+presentado|Congreso|Congress|Conference|Encuentro|Jornadas?|Seminario|Conferencia)\b", re.I)
_EXPLICIT_THESIS_RE = re.compile(
    r"\b(?:Tesis\s+(?:Doctoral|de\s+Doctorado|de\s+Maestr[ií]a|de\s+Licenciatura)|Doctoral\s+Thesis|Ph\.?D\.?\s+Thesis|Dissertation)\b",
    re.I,
)
_CHAPTER_EN_RE = re.compile(r"^\s*(?:en|En)\s+", re.I)
_META_START_RE = re.compile(
    r",\s*(?:A[ñn]o\s+[IVXLCDM\d]+|Vol(?:umen)?\.?\s*\d+|N(?:ú|u|º|°|o\.?|úmero)\s*\d+|"
    r"\d{1,4}\s*\([^)]*\)|\d{1,4}\s*[,;:]\s*\d|p(?:á|a)ginas?\b|pp?\.\s*\d)", re.I
)


def _clean_text(texto: str) -> str:
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    t = _BULLET_RE.sub("", t)
    return t.strip()


def _publication_year(text: str) -> Optional[str]:
    # Do not convert an access date into a publication date.
    core = _ACCESS_TAIL_RE.sub("", text)
    years = [m.group(1) for m in _YEAR_RE.finditer(core)]
    if not years:
        return None
    return years[-1]


def _looks_legacy_year_final(text: str) -> bool:
    if not text or _PARENTHESES_YEAR_EARLY_RE.search(text[:260]):
        return False
    # ABNT/Vancouver-like all-caps author blocks are handled by the frozen
    # v0.9/v0.10 routes. v0.11 must not reinterpret them merely because their
    # year is also near the end.
    if re.match(r"^[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý'’´-]{1,}(?:\s+[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý'’´-]{1,})*\s*,", text):
        return False
    if re.match(r"^[A-ZÀ-ÖØ-Ý]{2,}\s+[A-ZÀ-ÖØ-Ý]\.\s+", text):
        return False
    if re.search(r"\b(?:Monografia|Disserta[cç][aã]o|Tese)\b", text, re.I):
        return False
    if text.count(",") < 2:
        return False
    if _publication_year(text) is None and not _URL_RE.search(text):
        return False
    # Quotes are strong title evidence. Otherwise require either a monograph,
    # journal, thesis or conference cue somewhere in the record.
    if re.match(rf"^{_SURNAME}\s*,\s*", text) or _CORP_CUE_RE.search(text):
        return True
    return bool(
        re.search(r"[“\"«].+?[”\"»]", text)
        or _PUBLISHER_RE.search(text)
        or _JOURNAL_WORD_RE.search(text)
        or _EXPLICIT_THESIS_RE.search(text)
        or _CONF_RE.search(text)
        or _URL_RE.search(text)
    )


def _normalize_author_joiners(head: str) -> str:
    # ``Dalle, Pablo y Elbert, Rodolfo`` -> ``Dalle, Pablo, Elbert, Rodolfo``
    # only within the author head. This makes the pair scanner deterministic.
    return re.sub(
        rf",\s*({_GIVEN})\s+y\s+({_SURNAME})\s*,",
        lambda m: f", {m.group(1)}, {m.group(2)},",
        head,
        flags=re.I,
    )


def _personal_author_block(text: str) -> Optional[Tuple[List[str], int]]:
    """Read a comma-delimited legacy personal-author block.

    The local bibliography commonly writes ``Surname, Given, Title`` and
    multi-author sequences such as ``Harmon, Michel y Meyer, Richard, Title``
    or ``Sautu, Ruth, Boniolo, Paula, Dalle, Pablo y Elbert, Rodolfo, Title``.
    We consume only person-shaped pairs from the opening comma fields.
    """
    head = text[:300]
    parts = [p.strip() for p in head.split(",")]
    if len(parts) < 3:
        return None

    authors: List[str] = []
    i = 0
    consumed_parts = 0
    while i + 1 < len(parts):
        sur = parts[i].strip()
        giv = parts[i + 1].strip()
        if not sur or not giv:
            break
        giv = re.sub(rf"\s*\(\s*{_ROLE}\s*\)\s*$", "", giv, flags=re.I).strip()

        if not re.fullmatch(_SURNAME, sur):
            break
        if authors and not any(re.search(r"\sy\s", x, re.I) for x in parts[i:i+4]):
            break

        # ``Surname, Given y Surname2, Given2``: the conjunction lives in the
        # same comma field as the first given name.
        ym = re.match(rf"^(.+?)\s+y\s+({_SURNAME})$", giv, re.I)
        if ym and i + 2 < len(parts):
            giv1 = ym.group(1).strip()
            sur2 = ym.group(2).strip()
            giv2 = re.sub(rf"\s*\(\s*{_ROLE}\s*\)\s*$", "", parts[i + 2], flags=re.I).strip()
            if re.fullmatch(_GIVEN, giv1) and re.fullmatch(_GIVEN, giv2) and len(giv1.split()) <= 3 and not _PUBLISHER_RE.search(giv2):
                authors.append(f"{sur}, {giv1}")
                authors.append(f"{sur2}, {giv2}")
                i += 3
                consumed_parts = i
                continue

        if not re.fullmatch(_GIVEN, giv):
            break
        if _PUBLISHER_RE.search(sur + " " + giv) or len((sur + " " + giv).split()) > 9:
            break
        authors.append(f"{sur}, {giv}")
        i += 2
        consumed_parts = i

        # Do not greedily consume an apparent title as another person. A next
        # pair must look strongly name-like and the would-be given field must
        # be short. This is checked at the top of the next iteration.

    if not authors or consumed_parts <= 0:
        return None

    comma_positions = [m.start() for m in re.finditer(",", text[:300])]
    if consumed_parts > len(comma_positions):
        return None
    boundary = comma_positions[consumed_parts - 1] + 1
    qm = re.search(r"[“\"«]", text)
    if qm and boundary > qm.start():
        boundary = qm.start()
    return authors, boundary


def _author_and_rest(text: str) -> Tuple[Optional[str], str, str]:
    # Quoted titles give us an exact author/title boundary and are the safest
    # route for articles, chapters and web pieces.
    qm = re.search(r"[“\"«]", text)
    if qm and qm.start() < 240:
        prefix = text[:qm.start()].strip(" ,.;:")
        # Most records use ``Surname, Given``. Keep the complete prefix as
        # authors string if it is plausible, while author is the first person.
        pa = _personal_author_block(prefix + ", X")
        if pa:
            authors = pa[0]
            return authors[0], " | ".join(authors), text[qm.start():].strip()
        if prefix:
            if _CORP_CUE_RE.search(prefix):
                return prefix, prefix, text[qm.start():].strip()
            # Conservative single-person fallback.
            m = re.match(rf"^({_SURNAME})\s*,\s*({_GIVEN})(?:\s*\(\s*{_ROLE}\s*\))?$", prefix)
            if m:
                a = f"{m.group(1)}, {m.group(2)}"
                return a, a, text[qm.start():].strip()

    pa = _personal_author_block(text)
    if pa:
        authors, boundary = pa
        rest = text[boundary:].lstrip(" ,.;:")
        return authors[0], " | ".join(authors), rest

    # Shared surname shorthand: ``Toffler, Alvin y Heidi, Título``. This is
    # only used after the ordinary multi-author parser abstains.
    msh = re.match(rf"^({_SURNAME})\s*,\s*({_PERSON_WORD})\s+y\s+({_PERSON_WORD})\s*,\s*(.+)$", text)
    if msh:
        following = msh.group(4).split(",", 1)[0].strip()
        if not re.fullmatch(_GIVEN, following):
            a1 = f"{msh.group(1)}, {msh.group(2)}"
            a2 = f"{msh.group(1)}, {msh.group(3)}"
            return a1, f"{a1} | {a2}", msh.group(4).strip()

    # A small legacy family omits the comma between surname and given name
    # (``Foucault Michel, ...``; ``Habermas Jürgen, ...``).
    first_comma = text.find(",")
    if first_comma > 1:
        prefix = text[:first_comma].strip()
        mnc = re.match(rf"^({_PERSON_WORD})\s+({_PERSON_WORD})$", prefix)
        if mnc:
            a = f"{mnc.group(1)}, {mnc.group(2)}"
            return a, a, text[first_comma + 1:].strip()

    # Corporate author: first comma normally separates entity from title.
    if first_comma > 1:
        prefix = text[:first_comma].strip()
        if _CORP_CUE_RE.search(prefix):
            remainder = text[first_comma + 1:].strip()
            if re.match(r"^Institute for Court Management\s*,", remainder, re.I):
                second, rest2 = remainder.split(",", 1)
                full = f"{prefix}, {second.strip()}"
                return full, full, rest2.strip()
            return prefix, prefix, remainder
    return None, "", text


def _quoted_title_and_suffix(rest: str) -> Tuple[Optional[str], str]:
    m = re.match(r"^[“\"«](.+?)[”\"»]\s*,?\s*(.*)$", rest)
    if not m:
        return None, rest
    return m.group(1).strip(), m.group(2).strip()


def _publisher_from_text(text: str) -> Optional[str]:
    # Prefer comma-delimited segments containing a publisher cue.
    for seg in [s.strip(" .;:") for s in text.split(",")]:
        if _PUBLISHER_RE.search(seg) and 1 <= len(seg.split()) <= 10:
            return seg
    return None


def _journal_from_suffix(suffix: str) -> Optional[str]:
    if not _JOURNAL_WORD_RE.search(suffix):
        return None
    s = suffix.strip(" ,.;:")
    if re.match(r"^(?:Editorial|Ediciones?)\s+", s, re.I):
        return None
    # Journal normally ends before issue/volume/page metadata or a year/place.
    mm = _META_START_RE.search(s)
    if mm:
        s = s[:mm.start()].strip(" ,.;:")
    else:
        ym = _YEAR_RE.search(s)
        if ym and ym.start() > 3:
            s = s[:ym.start()].rstrip(" ,.;:")
    # Avoid carrying conference prose after a legitimate journal phrase.
    if ". Trabajo presentado" in s:
        s = s.split(". Trabajo presentado", 1)[0]
    # Legal citations often wrap the journal between a leading volume and a
    # trailing first page: ``30 California Western International Law Journal
    # 345``. Strip those citation numbers while preserving the container.
    s = re.sub(r"^\d{1,4}\s+(?=[A-ZÁÉÍÓÚÜÑ])", "", s)
    s = re.sub(r"\s+\d{1,6}(?:\s*[-–—]\s*\d{1,6})?(?:,\s*(?:Spring|Fall|Summer|Winter))?$", "", s, flags=re.I)
    if len(s.split()) > 18:
        # Search for an explicit journal-containing comma segment.
        for seg in suffix.split(","):
            if _JOURNAL_WORD_RE.search(seg) and 1 <= len(seg.split()) <= 14:
                seg = re.sub(r"^\s*\d{1,4}\s+", "", seg.strip())
                seg = re.sub(r"\s+\d{1,6}\s*$", "", seg)
                return seg.strip(" .;:")
        return None
    return s or None


def _unquoted_title(rest: str) -> Optional[str]:
    s = rest.strip()
    # Remove trailing access information for title/source reasoning.
    s = _ACCESS_TAIL_RE.sub("", s)
    # Explicit thesis form: the title ends immediately before it.
    tm = _EXPLICIT_THESIS_RE.search(s)
    if tm and tm.start() > 2:
        return s[:tm.start()].rstrip(" ,.;:")
    # Publisher cue: use comma-delimited segments so a title containing a
    # lexical publisher word (e.g. ``Justicia del Siglo XXI``) is not cut.
    segs = [x.strip() for x in s.split(",")]
    offset = 0
    for idx, seg in enumerate(segs):
        if idx > 0 and _PUBLISHER_RE.search(seg):
            before = ", ".join(segs[:idx]).strip(" ,.;:")
            return before or None
    # Journal cue: text before the journal container is the article title.
    jm = _JOURNAL_WORD_RE.search(s)
    if jm and jm.start() > 2:
        return s[:jm.start()].rstrip(" ,.;:")
    # Conference cue after title.
    cm = _CONF_RE.search(s)
    if cm and cm.start() > 2:
        return s[:cm.start()].rstrip(" ,.;:")
    # Generic year-final book: the first comma-delimited field after the author
    # is usually the title. This is intentionally a last resort.
    seg = s.split(",", 1)[0].strip(" .;:")
    return seg if len(seg) >= 3 else None


def _classify_legacy(text: str, rest: str, title: Optional[str], suffix: str, base_type: str) -> str:
    # Explicit document form has highest authority.
    if _EXPLICIT_THESIS_RE.search(text):
        return "tesis"

    journal = _journal_from_suffix(suffix if title else rest)
    if journal:
        return "articulo_revista"

    # Chapter/contribution: title + ``en <container>``. ``en línea`` is access
    # mode and ``en Revista`` is a journal article, not a book chapter.
    if title and _CHAPTER_EN_RE.match(suffix):
        if not re.match(r"^\s*en\s+(?:l[ií]nea|Revista|Journal)\b", suffix, re.I):
            return "capitulo_libro"

    if _CONF_RE.search(text):
        return "conference_paper"

    # URL alone is an access mode. It only becomes material_web when no
    # stronger source/container/publisher evidence exists.
    if _URL_RE.search(text) and not _PUBLISHER_RE.search(text):
        if re.search(r"\ben\s+l[ií]nea\b", suffix or rest, re.I):
            return "material_web"

    if re.search(r"\b(?:Manual|Gu[ií]a)\b", title or "", re.I):
        return "documento_guia_manual"
    if re.search(r"\bInforme\b", title or "", re.I):
        return "informe_documento"
    if _PUBLISHER_RE.search(text) or base_type == "libro":
        return "libro"
    if title and _publication_year(text) and not _URL_RE.search(text) and not _JOURNAL_WORD_RE.search(text):
        if len((suffix or rest).split(",")) >= 2:
            return "libro"
    return base_type or "sin_clasificar"


def _legacy_overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    if not _looks_legacy_year_final(text):
        return base

    out = dict(base)
    author, authors, rest = _author_and_rest(text)
    rest = re.sub(r"^con la colaboraci[oó]n de [^,]{2,100},\s*", "", rest, flags=re.I)
    title, suffix = _quoted_title_and_suffix(rest)
    if title is None:
        title = _unquoted_title(rest)
        suffix = rest[len(title):].lstrip(" ,.;:") if title and rest.startswith(title) else rest

    year = _publication_year(text)
    if author:
        out["author"] = author
        out["authors"] = authors
    if year:
        out["year"] = year
    elif _ACCESS_TAIL_RE.search(text):
        # v0.10 sometimes promoted the access year into publication year.
        out["year"] = None
    if title:
        out["title"] = title.strip(" “\"»«”.,;:")

    ptype = _classify_legacy(text, rest, title, suffix, str(base.get("publication_type") or "sin_clasificar"))
    out["publication_type"] = ptype

    journal = _journal_from_suffix(suffix if title else rest)
    if ptype == "articulo_revista" and journal:
        out["journal"] = journal
        out["publisher"] = None
        out["publisher_observed"] = None
        out["source_publisher"] = None
    elif ptype in {"libro", "capitulo_libro", "documento_guia_manual", "informe_documento"}:
        pub = _publisher_from_text(suffix or rest)
        if pub:
            out["publisher"] = pub
            out["publisher_observed"] = pub
            out["source_publisher"] = pub

    # Explicitly correct lexical false positives from previous versions.
    if base.get("publication_type") == "tesis" and not _EXPLICIT_THESIS_RE.search(text):
        out["publication_type"] = _classify_legacy(text, rest, title, suffix, "sin_clasificar")

    style = str(out.get("parse_style") or "")
    out["parse_style"] = "+".join([s for s in (style, "v11_legacy_year_final") if s])
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean_text(texto)
    out = dict(_v10.parse_reference(text))
    out = _legacy_overlay(text, out)
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
