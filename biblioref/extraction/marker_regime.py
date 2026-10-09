"""Evidence-gated bibliography marker regimes introduced in v0.6.5.

The stable engine already understands conventional 1., [1] and (1) markers.
This module adds a second, explicitly local regime for hierarchical reference
markers such as ``5.1.``, ``5.2.``, ... that are common in chapter-local
bibliographies.  A dotted number is never sufficient by itself: the candidate
must expose a sustained exact sequence at a shared layout margin and the
resulting chunks must look bibliographic.

The module is deliberately downstream of zone detection.  It does not decide
that a PDF region is a bibliography; it only repairs boundaries inside a region
that has already been accepted as bibliography-like.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import statistics
from typing import Dict, List, Sequence, Tuple

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, SIN_FECHA_RX

MARKER_REGIME_VERSION = "0.6.5-marker-regime1"

_HIERARCHICAL_RX = re.compile(
    r"^\s*(?P<group>\d{1,3})\.(?P<item>\d{1,3})\.(?:\s+|$)(?P<body>.*)$"
)


@dataclass(frozen=True)
class HierarchicalMarkerEvent:
    line_index: int
    page: int
    group: int
    item: int
    x0: float
    y0: float
    body: str


def explicit_hierarchical_marker(text: str) -> Tuple[int | None, int | None, str]:
    match = _HIERARCHICAL_RX.match(str(text or ""))
    if not match:
        return None, None, str(text or "").strip()
    return int(match.group("group")), int(match.group("item")), match.group("body").strip()


def _events(lines: Sequence[LayoutLine]) -> List[HierarchicalMarkerEvent]:
    events: List[HierarchicalMarkerEvent] = []
    for index, line in enumerate(lines):
        group, item, body = explicit_hierarchical_marker(line.text)
        if group is None or item is None:
            continue
        events.append(HierarchicalMarkerEvent(
            line_index=index,
            page=int(line.page),
            group=int(group),
            item=int(item),
            x0=float(line.x0),
            y0=float(line.y0),
            body=body,
        ))
    return events


def _best_exact_sequence(events: Sequence[HierarchicalMarkerEvent]) -> List[HierarchicalMarkerEvent]:
    """Return the longest 1..N sequence for one group at a stable x position."""
    best: List[HierarchicalMarkerEvent] = []
    groups = sorted({event.group for event in events})
    for group in groups:
        group_events = [event for event in events if event.group == group]
        # A genuine chapter-local bibliography should keep its markers at one
        # margin.  Try each observed x as the cluster centre rather than using a
        # global page assumption.
        for centre in [event.x0 for event in group_events]:
            cluster = [event for event in group_events if abs(event.x0 - centre) <= 8.0]
            cluster.sort(key=lambda event: (event.page, event.y0, event.line_index))
            starts = [i for i, event in enumerate(cluster) if event.item == 1]
            for start in starts:
                expected = 1
                sequence: List[HierarchicalMarkerEvent] = []
                for event in cluster[start:]:
                    if event.item == expected:
                        sequence.append(event)
                        expected += 1
                if len(sequence) > len(best):
                    best = sequence
    return best


def _segment(lines: Sequence[LayoutLine], sequence: Sequence[HierarchicalMarkerEvent]) -> List[Dict]:
    output: List[Dict] = []
    if not sequence:
        return output
    for pos, event in enumerate(sequence):
        start = event.line_index
        end = sequence[pos + 1].line_index if pos + 1 < len(sequence) else len(lines)
        chunk = list(lines[start:end])
        if not chunk:
            continue
        texts: List[str] = []
        for i, line in enumerate(chunk):
            text = str(line.text or "").strip()
            if not text:
                continue
            if i == 0:
                group, item, body = explicit_hierarchical_marker(text)
                if group == event.group and item == event.item:
                    text = body
            if text:
                texts.append(text)
        reference = re.sub(r"\s+", " ", " ".join(texts)).strip()
        if not reference:
            continue
        pages = sorted({int(line.page) for line in chunk}) or [event.page]
        output.append({
            "reference_text": f"{event.group}.{event.item}. {reference}",
            "annotation_text": "",
            "style": "hierarchical_numeric",
            "reference_start_page": int(event.page),
            "reference_end_page": int(pages[-1]),
            "reference_start_x": round(float(event.x0), 2),
            "boundary_evidence": "hierarchical_numeric_exact_sequence",
            "audit_flags": "marker_regime_v0_6_5",
        })
    return output


def _quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(item.get("reference_text", "")).strip() for item in segments]
    words = [len(text.split()) for text in texts if text]
    evidence = sum(
        bool(YEAR_OR_SOURCE_RX.search(text) or SIN_FECHA_RX.search(text))
        for text in texts
    )
    return {
        "n_segments": len(texts),
        "n_giant_segments": sum(value >= 500 for value in words),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "evidence_ratio": round(evidence / max(len(texts), 1), 3),
    }


def build_hierarchical_marker_repair(
    zone: AdaptiveLayoutZone,
    base_records: Sequence[Dict],
) -> Dict:
    """Build a strict hierarchical-marker resegmentation candidate.

    Acceptance requires at least three consecutive markers beginning at item 1,
    one shared group prefix, a stable x cluster, a changed record count and high
    bibliographic evidence in the resulting chunks.  This prevents ordinary
    section numbering (``5.1``, ``5.2``) from becoming a bibliography merely by
    resembling a marker.
    """
    events = _events(zone.lines)
    sequence = _best_exact_sequence(events)
    if len(sequence) < 3:
        return {
            "accepted": False,
            "reason": "no_sustained_hierarchical_marker_sequence",
            "version": MARKER_REGIME_VERSION,
            "n_events": len(events),
            "sequence_length": len(sequence),
        }

    group = sequence[0].group
    if any(event.group != group for event in sequence):
        return {"accepted": False, "reason": "mixed_hierarchical_groups", "version": MARKER_REGIME_VERSION}

    # Exact item continuity is a hard contract.
    items = [event.item for event in sequence]
    if items != list(range(1, len(items) + 1)):
        return {"accepted": False, "reason": "hierarchical_sequence_not_exact", "version": MARKER_REGIME_VERSION}

    x_values = [event.x0 for event in sequence]
    x_median = float(statistics.median(x_values))
    x_support = sum(abs(value - x_median) <= 8.0 for value in x_values) / len(x_values)
    if x_support < 0.90:
        return {
            "accepted": False,
            "reason": "hierarchical_marker_margin_unstable",
            "version": MARKER_REGIME_VERSION,
            "x_support": round(x_support, 3),
        }

    segments = _segment(zone.lines, sequence)
    quality = _quality(segments)
    base_n = len(base_records)
    new_n = len(segments)
    gain = new_n - base_n
    # For a three-item local bibliography, require at least one newly recovered
    # boundary; for larger sequences, permit both under- and over-segmentation
    # correction as long as the exact marker backbone is complete.
    changed = new_n != base_n
    accepted = bool(
        changed
        and new_n == len(sequence)
        and quality["n_giant_segments"] == 0
        and 2 <= quality["median_words"] <= 180
        and quality["evidence_ratio"] >= 0.55
        and x_support >= 0.90
    )
    return {
        "accepted": accepted,
        "reason": "hierarchical_numeric_sequence_resegmented" if accepted else "hierarchical_marker_candidate_failed_gate",
        "version": MARKER_REGIME_VERSION,
        "group_prefix": group,
        "sequence_first": 1,
        "sequence_last": len(sequence),
        "sequence_length": len(sequence),
        "n_events": len(events),
        "x_median": round(x_median, 2),
        "x_support": round(x_support, 3),
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        "record_delta": gain,
        **quality,
        "segments": segments,
    }
