# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.2.

Conservative audit overlay on v0.12.1.  This revision does not change reference
segmentation and does not reinterpret already-selected bibliographic fields.  It
refines *year evidence* so a year mentioned in a title or ordinary citation
context is not confused with an access date merely because the title contains a
word such as ``acceso``.

The selected publication year remains the parser's best interpretation.  Every
observed year is retained in ``year_candidates`` with a contextual role:
``publication``, ``access``, ``url``, ``title`` or ``context``.  Human review is
requested for competing access/URL years, but title/context years alone are
informative rather than ambiguous.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import v12_1 as _v121

PARSER_VERSION = "biblioref-parser-v0.12.2"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_YEAR_RE = re.compile(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)")
_APA_HEAD_RE = re.compile(
    r"^(?P<head>.{1,280}?)\s*\(\s*(?P<year>(?:18|19|20)\d{2})[a-z]?"
    r"(?:\s*,[^)]*)?\)\s*\.?\s*(?P<rest>.+)$",
    re.I,
)
_CONTEXT_YEAR_RANGE_RE = re.compile(
    r"\(\s*(?:18|19|20)\d{2}\s*[-–—]\s*(?:18|19|20)\d{2}\s*\)"
)
# Deliberately *not* a bare ``acceso`` token.  Access status requires a
# bibliographic retrieval phrase.  This prevents titles such as ``el acceso a
# la salud`` from turning every later year into an access date.
_ACCESS_CUE_RE = re.compile(
    r"\b(?:Retrieved|Extra[ií]d[oa](?:\s+el)?|Consultad[oa](?:\s+el)?|"
    r"[ÚU]ltima\s+visita|Last\s+accessed|Accessed)\b",
    re.I,
)
_URL_START_RE = re.compile(r"https?\s*:\s*/|www\.", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _split_reasons(value: Any) -> List[str]:
    return [x for x in str(value or "").split(";") if x]


def _title_span(text: str, title: Any) -> Optional[Tuple[int, int]]:
    """Locate the selected title when it survives verbatim after whitespace cleanup."""
    title_text = _clean(str(title or "")).strip(" .")
    if not title_text:
        return None
    pos = text.casefold().find(title_text.casefold())
    if pos < 0:
        return None
    return pos, pos + len(title_text)


def _publication_year_span(text: str, apa: Optional[re.Match[str]]) -> Optional[Tuple[int, int]]:
    if not apa:
        return None
    year = apa.group("year")
    # The publication year is the first year inside the APA author-year block.
    block_end = apa.start("rest")
    for m in _YEAR_RE.finditer(text[:block_end]):
        if m.group(1) == year:
            return m.start(), m.end()
    return None


def _year_roles(text: str, parsed: Dict[str, Any]) -> "OrderedDict[str, List[str]]":
    apa = _APA_HEAD_RE.match(text)
    publication_span = _publication_year_span(text, apa)
    title_span = _title_span(text, parsed.get("title"))
    context_year_ranges = [
        (m.start(), m.end()) for m in _CONTEXT_YEAR_RANGE_RE.finditer(text)
    ]
    url = _URL_START_RE.search(text)
    url_start = url.start() if url else None
    access_cues = list(_ACCESS_CUE_RE.finditer(text))

    roles: "OrderedDict[str, List[str]]" = OrderedDict()
    for mention in _YEAR_RE.finditer(text):
        year = mention.group(1)
        pos = mention.start()
        role = "context"

        if publication_span and publication_span[0] <= pos < publication_span[1]:
            role = "publication"
        elif url_start is not None and pos >= url_start:
            role = "url"
        else:
            # Access dates are only years following a structured retrieval cue.
            # The window ends at the URL (when present) or after a conservative
            # 120-character retrieval segment.
            for cue in access_cues:
                access_end = (
                    url_start
                    if url_start is not None and url_start > cue.start()
                    else min(len(text), cue.start() + 120)
                )
                if cue.start() <= pos < access_end:
                    role = "access"
                    break
            # Parenthesized year ranges such as ``(2005-2010)`` are contextual
            # evidence even when a prior layer kept that range inside a recovered
            # title span.  Ordinary title ranges such as ``2020-2021`` remain
            # title evidence.
            in_context_range = any(start <= pos < end for start, end in context_year_ranges)
            if (
                role == "context"
                and not in_context_range
                and title_span
                and title_span[0] <= pos < title_span[1]
            ):
                role = "title"

        roles.setdefault(year, [])
        if role not in roles[year]:
            roles[year].append(role)
    return roles


def _format_year_candidates(roles: "OrderedDict[str, List[str]]") -> str:
    return " | ".join(
        f"{year} [{' / '.join(year_roles)}]" for year, year_roles in roles.items()
    )


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


def _year_audit_overlay(text: str, base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    roles = _year_roles(text, out)
    out["year_candidates"] = _format_year_candidates(roles)

    reasons = [r for r in _split_reasons(out.get("review_reasons")) if r != "multiple_year_mentions"]
    selected = str(out.get("year") or "")
    distinct_years = list(roles.keys())

    # Only a genuinely competing retrieval/URL year makes an otherwise clear
    # APA publication year a human-review case.  Years in the selected title or
    # ordinary context remain visible but do not lower confidence by themselves.
    competing_secondary = {
        year
        for year, year_roles in roles.items()
        if year != selected and any(role in {"access", "url"} for role in year_roles)
    }
    if len(distinct_years) > 1 and competing_secondary:
        reasons.append("multiple_year_mentions")
    elif not selected and len(distinct_years) > 1:
        # Without a selected publication year, multiple structured date roles
        # remain genuinely ambiguous.  Pure title/context ranges are not.
        structured = {
            year
            for year, year_roles in roles.items()
            if any(role in {"publication", "access", "url"} for role in year_roles)
        }
        if len(structured) > 1:
            reasons.append("multiple_year_mentions")

    _set_review(out, reasons)

    notes = _split_reasons(out.get("parser_notes"))
    if len(distinct_years) > 1 and "v122_year_roles_contextualized" not in notes:
        notes.append("v122_year_roles_contextualized")
    out["parser_notes"] = ";".join(notes)

    style = str(out.get("parse_style") or "")
    if "v122_year_audit" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v122_year_audit") if x)
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _clean(texto)
    return _year_audit_overlay(text, _v121.parse_reference(text))


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v121.flatten_parsed(parsed, prefix=prefix)
