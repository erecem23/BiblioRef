# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.6.

Conservative overlay on v0.12.5, from an external development case (a
bulleted bibliography, 181 references):

* the date block is normalised before parsing: a day/month date
  («(4 y 5 de noviembre de 2011)») becomes its year, and no-date variants
  («(s/f)», «(sin fecha)», «(s/f. Varias versiones)») become «(s.f.)», the
  convention earlier versions already read. Otherwise the parser fell back to
  its year-final route and split compound surnames («De Souza» -> «De,
  Souza») or let the author absorb «(s/f»;
* ``tesis`` needs thesis evidence outside the title: «Cómo se hace una tesis»
  or «Tesis sobre Feuerbach» are books;
* a contribution «…, en <container>» is a chapter when the container carries
  an editor role (Comp., Coord., Ed., Dir.) or a page range (pp. x-y), and the
  container is not a journal;
* an explicit «[Ponencia]» label is a conference paper.

Extraction boundaries are untouched.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from . import v12_5 as _v125

PARSER_VERSION = "biblioref-parser-v0.12.6"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_MONTHS = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|sept?iembre|setiembre|octubre|"
    r"noviembre|diciembre|january|february|march|april|may|june|july|august|september|"
    r"october|november|december|janeiro|fevereiro|mar[cç]o|maio|junho|julho|outubro|novembro|dezembro"
)
_YEAR_TOKEN_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2}(?:-?[a-z](?![a-z]))?)(?!\d)")
#: The first parenthesis after the author holds a day/month date and one year.
_DATED_PAREN_RE = re.compile(
    rf"^(?P<head>[^()]{{2,200}}?)\(\s*(?P<inner>[^()]*?\b(?:{_MONTHS})\b[^()]*?)\s*\)", re.I
)
#: «(s/f)», «(s. f.)», «(sin fecha)», «(s/d)», «(n.d.)», with trailing words.
_NO_DATE_PAREN_RE = re.compile(
    r"^(?P<head>.{2,220}?)[\s,]*\(\s*(?:s\s*/\s*f|s\.\s*f|sin\s+fecha|s\s*/\s*d|n\.\s*d)\b[^()]*\)", re.I
)

#: Thesis evidence: a degree statement, a bracketed/parenthesised label or a
#: foreign form. The bare word inside a title is not evidence.
_THESIS_EVIDENCE_RE = re.compile(
    r"[\[(]\s*(?:tesis|tese|tesina|thesis)\b"
    r"|\b(?:tesis|tese|tesina)\s+(?:de\s+(?:la\s+)?|del\s+|para\s+(?:optar|obtener|la)|carrera\s+|en\s+)?"
    r"(?:doctor|dosctor|dotor|maestr|mag|licenc|grado|pregrado|posgrado|profesorado|ingenier|especializ|master|m[aá]ster|revalid|final)"
    r"|\b(?:thesis|dissertation|dissertatio|disserta[cç][aã]o|doctoralthesis|masterthesis|m[eé]moire)\b"
    r"|\btrabajo\s+(?:final|integrador)|\btesina\b",
    re.I,
)
_TITLE_THESIS_WORD_RE = re.compile(r"\btesis\b", re.I)
_CONFERENCE_RE = re.compile(
    r"\b(?:congreso|jornadas?|encuentro|simposio|coloquio|conferencia|congress|conference|symposium|workshop)\b", re.I
)
_PONENCIA_RE = re.compile(r"\[\s*(?:ponencia|comunicaci[oó]n|conferencia|presentaci[oó]n)\s*\]", re.I)

#: «…, en <container>» / «…. En <container>» / «…. In <container>».
_CONTAINER_RE = re.compile(r"(?:,\s+en|[.:]\s+(?:En|In)):?\s+(?P<container>.+)$")
_EDITOR_ROLE_RE = re.compile(
    r"\(\s*(?:comps?|coords?|eds?|dirs?|orgs?|compiladora?s?|coordinadora?s?|editora?s?|directora?s?)\.?\s*\)", re.I
)
_PAGE_RANGE_RE = re.compile(r"\bpp?\.\s*\d+\s*[-–]\s*\d+")
_JOURNAL_CONTAINER_RE = re.compile(
    r"^\s*(?:l[ií]nea\b|memoriam\b)"
    r"|\b(?:Revista|Journal|Anuario|Anales|Annals|Cuadernos|Quarterly|Review|Bulletin|Archives?|Archivos)\b"
    r"|\b\d+\s*\(\s*\d+\s*\)|\bvol\.?\s*\d+\s*,?\s*(?:n[°º.]|no\.)|\(\s*No\.\s*\d", re.I
)


