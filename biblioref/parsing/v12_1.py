# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.1.

Small conservative overlay on v0.12.  The main goals are:
- force a parser-version revision so persisted v0.12 parses are refreshed and
  the new audit/candidate fields are actually populated;
- repair additional field patterns exposed by the Apolonio field validation
  without touching extraction/segmentation;
- preserve the historical flattened export schema so CSV callers do not break.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v12 as _v12
from . import v11 as _v11

PARSER_VERSION = "biblioref-parser-v0.12.1"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇ"
_LC = "A-Za-zÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇáéíóúüñàâãèêìòôõùç"
_SURNAME_PREFIX = r"(?:(?:de|del|de\s+la|de\s+los|da|do|dos|das|van|von)\s+)?"
_APA_HEAD_RE = re.compile(
    r"^(?P<head>.{1,280}?)\s*\(\s*(?P<year>(?:18|19|20)\d{2})[a-z]?"
    r"(?:\s*,[^)]*)?\)\s*\.?\s*(?P<rest>.+)$",
    re.I,
)
_APA_PERSON_RE = re.compile(
    rf"(?P<surname>{_SURNAME_PREFIX}[{_UC}][{_LC}'’´\- ]*?),\s*"
    rf"(?P<given>(?:[{_UC}]\.\s*){{1,5}}(?:[a-záéíóúüñ]\.\s*)?)"
)
_ORG_PREFIX_RE = re.compile(
    r"^(?:Universidad|University|UNICEF|Organization|Organisation|Organizaci[oó]n|"
    r"Pan\s+American\s+Health\s+Organization|Ministerio|Ministry|OMS|OPS|WHO|PAHO|"
    r"Instituto|Institute|Gobierno|Government|Consejo|Council|Comisi[oó]n|Commission|"
    r"Fondo|Fund|Naciones\s+Unidas|United\s+Nations)\b",
    re.I,
)
_SERIAL_CUE_RE = re.compile(
    r"\b(?:Rev(?:ista)?\.?|Journal|Anales|Annals|Bolet[ií]n|Acta|Psykhe|PSYKHE|"
    r"Lancet|Medisan|Panorama|Psicoperspectivas|Enfermer[ií]a|Enfermagem|"
    r"Salud\s+Colectiva|Medicina\s+Social|Critical\s+Public\s+Health|"
    r"Dialogues\s+in|Health\s+education|Universitas\s+Psychologica|Index\s+de\s+enfermer[ií]a)\b",
    re.I,
)
_REPORT_TITLE_RE = re.compile(
    r"^(?:Informe|Estad[ií]sticas|Estado\s+mundial|Plan\s+Nacional|Estrategia|Pautas|"
    r"Resolution|Resoluci[oó]n|Gu[ií]a|Manual)\b",
    re.I,
)
_INSTITUTIONAL_REPORT_RE = re.compile(
    r"\b(?:Naciones\s+Unidas|United\s+Nations|CEPAL|Comisi[oó]n\s+Econ[oó]mica|"
    r"Organizaci[oó]n\s+Mundial\s+de\s+la\s+Salud|World\s+Health\s+Organization)\b",
    re.I,
)
_CONF_VENUE_RE = re.compile(
    r"^(?P<venue>(?:[IVXLCDM]+\s+)?(?:Jornadas?|Congreso|Congress|Conference|Seminario|Encuentro)[^.]{0,160})\.\s+(?P<tail>.+)$",
    re.I,
)

