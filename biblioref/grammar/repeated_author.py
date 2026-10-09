"""Repeated-author marker recognition with raw-form preservation."""

from __future__ import annotations

import re
from typing import Dict

# Three or more underscores/dash-like glyphs.  A single narrative dash/bullet
# is intentionally excluded.
REPEATED_AUTHOR_MARKER_RX = re.compile(
    r"^\s*(?P<marker>(?:_{3,}|[-–—]{3,}|[\uF000-\uF8FF]{3,}))\s*(?:,|\.)?\s*"
)


def detect_repeated_author_marker(text: str) -> Dict:
    raw = str(text).strip()
    match = REPEATED_AUTHOR_MARKER_RX.match(raw)
    if not match:
        return {
            "is_repeated_author_marker": False,
            "marker_raw": None,
            "marker_family": None,
        }
    marker = match.group("marker")
    if marker.startswith("_"):
        family = "underscore_like"
    elif any(ch in marker for ch in "–—"):
        family = "dash_like"
    elif marker.startswith("-"):
        family = "hyphen_like"
    else:
        family = "private_use_like"
    return {
        "is_repeated_author_marker": True,
        "marker_raw": marker,
        "marker_family": family,
    }


__all__ = ["REPEATED_AUTHOR_MARKER_RX", "detect_repeated_author_marker"]
