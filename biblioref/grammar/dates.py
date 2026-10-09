"""Adaptive-only representations of absent/unknown bibliographic dates."""
from __future__ import annotations
import re

UNDATED_TOKEN = r"(?:sin\s+fecha|s\.?\s*f\.?|no\s+date|n\.?\s*d\.?|undated|sem\s+data|s\.?\s*d\.?)"
UNDATED_RX = re.compile(rf"\b{UNDATED_TOKEN}\b", re.I)
UNDATED_PAREN_RX = re.compile(rf"\(\s*{UNDATED_TOKEN}\s*\)", re.I)


def undated_author_start(text: str) -> bool:
    raw = str(text).strip()[:320]
    if not UNDATED_RX.search(raw):
        return False
    # Person-like author before a comma, or a short institutional lead before
    # the undated token. This is shadow-only and does not alter the stable route.
    if re.match(r"^[^,\n]{1,90},\s*(?:[A-ZÁÉÍÓÚÑ](?:\.|\b)|[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)", raw):
        return True
    if re.match(rf"^[A-ZÁÉÍÓÚÑ][^.!?]{{1,120}}?\.?\s*\(\s*{UNDATED_TOKEN}\s*\)", raw, re.I):
        return True
    return False


__all__ = ["UNDATED_RX", "UNDATED_PAREN_RX", "undated_author_start"]
