# -*- coding: utf-8 -*-
"""Live reference parser: base reading, then one document-type decision.

Same output as :mod:`biblioref.parsing.v12_8` (hence the same version); the
three stacked type overlays are replaced by :func:`biblioref.parsing.doctype.decide_type`.

1. base reading: v0.12.5 plus the date-block normalisation (v0.12.6). Fields
   and a first type, decided together with the journal/publisher split;
2. repeated-author marker («-------------») → ``author_marker_raw``;
3. access medium: ``has_url``;
4. document type: :data:`biblioref.parsing.doctype.TYPE_PASSES`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from . import v12_5 as _v125
from . import v12_6 as _v126
from . import v12_7 as _v127
from . import v12_8 as _v128
from .doctype import decide_type

PARSER_VERSION = _v128.PARSER_VERSION
PARSER_SCHEMA_VERSION = _v128.PARSER_SCHEMA_VERSION
PARSER_STATUS = _v128.PARSER_STATUS
_STYLE_STAMPS = (("v126", "v126_type_evidence"), ("v127", "v127_repeated_author_and_type"),
                 ("v128", "v128_legal_chapter_report_web"))


def base_reading(text: str) -> Dict[str, Any]:
    """Fields and first type: v0.12.5 read on the text with a normalised date block."""
    out = _v125.parse_reference(text)
    normalised, how = _v126.normalise_date_block(text)
    if how:
        alt = _v125.parse_reference(normalised)
        if how == "no_date":
            _v126._complete_undated(alt, normalised)
        out = _v126._merge_normalised(out, alt, how, text)
    return out


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _v127._clean(texto)
    out = base_reading(text)
    _v127._mark_repeated_author(text, out)
    out["has_url"] = bool(_v128._URL_RE.search(text))
    decide_type(text, out)
    for mark, stamp in _STYLE_STAMPS:
        style = str(out.get("parse_style") or "")
        if mark not in style:
            out["parse_style"] = "+".join(x for x in (style, stamp) if x)
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
    return _v128.flatten_parsed(parsed, prefix=prefix)
