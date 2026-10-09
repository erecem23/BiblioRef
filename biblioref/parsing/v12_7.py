# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.7.

Overlay on v0.12.6 from the Candelero development case:

* a repeated-author marker («-------------», «---.», «———», «_______») is
  recorded in ``author_marker_raw`` and never becomes the author; the author is
  resolved at document level by :mod:`biblioref.parsing.inheritance`;
* document type from explicit bibliographic evidence (see ``_retype``).

Extraction boundaries are untouched.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from . import v12_6 as _v126
from .inheritance import repeated_author_marker

PARSER_VERSION = "biblioref-parser-v0.12.7"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _add_note(out: Dict[str, Any], note: str) -> None:
    notes = [x for x in str(out.get("parser_notes") or "").split(";") if x]
    if note not in notes:
        notes.append(note)
    out["parser_notes"] = ";".join(notes)


def _mark_repeated_author(text: str, out: Dict[str, Any]) -> None:
    marker = repeated_author_marker(text)
    if not marker:
        return
    if out.get("author"):
        _v126._append_candidate(out, "author", out.get("author"), "(autor repetido)")
    out["author"] = None
    out["authors"] = ""
    out["author_marker_raw"] = marker
    out["author_marker_detected"] = True
    _add_note(out, "v127_repeated_author_marker")


_UNPUBLISHED_RE = re.compile(r"\b(?:in[ée]dit[oa]s?|unpublished|sin\s+publicar|no\s+publicad[oa])\b", re.I)
_PAGES = r"(?:pp?|p[áa]g?s?)\.?\s*\d+\s*[-–]\s*\d+"
#: «…, Redes de la Letra , 3. pp. 63-83» / «Lalengua , 24. pp. 12-14» /
#: «Littoral: Revista…, 25/26. pp. 35-71» / «Contexto en psicoanálisis . 11. pág. 35-54».
_JOURNAL_NUMBER_PAGES_RE = re.compile(
    rf"[.,?!]\s*(?P<journal>[A-ZÁÉÍÓÚÑ][^.()?]{{2,90}}?)\s*[,.]\s*(?:vol\.?\s*|n[°º.]?\s*|no\.\s*)?"
    rf"(?:\d{{1,4}}(?:\s*/\s*\d{{1,4}})?|[IVXLC]{{1,6}})\s*(?:\(\s*\d+\s*\))?\s*[,.]\s*{_PAGES}",
)
#: «En: Anuario de Investigaciones…» — the container is a serial.
_SERIAL_CONTAINER_RE = re.compile(
    r"\b(?:En|In)\s*:?\s+(?:el\s+|la\s+)?(?P<journal>(?:Anuario|Revista|Cuadernos|Journal|Bolet[ií]n|Anales|Peri[óo]dico)\b[^.]{0,120})", re.I
)
_CITIES = (
    r"Buenos\s+Aires|Madrid|Barcelona|Valencia|M[ée]xico|Rosario|C[óo]rdoba|La\s+Plata|Mar\s+del\s+Plata|Santiago|Lima|"
    r"Bogot[áa]|Caracas|Montevideo|Quito|S[ãa]o\s+Paulo|R[ií]o\s+de\s+Janeiro|Par[ií]s|Paris|London|Londres|New\s+York|"
    r"Nueva\s+York|Roma|Milano|Mil[áa]n|Berl[ií]n|Lisboa|Sevilla|Granada|Salamanca|Guadalajara|Medell[ií]n|Mendoza|Tucum[áa]n|"
    r"Salta|Paran[áa]|Santa\s+Fe|Neuqu[ée]n|Bah[ií]a\s+Blanca|Oxford|Cambridge|Chicago|Boston|Philadelphia|Toronto"
)
#: «…. Barcelona, Argot.» / «Buenos Aires , Kliné.» / «Rosario. Nube Negra.»
_CITY_PUBLISHER_END_RE = re.compile(
    rf"[.,]\s*(?:{_CITIES})\s*[,.:]\s*(?P<publisher>[A-ZÁÉÍÓÚÑ][^.,:;()\d]{{1,60}}?)\s*\.?\s*$"
)
#: Edition and translation notes («[24 vols], XIX», «Traducción de…») carry volume
#: numbers and pages that are not a journal issue.
_EDITION_NOTE_RE = re.compile(
    r"\bvols?\.?\s*\]|\btraducci[oó]n\s+de\b|\btranslated\s+by\b|\bstandard\s+edition\b|\bobras\s+completas\b", re.I
)
_CITY_COLON_RE = re.compile(rf"\b(?:{_CITIES})\s*:\s*[A-ZÁÉÍÓÚÑ]")
#: A trailing country or state is a place, not a publisher; laws and serials are not books.
_NOT_PUBLISHER_RE = re.compile(
    r"^(?:Argentina|Espa[ñn]a|Spain|M[ée]xico|Chile|Bra[sz]il|Ecuador|Per[uú]|Colombia|Uruguay|Paraguay|Bolivia|Venezuela|"
    r"USA|EE\.?\s*UU\.?|U\.?S\.?A?\.?|UK|France|Francia|Italia|Italy|Portugal|Mass|Hungary|Hungr[ií]a|"
    r"Estados\s+Unidos|United\s+States|Inglaterra|England|Alemania|Germany|Canad[aá]|Cuba)$",
    re.I,
)
_NOT_A_BOOK_RE = re.compile(r"\b(?:registro\s+oficial|r[ée]vue|revista|journal)\b", re.I)
#: Portuguese degrees the v0.12.6 statement misses: «Tese de doutorado», «Dissertação de mestrado».
_THESIS_EXTRA_RE = re.compile(r"\b(?:tese|tesis|disserta[cç][aã]o)\s+de\s+(?:doutorado|mestrado|livre[\s-]doc[eê]ncia)\b", re.I)
_EVENT_RE = re.compile(
    r"\b(?:congreso|jornadas?|encuentro|simposio|coloquio|reuni[oó]n\s+(?:anual|nacional|cient[ií]fica|de\s+la|del)|"
    r"trabajo\s+presentado|ponencia|(?:general|annual)\s+meeting|conference|(?<!library of )congress|symposium|workshop)\b",
    re.I,
)


