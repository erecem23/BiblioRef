# -*- coding: utf-8 -*-
"""Unifying group labels that name the same thing.

"Universidad Nacional de La Plata" and "Universidad de La Plata" are one
institution written two ways, and counting them apart splits a group in half.
Merging them automatically would be worse: two labels that look alike are
sometimes two different places, and no similarity score knows which.

So this module only *proposes*. The decision is the user's, it is stored in
``project.json`` beside the rest of their manual work, and it stays visible and
reversible — the original label is never overwritten in the source.
"""
from __future__ import annotations

import sqlite3
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, Optional

from biblioref.resolver.normalize import clean_text, normalize_match_text

ALIAS_VERSION = "group-aliases-v0.1"

ALIASABLE_FIELDS = ("university", "program", "faculty", "director")

# Above this, two labels are similar enough to be worth asking about. It is a
# threshold for a question, not for an action.
SUGGEST_MIN_RATIO = 0.80

# Words that carry no distinguishing weight between institutions, so their
# presence or absence should not keep two labels apart.
_FILLER = frozenset({
    "de", "del", "la", "las", "los", "el", "y", "e", "en",
    "universidad", "universidade", "university", "universitat", "universidad",
    "nacional", "facultad", "faculty", "doctorado", "programa",
})


def canonical_form(value: Any) -> str:
    """Comparison form: normalized, with filler words removed."""
    words = [w for w in normalize_match_text(value).split() if w not in _FILLER]
    return " ".join(words)


def similarity(a: Any, b: Any) -> float:
    left, right = canonical_form(a), canonical_form(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def aliases_for(store: Mapping[str, Any], project_id: Optional[str], field: str) -> Dict[str, str]:
    """The alias map a project has confirmed for one grouping field."""
    if not project_id:
        return {}
    projects = store.get("projects") or {}
    project = projects.get(project_id) if isinstance(projects, Mapping) else None
    if not isinstance(project, Mapping):
        return {}
    groups = project.get("group_aliases") or {}
    table = groups.get(field) if isinstance(groups, Mapping) else None
    if not isinstance(table, Mapping):
        return {}
    return {str(k): str(v) for k, v in table.items() if clean_text(k) and clean_text(v)}


def apply_alias(value: Any, aliases: Mapping[str, str]) -> Optional[str]:
    """Resolve one label through the confirmed aliases.

    Chains are followed so that a variant pointing at another variant still
    lands on the canonical label, and a cycle stops rather than hanging.
    """
    current = clean_text(value)
    if not current or not aliases:
        return current or None
    seen = set()
    while current in aliases and current not in seen:
        seen.add(current)
        current = clean_text(aliases[current])
    return current or None


def suggest_aliases(conn: sqlite3.Connection, by: str = "university",
                    doc_ids: Optional[List[str]] = None,
                    min_ratio: float = SUGGEST_MIN_RATIO,
                    known: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    """Pairs of labels similar enough to ask whether they are the same.

    The larger group is proposed as the canonical one, because that is usually
    the fuller spelling, but the suggestion carries both so the user can pick.
    """
    if by not in ALIASABLE_FIELDS:
        return []

    where, params = "", []
    if doc_ids:
        where = " AND doc_id IN (%s)" % ",".join("?" for _ in doc_ids)
        params = list(doc_ids)

    rows = [
        (r["g"], r["n"])
        for r in conn.execute(
            f"""SELECT {by} AS g, COUNT(*) AS n FROM document
                WHERE {by} IS NOT NULL AND {by} <> ''{where}
                GROUP BY {by} ORDER BY n DESC""",
            params,
        )
    ]
    known = dict(known or {})
    out: List[Dict[str, Any]] = []
    for i, (a, a_n) in enumerate(rows):
        for b, b_n in rows[i + 1:]:
            if a in known or b in known:
                continue
            ratio = similarity(a, b)
            if ratio < min_ratio:
                continue
            canonical, variant = (a, b) if a_n >= b_n else (b, a)
            out.append({
                "a": a, "a_theses": a_n,
                "b": b, "b_theses": b_n,
                "ratio": round(ratio, 3),
                "suggested_canonical": canonical,
                "suggested_variant": variant,
                "identical_once_normalised": canonical_form(a) == canonical_form(b),
            })
    out.sort(key=lambda x: (-x["ratio"], -max(x["a_theses"], x["b_theses"])))
    return out
