"""Non-destructive suggestions used by the visual audit interface."""

import re
import statistics
from typing import Dict, List, Optional, Sequence

from biblioref.ingestion import LayoutLine
from biblioref.legacy.engine import (
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    BULLET_RX,
    NUMERIC_MARKER_RX,
    _strip_heading_prefix,
    _has_bare_author_year,
    _has_early_bibliographic_date,
    is_ref_heading,
)


def candidate_heading_lines(lines: Sequence[LayoutLine]) -> List[dict]:
    """Rank heading candidates without matching incidental prose."""
    lexical = re.compile(
        r"\b(?:referencias?|bibliograf(?:ia|y)|fuentes?|citas\s+bibliograficas?|literatura\s+citada|"
        r"obras\s+citadas|works\s+cited|literature\s+cited|cited\s+literature)\b",
        re.I,
    )
    page_font_medians: Dict[int, float] = {}
    for page in sorted({line.page for line in lines}):
        sizes = [
            line.median_font_size
            for line in lines
            if line.page == page and line.median_font_size > 0
        ]
        page_font_medians[page] = statistics.median(sizes) if sizes else 0.0
    candidates: List[dict] = []
    seen = set()
    for line_index, line in enumerate(lines):
        text = line.text.strip()
        if not text or len(text) > 140:
            continue
        if re.search(r"(?:\.{4,}|…{2,}).*\d{1,4}\s*$", text):
            continue
        exact = is_ref_heading(text)
        candidate_phrase = bool(re.fullmatch(
            r"\s*(?:(?:[ivxlcdm]+|\d+)(?:[.\-:]\d+)*[.\-:]?\s*)?"
            r"(?:fuentes\s+y\s+bibliograf[ií]a|bibliograf[ií]a\s+y\s+fuentes|citas\s+bibliogr[aá]ficas?)\s*",
            text, flags=re.I,
        ))
        if not exact and not candidate_phrase and not lexical.search(text):
            continue
        letters = [char for char in text if char.isalpha()]
        upper_ratio = sum(char.isupper() for char in letters) / max(len(letters), 1)
        larger_font = (
            line.median_font_size >= page_font_medians.get(line.page, 0.0) + 0.8
        )
        compact = len(text) <= 70
        heading_like = exact or candidate_phrase or (
            compact and (upper_ratio >= 0.65 or (larger_font and upper_ratio >= 0.40))
        )
        if not heading_like:
            continue
        key = (line.page, round(line.y0, 1), text)
        if key in seen:
            continue
        seen.add(key)
        score = (
            1.0
            if exact
            else 0.94
            if candidate_phrase
            else round(0.62 + 0.12 * larger_font + 0.10 * (upper_ratio >= 0.65), 2)
        )
        candidates.append({
            "page": line.page,
            "y": round(line.y0, 2),
            "text": text,
            "score": score,
            "reason": "recognized_heading" if exact else ("candidate_heading_phrase" if candidate_phrase else "heading_like_layout"),
            "font_size": round(line.median_font_size, 2),
            "_line_index": line_index,
        })

    grouped: Dict[str, List[dict]] = {}
    for item in candidates:
        key = re.sub(
            r"[^a-z0-9]+", " ", _strip_heading_prefix(item["text"])
        ).strip()
        grouped.setdefault(key, []).append(item)
    suppressed = set()
    for items in grouped.values():
        if len(items) < 2 or items[-1]["page"] < items[0]["page"] + 3:
            continue
        first = items[0]
        index = first["_line_index"]
        previous = [
            row.text.strip()
            for row in lines[max(0, index - 20):index]
            if row.page == first["page"]
        ]
        numbered = sum(
            bool(re.match(r"^(?:(?:[ivxlcdm]+|\d+)(?:[\.\-:]|\s))", value, flags=re.I))
            for value in previous
        )
        if numbered >= 4:
            suppressed.add(id(first))

    result = []
    last_kept_by_key: Dict[str, dict] = {}
    for item in candidates:
        if id(item) in suppressed:
            continue
        normalized = re.sub(
            r"[^a-z0-9]+", " ", _strip_heading_prefix(item["text"])
        ).strip()
        previous = last_kept_by_key.get(normalized)
        if previous and item["page"] <= previous["page"] + 3 and item["y"] <= 120:
            continue
        item.pop("_line_index", None)
        result.append(item)
        last_kept_by_key[normalized] = item
    return result