def _retype(text: str, out: Dict[str, Any]) -> None:
    """Document type from explicit evidence; accuracy first, never coverage."""
    ptype = out.get("publication_type") or "sin_clasificar"
    body = re.sub(r"^\s*(?:[○●•◦▪·*]\s*)?(?:-{2,}|_{2,}|–{2,}|—+)\s*[.,;:]?\s*", "", text)

    if _UNPUBLISHED_RE.search(body) and ptype in {"sin_clasificar", "libro", "material_web", "informe_documento"}:
        # An unpublished thesis is a thesis; one read at a colloquium is a conference paper.
        if _v126._THESIS_EVIDENCE_RE.search(body) or _THESIS_EXTRA_RE.search(body):
            _v126._set_type(out, "tesis", "v127_thesis_statement")
        elif _EVENT_RE.search(body):
            _v126._set_type(out, "conference_paper", "v127_unpublished_event")
        else:
            _v126._set_type(out, "material_inedito", "v127_unpublished_material")
        return

    # A URL does not make a web page: «En Anuario de investigaciones, 14. Recuperado de: http…» is an article.
    serial = _SERIAL_CONTAINER_RE.search(body)
    # «…en la revista El Gráfico» inside a title is prose: here the container must read «En Revista…».
    if ptype == "material_web" and serial and serial.group(0)[:1] in "EI" and serial.group("journal")[:1].isupper():
        _v126._set_type(out, "articulo_revista", "v127_serial_container_online")
        out["journal"] = serial.group("journal").split(",")[0].strip(" .:")
        return

    if ptype in {"sin_clasificar", "libro"}:
        serial = _SERIAL_CONTAINER_RE.search(body)
        numbered = _JOURNAL_NUMBER_PAGES_RE.search(body)
        journal = None
        if serial:
            journal = serial.group("journal").split(",")[0].strip(" .:")
        elif (numbered and not re.search(r"\b(?:En|In)\s*:?\s", body[: numbered.start() + 1])
              and not _EDITION_NOTE_RE.search(body) and not _CITY_COLON_RE.search(body)):
            journal = numbered.group("journal").strip(" .:")
        if journal:
            _v126._set_type(out, "articulo_revista", "v127_journal_number_pages")
            out["journal"] = journal
            out["publisher"] = None
            out["publisher_observed"] = None
            out["source_publisher"] = None
            return

    if ptype == "sin_clasificar":
        # Thesis and event statements outrank a trailing «City, Institution».
        if _v126._THESIS_EVIDENCE_RE.search(body) or _THESIS_EXTRA_RE.search(body):
            _v126._set_type(out, "tesis", "v127_thesis_statement")
            return
        if _EVENT_RE.search(body):
            _v126._set_type(out, "conference_paper", "v127_academic_event")
            return
        book = _CITY_PUBLISHER_END_RE.search(body)
        if book and not _NOT_PUBLISHER_RE.match(book.group("publisher").strip()) and not _NOT_A_BOOK_RE.search(body):
            # «Título. En Obra colectiva. São Paulo. Educ.» is a chapter of that book.
            chapter = re.search(r"(?:^|[.,)]\s*)(?:En|In)\s*:?\s+[A-ZÁÉÍÓÚÑ]", body[: book.start() + 1])
            _v126._set_type(out, "capitulo_libro" if chapter else "libro", "v127_city_and_publisher")
            out["publisher"] = book.group("publisher").strip()


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    out = _v126.parse_reference(text)
    _mark_repeated_author(text, out)
    _retype(text, out)
    style = str(out.get("parse_style") or "")
    if "v127" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v127_repeated_author_and_type") if x)
    out["parser_version"] = PARSER_VERSION
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        output.append(row)
    return output


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v126.flatten_parsed(parsed, prefix=prefix)
