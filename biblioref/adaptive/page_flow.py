"""Cross-page continuity diagnostics for BiblioRef v0.8.5-b.

The module never creates, merges or splits records.  It describes whether the
last useful line of one page and the first useful line of the next page look
like one logical bibliographic record.  All evidence is exposed for audit.
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence

from biblioref.adaptive.geometry import is_repeated_decoration, x0_cluster_profile
from biblioref.adaptive.input_hygiene import detect_input_decorations, decoration_status
from biblioref.adaptive.continuity import institutional_author_date
from biblioref.grammar.numeric import infer_marker_only_numeric, infer_prefix_numeric, infer_comma_numeric, marker_only_number
from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.legacy.engine import (
    BRACKET_KEY_RX,
    DOI_URL_AT_START_RX,
    NUMERIC_MARKER_RX,
    LayoutLine,
    _is_footer,
    _is_reference_heading,
)

CONNECTOR_END_RX = re.compile(
    r"(?:\b(?:and|y|e|et|of|de|del|da|do|dos|das|in|en|edited by|ed\. by)|&)\s*$",
    re.I,
)
INCOMPLETE_ABBREV_RX = re.compile(r"\b(?:vol\.?|v\.|n\.|no\.|p\.|pp\.|doi:)\s*$", re.I)
PAGE_RANGE_INCOMPLETE_RX = re.compile(r"\b\d{1,4}\s*[-–—]\s*$")
DOI_INCOMPLETE_RX = re.compile(r"(?:doi\s*:\s*|10\.\d{4,9}/)\s*$", re.I)
URL_INCOMPLETE_RX = re.compile(r"https?://\S*/\s*$", re.I)
CONTINUATION_START_RX = re.compile(
    r"^(?:[a-záéíóúàâêôãõçüñ]|(?i:https?://|www\.|doi\s*:|10\.\d{4,9}/)|"
    r"\d{1,4}(?:[-–—]\d+)?[.,;:]?\s*(?i:doi\s*:|https?://)|"
    r"(?i:(?:vol\.?|v\.?|n\.?|no\.?|p\.?|pp\.?)\s*\d))"
)



def _unbalanced(text: str, left: str, right: str) -> bool:
    return text.count(left) > text.count(right)


def terminal_completeness(text: str, line: LayoutLine | None = None) -> Dict:
    """Describe whether a physical record ending looks incomplete.

    This is an interpretable state, not a probability and not a correction.
    """
    raw = (text or "").strip()
    signals: List[str] = []
    strong = 0
    if not raw:
        return {"terminal_state": "neutral", "signals": ["empty_text"]}
    if raw.endswith(("-", "–", "—", ",", ":")):
        signals.append("trailing_connector_punctuation")
    if CONNECTOR_END_RX.search(raw):
        signals.append("ends_with_linking_word")
        strong += 1
    if _unbalanced(raw, "(", ")"):
        signals.append("unclosed_parenthesis")
        strong += 1
    if _unbalanced(raw, "[", "]"):
        signals.append("unclosed_bracket")
        strong += 1
    if PAGE_RANGE_INCOMPLETE_RX.search(raw):
        signals.append("incomplete_page_range")
        strong += 1
    if DOI_INCOMPLETE_RX.search(raw):
        signals.append("incomplete_doi")
        strong += 1
    if URL_INCOMPLETE_RX.search(raw):
        signals.append("incomplete_url")
        strong += 1
    if INCOMPLETE_ABBREV_RX.search(raw):
        signals.append("incomplete_bibliographic_abbreviation")
        strong += 1
    if line is not None:
        rel_bottom = float(line.y1) / max(float(line.page_height), 1.0)
        if rel_bottom >= 0.88:
            signals.append("ends_near_page_bottom")
    if strong >= 1 or len(signals) >= 2:
        state = "likely_incomplete"
    elif raw.endswith((".", ")", "]")):
        state = "likely_complete"
    else:
        state = "neutral"
    return {"terminal_state": state, "signals": signals}


def _is_decoration(line: LayoutLine, decoration_report: Dict | None) -> bool:
    if _is_reference_heading(line) or _is_footer(line):
        return True
    if decoration_report and decoration_status(line, decoration_report) == "DECORATION_CONFIRMED":
        return True
    return bool(decoration_report and is_repeated_decoration(line, decoration_report))


def _active_candidate_for_line(line_index: int, candidates: Sequence[Dict]) -> Dict | None:
    for item in candidates:
        if int(item.get("line_index", -1)) == int(line_index):
            return item
    return None


def _marker_number(text: str) -> int | None:
    m = NUMERIC_MARKER_RX.match(text.strip())
    if not m:
        return None
    raw = m.group(0)
    found = re.search(r"\d+", raw)
    return int(found.group(0)) if found else None


def analyze_page_flows(
    lines: Sequence[LayoutLine],
    candidates: Sequence[Dict] | None = None,
    decoration_report: Dict | None = None,
) -> List[Dict]:
    """Return diagnostics for consecutive physical pages represented in a zone."""
    candidates = list(candidates or [])
    marker_only_profile = infer_marker_only_numeric(lines)
    marker_only_map = marker_only_profile.get("line_to_value", {}) if marker_only_profile.get("detected") else {}
    prefix_numeric_profile = infer_prefix_numeric(lines)
    prefix_numeric_map = prefix_numeric_profile.get("line_to_value", {}) if prefix_numeric_profile.get("detected") else {}
    comma_numeric_profile = infer_comma_numeric(lines)
    comma_numeric_map = comma_numeric_profile.get("line_to_value", {}) if comma_numeric_profile.get("detected") else {}
    if decoration_report is None:
        decoration_report = detect_input_decorations(lines)
    indexed = [(i, line) for i, line in enumerate(lines) if line.text.strip()]
    pages = sorted({int(line.page) for _, line in indexed})
    xprof = x0_cluster_profile(lines)
    left = xprof.get("left_cluster_center")
    continuation = xprof.get("continuation_cluster_center")
    tolerance = float(xprof.get("tolerance") or 8.0)
    output: List[Dict] = []

    for p1, p2 in zip(pages, pages[1:]):
        if p2 != p1 + 1:
            continue
        prev_items = [(i, l) for i, l in indexed if int(l.page) == p1 and not _is_decoration(l, decoration_report)]
        next_items = [(i, l) for i, l in indexed if int(l.page) == p2 and not _is_decoration(l, decoration_report)]
        if not prev_items or not next_items:
            output.append({
                "from_page": p1, "to_page": p2, "flow_state": "no_record_crossing",
                "signals": ["no_useful_content_on_one_side"],
            })
            continue
        prev_idx, prev_line = prev_items[-1]
        next_idx, next_line = next_items[0]
        prev_text = prev_line.text.strip()
        next_text = next_line.text.strip()
        terminal = terminal_completeness(prev_text, prev_line)
        signals: List[str] = []
        continuation_support = 0
        boundary_support = 0

        if terminal["terminal_state"] == "likely_incomplete":
            signals.append("previous_terminal_incomplete")
            continuation_support += 2
        elif terminal["terminal_state"] == "likely_complete":
            signals.append("previous_terminal_complete")
            boundary_support += 1

        if CONTINUATION_START_RX.match(next_text):
            signals.append("next_starts_like_continuation")
            continuation_support += 2
        if continuation is not None and abs(float(next_line.x0) - float(continuation)) <= tolerance:
            signals.append("next_at_continuation_cluster")
            continuation_support += 1
        if left is not None and abs(float(next_line.x0) - float(left)) <= tolerance:
            signals.append("next_at_start_cluster")
            boundary_support += 1

        cand = _active_candidate_for_line(next_idx, candidates)
        if cand and cand.get("active_shadow_boundary"):
            signals.append("next_is_active_boundary_candidate")
            boundary_support += 2
        elif cand:
            signals.append("next_not_active_boundary_candidate")
            continuation_support += 1

        prev_num = _marker_number(prev_text)
        next_num = _marker_number(next_text)
        if prev_num is None and prev_idx in marker_only_map:
            prev_num = int(marker_only_map[prev_idx])
        if next_num is None and next_idx in marker_only_map:
            next_num = int(marker_only_map[next_idx])
        if prev_num is None and prev_idx in prefix_numeric_map:
            prev_num = int(prefix_numeric_map[prev_idx])
        if next_num is None and next_idx in prefix_numeric_map:
            next_num = int(prefix_numeric_map[next_idx])
        if prev_num is None and prev_idx in comma_numeric_map:
            prev_num = int(comma_numeric_map[prev_idx])
        if next_num is None and next_idx in comma_numeric_map:
            next_num = int(comma_numeric_map[next_idx])
        if next_num is not None:
            if prev_num is not None and next_num == prev_num + 1:
                signals.append("expected_next_numeric_marker")
                boundary_support += 3
            else:
                signals.append("numeric_marker_at_next_page_start")
                boundary_support += 2
        if BRACKET_KEY_RX.match(next_text):
            signals.append("bracket_key_at_next_page_start")
            boundary_support += 2
        if parenthetical_author_year(next_text) or bare_author_year(next_text):
            signals.append("strong_author_date_at_next_page_start")
            boundary_support += 2
        if institutional_author_date(next_text):
            signals.append("institutional_author_date_at_next_page_start")
            boundary_support += 3
        if DOI_URL_AT_START_RX.match(next_text):
            if "next_starts_like_continuation" not in signals:
                signals.append("doi_url_at_next_page_start")
            continuation_support += 2

        if continuation_support >= boundary_support + 2 and continuation_support >= 2:
            state = "likely_continuation"
        elif boundary_support >= continuation_support + 2 and boundary_support >= 2:
            state = "likely_new_reference"
        else:
            state = "ambiguous"

        skipped = [
            l.text.strip() for _, l in indexed
            if int(l.page) == p2 and float(l.y0) < float(next_line.y0) and _is_decoration(l, decoration_report)
        ]
        watched = [
            l.text.strip() for _, l in indexed
            if int(l.page) == p2 and float(l.y0) <= float(next_line.y0)
            and decoration_status(l, decoration_report) == "DECORATION_WATCH"
        ]
        if skipped:
            signals.append("page_top_decoration_skipped")
        if watched:
            signals.append("page_flow_decoration_uncertain")

        output.append({
            "from_page": p1,
            "to_page": p2,
            "previous_line_index": prev_idx,
            "next_line_index": next_idx,
            "previous_text_preview": prev_text[:180],
            "next_text_preview": next_text[:180],
            "previous_terminal_state": terminal["terminal_state"],
            "previous_terminal_signals": terminal["signals"],
            "flow_state": state,
            "continuation_support": continuation_support,
            "boundary_support": boundary_support,
            "signals": signals,
            "skipped_decorations": skipped[:5],
            "watched_decorations": watched[:5],
        })
    return output