_ARTICLE_META_PATTERNS = (
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:\d{1,4}|[IVXLCDM]{1,8})\s*"
        r"\(\s*[^)]{1,12}\s*\)\s*[,;:]\s*(?:pp?\.\s*)?"
        r"(?:\d{1,7}(?:\s*[-–—]\s*\d{1,7})?|s\.?\s*p\.?)\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*\(\s*(?:\d{1,3}|[IVXLCDM]{1,8})\s*\)\s*[,;:]\s*"
        r"(?:pp?\.\s*)?\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:\d{1,4}|[IVXLCDM]{1,8})\s*\.\s*"
        r"(?:pp?\.\s*)\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:\d{1,4}|[IVXLCDM]{1,8})\s*[,;:]\s*"
        r"(?:pp?\.\s*)?\d{1,7}(?:\s*[-–—]\s*\d{1,7})?\s*\.?$",
        re.I,
    ),
    re.compile(
        r"^(?P<prefix>.+?)\s*,\s*(?:pp?\.\s*)?\d{1,7}\s*[-–—]\s*\d{1,7}\s*\.?$",
        re.I,
    ),
)
_IN_SERIAL_RE = re.compile(
    r"^(?P<title>.+?)\.\s+(?:In|En)\s+(?P<journal>.+?)\s*"
    r"\(\s*(?:(?:Vol\.?\s*\d{1,4}\s*,\s*)?No\.?\s*\d{1,4}\s*,\s*)"
    r"pp?\.\s*\d{1,7}\s*[-–—]\s*\d{1,7}\s*\)",
    re.I,
)
_SPECIAL_PSYKHE_RE = re.compile(
    r"^(?P<title>.+?)\.\s+(?P<journal>[A-ZÁÉÍÓÚÜÑ]{4,})\s+(?:19|20)\d{2}\s*,\s*"
    r"Vol\.?\s*\d{1,4}\s*,\s*N[°ºo]\.?\s*\d{1,4}\s*,\s*\d{1,7}\s*[-–—]\s*\d{1,7}\s*\.?$",
    re.I,
)
_SPECIAL_REVISTA_ANO_RE = re.compile(
    r"^(?P<title>.+?)\.\s+En\s+(?P<journal>Revista\s+[^,]{2,80})\s*,\s*A[ñn]o\s+[IVXLCDM\d]+\s*,\s*"
    r"N[°ºo]\.?\s*\d+(?:\([^)]*\))?\s*:\s*\d{1,7}\s*[-–—]\s*\d{1,7}\s*\.?$",
    re.I,
)
_JOURNAL_VOLUME_ONLY_RE = re.compile(
    r"^(?P<title>.+?)\.\s+(?P<journal>(?:Rev(?:ista)?\.?|Journal|Anales|Annals|Acta|Psykhe|PSYKHE)[^,]{1,100})\s*,\s*"
    r"(?:\d{1,4}|[IVXLCDM]{1,8})\s*\.?$",
    re.I,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "", str(value or "").casefold())


def _pair(old: Any, new: Any) -> str:
    vals: List[str] = []
    for x in (old, new):
        if x not in (None, "") and str(x) not in vals:
            vals.append(str(x))
    return " || ".join(vals)


def _append_candidate(out: Dict[str, Any], key: str, old: Any, new: Any) -> None:
    field = f"{key}_candidates"
    current = str(out.get(field) or "")
    addition = _pair(old, new)
    if not addition:
        return
    vals = [x.strip() for x in current.split("||") if x.strip()]
    for x in [x.strip() for x in addition.split("||") if x.strip()]:
        if x not in vals:
            vals.append(x)
    out[field] = " || ".join(vals)


def _add_note(out: Dict[str, Any], note: str) -> None:
    notes = [x for x in str(out.get("parser_notes") or "").split(";") if x]
    if note not in notes:
        notes.append(note)
    out["parser_notes"] = ";".join(notes)


def _set_review(out: Dict[str, Any], reasons: List[str]) -> None:
    reasons = list(dict.fromkeys(x for x in reasons if x))
    out["review_reasons"] = ";".join(reasons)
    out["needs_review"] = bool(reasons)
    penalties = {
        "multiple_year_mentions": 0.10,
        "web_title_source_ambiguous": 0.15,
        "author_boundary_ambiguous": 0.20,
        "document_type_unresolved": 0.20,
        "publisher_inside_title": 0.15,
    }
    confidence = 1.0 - sum(penalties.get(x, 0.05) for x in reasons)
    out["parser_confidence"] = max(0.20, round(confidence, 2))


def _better_authors(head: str) -> List[str]:
    h = re.sub(r"\s+", " ", head).strip()
    if _ORG_PREFIX_RE.search(h):
        parts = re.split(
            r"\s+y\s+(?=(?:Organizaci[oó]n|Organization|Organisation|Universidad|University|Ministerio|Ministry|Consejo|Council|Comisi[oó]n|Commission|Instituto|Institute|UNICEF)\b)",
            h,
            flags=re.I,
        )
        return [p.strip(" .") for p in parts if p.strip(" .")]
    out: List[str] = []
    for m in _APA_PERSON_RE.finditer(h):
        surname = re.sub(r"\s+", " ", m.group("surname")).strip(" ,;&")
        given = re.sub(r"\s+", " ", m.group("given")).strip()
        if surname and given:
            out.append(f"{surname}, {given}")
    if out:
        return out
    if h and "," not in h and len(h.split()) <= 16:
        return [h.strip(" .")]
    return []


def _split_article(rest: str) -> Optional[Tuple[str, str]]:
    s = _clean(rest)
    s = re.split(r"\s+(?=https?\s*:\s*/|www\.)", s, maxsplit=1, flags=re.I)[0].rstrip(" .")

    m = _IN_SERIAL_RE.match(s)
    if m and _SERIAL_CUE_RE.search(m.group("journal")):
        return m.group("title").strip(" ."), m.group("journal").strip(" .,:;")
    for rx in (_SPECIAL_PSYKHE_RE, _SPECIAL_REVISTA_ANO_RE, _JOURNAL_VOLUME_ONLY_RE):
        m = rx.match(s)
        if m:
            return m.group("title").strip(" ."), m.group("journal").strip(" .,:;")
    if re.search(r"\.\s+(?:In|En)\s+", s, re.I):
        return None

    prefix = None
    for rx in _ARTICLE_META_PATTERNS:
        m = rx.match(s)
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
    if not title or not journal or len(journal.split()) > 18:
        return None
    return title, journal


