# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.3.

Conservative field overlay on v0.12.2.  It targets residual silent errors in
bibliographic fields while keeping reference extraction/segmentation untouched.

Main changes:
- article title/journal recovery when volume(issue) is present but pages are not;
- preservation of multi-sentence monograph/report titles before a closing imprint;
- institutional report publishers recovered from explicit trailing organizations;
- strong institutional PDF documents outrank generic web-access classification;
- guideline/manual cues outrank generic web-access classification;
- repository/thesis URLs are surfaced as review candidates rather than silently
  reclassified without textual evidence;
- ``Extraído de`` source/title forms recover the actual web title;
- conference page numbers are not retained as part of contribution titles;
- web source/publisher duplicates are removed conservatively;
- serial containers whose name looks monographic (e.g. ``Manual ...``) are
  flagged for review instead of being silently trusted as journal titles.

All audit/candidate fields remain downstream metadata.  No PDF geometry or
reference boundary code is imported here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v12_2 as _v122

PARSER_VERSION = "biblioref-parser-v0.12.3"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_APA_HEAD_RE = re.compile(
    r"^(?P<head>.{1,280}?)\s*\(\s*(?P<year>(?:18|19|20)\d{2})[a-z]?"
    r"(?:\s*,[^)]*)?\)\s*\.?\s*(?P<rest>.+)$",
    re.I,
)
_ORG_HEAD_RE = re.compile(
    r"\b(?:Organizaci[oó]n|Organization|Organisation|Ministerio|Ministry|Universidad|"
    r"University|Instituto|Institute|Consejo|Council|Comisi[oó]n|Commission|UNICEF|"
    r"OMS|OPS|WHO|PAHO|Naciones\s+Unidas|United\s+Nations|Gobierno|Government)\b",
    re.I,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:Organizaci[oó]n|Organization|Organisation|Ministerio|Ministry|Universidad|"
    r"University|Instituto|Institute|Consejo|Council|Comisi[oó]n|Commission|UNICEF|"
    r"OMS|OPS|WHO|PAHO|CEPAL|Naciones\s+Unidas|United\s+Nations|Fondo|Fund)\b",
    re.I,
)
_GUIDE_TITLE_RE = re.compile(
    r"^(?:Pautas?|Gu[ií]as?|Manual(?:es)?|Guidelines?|Handbook|Recomendaciones?)\b",
    re.I,
)
_REPORT_TITLE_RE = re.compile(
    r"^(?:Informe|Report|Estad[ií]sticas|Statistics|Estado\s+mundial|Plan(?:\s+Nacional)?|"
    r"Estrategia|Strategy|Evidencias|Resolution|Resoluci[oó]n|Declaraci[oó]n|Declaration)\b",
    re.I,
)
_REPOSITORY_THESIS_RE = re.compile(
    r"(?:\btesis\b|\bthesis\b|\bdissertation\b|repositorio|repository|/handle/|/tesis/|tesis\.)",
    re.I,
)
_URL_RE = re.compile(r"https?\s*:\s*/|www\.", re.I)
_PDF_RE = re.compile(r"\.pdf(?:\b|$)", re.I)
_SERIAL_CUE_RE = re.compile(
    r"\b(?:Rev(?:ista)?\.?|Journal|Anales|Annals|Bolet[ií]n|Acta|Psykhe|PSYKHE|"
    r"Lancet|Medisan|Panorama|Psicoperspectivas|Enfermer[ií]a|Enfermagem|"
    r"Salud\s+Colectiva|Medicina\s+Social|Critical\s+Public\s+Health|"
    r"Dialogues\s+in|Health\s+education|Universitas\s+Psychologica|Index\s+de\s+enfermer[ií]a)\b",
    re.I,
)
_MONOGRAPHIC_SOURCE_RE = re.compile(r"^(?:Manual|Handbook|Gu[ií]a|Tratado|Libro)\b", re.I)

# Journal article without explicit pages: ``Title. Journal Name, 4(1).``
_ARTICLE_NO_PAGES_RE = re.compile(
    r"^(?P<title>.+?)\.\s+(?P<journal>[^.]{2,120}?)\s*,\s*"
    r"\d{1,4}\s*\(\s*[^)]{1,12}\s*\)\s*\.?$",
    re.I,
)

# Multi-sentence monograph/report title followed by an imprint. The place may
# not cross a full stop; Washington D.C. is the deliberate exception.
_IMPRINT_RE = re.compile(
    r"^(?P<body>.+?)\."
    r"(?:\s+\([^)]*\bEds?\.?[^)]*\))?\s+"
    r"(?P<place>(?:Washington\s*,?\s*D\.?C\.?|[A-ZÁÉÍÓÚÜÑ][^.:]{1,75}))\s*:\s*"
    r"(?P<publisher>[^:]{2,120})\s*\.?$",
    re.I,
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "", str(value or "").casefold())


