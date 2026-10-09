# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.4.

Author-focused conservative overlay on v0.12.3.  It preserves extraction and
all previously selected non-author bibliographic fields while strengthening:

- personal author blocks with surname particles and lowercase initials;
- corporate coauthors joined by ``y``, ``&`` or ``and`` only when the right
  side is clearly another organization;
- PDF line-break artefacts inside hyphenated surnames (``Duran- Aniotz`` ->
  ``Duran-Aniotz``) without changing the raw reference;
- explicit source truncation (APA ellipsis / ``et al.``), surfaced as audit
  metadata rather than silently presenting an observed partial list as complete.

The new ``author_list_status`` field is intentionally small:
``complete``, ``explicit_ellipsis``, ``et_al`` or ``unresolved``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from . import v12_3 as _v123

PARSER_VERSION = "biblioref-parser-v0.12.4"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇ"
_LC = "A-Za-zÁÉÍÓÚÜÑÀÂÃÈÊÌÒÔÕÙÇáéíóúüñàâãèêìòôõùç"
_SURNAME_PREFIX = r"(?:(?:de|del|de\s+la|de\s+los|da|do|dos|das|van|von)\s+)?"
_APA_HEAD_RE = re.compile(
    r"^(?P<head>.{1,320}?)\s*\(\s*(?:18|19|20)\d{2}[a-z]?"
    r"(?:\s*,[^)]*)?\)\s*\.?\s*.+$",
    re.I,
)
_PERSON_RE = re.compile(
    rf"(?P<surname>{_SURNAME_PREFIX}[{_UC}][{_LC}'’´\- ]*?),\s*"
    rf"(?P<given>(?:[{_UC}]\.\s*){{1,6}}(?:[a-záéíóúüñ]\.\s*)?)"
)
_ORG_START = (
    r"(?:Universidad|University|UNICEF|Organization|Organisation|Organizaci[oó]n|"
    r"Pan\s+American\s+Health\s+Organization|Ministerio|Ministry|OMS|OPS|WHO|PAHO|"
    r"Instituto|Institute|Gobierno|Government|Consejo|Council|Comisi[oó]n|Commission|"
    r"Fondo|Fund|Naciones\s+Unidas|United\s+Nations|Secretar[ií]a|Secretariat|"
    r"Departamento|Department|Centro|Centre|Center)"
)
_ORG_PREFIX_RE = re.compile(rf"^{_ORG_START}\b", re.I)
_ORG_CONJ_RE = re.compile(rf"\s+(?:&|and|y|e)\s+(?={_ORG_START}\b)", re.I)
_TRAILING_ORG_RE = re.compile(rf"\s+(?:&|and|y|e)\s+(?P<org>{_ORG_START}\b.+)$", re.I)
_ET_AL_RE = re.compile(r"\bet\s+al\.?\b", re.I)
_ELLIPSIS_RE = re.compile(r"(?:\.\s*\.\s*\.|…)")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "", str(value or "").casefold())


def _fix_hyphen_space(value: str) -> str:
    # Only author metadata is normalized; the raw reference remains untouched.
    return re.sub(r"(?<=\w)-\s+(?=\w)", "-", _clean(value))


def _split_values(value: Any) -> List[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip()]


def _append_candidate(out: Dict[str, Any], key: str, old: Any, new: Any) -> None:
    field = f"{key}_candidates"
    current = [x.strip() for x in str(out.get(field) or "").split("||") if x.strip()]
    for item in (old, new):
        text = _clean(item)
        if text and text not in current:
            current.append(text)
    out[field] = " || ".join(current)


def _notes(out: Dict[str, Any]) -> List[str]:
    return [x for x in str(out.get("parser_notes") or "").split(";") if x]


def _reasons(out: Dict[str, Any]) -> List[str]:
    return [x for x in str(out.get("review_reasons") or "").split(";") if x]


def _set_notes(out: Dict[str, Any], notes: List[str]) -> None:
    out["parser_notes"] = ";".join(dict.fromkeys(x for x in notes if x))


