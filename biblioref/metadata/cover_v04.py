# -*- coding: utf-8 -*-
from __future__ import annotations

"""Front-matter metadata v0.4.

Keeps the conservative v0.3 detector, but fixes two common real-thesis cases:
metadata labels written inline (``Doctorando: Nombre`` / ``Directora: Nombre``)
and institutional/author data placed on a later title/front-matter page instead
of page 1. Bibliography extraction and reference parsing remain untouched.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import cover as _base
from . import cover_v03 as _v03

COVER_METADATA_VERSION = "cover-metadata-v0.4"
_MAX_FRONTMATTER_PAGES = 8

_AUTHOR_ROLE_RE = re.compile(
    r"^(?:autor(?:a|es)?|tesista|doctorand[oa]|doctorante|candidat[oa]|candidate|"
    r"presentad[oa]\s+por|presented\s+by|submitted\s+by)\b\s*[:.\-–—]?\s*",
    re.I,
)
_DIRECTOR_RE = re.compile(
    r"^(?:director(?:a)?(?:\s+(?:de\s+tesis|del\s+trabajo|de\s+trabajo))?|"
    r"thesis\s+director|supervisor|advisor|adviser|orientador(?:a)?|tutor(?:a)?|"
    r"profesor(?:a)?\s+gu[ií]a)\b\s*[:.\-–—]?\s*",
    re.I,
)
_CODIRECTOR_RE = re.compile(
    r"^(?:co-?director(?:a)?(?:\s+(?:de\s+tesis|del\s+trabajo|de\s+trabajo))?|"
    r"co-?supervisor|co-?advisor|co-?adviser|co-?orientador(?:a)?|co-?tutor(?:a)?|"
    r"profesor(?:a)?\s+co-?gu[ií]a)\b\s*[:.\-–—]?\s*",
    re.I,
)
_STOP_RE = re.compile(
    r"^(?:tribunal|jurado|comit[eé]|comisi[oó]n\s+evaluadora|evaluation\s+committee|"
    r"examining\s+committee|examination\s+committee|thesis\s+committee|jury|"
    r"examiners?|banca\s+(?:examinadora|de\s+defesa))\b",
    re.I,
)
_UNIVERSITY_ANY_RE = re.compile(
    r"\b(?:(?:pontificia|nacional|estatal|aut[oó]noma)\s+)?(?:universidad|university|universidade)\b[^|]{0,180}",
    re.I,
)
_FACULTY_ANY_RE = re.compile(
    r"\b(?:facultad|faculty|faculdade|escuela|school|escola)\b[^|]{0,160}",
    re.I,
)
_INSTITUTION_ANY_RE = re.compile(
    r"\b(?:instituto|institute|institut|centro|centre|center|departamento|department)\b[^|]{0,180}",
    re.I,
)


def _norm(value: Any) -> str:
    return _base._norm(value)


def _line_value_after_role(text: str, role_re: re.Pattern[str]) -> str:
    raw = _norm(text)
    match = role_re.match(raw)
    if not match:
        return ""
    value = raw[match.end():].strip(" .:;,-–—")
    if value and _base._person_like(value):
        return _base._clean_person(value)
    return ""


def _following_person(
    lines: List[Dict[str, Any]], index: int, role_re: re.Pattern[str]
) -> Tuple[Optional[str], float]:
    inline = _line_value_after_role(lines[index]["text"], role_re)
    if inline:
        return inline, 0.99

    anchor = lines[index]
    for nxt in lines[index + 1:index + 5]:
        text = _norm(nxt["text"])
        if not text:
            continue
        if (_AUTHOR_ROLE_RE.match(text) or _DIRECTOR_RE.match(text) or _CODIRECTOR_RE.match(text)
                or _STOP_RE.match(text) or _base._AFFILIATION_RE.match(text)
                or _base._DEGREE_RE.match(text) or _base._PROGRAM_RE.match(text)):
            break
        gap = float(nxt["y0"]) - float(anchor["y1"])
        if gap > max(48.0, 3.4 * max(float(anchor.get("size") or 0), float(nxt.get("size") or 0), 1.0)):
            break
        if _base._person_like(text):
            return _base._clean_person(text), 0.96
    return None, 0.0


def _detect_role_people(pages: List[List[Dict[str, Any]]]) -> Tuple[Optional[str], Optional[str], Optional[str], float, float, float]:
    author = director = codirector = None
    author_conf = director_conf = codirector_conf = 0.0
    for lines in pages:
        for i, ln in enumerate(lines):
            text = _norm(ln["text"])
            if codirector is None and _CODIRECTOR_RE.match(text):
                codirector, codirector_conf = _following_person(lines, i, _CODIRECTOR_RE)
            if director is None and _DIRECTOR_RE.match(text) and not _CODIRECTOR_RE.match(text):
                director, director_conf = _following_person(lines, i, _DIRECTOR_RE)
            if author is None and _AUTHOR_ROLE_RE.match(text):
                author, author_conf = _following_person(lines, i, _AUTHOR_ROLE_RE)
        if author and director and codirector:
            break
    return author, director, codirector, author_conf, director_conf, codirector_conf


def _clean_affiliation_fragment(fragment: str) -> str:
    text = _norm(fragment)
    text = re.split(r"\s{2,}|[;|]", text, maxsplit=1)[0]
    text = text.strip(" .:;,-–—")
    return _base._smart_case(text)


def _detect_affiliations(pages: List[List[Dict[str, Any]]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    university = faculty = institution = None
    for lines in pages:
        for ln in lines:
            text = _norm(ln["text"])
            if not text:
                continue
            if university is None:
                match = _UNIVERSITY_ANY_RE.search(text)
                if match:
                    university = _clean_affiliation_fragment(match.group(0))
            if faculty is None:
                match = _FACULTY_ANY_RE.search(text)
                if match:
                    faculty = _clean_affiliation_fragment(match.group(0))
            if institution is None:
                match = _INSTITUTION_ANY_RE.search(text)
                if match:
                    institution = _clean_affiliation_fragment(match.group(0))
        if university and faculty:
            break
    if university:
        institution = university
    elif not institution and faculty:
        institution = faculty
    return university, faculty, institution


def _best_year(pages: List[List[Dict[str, Any]]]) -> Tuple[Optional[str], float]:
    best_year = None
    best_conf = 0.0
    for page_index, lines in enumerate(pages):
        year, confidence, _ = _base._detect_year(lines)
        if not year:
            continue
        adjusted = float(confidence) - min(page_index, 5) * 0.03
        if adjusted > best_conf:
            best_year, best_conf = year, adjusted
    return best_year, max(0.0, min(0.99, best_conf))


def _first_program(pages: List[List[Dict[str, Any]]]) -> Tuple[Optional[str], float]:
    for page_index, lines in enumerate(pages):
        value, confidence = _base._detect_program(lines)
        if value:
            return value, max(0.75, float(confidence) - page_index * 0.03)
    return None, 0.0


def _first_degree_level(pages: List[List[Dict[str, Any]]]) -> Optional[str]:
    for lines in pages:
        value = _base._degree_level(lines)
        if value:
            return value
    return None


def _pdf_metadata_author(pdf) -> Optional[str]:
    value = _norm((pdf.metadata or {}).get("author") or "")
    if value and _base._person_like(value):
        return _base._clean_person(value)
    return None


def detect_cover_metadata(path: str | Path, filename: str | None = None) -> Dict[str, Any]:
    path = Path(path)
    out = _v03.detect_cover_metadata(path, filename)
    out["version"] = COVER_METADATA_VERSION
    if _base.fitz is None or not path.exists():
        return out

    try:
        with _base.fitz.open(path) as pdf:
            pages = [
                _base._page_lines(pdf[pno], pno)
                for pno in range(min(_MAX_FRONTMATTER_PAGES, len(pdf)))
            ]
            pdf_author = _pdf_metadata_author(pdf)
    except Exception:
        return out

    meta = out.setdefault("metadata", {})
    confidence = out.setdefault("confidence", {})
    sources = out.setdefault("sources", {})

    author, director, codirector, author_conf, director_conf, codirector_conf = _detect_role_people(pages)
    university, faculty, institution = _detect_affiliations(pages)
    year, year_conf = _best_year(pages)
    program, program_conf = _first_program(pages)
    degree_level = _first_degree_level(pages)

    # Prefer explicit role labels; PDF metadata is only a fallback for author.
    if author:
        meta["author"] = author
        confidence["author"] = round(author_conf, 2)
        sources["author"] = "frontmatter_role"
    elif not meta.get("author") and pdf_author:
        meta["author"] = pdf_author
        confidence["author"] = 0.78
        sources["author"] = "pdf_metadata"

    for key, value, conf, source in (
        ("director", director, director_conf, "frontmatter_role"),
        ("codirector", codirector, codirector_conf, "frontmatter_role"),
        ("university", university, 0.96 if university else 0.0, "frontmatter_affiliation"),
        ("faculty", faculty, 0.94 if faculty else 0.0, "frontmatter_affiliation"),
        ("institution", institution, 0.94 if institution else 0.0, "frontmatter_affiliation"),
        ("year", year, year_conf, "frontmatter_date"),
        ("program", program, program_conf, "frontmatter_degree"),
        ("degree_level", degree_level, 0.92 if degree_level else 0.0, "frontmatter_degree"),
    ):
        if not value:
            continue
        # The broader scan may replace an earlier automatic suggestion, but it
        # never touches a user-edited field here; integration owns that policy.
        meta[key] = value
        confidence[key] = round(float(conf), 2)
        sources[key] = source

    return out


__all__ = ["COVER_METADATA_VERSION", "detect_cover_metadata"]
