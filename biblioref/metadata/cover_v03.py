# -*- coding: utf-8 -*-
from __future__ import annotations

"""Front-matter metadata v0.3.

Extends the conservative cover-metadata v0.2 detector with explicit thesis
advisor roles and a generic institution field. Bibliography extraction and
reference parsing are intentionally untouched.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import cover as _base

COVER_METADATA_VERSION = "cover-metadata-v0.3"

_DIRECTOR_RE = re.compile(
    r"^(?:director(?:a)?(?:\s+de\s+tesis)?|thesis\s+director|supervisor|advisor|adviser|"
    r"orientador(?:a)?|tutor(?:a)?|profesor(?:a)?\s+gu[ií]a)\b\s*[:.\-–—]?\s*",
    re.I,
)
_CODIRECTOR_RE = re.compile(
    r"^(?:co-?director(?:a)?(?:\s+de\s+tesis)?|co-?supervisor|co-?advisor|co-?adviser|"
    r"co-?orientador(?:a)?|co-?tutor(?:a)?|profesor(?:a)?\s+co-?gu[ií]a)\b\s*[:.\-–—]?\s*",
    re.I,
)
_ADMIN_STOP_RE = re.compile(
    r"^(?:tribunal(?:\s+(?:evaluador|examinador|de\s+tesis))?|jurado(?:\s+(?:evaluador|de\s+tesis))?|"
    r"comit[eé](?:\s+(?:evaluador|de\s+tesis))?|comisi[oó]n\s+evaluadora|evaluation\s+committee|"
    r"examining\s+committee|examination\s+committee|thesis\s+committee|jury|examiners?|"
    r"banca(?:\s+(?:examinadora|de\s+defesa))?)\b",
    re.I,
)
_GENERIC_INSTITUTION_RE = re.compile(
    r"^(?:universidad|university|universidade|facultad|faculty|faculdade|departamento|department|"
    r"instituto|institute|institut|centro|centre|center|escuela|school|escola)\b",
    re.I,
)


def _norm(value: Any) -> str:
    return _base._norm(value)


def _inline_or_following_person(
    lines: List[Dict[str, Any]], index: int, label_re: re.Pattern[str]
) -> Tuple[Optional[str], float]:
    raw = _norm(lines[index]["text"])
    match = label_re.match(raw)
    if not match:
        return None, 0.0

    inline = raw[match.end():].strip(" .:;,-–—")
    if inline and _base._person_like(inline):
        return _base._clean_person(inline), 0.99

    anchor = lines[index]
    for nxt in lines[index + 1:index + 5]:
        text = _norm(nxt["text"])
        if not text:
            continue
        if _DIRECTOR_RE.match(text) or _CODIRECTOR_RE.match(text) or _ADMIN_STOP_RE.match(text):
            break
        if _base._AUTHOR_LABEL_RE.match(text) or _base._AFFILIATION_RE.match(text):
            break
        if _base._DEGREE_RE.match(text) or _base._PROGRAM_RE.match(text):
            break
        # Role labels and their value are normally physically adjacent. This
        # avoids harvesting an unrelated personal name farther down the page.
        gap = float(nxt["y0"]) - float(anchor["y1"])
        if gap > max(42.0, 3.0 * max(float(anchor.get("size") or 0), float(nxt.get("size") or 0), 1.0)):
            break
        if _base._person_like(text):
            return _base._clean_person(text), 0.96
    return None, 0.0


def _detect_advisors(lines: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], float, float]:
    director = codirector = None
    director_conf = codirector_conf = 0.0

    # Check co-director first because the broader director expression must never
    # absorb a co-director label.
    for i, ln in enumerate(lines):
        text = _norm(ln["text"])
        if codirector is None and _CODIRECTOR_RE.match(text):
            codirector, codirector_conf = _inline_or_following_person(lines, i, _CODIRECTOR_RE)
        if director is None and _DIRECTOR_RE.match(text) and not _CODIRECTOR_RE.match(text):
            director, director_conf = _inline_or_following_person(lines, i, _DIRECTOR_RE)
        if director and codirector:
            break
    return director, codirector, director_conf, codirector_conf


def _detect_institution(lines: List[Dict[str, Any]], university: Optional[str], faculty: Optional[str]) -> Tuple[Optional[str], float]:
    if university:
        return university, 0.99
    for ln in lines:
        text = _norm(ln["text"])
        if _GENERIC_INSTITUTION_RE.match(text):
            return _base._smart_case(text), 0.92
    if faculty:
        return faculty, 0.82
    return None, 0.0


def detect_cover_metadata(path: str | Path, filename: str | None = None) -> Dict[str, Any]:
    path = Path(path)
    out = _base.detect_cover_metadata(path, filename)
    out["version"] = COVER_METADATA_VERSION
    if _base.fitz is None or not path.exists():
        return out

    try:
        with _base.fitz.open(path) as pdf:
            pages = [_base._page_lines(pdf[pno], pno) for pno in range(min(3, len(pdf)))]
    except Exception:
        return out

    # Advisor and institution data are usually on the cover or immediate
    # approval/front-matter pages, so scan up to three pages but prefer the first
    # explicit anchored role found.
    director = codirector = None
    director_conf = codirector_conf = 0.0
    for lines in pages:
        d, c, dc, cc = _detect_advisors(lines)
        if director is None and d:
            director, director_conf = d, dc
        if codirector is None and c:
            codirector, codirector_conf = c, cc
        if director and codirector:
            break

    first = pages[0] if pages else []
    university = (out.get("metadata") or {}).get("university")
    faculty = (out.get("metadata") or {}).get("faculty")
    institution, institution_conf = _detect_institution(first, university, faculty)

    additions = (
        ("director", director, director_conf, "cover_role"),
        ("codirector", codirector, codirector_conf, "cover_role"),
        ("institution", institution, institution_conf, "cover_affiliation"),
    )
    for key, value, confidence, source in additions:
        if not value:
            continue
        out.setdefault("metadata", {})[key] = value
        out.setdefault("confidence", {})[key] = round(float(confidence), 2)
        out.setdefault("sources", {})[key] = source

    return out


__all__ = ["COVER_METADATA_VERSION", "detect_cover_metadata"]