def _set_review(out: Dict[str, Any], reasons: List[str]) -> None:
    reasons = list(dict.fromkeys(x for x in reasons if x))
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
    confidence = 1.0 - sum(penalties.get(x, 0.05) for x in reasons)
    out["parser_confidence"] = max(0.20, round(confidence, 2))


def _personal_authors(head: str) -> List[str]:
    out: List[str] = []
    for m in _PERSON_RE.finditer(head):
        surname = _fix_hyphen_space(m.group("surname")).strip(" ,;&")
        given = _clean(m.group("given"))
        if surname and given:
            out.append(f"{surname}, {given}")
    return out


def _corporate_authors(head: str) -> List[str]:
    h = _clean(head).strip(" .")
    if not _ORG_PREFIX_RE.search(h):
        return []
    # Split only when the conjunction is followed by another organization.
    # This deliberately preserves e.g. ``Ministerio de Economía, Fomento y Turismo``.
    parts = [p.strip(" .") for p in _ORG_CONJ_RE.split(h) if p.strip(" .")]
    return parts or [h]


def _mixed_person_corporate(head: str, persons: List[str]) -> List[str]:
    """Append a trailing corporate coauthor after a personal block when explicit."""
    if not persons:
        return persons
    m = _TRAILING_ORG_RE.search(head)
    if not m:
        return persons
    org = _clean(m.group("org")).strip(" .")
    if org and all(_norm(org) != _norm(x) for x in persons):
        return persons + [org]
    return persons


def _author_list_status(head: str, authors: List[str]) -> str:
    if _ELLIPSIS_RE.search(head):
        return "explicit_ellipsis"
    if _ET_AL_RE.search(head):
        return "et_al"
    if authors:
        return "complete"
    return "unresolved"


def _author_overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    m = _APA_HEAD_RE.match(text)
    notes = _notes(out)
    reasons = _reasons(out)

    if m:
        head = _clean(m.group("head"))
        corporate = _corporate_authors(head)
        if corporate:
            authors = corporate
        else:
            authors = _personal_authors(head)
            authors = _mixed_person_corporate(head, authors)

        current = _split_values(out.get("authors"))
        current_norm = [_fix_hyphen_space(x) for x in current]

        # Prefer recomputation when it finds at least as much author evidence;
        # otherwise only apply safe hyphen-space normalization to current output.
        selected = authors if authors and len(authors) >= len(current) else current_norm
        selected = [_fix_hyphen_space(x) for x in selected]
        joined = " | ".join(selected)
        old_joined = " | ".join(current)

        if joined and _norm(joined) != _norm(old_joined):
            _append_candidate(out, "author", old_joined, joined)
            out["author"] = selected[0]
            out["authors"] = joined
            notes.append("v124_author_block_recovered")
        elif selected and old_joined != joined:
            # `_norm` intentionally ignores hyphen spacing; preserve a candidate
            # trace even when this is punctuation/line-break normalization only.
            _append_candidate(out, "author", old_joined, joined)
            out["author"] = selected[0]
            out["authors"] = joined
            notes.append("v124_author_hyphen_space_normalized")

        status = _author_list_status(head, selected)
        out["author_list_status"] = status
        if status in {"explicit_ellipsis", "et_al"}:
            if "author_list_truncated" not in reasons:
                reasons.append("author_list_truncated")
            notes.append(f"v124_author_list_{status}")
        elif status == "unresolved":
            if re.search(r"(?:&|\band\b|\by\b|\be\b)", head, re.I) and "author_boundary_ambiguous" not in reasons:
                reasons.append("author_boundary_ambiguous")
        else:
            # If an earlier layer emitted the generic boundary warning but the
            # complete block is now structurally recovered, remove that warning.
            if len(selected) >= 2:
                reasons = [r for r in reasons if r != "author_boundary_ambiguous"]
    else:
        out["author_list_status"] = "unresolved"

    _set_notes(out, notes)
    _set_review(out, reasons)

    style = str(out.get("parse_style") or "")
    if "v124_author_audit" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v124_author_audit") if x)
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    return _author_overlay(text, _v123.parse_reference(text))


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v123.flatten_parsed(parsed, prefix=prefix)
