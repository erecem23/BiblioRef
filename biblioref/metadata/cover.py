# -*- coding: utf-8 -*-
"""Conservative metadata suggestions from thesis cover/front-matter pages.

v0.2 prioritizes explicit cover anchors and keeps every suggestion editable.
It is document-metadata only: reference extraction/parsing are untouched.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from biblioref.ingestion.backend_context import pymupdf as fitz

COVER_METADATA_VERSION = "cover-metadata-v0.2"

_MONTH_RE = re.compile(
    r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|"
    r"octubre|noviembre|diciembre|january|february|march|april|may|june|july|"
    r"august|september|october|november|december)\b", re.I)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DOC_TYPE_RE = re.compile(
    r"^(?:tesis(?:\s+de)?\s+(?:maestr[ií]a|doctorado|doctoral)|tesis\s+doctoral|"
    r"doctoral\s+(?:thesis|dissertation)|master(?:'s)?\s+thesis|dissertation|"
    r"trabajo\s+final(?:\s+de\s+(?:maestr[ií]a|doctorado))?)\b", re.I)
_DEGREE_RE = re.compile(
    r"^(?:para\s+(?:obtener|optar|acceder)(?:\s+a)?(?:\s+el)?\s+t[ií]tulo\b|"
    r"para\s+(?:obtener|optar|acceder)\b|to\s+(?:obtain|qualify|fulfil|fulfill)\b|"
    r"(?:t[ií]tulo|grado)\s+de\b|requisito\b)", re.I)
_PROGRAM_RE = re.compile(
    r"^(?:mag[ií]ster\s+en|maestr[ií]a\s+en|master(?:'s)?\s+(?:in|of)|"
    r"doctorado\s+en|doctoral\s+program(?:me)?\s+(?:in|of)|ph\.?d\.?\s+(?:in|of))\b", re.I)
_AUTHOR_LABEL_RE = re.compile(
    r"^(?:presentan?|presentad[oa]\s+por|presented\s+by|autor(?:a|es)?|author|tesista)\s*:?$", re.I)
_ADVISOR_RE = re.compile(
    r"^(?:director(?:a)?|directores|supervisor|advisor|adviser|co-?director(?:a)?|"
    r"tutor(?:a)?|orientador(?:a)?|profesor(?:a|as|es)?\s+(?:gu[ií]as?|co-?gu[ií]as?))\b", re.I)
_UNIVERSITY_RE = re.compile(r"^(?:(?:pontificia|nacional)\s+)?universidad\b|^university\b", re.I)
_FACULTY_RE = re.compile(r"^(?:facultad|faculty|escuela|school)\b", re.I)
_AFFILIATION_RE = re.compile(
    r"^(?:universidad|university|pontificia\s+universidad|facultad|faculty|departamento|department|"
    r"escuela|school|instituto|institute|centro|centre|center)\b", re.I)
_LOCATION_RE = re.compile(
    r"^(?:buenos\s+aires|santiago|c[oó]rdoba|mendoza|la\s+plata|mar\s+del\s+plata|"
    r"san\s+luis|rosario|tucum[aá]n)(?:\s*,|\.|$)", re.I)
_PERSON_PREFIX_RE = re.compile(
    r"^(?:(?:lic|licda|mg|mgtr|msc|m\.?sc|dr|dra|prof|profesor|profesora)\.?\s+)+", re.I)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _smart_case(value: str) -> str:
    text = _norm(value).strip(" .:;,-")
    if not text:
        return ""
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.85:
        small = {"de", "del", "la", "las", "los", "y", "e", "en", "of", "the", "and"}
        out = []
        for i, word in enumerate(text.lower().split()):
            if i > 0 and word in small:
                out.append(word)
            else:
                out.append(word[:1].upper() + word[1:])
        return " ".join(out)
    return text


def _join_spans(spans: List[dict[str, Any]]) -> str:
    parts = [sp for sp in spans if str(sp.get("text") or "").strip()]
    if not parts:
        return ""
    parts.sort(key=lambda sp: float((sp.get("bbox") or (0, 0, 0, 0))[0]))
    out = str(parts[0].get("text") or "").strip()
    prev = parts[0]
    for cur in parts[1:]:
        rp, rc = str(prev.get("text") or ""), str(cur.get("text") or "")
        pb, cb = prev.get("bbox") or (0, 0, 0, 0), cur.get("bbox") or (0, 0, 0, 0)
        gap = float(cb[0]) - float(pb[2])
        size = max(1.0, (float(prev.get("size") or 0) + float(cur.get("size") or 0)) / 2.0)
        sep = " " if rp.endswith((" ", "\t")) or rc.startswith((" ", "\t")) or gap > max(1.15, size * 0.19) else ""
        out = out.rstrip() + sep + rc.lstrip()
        prev = cur
    return _norm(out)


def _page_lines(page, pno: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    height, width = float(page.rect.height or 1), float(page.rect.width or 1)
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = _join_spans(spans)
            if not text:
                continue
            bbox = line.get("bbox") or (0, 0, 0, 0)
            out.append({
                "page": pno,
                "text": text,
                "size": max((float(sp.get("size") or 0) for sp in spans), default=0.0),
                "y0": float(bbox[1]),
                "y1": float(bbox[3]),
                "x0": float(bbox[0]),
                "x1": float(bbox[2]),
                "height": height,
                "width": width,
            })
    out.sort(key=lambda x: (x["y0"], x["x0"]))
    return out


def _title_forbidden(text: str) -> bool:
    t = _norm(text)
    return bool(
        _DOC_TYPE_RE.match(t) or _DEGREE_RE.match(t) or _PROGRAM_RE.match(t) or
        _AUTHOR_LABEL_RE.match(t) or _ADVISOR_RE.match(t) or _AFFILIATION_RE.match(t) or
        _LOCATION_RE.match(t) or (_MONTH_RE.search(t) and _YEAR_RE.search(t))
    )


def _plausible_title(text: str) -> bool:
    t = _norm(text).strip(" -–—:;,.|")
    if not 12 <= len(t) <= 420 or _title_forbidden(t):
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ]+", t)
    return len(words) >= 3


def _title_anchor_candidate(lines: List[Dict[str, Any]]) -> Optional[Tuple[str, float]]:
    """Prefer text between an explicit thesis-type marker and the next cover role."""
    marker_indexes = [i for i, ln in enumerate(lines) if _DOC_TYPE_RE.match(_norm(ln["text"]))]
    for idx in marker_indexes:
        collected: List[Dict[str, Any]] = []
        for ln in lines[idx + 1:]:
            if ln["y0"] <= lines[idx]["y1"]:
                continue
            t = _norm(ln["text"])
            if _DEGREE_RE.match(t) or _PROGRAM_RE.match(t) or _AUTHOR_LABEL_RE.match(t) or _ADVISOR_RE.match(t):
                break
            if _LOCATION_RE.match(t) or (_MONTH_RE.search(t) and _YEAR_RE.search(t)):
                break
            if _plausible_title(t):
                if collected:
                    gap = ln["y0"] - collected[-1]["y1"]
                    if gap > max(34.0, 2.3 * max(ln["size"], collected[-1]["size"])):
                        break
                collected.append(ln)
            elif collected and ln["y0"] - collected[-1]["y1"] > 18:
                break
        if collected:
            text = _norm(" ".join(x["text"] for x in collected)).strip(" -–—:;,.|")
            if _plausible_title(text):
                return text, 0.99
    return None


def _looks_like_person_name_text(text: str) -> bool:
    t = _PERSON_PREFIX_RE.sub("", _norm(text)).strip(" .:;,-")
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’.-]+", t)
    particles = {"de", "del", "la", "las", "los", "y", "e", "da", "do", "dos", "van", "von"}
    significant = [w for w in words if w.casefold() not in particles]
    return 2 <= len(words) <= 6 and len(significant) >= 2 and all(w[:1].isupper() for w in significant)


def _generic_title_candidates(lines_by_page: List[List[Dict[str, Any]]]) -> List[Tuple[float, str]]:
    scored: List[Tuple[float, str]] = []
    for pno, lines in enumerate(lines_by_page[:3]):
        usable = [
            x for x in lines
            if x["y0"] <= 0.78 * x["height"] and x["size"] >= 10.5 and _plausible_title(x["text"])
        ]
        groups: List[List[Dict[str, Any]]] = []
        cur: List[Dict[str, Any]] = []
        for ln in usable:
            if cur and (
                ln["page"] != cur[-1]["page"] or
                ln["y0"] - cur[-1]["y1"] > max(34.0, 2.2 * max(ln["size"], cur[-1]["size"]))
            ):
                groups.append(cur)
                cur = []
            cur.append(ln)
        if cur:
            groups.append(cur)
        for group in groups:
            text = _norm(" ".join(x["text"] for x in group)).strip(" -–—:;,.|")
            if not _plausible_title(text):
                continue
            size = max(x["size"] for x in group)
            y0, y1, height = group[0]["y0"], group[-1]["y1"], group[0]["height"]
            score = size * 2 + min(len(text), 240) / 18
            if 0.20 * height <= (y0 + y1) / 2 <= 0.64 * height:
                score += 9
            if len(group) >= 2:
                score += 5
            after = [x for x in lines if x["y0"] >= y1 - 1 and x not in group]
            if after:
                nxt = _norm(after[0]["text"])
                if _DEGREE_RE.match(nxt) or _PROGRAM_RE.match(nxt) or _AUTHOR_LABEL_RE.match(nxt):
                    score += 7
            if len(text.split()) <= 4:
                score -= 4
            if _looks_like_person_name_text(text):
                score -= 8
            score -= pno * 5
            scored.append((score, text))
    return sorted(scored, reverse=True, key=lambda x: x[0])


def _plausible_pdf_title(text: str, fallback: str) -> bool:
    t = _norm(text).strip(" -–—:;,.|")
    if not _plausible_title(t):
        return False
    low = t.casefold()
    junk = (
        "microsoft word", "acrobat", "untitled", "document1", "documento1",
        "tesis_final", "tesis final.doc", ".docx", ".doc", ".pdf",
    )
    if any(x in low for x in junk):
        return False
    norm_t = re.sub(r"[^a-z0-9áéíóúüñ]+", "", low)
    norm_f = re.sub(r"[^a-z0-9áéíóúüñ]+", "", fallback.casefold())
    if norm_t and norm_t == norm_f:
        return False
    return True


def _detect_title(
    lines_by_page: List[List[Dict[str, Any]]], pdf_title: str, fallback: str
) -> tuple[str, str, float, List[str]]:
    if lines_by_page:
        anchored = _title_anchor_candidate(lines_by_page[0])
        if anchored:
            return anchored[0], "cover_anchor", anchored[1], []
    scored = _generic_title_candidates(lines_by_page)
    if scored and scored[0][0] >= 27:
        best = scored[0][1]
        alternatives = []
        for score, text in scored[1:4]:
            if text != best and score >= scored[0][0] - 7:
                alternatives.append(text)
        confidence = 0.96 if not alternatives else 0.82
        return best, "cover_layout", confidence, alternatives
    meta = _norm(pdf_title)
    if _plausible_pdf_title(meta, fallback):
        return meta, "pdf_metadata", 0.65, []
    return fallback, "filename", 0.35, []


def _person_like(text: str) -> bool:
    t = _PERSON_PREFIX_RE.sub("", _norm(text)).strip(" .:;,-")
    if not t or any(c.isdigit() for c in t) or _title_forbidden(t):
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’.-]+", t)
    if not 2 <= len(words) <= 7:
        return False
    particles = {"de", "del", "la", "las", "los", "y", "da", "do", "dos", "van", "von"}
    significant = [w for w in words if w.casefold() not in particles]
    return len(significant) >= 2 and all(w[:1].isupper() for w in significant)


def _clean_person(text: str) -> str:
    return _smart_case(_PERSON_PREFIX_RE.sub("", _norm(text)).strip(" .:;,-"))


def _find_title_end(lines: List[Dict[str, Any]], title: str) -> float:
    tokens = set(re.findall(r"\w+", title.casefold()))
    found = []
    for ln in lines:
        line_tokens = set(re.findall(r"\w+", ln["text"].casefold()))
        if line_tokens and len(line_tokens & tokens) >= max(1, min(3, len(line_tokens))):
            found.append(ln)
    return max((x["y1"] for x in found), default=0.0)


def _detect_author(lines: List[Dict[str, Any]], title: str) -> tuple[Optional[str], float, List[str]]:
    for i, ln in enumerate(lines):
        if _AUTHOR_LABEL_RE.match(_norm(ln["text"])):
            for nxt in lines[i + 1:i + 5]:
                if _ADVISOR_RE.match(_norm(nxt["text"])):
                    break
                if _person_like(nxt["text"]):
                    return _clean_person(nxt["text"]), 0.99, []
    title_end = _find_title_end(lines, title)
    candidates = []
    for ln in lines:
        if ln["y0"] <= title_end + 8:
            continue
        t = _norm(ln["text"])
        if _ADVISOR_RE.match(t):
            break
        if _MONTH_RE.search(t) and _YEAR_RE.search(t):
            break
        if _person_like(t):
            candidates.append(_clean_person(t))
    if candidates:
        return candidates[0], 0.86, candidates[1:]
    return None, 0.0, []


def _detect_year(lines: List[Dict[str, Any]]) -> tuple[Optional[str], float, List[str]]:
    candidates = []
    for ln in lines:
        for match in _YEAR_RE.finditer(ln["text"]):
            score = 0.35
            if _MONTH_RE.search(ln["text"]):
                score += 0.5
            if ln["y0"] >= 0.65 * ln["height"]:
                score += 0.12
            if _LOCATION_RE.match(_norm(ln["text"])):
                score += 0.05
            candidates.append((score, match.group(1)))
    if not candidates:
        return None, 0.0, []
    candidates.sort(reverse=True)
    best = candidates[0]
    alternatives = []
    for _, year in candidates[1:]:
        if year != best[1] and year not in alternatives:
            alternatives.append(year)
    return best[1], min(0.99, best[0]), alternatives


def _detect_affiliation(lines: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    university = faculty = None
    for ln in lines:
        t = _norm(ln["text"])
        if university is None and _UNIVERSITY_RE.match(t):
            university = _smart_case(t)
        if faculty is None and _FACULTY_RE.match(t):
            faculty = _smart_case(t)
        if university and faculty:
            break
    return university, faculty


def _clean_program(text: str) -> str:
    return _smart_case(_norm(text).strip(" .:;,-"))


def _detect_program(lines: List[Dict[str, Any]]) -> tuple[Optional[str], float]:
    for ln in lines:
        t = _norm(ln["text"])
        if _PROGRAM_RE.match(t):
            return _clean_program(t), 0.98
    for i, ln in enumerate(lines):
        if not _DEGREE_RE.match(_norm(ln["text"])):
            continue
        for nxt in lines[i + 1:i + 3]:
            t = _norm(nxt["text"])
            if _PROGRAM_RE.match(t):
                return _clean_program(t), 0.98
    return None, 0.0


def _degree_level(lines: List[Dict[str, Any]]) -> Optional[str]:
    blob = " ".join(_norm(x["text"]) for x in lines[:30])
    if re.search(r"\b(?:maestr[ií]a|mag[ií]ster|master(?:'s)?)\b", blob, re.I):
        return "maestria"
    if re.search(r"\b(?:doctorado|doctoral|ph\.?d\.?)\b", blob, re.I):
        return "doctorado"
    return None


def detect_cover_metadata(path: str | Path, filename: str | None = None) -> Dict[str, Any]:
    path = Path(path)
    filename = filename or path.name
    fallback = _norm(re.sub(r"[_-]+", " ", Path(filename).stem))
    out: Dict[str, Any] = {
        "version": COVER_METADATA_VERSION,
        "title": fallback,
        "title_source": "filename",
        "metadata": {},
        "sources": {},
        "confidence": {},
        "needs_review": False,
        "review_reasons": [],
        "candidates": {},
    }
    if fitz is None or not path.exists():
        out["confidence"]["title"] = 0.35
        return out
    try:
        with fitz.open(path) as pdf:
            lines_by_page = [_page_lines(pdf[pno], pno) for pno in range(min(3, len(pdf)))]
            pdf_title = _norm((pdf.metadata or {}).get("title") or "")
    except Exception as exc:
        out["notes"] = [f"cover_read_error:{type(exc).__name__}"]
        out["confidence"]["title"] = 0.35
        return out

    title, source, title_conf, title_alts = _detect_title(lines_by_page, pdf_title, fallback)
    out["title"] = title
    out["title_source"] = source
    out["confidence"]["title"] = title_conf
    out["sources"]["title"] = source
    if title_alts:
        out["candidates"]["title"] = [title] + title_alts
        out["needs_review"] = True
        out["review_reasons"].append("title_ambiguous")

    first = lines_by_page[0] if lines_by_page else []
    author, author_conf, author_alts = _detect_author(first, title)
    year, year_conf, year_alts = _detect_year(first)
    university, faculty = _detect_affiliation(first)
    program, program_conf = _detect_program(first)
    level = _degree_level(first)
    for key, value, confidence, field_source in (
        ("author", author, author_conf, "cover_role"),
        ("year", year, year_conf, "cover_date"),
        ("university", university, 0.98 if university else 0.0, "cover_affiliation"),
        ("faculty", faculty, 0.98 if faculty else 0.0, "cover_affiliation"),
        ("program", program, program_conf, "cover_degree"),
        ("degree_level", level, 0.92 if level else 0.0, "cover_degree"),
    ):
        if value:
            out["metadata"][key] = value
            out["confidence"][key] = round(confidence, 2)
            out["sources"][key] = field_source

    if author_alts:
        out["candidates"]["author"] = [author] + author_alts
        out["needs_review"] = True
        out["review_reasons"].append("author_ambiguous")
    if year_alts:
        out["candidates"]["year"] = [year] + year_alts
        if year_conf < 0.78:
            out["needs_review"] = True
            out["review_reasons"].append("year_ambiguous")
    if title_conf < 0.65:
        out["needs_review"] = True
        out["review_reasons"].append("title_low_confidence")
    out["review_reasons"] = list(dict.fromkeys(out["review_reasons"]))
    return out