def _split_semicolon(value: Any) -> List[str]:
    return [x for x in str(value or "").split(";") if x]


def _append_candidate(out: Dict[str, Any], field: str, old: Any, new: Any) -> None:
    key = f"{field}_candidates"
    values = [x.strip() for x in str(out.get(key) or "").split("||") if x.strip()]
    for item in (old, new):
        if item in (None, ""):
            continue
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    out[key] = " || ".join(values)


def _add_note(out: Dict[str, Any], note: str) -> None:
    notes = _split_semicolon(out.get("parser_notes"))
    if note not in notes:
        notes.append(note)
    out["parser_notes"] = ";".join(notes)


def _add_review(out: Dict[str, Any], reason: str, penalty: float = 0.10) -> None:
    reasons = _split_semicolon(out.get("review_reasons"))
    if reason not in reasons:
        reasons.append(reason)
        current = float(out.get("parser_confidence") if out.get("parser_confidence") is not None else 1.0)
        out["parser_confidence"] = max(0.20, round(current - penalty, 2))
    out["review_reasons"] = ";".join(reasons)
    out["needs_review"] = bool(reasons)


def _remove_review(out: Dict[str, Any], reason: str) -> None:
    reasons = [x for x in _split_semicolon(out.get("review_reasons")) if x != reason]
    out["review_reasons"] = ";".join(reasons)
    out["needs_review"] = bool(reasons)


def _article_without_pages(rest: str) -> Optional[Tuple[str, str]]:
    core = re.split(r"\s+(?=https?\s*:\s*/|www\.)", _clean(rest), maxsplit=1, flags=re.I)[0].rstrip(" .")
    m = _ARTICLE_NO_PAGES_RE.match(core)
    if not m:
        return None
    journal = m.group("journal").strip(" .,:;")
    if not _SERIAL_CUE_RE.search(journal):
        return None
    return m.group("title").strip(" ."), journal


def _monograph_body(rest: str) -> Optional[Tuple[str, str]]:
    m = _IMPRINT_RE.match(_clean(rest))
    if not m:
        return None
    body = m.group("body").strip(" .")
    publisher = m.group("publisher").strip(" .,:;")
    if not body or not publisher:
        return None
    return body, publisher


def _institutional_tail(rest: str, title: Any) -> Optional[str]:
    core = _clean(rest).rstrip(" .")
    selected = _clean(title).strip(" .")
    if not selected:
        return None
    pos = core.casefold().find(selected.casefold())
    if pos < 0:
        return None
    tail = core[pos + len(selected):].strip(" .,:;")
    if not tail or ":" in tail:
        return None
    parts = [p.strip(" .,:;") for p in re.split(r"\.\s+", tail) if p.strip(" .,:;")]
    institutional = [p for p in parts if _INSTITUTION_RE.search(p)]
    if not institutional:
        return None
    candidate = institutional[-1]
    return candidate if 1 <= len(candidate.split()) <= 24 else None


def _extraido_de_title(rest: str, author: Any) -> Optional[Tuple[str, str]]:
    core = _clean(rest)
    cue = re.search(r"\bExtra[ií]d[oa]\s+de\s+", core, re.I)
    url = _URL_RE.search(core)
    if not cue or not url or url.start() <= cue.end():
        return None
    before = core[:cue.start()].strip(" .,:;")
    candidate = core[cue.end():url.start()].strip(" .,:;")
    if not candidate:
        return None
    # Many web citations end the title segment as ``, SiteName: URL``. Remove
    # that source label only when it matches the author/source already present.
    source = _clean(author).strip(" .") or before
    m = re.match(r"^(?P<title>.+?),\s*(?P<site>[^,:]{2,80})\s*:?$", candidate)
    if m and _norm(m.group("site")) in {_norm(source), _norm(before)}:
        candidate = m.group("title").strip(" .,:;")
    if not candidate:
        return None
    return before, candidate


def _institutional_web_type(head: str, title: Any, text: str) -> Optional[str]:
    if not _ORG_HEAD_RE.search(head):
        return None
    title_text = _clean(title)
    if _GUIDE_TITLE_RE.search(title_text):
        return "documento_guia_manual"
    if _REPORT_TITLE_RE.search(title_text) or _PDF_RE.search(text):
        return "informe_documento"
    return None


def _conference_title_without_page(title: Any) -> Optional[str]:
    text = _clean(title).strip(" .")
    fixed = re.sub(r"\s*,\s*(?:p\.?\s*)?\d{1,5}\s*$", "", text, flags=re.I).strip(" .")
    return fixed if fixed and fixed != text else None