def _closing_publisher(rest: str) -> Optional[str]:
    core = _clean(rest).rstrip(" .")
    m = re.search(
        r"\b(?:Washington\s*,?\s*D\.?C\.?|Santiago(?:\s+de\s+Chile)?|México|Mexico|Buenos\s+Aires|"
        r"Barcelona|Ginebra|Geneva|New\s+York|Nueva\s+York|Lima|Bogot[aá])\s*:\s*(?P<pub>[^:.;]{2,90})$",
        core,
        re.I,
    )
    if not m:
        return None
    pub = m.group("pub").strip(" .,:;")
    return pub if 1 <= len(pub.split()) <= 12 else None


def _acronym_publisher(rest: str) -> Optional[str]:
    m = re.search(r"\.\s*([A-ZÁÉÍÓÚÜÑ]{2,10})\s*\([^)]+\)\s*\.?$", _clean(rest))
    return m.group(1) if m else None


def _conference_title(rest: str) -> Optional[Tuple[str, str]]:
    m = _CONF_VENUE_RE.match(_clean(rest))
    if not m:
        return None
    venue = m.group("venue").strip(" .")
    bits = [b.strip() for b in re.split(r"\.\s+", m.group("tail")) if b.strip()]
    if len(bits) >= 2 and len(bits[-1].split()) <= 4 and not re.search(r"\d", bits[-1]):
        bits = bits[:-1]
    title = ". ".join(bits).strip(" .")
    return (title, venue) if title else None


def _web_title_before_available(rest: str) -> Optional[str]:
    m = re.search(r"\bDisponible\s+en\b", rest, re.I)
    if not m:
        return None
    return rest[:m.start()].strip(" .") or None


def _report_title_with_subtitle(rest: str) -> Optional[str]:
    core = _clean(rest)
    m = re.search(
        r"\s+(?:Washington\s*,?\s*D\.?C\.?|Santiago(?:\s+de\s+Chile)?|México|Mexico|Buenos\s+Aires|"
        r"Barcelona|Ginebra|Geneva|New\s+York|Nueva\s+York|Lima|Bogot[aá])\s*:\s*[^:.;]{2,90}\.?$",
        core,
        re.I,
    )
    if not m:
        return None
    candidate = core[:m.start()].strip(" .")
    return candidate or None