LEGAL_SOURCE_RX = re.compile(
    r"(?:\bExp(?:te|ediente)\b|\bFallos?\b|\bCSJN\b|\bGC?BA\b|\bSala\s+[IVX\d]+\b|"
    r"\bc/\s*|\bs/\s*|\bLey\s+\d|\bDecreto\s+\d|\bResoluci[oó]n\s+\d)",
    re.I,
)


def _boundary_signal(line: LayoutLine) -> str:
    text = line.text.strip()
    if BULLET_RX.match(text):
        return "bullet"
    if NUMERIC_MARKER_RX.match(text):
        return "numeric"
    if BRACKET_KEY_RX.match(text):
        return "bracket_key"
    if AUTHOR_COMMA_RX.match(text) and (
        _has_early_bibliographic_date(text) or _has_bare_author_year(text)
    ):
        return "author_year"
    return ""


def detect_reference_like_regions(
    lines: Sequence[LayoutLine], page_count: int
) -> List[dict]:
    """Propose dense reference-like regions without accepting them automatically."""
    by_page: Dict[int, List[LayoutLine]] = {}
    for line in lines:
        if 0.12 * line.page_height <= line.y0 <= 0.92 * line.page_height:
            by_page.setdefault(line.page, []).append(line)

    profiles: Dict[int, dict] = {}
    for page, page_lines in by_page.items():
        signaled = [(line, _boundary_signal(line)) for line in page_lines]
        signaled = [(line, signal) for line, signal in signaled if signal]
        if not signaled:
            continue
        counts: Dict[str, int] = {}
        for _, signal in signaled:
            counts[signal] = counts.get(signal, 0) + 1
        dominant, dominant_count = max(counts.items(), key=lambda item: item[1])
        legal_count = sum(bool(LEGAL_SOURCE_RX.search(line.text)) for line, _ in signaled)
        structural = sum(
            counts.get(key, 0) for key in ("bullet", "numeric", "bracket_key")
        )
        near_end = page >= max(1, int(page_count * 0.55))
        strong = (
            len(signaled) >= 3
            and (structural >= 2 or counts.get("author_year", 0) >= 3)
            and (near_end or len(signaled) >= 6)
        )
        if not strong:
            continue
        dominance = dominant_count / len(signaled)
        score = min(
            0.98,
            0.58 + 0.045 * len(signaled) + 0.10 * dominance + 0.07 * near_end,
        )
        style = (
            "legal_bulleted"
            if dominant == "bullet" and legal_count >= max(2, len(signaled) // 3)
            else dominant
        )
        profiles[page] = {
            "page": page,
            "start_y": min(line.y0 for line, _ in signaled),
            "last_y": max(line.y1 for line, _ in signaled),
            "n_starts": len(signaled),
            "style_guess": style,
            "score": round(score, 3),
            "evidence": ";".join(
                f"{key}:{value}" for key, value in sorted(counts.items())
            ),
        }

    if not profiles:
        return []
    pages = sorted(profiles)
    groups: List[List[int]] = [[pages[0]]]
    for page in pages[1:]:
        if page - groups[-1][-1] <= 2:
            groups[-1].append(page)
        else:
            groups.append([page])

    regions: List[dict] = []
    for index, group in enumerate(groups, 1):
        start_page, end_page = min(group), max(group)
        total_starts = sum(profiles[page]["n_starts"] for page in group)
        dominant_style = max(
            (profiles[page]["style_guess"] for page in group),
            key=lambda value: sum(
                profiles[p]["style_guess"] == value for p in group
            ),
        )
        score = round(
            sum(profiles[page]["score"] for page in group) / len(group), 3
        )
        regions.append({
            "region_id": index,
            "start_page": start_page,
            "start_y": round(profiles[start_page]["start_y"], 2),
            "end_page": end_page,
            "style_guess": dominant_style,
            "n_boundary_signals": total_starts,
            "confidence_score": score,
            "evidence": " | ".join(
                profiles[page]["evidence"] for page in group[:4]
            ),
            "requires_confirmation": True,
        })
    return regions


def nearest_line(
    lines: Sequence[LayoutLine], page_number: int, y_pdf: float
) -> Optional[LayoutLine]:
    page_lines = [line for line in lines if line.page == page_number]
    if not page_lines:
        return None
    return min(page_lines, key=lambda line: abs(((line.y0 + line.y1) / 2) - y_pdf))