def _field_overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    apa = _APA_HEAD_RE.match(text)
    rest = apa.group("rest") if apa else ""
    head = apa.group("head") if apa else ""

    # 1) Strong journal suffix with volume(issue), even when pages are omitted.
    if apa:
        article = _article_without_pages(rest)
        if article:
            title, journal = article
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
            _add_note(out, "v123_article_no_pages_recovered")

    # 2) Preserve complete multi-sentence monograph/report titles before imprint.
    if apa and out.get("publication_type") in {"libro", "informe_documento", "documento_guia_manual"}:
        imprint = _monograph_body(rest)
        if imprint:
            body, publisher = imprint
            current_title = _clean(out.get("title")).strip(" .")
            if current_title and _norm(body).startswith(_norm(current_title)) and len(body) > len(current_title) + 3:
                _append_candidate(out, "title", out.get("title"), body)
                out["title"] = body
                _add_note(out, "v123_monograph_subtitle_recovered")
            if not out.get("publisher"):
                _append_candidate(out, "publisher", out.get("publisher"), publisher)
                out["publisher"] = publisher
                out["publisher_observed"] = publisher
                out["source_publisher"] = publisher
                _add_note(out, "v123_imprint_publisher_recovered")

    # 3) A strong document identity outranks the generic fact that it was read online.
    if apa and out.get("publication_type") == "material_web":
        stronger_type = _institutional_web_type(head, out.get("title"), text)
        if stronger_type:
            _append_candidate(out, "type", out.get("publication_type"), stronger_type)
            out["publication_type"] = stronger_type
            _add_note(out, "v123_institutional_document_over_web")

    # 4) Recover `Source. Extraído de Actual title, Source: URL` forms.
    if apa and out.get("publication_type") == "material_web":
        web = _extraido_de_title(rest, out.get("author"))
        if web:
            source, title = web
            if _norm(title) != _norm(out.get("title")):
                _append_candidate(out, "title", out.get("title"), title)
                out["title"] = title
                _add_note(out, "v123_extraido_de_title_recovered")

    # 5) Repository URLs are evidence for a thesis candidate, not enough for an
    # automatic reclassification when the citation itself never says thesis.
    if out.get("publication_type") == "material_web" and _REPOSITORY_THESIS_RE.search(text):
        _append_candidate(out, "type", out.get("publication_type"), "tesis")
        _add_review(out, "possible_repository_thesis", 0.10)
        _add_note(out, "v123_repository_thesis_candidate")

    # 6) Do not keep a website/source duplicated as a bibliographic publisher.
    if out.get("publication_type") == "material_web" and out.get("publisher"):
        author = out.get("author")
        if author and _norm(out.get("publisher")) == _norm(author):
            _append_candidate(out, "publisher", out.get("publisher"), "(none: web source)")
            out["publisher"] = None
            out["publisher_observed"] = None
            out["source_publisher"] = None
            _add_note(out, "v123_web_source_not_publisher")

    # 7) Conference page numbers belong to locators, not to the title string.
    if out.get("publication_type") == "conference_paper":
        fixed = _conference_title_without_page(out.get("title"))
        if fixed:
            _append_candidate(out, "title", out.get("title"), fixed)
            out["title"] = fixed
            _add_note(out, "v123_conference_page_removed_from_title")

    # 8) Once an item is a report, replace weak lexical publisher fragments or
    # empty publishers with an explicit institutional tail when present.
    if apa and out.get("publication_type") == "informe_documento":
        candidate = _institutional_tail(rest, out.get("title"))
        current = _clean(out.get("publisher"))
        if candidate and (
            not current
            or _norm(current) in _norm(candidate)
            or current.casefold() in {"panamericana", "iberoamericana"}
        ) and _norm(candidate) != _norm(current):
            _append_candidate(out, "publisher", out.get("publisher"), candidate)
            out["publisher"] = candidate
            out["publisher_observed"] = candidate
            out["source_publisher"] = candidate
            _add_note(out, "v123_institutional_publisher_recovered")

    # 9) Serial-looking metadata can still be semantically ambiguous when the
    # selected container itself advertises a monograph/manual identity.
    journal = _clean(out.get("journal"))
    if out.get("publication_type") == "articulo_revista" and journal and _MONOGRAPHIC_SOURCE_RE.search(journal):
        _append_candidate(out, "type", out.get("publication_type"), "capitulo_libro/documento_guia_manual")
        _add_review(out, "serial_container_monograph_like", 0.15)
        _add_note(out, "v123_serial_container_review")

    style = str(out.get("parse_style") or "")
    if "v123_field_overlay" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v123_field_overlay") if x)
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    return _field_overlay(text, _v122.parse_reference(text))


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v122.flatten_parsed(parsed, prefix=prefix)