def _overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    apa = _APA_HEAD_RE.match(text)
    reasons = [x for x in str(out.get("review_reasons") or "").split(";") if x]

    if apa:
        head, rest = apa.group("head"), apa.group("rest")

        # Preserve complete personal/corporate author blocks, including particles.
        authors = _better_authors(head)
        if authors:
            joined = " | ".join(authors)
            if _norm(joined) != _norm(out.get("authors")):
                _append_candidate(out, "author", out.get("authors"), joined)
                out["author"] = authors[0]
                out["authors"] = joined
                _add_note(out, "v121_author_block_recovered")

        # Strong serial metadata outranks URL/access mode and weak lexical publishers.
        article = _split_article(rest)
        if article:
            title, journal = article
            if _norm(title) != _norm(out.get("title")):
                _append_candidate(out, "title", out.get("title"), title)
            if _norm(journal) != _norm(out.get("journal")):
                _append_candidate(out, "journal", out.get("journal"), journal)
            if out.get("publication_type") != "articulo_revista":
                _append_candidate(out, "type", out.get("publication_type"), "articulo_revista")
            if out.get("publisher"):
                _append_candidate(out, "publisher", out.get("publisher"), "(none: journal article)")
            out["title"] = title
            out["journal"] = journal
            out["publication_type"] = "articulo_revista"
            out["publisher"] = None
            out["publisher_observed"] = None
            out["source_publisher"] = None
            reasons = [r for r in reasons if r not in {"document_type_unresolved", "publisher_inside_title", "web_title_source_ambiguous"}]
            _add_note(out, "v121_article_boundary_recovered")

        # v0.12 web routing must never erase an already-established thesis type.
        prior = _v11.parse_reference(text)
        if prior.get("publication_type") == "tesis" and out.get("publication_type") == "material_web":
            _append_candidate(out, "type", out.get("publication_type"), "tesis")
            out["publication_type"] = "tesis"
            _add_note(out, "v121_thesis_over_web_preserved")

        # Conference venue is not the contribution title.
        if out.get("publication_type") == "conference_paper":
            conf = _conference_title(rest)
            if conf:
                title, venue = conf
                if _norm(out.get("title")) == _norm(venue) and _norm(title) != _norm(venue):
                    _append_candidate(out, "title", out.get("title"), title)
                    out["title"] = title
                    _add_note(out, "v121_conference_title_recovered")

        # ``Disponible en`` is an access marker; keep the full title before it.
        if out.get("publication_type") == "material_web":
            available_title = _web_title_before_available(rest)
            if available_title and _norm(available_title) != _norm(out.get("title")):
                _append_candidate(out, "title", out.get("title"), available_title)
                out["title"] = available_title
                _add_note(out, "v121_available_title_recovered")

        # Remove a clear author/byline note from a web title.
        title_now = str(out.get("title") or "")
        cleaned_title = re.sub(r"\.\s*Columna\s+de\s+opini[oó]n\s+escrita\s+por\s+.+$", "", title_now, flags=re.I).strip(" .")
        if cleaned_title and cleaned_title != title_now:
            _append_candidate(out, "title", title_now, cleaned_title)
            out["title"] = cleaned_title
            _add_note(out, "v121_web_byline_removed")

        # Institutional reports/documents.
        title_now = str(out.get("title") or "").strip()
        institutional_hits = len(_INSTITUTIONAL_REPORT_RE.findall(rest))
        if (
            not out.get("journal")
            and out.get("publication_type") in {None, "", "sin_clasificar", "libro"}
            and (
                (_ORG_PREFIX_RE.search(head) and _REPORT_TITLE_RE.search(title_now))
                or (out.get("publication_type") in {None, "", "sin_clasificar"} and institutional_hits >= 1)
                or (out.get("publication_type") == "libro" and institutional_hits >= 2)
            )
        ):
            if out.get("publication_type") != "informe_documento":
                _append_candidate(out, "type", out.get("publication_type"), "informe_documento")
                out["publication_type"] = "informe_documento"
                reasons = [r for r in reasons if r != "document_type_unresolved"]
                _add_note(out, "v121_institutional_report_recovered")

        # Recover report subtitles before a closing place:publisher imprint.
        if out.get("publication_type") == "informe_documento":
            report_title = _report_title_with_subtitle(rest)
            if report_title and _norm(report_title) != _norm(out.get("title")):
                _append_candidate(out, "title", out.get("title"), report_title)
                out["title"] = report_title
                _add_note(out, "v121_report_subtitle_recovered")

        # Closing imprint beats lexical fragments such as ``Panamericana``.
        if out.get("publication_type") in {"libro", "capitulo_libro", "informe_documento", "documento_guia_manual"}:
            pub = _closing_publisher(rest)
            if pub and _norm(pub) != _norm(out.get("publisher")):
                _append_candidate(out, "publisher", out.get("publisher"), pub)
                out["publisher"] = pub
                out["publisher_observed"] = pub
                out["source_publisher"] = pub
                _add_note(out, "v121_closing_publisher_recovered")
            elif out.get("publication_type") == "libro":
                acronym = _acronym_publisher(rest)
                if acronym and _norm(acronym) != _norm(out.get("publisher")):
                    _append_candidate(out, "publisher", out.get("publisher"), acronym)
                    out["publisher"] = acronym
                    out["publisher_observed"] = acronym
                    out["source_publisher"] = acronym
                    _add_note(out, "v121_acronym_publisher_recovered")

        # A repeated parenthetical year must not leak into the selected title.
        year = str(out.get("year") or "")
        title_now = str(out.get("title") or "")
        if year and re.match(rf"^\(\s*{re.escape(year)}\s*\)\s+", title_now):
            fixed = re.sub(rf"^\(\s*{re.escape(year)}\s*\)\s+", "", title_now).strip()
            _append_candidate(out, "title", title_now, fixed)
            out["title"] = fixed
            _add_note(out, "v121_duplicate_year_removed_from_title")

    if out.get("publication_type") in (None, "", "sin_clasificar") and "document_type_unresolved" not in reasons:
        reasons.append("document_type_unresolved")
    _set_review(out, reasons)

    style = str(out.get("parse_style") or "")
    if "v121_overlay" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v121_overlay") if x)
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    return _overlay(text, _v12.parse_reference(text))


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    """Keep the pre-v0.12 flattened schema stable for CSV compatibility.

    Audit fields remain in the nested parsed object and are exported explicitly
    by XLSX/JSON paths.
    """
    parsed = parsed or {}
    fields = (
        "parser_version", "parser_status", "parse_style", "author", "authors", "year",
        "publication_type", "title", "journal", "publisher", "publisher_observed",
        "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