_LIST_MARKER_RE = re.compile(r"^[\s○●•◦▪·*\-–—]+")
#: «en A. Abello Blanco y A. Liberman, <Obra>»: the container opens with its editors.
_EDITOR_NAMES_RE = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,3}[A-ZÁÉÍÓÚÑ][\wáéíóúñü'’\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü'’\-]+)?"
    r"\s*(?:,|\s+y\s+|\s+and\s+|\s*&|\s*\()"
)
#: «Título. Editorial.»: a short capitalised imprint closes the reference.
_TITLE_PUBLISHER_RE = re.compile(
    r"^(?P<title>.{10,}?)\s*\.\s+(?P<publisher>[A-ZÁÉÍÓÚÑ][\wáéíóúñü'’&\-]*(?:\s+[\wáéíóúñü'’&\-]+){0,3})\.?\s*$"
)
_NOT_IMPRINT_RE = re.compile(
    r"\b(?:Revista|Rev|Journal|Anuario|Cuadernos|Review|Bulletin|Anales|Archivos|Boletín|Diario|Newspaper|Blog|"
    r"Facebook|YouTube|In[ée]dit[oa]|Universi\w+|Institut\w*|Instituto|College|School|Facultad|Seminario|Tesis|"
    r"Informe|Report|Manual|Program\w*|Ministerio|Departamento|Hospital|Congreso|Jornadas?|"
    r"Sin\s+datos|Cat[áa]logo|Databases?|Software|Authors?|Autor(?:es)?)\b"
    # Places close references too, not only imprints.
    r"|^(?:Buenos\s+Aires|Madrid|Barcelona|M[ée]xico|New\s+York|New\s+Jersey|Nueva\s+York|London|Londres|Par[ií]s|"
    r"Texas|California|Lyon|Cuenca|Santiago|Lima|Bogot[áa]|Caracas|Montevideo|Quito|S[ãa]o\s+Paulo|R[ií]o\s+de\s+Janeiro|"
    r"C[óo]rdoba|La\s+Plata|Rosario|Mendoza|Tucum[áa]n|Salta|Mar\s+del\s+Plata|Asunci[óo]n|Lisboa|Roma|Berl[ií]n|Oxford|"
    r"Cambridge|Chicago|Boston|Washington|Philadelphia|Toronto|Valencia|Sevilla|Granada|Salamanca|Guadalajara|Medell[ií]n|Cali|"
    r"Argentina|Espa[ñn]a|Spain|Chile|Uruguay|Paraguay|Brasil|Brazil|Colombia|Per[úu]|Ecuador|Venezuela|Bolivia|Portugal|"
    r"Francia|France|Italia|Italy|Alemania|Germany|Canad[áa]|USA|EE\.?\s?UU\.?|Estados\s+Unidos|United\s+States|UK|Inglaterra)$",
    re.I,
)


def _title_and_publisher_only(text: str) -> bool:
    m = _v125._APA_RE.match(text)
    if not m:
        return False
    rest = m.group("rest").strip()
    if _v125._ACCESS_RE.search(rest) or re.search(r"\d", rest.rsplit(".", 2)[-2] if rest.count(".") >= 2 else rest):
        return False
    tp = _TITLE_PUBLISHER_RE.match(rest)
    if not tp:
        return False
    publisher = tp.group("publisher").strip()
    # «Rev.», «Ed.»: an abbreviation is not an imprint.
    if len(publisher) <= 4 or _NOT_IMPRINT_RE.search(publisher):
        return False
    return True


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _add_note(out: Dict[str, Any], note: str) -> None:
    notes = [x for x in str(out.get("parser_notes") or "").split(";") if x]
    if note not in notes:
        notes.append(note)
    out["parser_notes"] = ";".join(notes)


def _append_candidate(out: Dict[str, Any], field: str, old: Any, new: Any) -> None:
    _v125._append_candidate(out, field, old, new)


def _set_type(out: Dict[str, Any], new_type: str, note: str) -> None:
    if out.get("publication_type") == new_type:
        return
    _append_candidate(out, "type", out.get("publication_type"), new_type)
    out["publication_type"] = new_type
    _v125._remove_review(out, "document_type_unresolved")
    _add_note(out, note)


def normalise_date_block(text: str) -> tuple[str, str]:
    """Return the text with a parseable date block, and what was normalised."""
    m = _NO_DATE_PAREN_RE.match(text)
    if m and not _YEAR_TOKEN_RE.search(m.group(0)[len(m.group("head")):]):
        head = m.group("head").rstrip(" ,")
        return f"{head} (s.f.){text[m.end():]}", "no_date"
    m = _DATED_PAREN_RE.match(text)
    if m:
        years = _YEAR_TOKEN_RE.findall(m.group("inner"))
        if len(set(years)) == 1:
            return f"{m.group('head')}({years[0]}){text[m.end():]}", "day_month_date"
    return text, ""


def _complete_undated(out: Dict[str, Any], normalised: str) -> None:
    """A corporate author before «(s.f.)»: the base layer leaves year and title empty."""
    head, _, rest = normalised.partition(" (s.f.)")
    head = _LIST_MARKER_RE.sub("", head)
    author = _clean(out.get("author"))
    if not author or not _clean(head).startswith(author.rstrip(".")):
        return
    if not out.get("year"):
        out["year"] = "s.f."
        _add_note(out, "v126_undated_year")
    title = _clean(out.get("title"))
    if title and not title.startswith(author.rstrip(".")[:20]):
        return
    body = rest.lstrip(" .,:;")
    access = _v125._ACCESS_RE.search(body)
    if access:
        body = body[:access.start()]
    new_title = re.split(r"\.\s+(?=[A-ZÁÉÍÓÚÑ])", body.strip(), maxsplit=1)[0].strip(" .,:;")
    if len(new_title) >= 3 and new_title != title:
        _append_candidate(out, "title", title, new_title)
        out["title"] = new_title
        _add_note(out, "v126_undated_title_recovered")


