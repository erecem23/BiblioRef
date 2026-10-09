# -*- coding: utf-8 -*-
"""Possible problems of a thesis, counted from stored data so every screen can show them.

Two groups: extraction (a reference may be missing, merged or cut at a page
boundary) and reference data (type, author or year not read). A person's
decision in ``audit_decisions`` removes an item from the count; the same rules
are mirrored in static/review-problems.js, which lists the items one by one.
"""
from __future__ import annotations

from typing import Any, Dict

from biblioref.parsing.inheritance import inherited_author_ids

KINDS = ("missing", "merged", "boundaries", "type", "author", "year")
_MISSING_CLOSED = {"ignore", "resolved", "accepted_missing"}
_DISMISSED = {"ignore", "resolved"}
_UNCLASSIFIED = {"", "sin_clasificar"}
_CACHE: Dict[str, tuple] = {}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def merged_check_id(item: Dict[str, Any]) -> str:
    return f"merged_{item.get('page') or 0}_{item.get('record_index') or 0}"


def data_check_id(kind: str, ref_id: str) -> str:
    return f"data_{kind}_{ref_id}"


def _effective_parsed(ref: Dict[str, Any]) -> Dict[str, Any]:
    parsed = dict(ref.get("parsed") or {})
    parsed.update((ref.get("parsed_review") or {}).get("overrides") or {})
    return parsed


def problem_counts(doc: Dict[str, Any]) -> Dict[str, int]:
    coverage_now = (doc.get("analysis") or {}).get("coverage") or {}
    key = (doc.get("updated_at"), doc.get("n_references"), len(doc.get("audit_decisions") or {}),
           len(coverage_now.get("merged_suspects") or []), len(coverage_now.get("possible_missing") or []))
    cached = _CACHE.get(doc.get("id"))
    if cached and cached[0] == key:
        return dict(cached[1])
    decisions = doc.get("audit_decisions") or {}
    decision = lambda check_id: (decisions.get(check_id) or {}).get("decision")
    coverage = (doc.get("analysis") or {}).get("coverage") or {}
    counts = {
        "missing": sum(1 for x in coverage.get("possible_missing") or [] if decision(x.get("id")) not in _MISSING_CLOSED),
        "merged": sum(1 for x in coverage.get("merged_suspects") or [] if decision(merged_check_id(x)) not in _DISMISSED),
        "boundaries": sum(1 for x in coverage.get("page_boundaries") or []
                          if (decision(x.get("id")) or x.get("verdict")) in {"review", "pending"}),
        "type": 0, "author": 0, "year": 0,
    }
    visible = [ref for ref in doc.get("references") or [] if not ref.get("deleted")]
    # «------------- (2013)» has the author of the entry above; it is not missing.
    inherited = inherited_author_ids(visible, _effective_parsed)
    for ref in visible:
        parsed = _effective_parsed(ref)
        checks = {
            "type": _text(parsed.get("publication_type")) in _UNCLASSIFIED,
            "author": not _text(parsed.get("author")) and not inherited.get(ref.get("id")),
            "year": not _text(parsed.get("year")),
        }
        for kind, open_ in checks.items():
            if open_ and decision(data_check_id(kind, ref.get("id"))) not in _DISMISSED:
                counts[kind] += 1
    _CACHE[doc.get("id")] = (key, counts)
    return dict(counts)


__all__ = ["KINDS", "data_check_id", "merged_check_id", "problem_counts"]
