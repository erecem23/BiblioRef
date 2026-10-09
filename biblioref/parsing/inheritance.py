# -*- coding: utf-8 -*-
"""Repeated-author markers resolved at document level.

A bibliography writes «------------- (2013). Clasificar en psiquiatría…» for
"same author as the entry above". The parser sees one reference at a time, so it
only records the marker (``author_marker_raw``) and leaves the author empty.
Once the references of a thesis are segmented and ordered, this module gives
each marked reference the author of the last explicit one in the same zone,
flags it as inherited and keeps the marker for provenance.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

#: List marker (bullet) that may precede the reference itself.
_LEADING_BULLET_RE = re.compile(r"^\s*[○●•◦▪·*]\s*")
#: Two or more hyphens/underscores/en dashes, or one or more em dashes, then the
#: date or the title. «- Pérez, J.» (a bullet) and «-Pérez» are not markers.
REPEATED_AUTHOR_RE = re.compile(r"^\s*(?P<marker>-{2,}|_{2,}|–{2,}|—+)\s*[.,;:]?\s*(?=[(\[\dA-ZÁÉÍÓÚÑ«“\"]|$)")

_AUTHOR_FIELDS = ("author", "authors")


def repeated_author_marker(text: Any) -> Optional[str]:
    body = _LEADING_BULLET_RE.sub("", str(text or ""), count=1)
    match = REPEATED_AUTHOR_RE.match(body)
    return match.group("marker") if match else None


def _text_of(ref: Dict[str, Any]) -> str:
    return str(ref.get("text") or ref.get("reference_text") or "")


def inherit_repeated_authors(refs: Sequence[Dict[str, Any]], parsed_keys=("parsed", "effective_parsed")) -> List[Dict[str, Any]]:
    """Return copies of ``refs`` (in their order) with inherited authors.

    Deleted references are skipped and never serve as the source. A marker at
    the start of a zone has nothing to inherit and keeps an empty author.
    """
    out: List[Dict[str, Any]] = []
    last: Optional[Dict[str, Any]] = None
    for ref in refs:
        row = dict(ref)
        out.append(row)
        if row.get("deleted"):
            continue
        parsed = row.get(parsed_keys[0]) or {}
        marker = parsed.get("author_marker_raw") or repeated_author_marker(_text_of(row))
        zone = row.get("zone_id")
        if marker:
            if last is not None and (zone is None or last["zone"] is None or zone == last["zone"]):
                for key in parsed_keys:
                    if isinstance(row.get(key), dict):
                        value = deepcopy(row[key])
                        value.update({
                            "author": last["author"],
                            "authors": last["authors"],
                            "author_marker_raw": marker,
                            "author_inherited": True,
                            "author_inherited_from": last["id"],
                        })
                        row[key] = value
            continue
        if str(parsed.get("author") or "").strip():
            last = {"id": row.get("id"), "zone": zone,
                    "author": parsed.get("author"), "authors": parsed.get("authors") or parsed.get("author")}
    return out


def inherited_author_ids(refs: Sequence[Dict[str, Any]], parsed_of) -> Dict[str, str]:
    """Map ref id -> inherited author, reading parsed data through ``parsed_of``."""
    rows = [dict(r, parsed=parsed_of(r)) for r in refs]
    return {
        row.get("id"): row["parsed"].get("author")
        for row in inherit_repeated_authors(rows, parsed_keys=("parsed",))
        if (row.get("parsed") or {}).get("author_inherited")
    }


__all__ = ["REPEATED_AUTHOR_RE", "inherit_repeated_authors", "inherited_author_ids", "repeated_author_marker"]
