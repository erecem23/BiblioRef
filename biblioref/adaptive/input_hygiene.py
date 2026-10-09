"""Input-hygiene diagnostics for BiblioRef v0.8.5-c.

This layer sits before page-flow reasoning. It identifies high-confidence
running decorations (including templates with page-number variation), keeps
uncertain cases visible for audit, and never alters validated extraction output.
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from typing import Dict, List, Sequence

from biblioref.legacy.engine import LayoutLine, _is_reference_heading


_PAGE_NUMBER_RX = re.compile(r"\b\d{1,4}\b")
_LONG_ID_RX = re.compile(r"\b\d{5,}\b")
_ROMAN_PAGE_RX = re.compile(r"\b[ivxlcdm]{1,8}\b", re.I)


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def decoration_template(text: str) -> str:
    """Return a conservative template for variable running decorations.

    Page-like numbers become ``<N>`` and long identifiers become ``<ID>``.
    The raw text is always preserved elsewhere for audit.
    """
    value = _fold(text)
    value = _LONG_ID_RX.sub("<ID>", value)
    value = _PAGE_NUMBER_RX.sub("<N>", value)
    value = re.sub(r"\s+", " ", value).strip(" .-|_")
    return value


def _band(line: LayoutLine) -> str | None:
    rel = float(line.y0) / max(float(line.page_height), 1.0)
    if rel <= 0.14:
        return "top"
    if rel >= 0.86:
        return "bottom"
    return None


def _looks_bibliographic_start(text: str) -> bool:
    raw = text.strip()
    if _is_reference_heading(SimpleLine(raw)):
        return False
    if re.match(r"^(?:\[?\d{1,4}\]?\s*[.)]?\s+)", raw):
        # A page number alone can be decoration, but a numeric marker followed
        # by substantial text may be a real numeric reference.
        rest = re.sub(r"^(?:\[?\d{1,4}\]?\s*[.)]?\s+)", "", raw)
        if len(rest.split()) >= 4:
            return True
    if re.search(r"\((?:18|19|20)\d{2}[a-z]?\)", raw):
        return True
    if re.match(r"^[A-ZÁÉÍÓÚÑ][^,]{1,70},\s*[A-ZÁÉÍÓÚÑ]", raw):
        return True
    return False


class SimpleLine:
    """Tiny adapter used only for heading checks without constructing LayoutLine."""
    def __init__(self, text: str):
        self.text = text


def detect_input_decorations(lines: Sequence[LayoutLine]) -> Dict:
    """Detect confirmed and uncertain running decorations.

    Confirmation uses recurrence in the same vertical band plus a normalized
    template. Two-page recurrence is sufficient only for a strongly variable
    page-number/ID template; otherwise three pages are required.
    """
    occurrences: Dict[tuple[str, str], List[LayoutLine]] = defaultdict(list)
    raw_occurrences: Dict[tuple[str, str], List[LayoutLine]] = defaultdict(list)
    for line in lines:
        text = line.text.strip()
        band = _band(line)
        if not band or not 1 <= len(text) <= 180:
            continue
        template = decoration_template(text)
        if not template:
            continue
        occurrences[(template, band)].append(line)
        raw_occurrences[(_fold(text), band)].append(line)

    confirmed: List[Dict] = []
    watch: List[Dict] = []
    confirmed_keys = set()
    watch_keys = set()

    for (template, band), items in occurrences.items():
        pages = sorted({int(item.page) for item in items})
        if len(pages) < 2:
            continue
        raw_examples = list(dict.fromkeys(item.text.strip() for item in items))[:8]
        has_variable_token = "<N>" in template or "<ID>" in template
        raw_variation = len({_fold(item.text) for item in items}) >= 2
        same_band_y = [float(item.y0) / max(float(item.page_height), 1.0) for item in items]
        y_spread = max(same_band_y) - min(same_band_y) if same_band_y else 1.0
        text_is_reference_like = any(_looks_bibliographic_start(item.text) for item in items)

        strong = bool(
            y_spread <= 0.035
            and not text_is_reference_like
            and (
                len(pages) >= 3
                or (len(pages) >= 2 and has_variable_token and raw_variation)
                or (len(pages) >= 2 and "<ID>" in template)
            )
        )
        entry = {
            "template": template,
            "band": band,
            "pages": pages[:50],
            "page_count": len(pages),
            "example_texts": raw_examples,
            "median_x0": round(float(statistics.median(item.x0 for item in items)), 2),
            "relative_y_spread": round(float(y_spread), 4),
            "has_variable_token": has_variable_token,
            "raw_variation": raw_variation,
            "bibliographic_start_conflict": text_is_reference_like,
            "evidence": [
                "same_vertical_band",
                "normalized_template_recurrence",
                *( ["variable_page_or_id_token"] if has_variable_token else [] ),
                *( ["three_or_more_pages"] if len(pages) >= 3 else [] ),
            ],
        }
        key = (template, band)
        if strong:
            entry["status"] = "DECORATION_CONFIRMED"
            confirmed.append(entry)
            confirmed_keys.add(key)
        else:
            entry["status"] = "DECORATION_WATCH"
            watch.append(entry)
            watch_keys.add(key)

    return {
        "version": "input_hygiene_v0_8_5c",
        "confirmed": confirmed,
        "watch": watch,
        "confirmed_keys": confirmed_keys,
        "watch_keys": watch_keys,
        "n_confirmed": len(confirmed),
        "n_watch": len(watch),
    }


def decoration_status(line: LayoutLine, report: Dict | None) -> str:
    if not report:
        return "NOT_DECORATION"
    band = _band(line)
    if not band:
        return "NOT_DECORATION"
    key = (decoration_template(line.text), band)
    if key in report.get("confirmed_keys", set()):
        return "DECORATION_CONFIRMED"
    if key in report.get("watch_keys", set()):
        return "DECORATION_WATCH"
    return "NOT_DECORATION"


def public_decoration_report(report: Dict) -> Dict:
    return {k: v for k, v in report.items() if k not in {"confirmed_keys", "watch_keys"}}


__all__ = [
    "decoration_template",
    "detect_input_decorations",
    "decoration_status",
    "public_decoration_report",
]
