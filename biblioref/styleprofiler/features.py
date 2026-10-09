# -*- coding: utf-8 -*-
"""Explainable structural features for BiblioRef StyleProfiler.

This module is deliberately downstream-only: it reads raw reference strings and
parser metadata, and never modifies extraction or parsing output.
"""
from __future__ import annotations

import re
from typing import Any, Dict

_YEAR = r"(?:18|19|20)\d{2}[a-z]?"
_NUM_PREFIX_RE = re.compile(r"^\s*(?:\[(\d{1,4})\]|\((\d{1,4})\)|(\d{1,4})[.)])\s+")
_BRACKET_NUM_RE = re.compile(r"^\s*\[\d{1,4}\]\s+")
_PAREN_YEAR_AFTER_AUTHOR_RE = re.compile(rf"^.{{1,180}}?\(\s*{_YEAR}\s*\)", re.I)
_BARE_YEAR_AFTER_AUTHOR_RE = re.compile(rf"^.{{1,180}}?[.,;:]\s*{_YEAR}\s*[.,;:]", re.I)
_TERMINAL_YEAR_RE = re.compile(rf"{_YEAR}\s*[.)]?\s*$", re.I)
_UPPERCASE_SURNAME_RE = re.compile(r"^\s*[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Ý][A-ZÁÉÍÓÚÜÑÀ-ÖØ-Ý'’´-]{1,}(?:\s+[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Ý][A-ZÁÉÍÓÚÜÑÀ-ÖØ-Ý'’´-]{1,})*\s*,")
_SURNAME_INITIALS_RE = re.compile(r"^\s*[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Ý][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’´-]+\s*,\s*(?:[A-ZÁÉÍÓÚÜÑ]\.?\s*){1,4}")
_INITIALS_SURNAME_RE = re.compile(r"^\s*(?:[A-Z]\.?\s*){1,4}[A-Z][A-Za-z'’-]{2,}")
_QUOTED_TITLE_RE = re.compile(r"[\"“”«»].{3,}?[\"“”«»]")
_VOL_ISSUE_PAGES_RE = re.compile(r"\b\d{1,4}\s*\(\s*\d{1,4}\s*\)\s*[,;:]\s*(?:pp?\.?\s*)?\d{1,6}(?:\s*[-–—]\s*\d{1,6})?", re.I)
_VANCOUVER_SEQUENCE_RE = re.compile(rf"\b{_YEAR}\s*;\s*\d{{1,4}}(?:\(\d{{1,4}}\))?\s*:\s*\d{{1,6}}(?:\s*[-–—]\s*\d{{1,6}})?", re.I)
_DOI_RE = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|\bdoi\s*:\s*)10\.\d{4,9}/\S+", re.I)
_URL_RE = re.compile(r"https?://|\bwww\.", re.I)
_ACCESS_RE = re.compile(r"\b(?:retrieved|recuperad[oa]\s+de|consultad[oa]|acceso|acess[oa]|última\s+visita|ultima\s+visita)\b", re.I)
_PLACE_PUBLISHER_RE = re.compile(r"\b[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ .'-]{2,40}\s*:\s*[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ .&'-]{2,60}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def extract_reference_features(text: str, parsed: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return stable, interpretable morphology features for one reference."""
    raw = _norm(text)
    parsed = parsed or {}
    num = _NUM_PREFIX_RE.match(raw)
    numeric_value = None
    if num:
        numeric_value = next((int(x) for x in num.groups() if x), None)
    parse_style = str(parsed.get("parse_style") or "")
    return {
        "numbered_prefix": bool(num),
        "numeric_value": numeric_value,
        "bracketed_number": bool(_BRACKET_NUM_RE.match(raw)),
        "year_parenthesized_after_author": bool(_PAREN_YEAR_AFTER_AUTHOR_RE.search(raw)),
        "bare_year_after_author": bool(_BARE_YEAR_AFTER_AUTHOR_RE.search(raw)),
        "terminal_year": bool(_TERMINAL_YEAR_RE.search(raw)),
        "uppercase_surname": bool(_UPPERCASE_SURNAME_RE.match(raw)),
        "surname_then_initials": bool(_SURNAME_INITIALS_RE.match(raw)),
        "initials_then_surname": bool(_INITIALS_SURNAME_RE.match(raw)),
        "quoted_title": bool(_QUOTED_TITLE_RE.search(raw)),
        "volume_issue_pages": bool(_VOL_ISSUE_PAGES_RE.search(raw)),
        "year_volume_pages_sequence": bool(_VANCOUVER_SEQUENCE_RE.search(raw)),
        "has_doi": bool(_DOI_RE.search(raw)) or bool(parsed.get("doi")),
        "has_url": bool(_URL_RE.search(raw)),
        "has_access_date_cue": bool(_ACCESS_RE.search(raw)),
        "place_colon_publisher": bool(_PLACE_PUBLISHER_RE.search(raw)),
        "legacy_year_final_parser_route": "v11_legacy_year_final" in parse_style,
        "parsed_author_present": bool(parsed.get("author")),
        "parsed_year_present": bool(parsed.get("year")),
        "parsed_journal_present": bool(parsed.get("journal")),
        "parsed_publisher_present": bool(parsed.get("publisher")),
        "publication_type": parsed.get("publication_type") or "sin_clasificar",
    }