def _chapter_container(out: Dict[str, Any], text: str) -> bool:
    title = _clean(out.get("title"))
    rest = text
    year = _v125._APA_RE.match(text)
    if year:
        rest = year.group("rest")
    m = _CONTAINER_RE.search(rest[: 400])
    if not m or m.start() < 8:
        return False
    container = m.group("container")
    # Journal marks before the container: an article (the «In …» that follows
    # belongs to another reference fused behind it).
    if _JOURNAL_CONTAINER_RE.search(container[:160]) or _JOURNAL_CONTAINER_RE.search(rest[:m.start()]):
        return False
    return bool(
        _EDITOR_ROLE_RE.search(container[:240])
        or _PAGE_RANGE_RE.search(container[:260])
        or _EDITOR_NAMES_RE.match(container)
    )


def _overlay(original: str, out: Dict[str, Any]) -> Dict[str, Any]:
    ptype = out.get("publication_type")
    title = _clean(out.get("title"))

    if ptype == "tesis" and _TITLE_THESIS_WORD_RE.search(title):
        outside = original.replace(title, " ", 1) if title else original
        if not _THESIS_EVIDENCE_RE.search(outside) and not _THESIS_EVIDENCE_RE.search(title):
            _set_type(out, "conference_paper" if _CONFERENCE_RE.search(outside) else "libro",
                      "v126_thesis_word_in_title_only")
            ptype = out["publication_type"]

    if _PONENCIA_RE.search(original) and ptype not in {"conference_paper", "tesis"}:
        _set_type(out, "conference_paper", "v126_explicit_ponencia_label")
        ptype = out["publication_type"]

    if ptype in {"libro", "sin_clasificar", "articulo_revista"} and _chapter_container(out, original):
        if ptype == "articulo_revista":
            out["journal"] = None
        _set_type(out, "capitulo_libro", "v126_chapter_container_with_editor_or_pages")
    elif ptype == "sin_clasificar" and _title_and_publisher_only(_LIST_MARKER_RE.sub("", original)):
        _set_type(out, "libro", "v126_title_and_publisher_book")

    style = str(out.get("parse_style") or "")
    if "v126" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v126_type_evidence") if x)
    out["parser_version"] = PARSER_VERSION
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


#: Fields read from the normalised date block. Type, journal and publisher stay
#: with the original reading: «(2016, 6 de diciembre)» is itself a cue that the
#: earlier layers use for conference papers and press items.
_DATE_FIELDS = ("author", "authors", "author_list_status", "year", "title")


_NAME_HEAD_RE = re.compile(r"[^\W\d_][^,]{0,80},\s*[A-ZÁÉÍÓÚÑ]\.")


def _author_is_a_name(original: Dict[str, Any], normalised: Dict[str, Any], text: str) -> bool:
    """A headline in author position («Murieron 463 personas…. (13 de agosto de
    2020). Hoy día Córdoba») is a title, not an author."""
    if original.get("author"):
        return True
    head = text.split("(", 1)[0]
    return bool(_NAME_HEAD_RE.match(head.strip(" -•○"))) or len(head.split()) <= 6


def _merge_normalised(original: Dict[str, Any], normalised: Dict[str, Any], how: str, text: str) -> Dict[str, Any]:
    out = dict(original)
    if not _author_is_a_name(original, normalised, text):
        return out
    new_title = _clean(normalised.get("title"))
    if len(new_title) < 8 or new_title.startswith("("):
        normalised = dict(normalised, title=original.get("title"))
    for field in _DATE_FIELDS:
        if _clean(normalised.get(field)) != _clean(original.get(field)):
            if field in ("author", "year", "title"):
                _append_candidate(out, field, original.get(field), normalised.get(field))
            out[field] = normalised.get(field)
    ptype, ntype = original.get("publication_type"), normalised.get("publication_type")
    # The type moves only out of «unclassified», or from a book to a named journal.
    upgrade = (ptype == "sin_clasificar" and not (ntype == "libro" and _v125._ACCESS_RE.search(text))) or (
        ptype == "libro" and ntype == "articulo_revista" and normalised.get("journal")
    )
    if upgrade and ntype and ntype != ptype:
        for field in ("journal", "publisher", "publisher_observed", "source_publisher"):
            out[field] = normalised.get(field)
        _set_type(out, ntype, f"v126_date_block_{how}_type")
    _add_note(out, f"v126_date_block_{how}")
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    out = _v125.parse_reference(text)
    normalised, how = normalise_date_block(text)
    if how:
        alt = _v125.parse_reference(normalised)
        if how == "no_date":
            _complete_undated(alt, normalised)
        out = _merge_normalised(out, alt, how, text)
    return _overlay(text, out)


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        output.append(row)
    return output


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v125.flatten_parsed(parsed, prefix=prefix)
