"""Auditable author-inheritance candidates.

The functions here *represent* inheritance; they never rewrite raw reference
text and never create validated records.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from biblioref.grammar.repeated_author import detect_repeated_author_marker

DATE_ONLY_START_RX = re.compile(
    r"^\s*\(\s*(?P<year>(?:18|19|20)\d{2}[a-z]?)(?:\s*\[[^\]]+\])?\s*\)"
)


def infer_author_inheritance(
    current_text: str,
    previous_author_key: Optional[str],
    previous_record_index: Optional[int] = None,
    bibliographic_context: bool = True,
) -> Dict:
    """Return an inheritance candidate without mutating source text."""
    raw = str(current_text).strip()
    repeated = detect_repeated_author_marker(raw)
    date_only = DATE_ONLY_START_RX.match(raw)

    if not bibliographic_context or not previous_author_key:
        return {
            "inheritance_type": None,
            "inheritance_candidate": False,
            "resolved_author": None,
            "source_record_index": previous_record_index,
            "evidence": [],
        }

    if repeated["is_repeated_author_marker"]:
        return {
            "inheritance_type": "repeated_author_marker",
            "inheritance_candidate": True,
            "resolved_author": previous_author_key,
            "source_record_index": previous_record_index,
            "marker_raw": repeated["marker_raw"],
            "marker_family": repeated["marker_family"],
            "evidence": ["repeated_author_marker", "adjacent_previous_record"],
        }

    if date_only:
        return {
            "inheritance_type": "date_only_after_explicit_author",
            "inheritance_candidate": True,
            "resolved_author": previous_author_key,
            "source_record_index": previous_record_index,
            "year_token": date_only.group("year"),
            "evidence": ["year_only_start", "adjacent_previous_record"],
        }

    return {
        "inheritance_type": None,
        "inheritance_candidate": False,
        "resolved_author": None,
        "source_record_index": previous_record_index,
        "evidence": [],
    }


__all__ = ["DATE_ONLY_START_RX", "infer_author_inheritance"]
