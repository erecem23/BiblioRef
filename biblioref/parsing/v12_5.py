# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.5.

Conservative overlay on v0.12.4 for older Ibero-American humanities/social-
science references that cite journals with legacy metadata such as ``N°``,
``Número``, ``Tomo``, ``Año`` or ``Vol.`` rather than APA volume(issue) syntax.
It also distinguishes URL-only web items from monographs, handles local year
suffixes such as ``(2008-a)``, and recovers a narrow edition+imprint book
pattern. Extraction boundaries are untouched.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v12_4 as _v124

PARSER_VERSION = "biblioref-parser-v0.12.5"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_APA_RE = re.compile(
    r"^(?P<head>.{1,340}?)\s*\(\s*(?P<year>(?:18|19|20)\d{2})(?:-?[a-z]\.?)?"
    r"(?:\s*,[^)]*)?\)\s*[,\.]?\s*(?P<rest>.+)$", re.I
)
_ACCESS_RE = re.compile(
    r"\b(?:Disponible\s+en|Extra[ií]d[oa]\s+de|Recuperad[oa]\s+de|Retrieved\s+from)\b"
    r"|https?\s*:\s*/|www\.", re.I
)
_NO_IMPRINT_RE = re.compile(
    r"\b(?:sin\s+datos\s+editoriales|sin\s+datos\s+de\s+publicaci[oó]n|"
    r"sin\s+datos\s+bibliogr[aá]ficos)\b",
    re.I,
)
_SERIAL_START_RE = re.compile(
    r"^(?:Revista(?:\s+del)?|Journal|Anuario|Cuadernos?|N[oó]madas|Campo\s+Grupal|"
    r"Eccos(?:\s+Revista\s+Cient[ií]fica)?|Perfiles\s+educativos|Ensayos\s+y\s+Experiencias|"
    r"Sujeto\s*,?\s*Subjetividad\s+y\s+Cultura|Multitudes|Comportamiento|"
    r"Educa[cç][aã]o|Educacao|Psykhe|Psicoperspectivas|Universitas\s+Psychologica|"
    r"Salud\s+Colectiva)\b", re.I
)
_SERIAL_META_RE = re.compile(
    r",\s*(?:N(?:[°º]|[uú]mero|ro\.?)\s*\d+|Vol(?:umen)?\.?\s*[IVXLCDM\d]+|"
    r"V\.?\s*[IVXLCDM\d]+|Tomo\s+[IVXLCDM\d]+|A[ñn]o\s+[IVXLCDM\d]+|"
    r"\d+\s*\(\s*\d+\s*\))", re.I
)
_EXPLICIT_SERIAL_NAMES = [
    re.compile(r"^Sujeto\s*,\s*Subjetividad\s+y\s+Cultura\b", re.I),
    re.compile(r"^Revista\s+del\s+Observatorio\s+Social\s+sobre\s+Empresas\s+Recuperadas\s+Autogestionadas(?:\s*\(OSERA\))?\b", re.I),
    re.compile(r"^Revista\s+de\s+la\s+Asociaci[oó]n\s+Argentina\s+de\s+Psicolog[ií]a\s+y\s+Psicoterapia\s+de\s+Grupos\b", re.I),
    re.compile(r"^Revista\s+del\s+Instituto\s+de\s+Investigaciones\s+en\s+Ciencias\s+de\s+la\s+Educaci[oó]n\b", re.I),
]
_EDITION_IMPRINT_RE = re.compile(
    r"^(?P<title>.+?)\.\s*\((?P<edition>[^)]*(?:ed\.|edici[oó]n|reimpresi[oó]n)[^)]*)\)\s*"
    r"(?P<place>[A-ZÁÉÍÓÚÜÑ][^:]{1,70})\s*:\s*(?P<publisher>[^.]{2,120})\.?", re.I
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "", str(value or "").casefold())


def _split_semicolon(value: Any) -> List[str]:
    return [x for x in str(value or "").split(";") if x]


def _append_candidate(out: Dict[str, Any], field: str, old: Any, new: Any) -> None:
    key = f"{field}_candidates"
    current = [x.strip() for x in str(out.get(key) or "").split("||") if x.strip()]
    for item in (old, new):
        text = _clean(item)
        if text and text not in current:
            current.append(text)
    out[key] = " || ".join(current)


def _add_note(out: Dict[str, Any], note: str) -> None:
    notes = _split_semicolon(out.get("parser_notes"))
    if note not in notes:
        notes.append(note)
    out["parser_notes"] = ";".join(notes)


def _remove_review(out: Dict[str, Any], reason: str) -> None:
    reasons = [x for x in _split_semicolon(out.get("review_reasons")) if x != reason]
    out["review_reasons"] = ";".join(reasons)
    out["needs_review"] = bool(reasons)
    penalties = {
        "multiple_year_mentions": 0.10,
        "web_title_source_ambiguous": 0.15,
        "author_boundary_ambiguous": 0.20,
        "author_list_truncated": 0.10,
        "document_type_unresolved": 0.20,
        "publisher_inside_title": 0.15,
        "possible_repository_thesis": 0.10,
        "serial_container_monograph_like": 0.15,
    }
    out["parser_confidence"] = max(
        0.20, round(1.0 - sum(penalties.get(x, 0.05) for x in reasons), 2)
    )


