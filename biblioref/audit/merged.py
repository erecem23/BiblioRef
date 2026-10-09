# -*- coding: utf-8 -*-
"""Records that hold two or more references glued together.

Two signatures count as two references. The original rule («Surname … (year)» within
80 characters) missed long author lists and years with a letter («Navarro-Carrillo, G.,
Méndez, L., …, Cueto, R. M. (2021)», «(2008a)»); the second rule accepts both.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

MERGED_SCAN_REVISION = "merged-scan-v2"

_UP = "A-ZÁÉÍÓÚÜÑ"
_SHORT_SIGNATURE = re.compile(
    r"(?:^|[.;)]\s+)([A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+[^\n]{0,80}?"
    r"(?:\((?:18|19|20)\d{2}\)|[,;]\s*(?:18|19|20)\d{2}\s*[,.:]))",
    re.M,
)
_AUTHOR_YEAR_SIGNATURE = re.compile(
    rf"(?:^|(?<=[.)\]])\s+|(?<=\d)\s+|(?<=\S/)\s+)"
    rf"([{_UP}][\w'’\-]+(?:[\s\-][{_UP}][\w'’\-]+){{0,2}},\s(?:[{_UP}]\.\s?-?){{1,3}}"
    rf"[^()]{{0,700}}?\((?:18|19|20)\d{{2}}[a-z]?(?:,\s*[^)]{{0,20}})?\))"
)


def looks_merged(text: str) -> bool:
    text = " ".join(str(text or "").split())
    return len(_SHORT_SIGNATURE.findall(text)) >= 2 or len(_AUTHOR_YEAR_SIGNATURE.findall(text)) >= 2


def backfill_merged_suspects(doc: Dict[str, Any]) -> bool:
    """Add suspects the stored analysis missed; returns whether the document changed."""
    if doc.get("merged_scan_revision") == MERGED_SCAN_REVISION:
        return False
    coverage = (doc.get("analysis") or {}).get("coverage")
    doc["merged_scan_revision"] = MERGED_SCAN_REVISION
    if not isinstance(coverage, dict):
        return True
    suspects: List[Dict[str, Any]] = list(coverage.get("merged_suspects") or [])
    known = [" ".join(str(s.get("text") or "").split())[:60] for s in suspects]
    added = 0
    for ref in doc.get("references") or []:
        if ref.get("deleted"):
            continue
        text = " ".join(str(ref.get("text") or "").split())
        if not text or not looks_merged(text):
            continue
        head = text[:60]
        if any(k and (k.startswith(head[:40]) or head.startswith(k[:40])) for k in known):
            continue
        suspects.append({
            "record_index": f"r{ref.get('order')}",
            "page": ref.get("start_page"),
            "reason": "multiple_reference_signatures_inside_record",
            "text": text[:700],
            "detector": MERGED_SCAN_REVISION,
        })
        known.append(head)
        added += 1
    coverage["merged_suspects"] = suspects
    if isinstance(coverage.get("summary"), dict):
        coverage["summary"]["n_merged_suspects"] = len(suspects)
    return True


__all__ = ["MERGED_SCAN_REVISION", "backfill_merged_suspects", "looks_merged"]
