"""Post-segmentation surveillance used by BiblioRef v0.8.5-e.

This module intentionally does not repair extraction output.  It describes
anomalies and contradictory evidence so a later reconciliation layer can
compare reversible alternatives (merge/split/shift/extend) safely.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Sequence

from biblioref.adaptive.length_profile import build_length_profile
from biblioref.adaptive.page_flow import terminal_completeness
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.grammar.signatures import line_grammar_signature
from biblioref.legacy.engine import LayoutLine

SEVERITY_ORDER = {"INFO": 0, "WATCH": 1, "HIGH_WATCH": 2}
INLINE_AUTHOR_YEAR_RX = re.compile(
    r"(?<!^)(?<!\n)\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]{1,40},\s*"
    r"(?:[A-ZÁÉÍÓÚÑ](?:\.|[a-z]+)[^()]{0,80})?\((?:18|19|20)\d{2}[a-z]?\)"
)
YEAR_TOKEN_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b")
DOI_TOKEN_RX = re.compile(r"(?:doi\s*:|https?://doi\.org/|10\.\d{4,9}/)", re.I)
SOURCEISH_START_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^.!?]{0,80},\s*(?:18|19|20)\d{2}|"
    r"(?:Journal|Revista|Proceedings|Editorial|Editora|Press|University|Universidade|"
    r"Springer|Elsevier|Wiley|Routledge|Sage)\b)", re.I
)
CONTINUATION_SIGNALS = {
    "wrapped_author_continuation",
    "wrapped_date_continuation",
    "publisher_year_continuation",
    "conference_event_continuation",
    "numeric_page_continuation",
    "source_metadata_continuation",
    "numeric_regime_missing_marker",
    "previous_ends_hyphen",
    "previous_ends_linking_word",
}


def _layout_line_from_source(item: Dict) -> LayoutLine | None:
    try:
        return LayoutLine(
            page=int(item.get("page", 1)),
            page_height=float(item.get("page_height", 800.0) or 800.0),
            text=str(item.get("text", "")),
            x0=float(item.get("x0", 0.0)),
            y0=float(item.get("y0", 0.0)),
            x1=float(item.get("x1", 0.0)),
            y1=float(item.get("y1", 0.0)),
            median_font_size=float(item.get("median_font_size", 10.0) or 10.0),
            fragment_count=int(item.get("fragment_count", 1) or 1),
        )
    except Exception:
        return None


def _terminal_for_segment(segment: Dict) -> Dict:
    source = list(segment.get("source_lines") or [])
    line = _layout_line_from_source(source[-1]) if source else None
    return terminal_completeness(str(segment.get("reference_text", "")), line)


def _internal_candidates(segment: Dict, candidates_by_index: Dict[int, Dict]) -> Dict:
    source = list(segment.get("source_lines") or [])
    line_indices = [
        int(item["line_index"]) for item in source
        if item.get("line_index") is not None
    ]
    if len(line_indices) <= 1:
        internal = []
    else:
        internal = [
            candidates_by_index[idx] for idx in line_indices[1:]
            if idx in candidates_by_index
            and (
                candidates_by_index[idx].get("semantic_anchor")
                or float(candidates_by_index[idx].get("score", 0.0)) >= 3.0
            )
        ]
    text = str(segment.get("reference_text", ""))
    inline = len(INLINE_AUTHOR_YEAR_RX.findall(text))
    order_conflicts = sum(
        bool(item.get("features", {}).get("strong_alphabetical_inversion") and item.get("semantic_anchor"))
        for item in internal
    )
    strong = sum(float(item.get("score", 0.0)) >= 3.0 and bool(item.get("semantic_anchor")) for item in internal)
    return {
        "items": internal,
        "n_internal_candidate_boundaries": len(internal) + inline,
        "n_internal_strong_boundaries": strong + inline,
        "n_internal_order_conflicts": order_conflicts,
        "internal_boundary_density": round((len(internal) + inline) / max(len(line_indices) - 1, 1), 3),
        "inline_author_year_candidates": inline,
    }


def _add_alert(alerts: List[Dict], severity: str, flag: str, reason: str, record_index: int | None = None, evidence: Sequence[str] | None = None) -> None:
    alerts.append({
        "severity": severity,
        "flag": flag,
        "reason": reason,
        "record_index": record_index,
        "evidence": list(evidence or []),
    })


def _segment_surveillance(
    segments: Sequence[Dict],
    candidates: Sequence[Dict],
    length_profile: Dict,
) -> List[Dict]:
    cand_by_index = {int(item.get("line_index")): item for item in candidates if item.get("line_index") is not None}
    out: List[Dict] = []
    length_rows = length_profile.get("records", [])
    terminals = [_terminal_for_segment(seg) for seg in segments]

    for i, segment in enumerate(segments):
        length = length_rows[i] if i < len(length_rows) else {}
        terminal = terminals[i]
        internal = _internal_candidates(segment, cand_by_index)
        text = str(segment.get("reference_text", "")).strip()
        start_sig = line_grammar_signature(text[:300])
        start_signals = set(segment.get("shadow_boundary_signals") or [])
        alerts: List[Dict] = []

        if "cross_page" in set(length.get("length_flags", [])):
            _add_alert(alerts, "INFO", "PAGE_FLOW_WATCH", "record_spans_multiple_pages", i, ["cross_page"])

        if terminal.get("terminal_state") == "likely_incomplete":
            _add_alert(alerts, "WATCH", "TRUNCATION_WATCH", "record_terminal_looks_incomplete", i, terminal.get("signals", []))
            if i == len(segments) - 1:
                _add_alert(alerts, "HIGH_WATCH", "ZONE_END_TRUNCATION_WATCH", "last_record_of_zone_looks_incomplete", i, terminal.get("signals", []))

        # Probable false split: short/local outlier + evidence that the current
        # piece is a continuation + previous record has an incomplete ending.
        length_flags = set(length.get("length_flags", []))
        previous_incomplete = i > 0 and terminals[i - 1].get("terminal_state") == "likely_incomplete"
        continuation_boundary = sorted(start_signals.intersection(CONTINUATION_SIGNALS))
        sourceish = bool(SOURCEISH_START_RX.search(text[:180]) or (YEAR_OR_SOURCE_RX.search(text[:180]) and start_sig.get("reference_start_kind") == "unknown"))
        shortish = bool({"very_short_absolute", "short_relative", "short_vs_zone_median"}.intersection(length_flags))
        if shortish and previous_incomplete and (continuation_boundary or sourceish):
            _add_alert(
                alerts, "HIGH_WATCH", "SPLIT_WATCH",
                "short_piece_follows_incomplete_record_and_looks_like_continuation", i,
                ["short_relative_or_ratio", "previous_terminal_incomplete", *(continuation_boundary or ["source_metadata_like_start"])],
            )
        elif shortish and (continuation_boundary or sourceish):
            _add_alert(
                alerts, "WATCH", "SPLIT_WATCH",
                "short_piece_has_continuation_like_start", i,
                ["short_relative_or_ratio", *(continuation_boundary or ["source_metadata_like_start"])],
            )
        elif shortish:
            _add_alert(alerts, "INFO", "LENGTH_OUTLIER", "short_record_relative_to_zone", i, list(length_flags))

        # Probable false merge: internal start evidence is intentionally more
        # important than raw length.  ORDER_CONFLICT is surfaced because the
        # current scorer can miss real starts solely due to alphabetical veto.
        longish = bool({"long_relative", "long_vs_zone_median", "giant_absolute"}.intersection(length_flags))
        if internal["n_internal_strong_boundaries"] >= 2 and longish:
            _add_alert(
                alerts, "HIGH_WATCH", "MERGE_WATCH",
                "long_record_contains_multiple_internal_boundary_candidates", i,
                ["long_relative_or_ratio", f"internal_strong={internal['n_internal_strong_boundaries']}"]
            )
        elif internal["n_internal_order_conflicts"] >= 1:
            _add_alert(
                alerts, "WATCH", "MERGE_WATCH",
                "record_contains_internal_start_suppressed_by_order_conflict", i,
                ["ORDER_CONFLICT_WATCH", f"internal_order_conflicts={internal['n_internal_order_conflicts']}"]
            )
        elif internal["n_internal_strong_boundaries"] >= 2:
            _add_alert(
                alerts, "WATCH", "MERGE_WATCH",
                "record_contains_multiple_internal_boundary_candidates", i,
                [f"internal_strong={internal['n_internal_strong_boundaries']}"]
            )
        elif longish:
            _add_alert(alerts, "INFO", "LENGTH_OUTLIER", "long_record_relative_to_zone", i, list(length_flags))

        year_tokens = len(YEAR_TOKEN_RX.findall(text))
        doi_tokens = len(DOI_TOKEN_RX.findall(text))
        max_severity = max((SEVERITY_ORDER[a["severity"]] for a in alerts), default=-1)
        out.append({
            "record_index": i,
            "reference_start_page": segment.get("reference_start_page"),
            "reference_end_page": segment.get("reference_end_page"),
            "text_preview": text[:220],
            "length": length,
            "terminal_state": terminal.get("terminal_state"),
            "terminal_signals": terminal.get("signals", []),
            "internal_candidate_boundaries": internal["n_internal_candidate_boundaries"],
            "internal_strong_boundaries": internal["n_internal_strong_boundaries"],
            "internal_order_conflicts": internal["n_internal_order_conflicts"],
            "internal_boundary_density": internal["internal_boundary_density"],
            "n_year_tokens": year_tokens,
            "n_doi_tokens": doi_tokens,
            "surveillance_flags": list(dict.fromkeys(a["flag"] for a in alerts)),
            "highest_severity": {0: "INFO", 1: "WATCH", 2: "HIGH_WATCH"}.get(max_severity, "NONE"),
            "alerts": alerts,
        })
    return out


def _page_flow_surveillance(page_flows: Sequence[Dict]) -> List[Dict]:
    items: List[Dict] = []
    for flow in page_flows:
        flags = []
        severity = "INFO"
        if "page_flow_decoration_uncertain" in flow.get("signals", []):
            flags.append("PAGE_FLOW_DECORATION_UNCERTAIN")
            severity = "HIGH_WATCH"
        margin = abs(int(flow.get("continuation_support", 0)) - int(flow.get("boundary_support", 0)))
        if flow.get("flow_state") == "ambiguous" or margin <= 1:
            flags.append("PAGE_FLOW_CONFLICT")
            severity = "WATCH" if severity != "HIGH_WATCH" else severity
        if flags:
            items.append({
                "from_page": flow.get("from_page"),
                "to_page": flow.get("to_page"),
                "flow_state": flow.get("flow_state"),
                "severity": severity,
                "flags": flags,
                "continuation_support": flow.get("continuation_support"),
                "boundary_support": flow.get("boundary_support"),
                "signals": flow.get("signals", []),
            })
    return items


def analyze_surveillance(
    segments: Sequence[Dict],
    candidates: Sequence[Dict],
    page_flows: Sequence[Dict] | None = None,
) -> Dict:
    """Inspect a segmentation without modifying it."""
    segments = list(segments)
    candidates = list(candidates)
    page_flows = list(page_flows or [])
    length = build_length_profile(segments)
    records = _segment_surveillance(segments, candidates, length)
    page_items = _page_flow_surveillance(page_flows)
    all_alerts = [a for row in records for a in row.get("alerts", [])]
    counts = Counter(a["flag"] for a in all_alerts)
    severity_counts = Counter(a["severity"] for a in all_alerts)
    for item in page_items:
        for flag in item["flags"]:
            counts[flag] += 1
        severity_counts[item["severity"]] += 1

    flagged_records = sum(bool(row.get("surveillance_flags")) for row in records)
    n = len(records)
    high_records = sum(row.get("highest_severity") == "HIGH_WATCH" for row in records)
    watch_records = sum(row.get("highest_severity") in {"WATCH", "HIGH_WATCH"} for row in records)
    return {
        "version": "0.8.5-d-surveillance1",
        "diagnostic_only": True,
        "auto_apply": False,
        "length_profile": {k: v for k, v in length.items() if k != "records"},
        "records": records,
        "page_flow_watches": page_items,
        "summary": {
            "n_records": n,
            "n_flagged_records": flagged_records,
            "n_watch_or_high_records": watch_records,
            "n_high_watch_records": high_records,
            "alerts_per_100_references": round(100.0 * len(all_alerts) / max(n, 1), 2),
            "flag_counts": dict(sorted(counts.items())),
            "severity_counts": dict(sorted(severity_counts.items())),
        },
        "repair_authority": "none",
        "next_stage": "reconciliation_available_as_proposal_only_shadow_layer",
    }


__all__ = ["analyze_surveillance"]