def _explicit_serial_name(suffix: str) -> Optional[str]:
    for pattern in _EXPLICIT_SERIAL_NAMES:
        m = pattern.search(suffix)
        if m:
            return m.group(0).strip(" .,:;")
    return None


def _legacy_serial_split(rest: str, current_type: Any) -> Optional[Tuple[str, str]]:
    core = _clean(rest)
    access = _ACCESS_RE.search(core)
    parse_core = core[:access.start()].rstrip(" .,:;") if access else core.rstrip(" .,:;")

    for boundary in re.finditer(r"\.\s+", parse_core):
        title = parse_core[:boundary.start()].strip(" .;,‘’“”\"")
        suffix = parse_core[boundary.end():].strip()
        if len(title) < 10 or not _SERIAL_START_RE.search(suffix[:180]):
            continue
        start = _SERIAL_START_RE.search(suffix[:180])
        if not start or start.start() != 0:
            continue

        meta = _SERIAL_META_RE.search(suffix[:260])
        explicit = _explicit_serial_name(suffix)
        if str(current_type or "") == "capitulo_libro" and not meta:
            continue

        if explicit:
            journal = explicit
        elif meta:
            journal = suffix[:meta.start()].strip(" .,:;")
            journal = re.split(r"\s*,\s*[“\"]", journal, maxsplit=1)[0].strip(" .,:;")
        else:
            journal = suffix.split(".", 1)[0].strip(" .,:;")
            if "," in journal:
                journal = journal.split(",", 1)[0].strip()

        if 2 <= len(journal) <= 180:
            return title, journal
    return None


def _edition_imprint(rest: str) -> Optional[Tuple[str, str]]:
    m = _EDITION_IMPRINT_RE.match(_clean(rest))
    if not m:
        return None
    title = m.group("title").strip(" .“”\"")
    publisher = m.group("publisher").strip(" .,:;")
    if not title or not publisher:
        return None
    return title, publisher


def _overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    m = _APA_RE.match(text)
    if not m:
        out["parser_version"] = PARSER_VERSION
        out["schema_version"] = PARSER_SCHEMA_VERSION
        out["parser_status"] = PARSER_STATUS
        return out

    # v0.12.4 intentionally used a stricter year token.  Local bibliographies
    # often encode same-year disambiguation as (2008-a)/(2008-b).  If the base
    # parser already recovered an author list, that list is not unresolved.
    if out.get("author_list_status") == "unresolved" and out.get("authors"):
        out["author_list_status"] = "complete"
        _add_note(out, "v125_hyphenated_year_author_status_recovered")

    rest = m.group("rest")
    serial = _legacy_serial_split(rest, out.get("publication_type"))
    if serial:
        title, journal = serial
        if _norm(title) != _norm(out.get("title")):
            _append_candidate(out, "title", out.get("title"), title)
            out["title"] = title
        if _norm(journal) != _norm(out.get("journal")):
            _append_candidate(out, "journal", out.get("journal"), journal)
            out["journal"] = journal
        if out.get("publication_type") != "articulo_revista":
            _append_candidate(out, "type", out.get("publication_type"), "articulo_revista")
            out["publication_type"] = "articulo_revista"
        if out.get("publisher"):
            _append_candidate(out, "publisher", out.get("publisher"), "(none: journal article)")
            out["publisher"] = None
            out["publisher_observed"] = None
            out["source_publisher"] = None
        _remove_review(out, "document_type_unresolved")
        _add_note(out, "v125_legacy_serial_recovered")

    elif out.get("publication_type") == "sin_clasificar":
        book = _edition_imprint(rest)
        if book:
            title, publisher = book
            _append_candidate(out, "type", out.get("publication_type"), "libro")
            out["publication_type"] = "libro"
            if _norm(title) != _norm(out.get("title")):
                _append_candidate(out, "title", out.get("title"), title)
                out["title"] = title
            _append_candidate(out, "publisher", out.get("publisher"), publisher)
            out["publisher"] = publisher
            out["publisher_observed"] = publisher
            out["source_publisher"] = publisher
            _remove_review(out, "document_type_unresolved")
            _add_note(out, "v125_edition_imprint_book_recovered")
        elif _ACCESS_RE.search(rest):
            _append_candidate(out, "type", out.get("publication_type"), "material_web")
            out["publication_type"] = "material_web"
            _remove_review(out, "document_type_unresolved")
            _add_note(out, "v125_url_only_web_recovered")

    # A previous layer may infer ``informe_documento`` from a generic document
    # noun alone.  Explicitly saying that publication/imprint data are absent,
    # together with a retrieval URL and no recovered publisher, is stronger
    # evidence that the citation is URL-only.  Keep this deliberately narrow so
    # genuine institutional reports accessed online remain reports.
    elif (
        out.get("publication_type") == "informe_documento"
        and not out.get("publisher")
        and _ACCESS_RE.search(rest)
        and _NO_IMPRINT_RE.search(_clean(out.get("title") or rest))
    ):
        _append_candidate(out, "type", out.get("publication_type"), "material_web")
        out["publication_type"] = "material_web"
        _remove_review(out, "document_type_unresolved")
        _add_note(out, "v125_url_only_web_recovered")

    style = str(out.get("parse_style") or "")
    if "v125_legacy_serial_web" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v125_legacy_serial_web") if x)
    out["parser_version"] = PARSER_VERSION
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    return _overlay(text, _v124.parse_reference(text))


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        output.append(row)
    return output


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v124.flatten_parsed(parsed, prefix=prefix)
