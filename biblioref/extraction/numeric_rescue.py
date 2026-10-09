"""Numeric bibliography rescue candidates for BiblioRef v0.9.3.

All helpers in this module are *candidate builders*.  They never modify the
stable/effective extraction unless the caller explicitly selects the matching
rescue profile.

Two distinct failure families are intentionally separated:

``numeric_filter``
    The stable segmentation already contains a complete 1..N backbone and a
    few isolated false numeric boundaries.  Only those extras are removed.

``numeric_layout_resegmentation``
    True numeric markers are present in the PDF layout but were lost/merged by
    stable segmentation.  Records are rebuilt directly from raw marker anchors.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import re
import statistics
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from biblioref.ingestion.backend_context import pymupdf

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine
from biblioref.extraction.column_reflow import _raw_page_lines, _column_geometry


_BRACKET_MARKER_RX = re.compile(r"^\s*\[(\d{1,4})\]\s*(.*)$")
_PAREN_MARKER_RX = re.compile(r"^\s*\((\d{1,4})\)\s*(.*)$")
_DOT_MARKER_RX = re.compile(r"^\s*(\d{1,4})[.)]\s+(.*)$")
_STANDALONE_PUNCT_MARKER_RX = re.compile(r"^\s*(\d{1,4})([.)])\s*$")
_BARE_INLINE_MARKER_RX = re.compile(r"^\s*(\d{1,3})\s*(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])(.{3,})$")
_CONTINUATION_FRAGMENT_RX = re.compile(
    r"^(?:doi\s*[:]?\s*10\.|https?://|www\.|(?:pp?\.?\s*)?\d{1,4}(?:[-–—]\d{1,4})?\s*[.;,:]?$)",
    re.I,
)


def explicit_numeric_marker(text: str) -> Tuple[int | None, str | None, str]:
    """Return (value, syntax, remainder) for an explicit record marker.

    Bare leading integers are deliberately excluded here.  A four-digit year
    or page number must never become a marker merely because it starts a line.
    Detached marker columns are handled by the raw-layout path below.
    """
    raw = str(text or "")
    for syntax, rx in (
        ("bracket", _BRACKET_MARKER_RX),
        ("paren", _PAREN_MARKER_RX),
        ("dot", _DOT_MARKER_RX),
    ):
        match = rx.match(raw)
        if match:
            return int(match.group(1)), syntax, match.group(2).strip()
    return None, None, raw.strip()


def _longest_prefix_backbone(candidates: Sequence[Dict]) -> Dict:
    """Find an ordered 1..N backbone while allowing unrelated extras.

    The prefix is intentionally anchored at 1.  Filtering a zone that begins
    mid-sequence is unsafe because a missing true marker and an isolated false
    marker are then difficult to distinguish.
    """
    if not candidates:
        return {"positions": [], "values": [], "end": 0}
    starts = [i for i, item in enumerate(candidates) if int(item["value"]) == 1]
    best_positions: List[int] = []
    best_values: List[int] = []
    for start in starts:
        expected = 1
        positions: List[int] = []
        values: List[int] = []
        for idx in range(start, len(candidates)):
            value = int(candidates[idx]["value"])
            if value == expected:
                positions.append(idx)
                values.append(value)
                expected += 1
        if len(values) > len(best_values):
            best_positions, best_values = positions, values
    return {
        "positions": best_positions,
        "values": best_values,
        "end": best_values[-1] if best_values else 0,
    }


def _safe_numeric_continuation_fragment(record: Dict) -> bool:
    """Return True for a short continuation misread as a numeric marker.

    Numeric bibliographies often wrap a DOI or page fragment onto a new physical
    line.  Stable author/year heuristics can then interpret the leading digits
    (for example ``37. doi:...``) as a fresh numbered reference.  We only
    suppress that boundary when the remainder is unmistakably continuation-like
    and short; ordinary numbered references remain untouched.
    """
    text = str(record.get("reference_text", "") or "").strip()
    value, syntax, remainder = explicit_numeric_marker(text)
    if value is None or syntax is None:
        return False
    remainder = remainder.strip()
    if not remainder or len(remainder.split()) > 8 or len(remainder) > 180:
        return False
    return bool(_CONTINUATION_FRAGMENT_RX.search(remainder))


def numeric_filter_support(records: Sequence[Dict]) -> Dict:
    """Identify a *complete* explicit 1..N backbone plus safe extra markers.

    This is deliberately stricter than the v0.9.2 numeric-sequence gate.  In
    particular, a marker N+2 shortly after a 1..N prefix is treated as evidence
    that true marker N+1 may have been merged, so the filter abstains.
    """
    candidates: List[Dict] = []
    syntax_counts: Dict[str, int] = {}
    for pos, record in enumerate(records):
        value, syntax, _ = explicit_numeric_marker(record.get("reference_text", ""))
        if value is None or syntax is None:
            continue
        syntax_counts[syntax] = syntax_counts.get(syntax, 0) + 1
        candidates.append({"record_position": pos, "value": value, "syntax": syntax})

    if len(candidates) < 8:
        return {"eligible": False, "reason": "too_few_explicit_numeric_markers", "candidates": candidates}

    dominant_syntax = max(syntax_counts, key=lambda key: (syntax_counts[key], key))
    dominant = [item for item in candidates if item["syntax"] == dominant_syntax]
    backbone = _longest_prefix_backbone(dominant)
    n = int(backbone["end"])
    if n < 8:
        return {
            "eligible": False,
            "reason": "no_long_complete_prefix_from_one",
            "dominant_syntax": dominant_syntax,
            "backbone_end": n,
            "candidates": dominant,
        }

    backbone_indices = set(backbone["positions"])
    extras = [item for i, item in enumerate(dominant) if i not in backbone_indices]
    if not extras:
        return {
            "eligible": False,
            "reason": "complete_numeric_sequence_has_no_extra_markers",
            "dominant_syntax": dominant_syntax,
            "backbone_end": n,
            "n_backbone": len(backbone["values"]),
            "extras": [],
        }

    final_backbone_dom_index = max(backbone_indices)
    annotated_extras: List[Dict] = []
    unsafe: List[Dict] = []
    for dom_index, item in enumerate(dominant):
        if dom_index in backbone_indices:
            continue
        value = int(item["value"])
        location = "trailing" if dom_index > final_backbone_dom_index else "interleaved"
        entry = {**item, "dominant_index": dom_index, "location": location}
        annotated_extras.append(entry)
        # A near-future value (N+2, N+3, ...) strongly suggests that marker
        # N+1 was lost.  Do not prune anything in that situation (Sennefelder).
        if n < value <= n + 5:
            unsafe.append({**entry, "unsafe_reason": "near_future_marker_after_prefix"})
        # Interleaved duplicates / values inside 1..N are ambiguous.  Trailing
        # duplicates are safe once the full sequence has already completed.
        elif location == "interleaved" and value <= n:
            record = records[int(item["record_position"])]
            if _safe_numeric_continuation_fragment(record):
                entry["safe_reason"] = "short_doi_or_page_continuation_fragment"
            else:
                unsafe.append({**entry, "unsafe_reason": "interleaved_marker_inside_backbone_range"})
        elif location == "interleaved" and value <= n + 5:
            unsafe.append({**entry, "unsafe_reason": "interleaved_near_sequence_value"})

    # A second marker syntax is only unsafe while the true 1..N sequence is
    # still unfolding.  Once the complete backbone has already finished,
    # trailing duplicate markers (for example bracketed citation call-outs in
    # article body text) are safe to discard with the same filter.  This keeps
    # the rule structural rather than tied to a particular thesis.
    final_backbone_record_pos = max(dominant[i]["record_position"] for i in backbone["positions"])
    mixed_syntax = [item for item in candidates if item["syntax"] != dominant_syntax]
    for item in mixed_syntax:
        value = int(item["value"])
        if int(item["record_position"]) > final_backbone_record_pos and value <= n:
            annotated_extras.append({**item, "dominant_index": None, "location": "trailing", "mixed_syntax": True})
        else:
            unsafe.append({**item, "unsafe_reason": "mixed_marker_syntax_before_backbone_complete"})

    max_extras = max(8, int(round(n * 0.15)))
    eligible = bool(
        n >= 8
        and not unsafe
        and 1 <= len(annotated_extras) <= max_extras
        and len(backbone["values"]) == n
    )
    return {
        "eligible": eligible,
        "reason": "complete_numeric_backbone_with_safe_extra_markers" if eligible else "numeric_filter_gate_not_met",
        "dominant_syntax": dominant_syntax,
        "backbone_start": 1,
        "backbone_end": n,
        "n_backbone": len(backbone["values"]),
        "n_explicit_candidates": len(candidates),
        "n_extras": len(annotated_extras),
        "extras": annotated_extras,
        "unsafe_extras": unsafe,
        "backbone_record_positions": [dominant[i]["record_position"] for i in backbone["positions"]],
    }


def numeric_filter_candidate(records: Sequence[Dict]) -> Dict:
    support = numeric_filter_support(records)
    if not support.get("eligible"):
        return {"accepted": False, **support}

    backbone_positions = {int(x) for x in support["backbone_record_positions"]}
    extras_by_pos = {int(x["record_position"]): x for x in support["extras"]}
    final_backbone_record_pos = max(backbone_positions)
    rebuilt: List[Dict] = []
    for pos, record in enumerate(records):
        item = copy.deepcopy(record)
        if pos in backbone_positions:
            rebuilt.append(item)
            continue
        extra = extras_by_pos.get(pos)
        if extra is None:
            # Non-explicit continuation record created by stable segmentation.
            # It is not part of this filter's evidence; preserve it.
            rebuilt.append(item)
            continue
        if extra["location"] == "trailing" and pos > final_backbone_record_pos:
            # Full 1..N already completed.  Trailing numbered body/figure text
            # belongs outside the bibliography candidate, so drop it.
            continue
        if not rebuilt:
            return {"accepted": False, "reason": "leading_extra_cannot_be_safely_merged", **support}
        _, _, continuation = explicit_numeric_marker(item.get("reference_text", ""))
        previous = rebuilt[-1]
        if continuation:
            previous["reference_text"] = (
                str(previous.get("reference_text", "")).rstrip() + " " + continuation
            ).strip()
        previous["reference_end_page"] = max(
            int(previous.get("reference_end_page", 0) or 0),
            int(item.get("reference_end_page", 0) or 0),
        )
        flags = [x for x in str(previous.get("audit_flags", "")).split(";") if x]
        if "numeric_filter_extra_merged" not in flags:
            flags.append("numeric_filter_extra_merged")
        previous["audit_flags"] = ";".join(flags)

    values = [explicit_numeric_marker(r.get("reference_text", ""))[0] for r in rebuilt]
    values = [int(v) for v in values if v is not None]
    # The candidate must now expose exactly one 1..N backbone and contain no
    # additional explicit marker values.
    n = int(support["backbone_end"])
    accepted = bool(values == list(range(1, n + 1)) and len(rebuilt) < len(records))
    return {
        "accepted": accepted,
        "reason": "safe_extra_numeric_boundaries_removed" if accepted else "numeric_filter_candidate_failed_postcheck",
        "n_base_segments": len(records),
        "n_enhanced_segments": len(rebuilt),
        **support,
        "segments": rebuilt,
    }


# ---------------------------------------------------------------------------
# Raw-layout numeric resegmentation

@dataclass
class _MarkerEvent:
    page: int
    value: int
    marker_x: float
    marker_y: float
    body_x: float
    body_y: float
    syntax: str


def _page_spans(page) -> List[Dict]:
    output: List[Dict] = []
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text", ""))
                if not text.strip():
                    continue
                x0, y0, x1, y1 = [float(x) for x in span["bbox"]]
                output.append({
                    "text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                    "size": float(span.get("size", 0.0)),
                })
    return output


def _span_center_y(span: Dict) -> float:
    return (float(span["y0"]) + float(span["y1"])) / 2.0


def _marker_events_for_page(page, page_number: int) -> List[_MarkerEvent]:
    spans = _page_spans(page)
    events: List[_MarkerEvent] = []
    for span in spans:
        raw = str(span["text"])
        stripped = raw.strip()

        value = None
        syntax = None
        remainder = ""

        # A very common PDF layout stores ``103)`` / ``103.`` in its own span
        # and the author text in the next span on the same baseline.  Treat it
        # as a detached marker with punctuation rather than requiring text to
        # follow inside the marker span itself.
        standalone = _STANDALONE_PUNCT_MARKER_RX.fullmatch(stripped)
        if standalone:
            value = int(standalone.group(1))
            cy = _span_center_y(span)
            companions = [
                other for other in spans
                if float(other["x0"]) >= float(span["x1"]) - 0.5
                and 0.0 <= max(0.0, float(other["x0"]) - float(span["x1"])) <= 120.0
                and abs(_span_center_y(other) - cy) <= 6.0
                and len(str(other["text"]).strip()) >= 2
            ]
            if companions:
                companion = min(companions, key=lambda item: float(item["x0"]))
                events.append(_MarkerEvent(
                    page=page_number, value=value, marker_x=float(span["x0"]), marker_y=float(span["y0"]),
                    body_x=float(companion["x0"]), body_y=float(companion["y0"]), syntax="detached_punct",
                ))
            continue

        # Some biomedical theses use a bare ordered-list prefix (``12 Author``)
        # without punctuation.  We do not expose this as a general record marker
        # because bare numbers are ambiguous; at raw-layout level it is only a
        # candidate event and must later form an exact 1..N sequence to be used.
        bare_inline = _BARE_INLINE_MARKER_RX.fullmatch(stripped)
        if bare_inline:
            events.append(_MarkerEvent(
                page=page_number, value=int(bare_inline.group(1)), marker_x=float(span["x0"]), marker_y=float(span["y0"]),
                body_x=float(span["x0"]), body_y=float(span["y0"]), syntax="bare_inline",
            ))
            continue

        # Explicit markers may share a span with the beginning of the entry.
        value, syntax, remainder = explicit_numeric_marker(stripped)
        if value is not None:
            body_x = float(span["x0"])
            body_y = float(span["y0"])
            events.append(_MarkerEvent(
                page=page_number, value=int(value), marker_x=float(span["x0"]), marker_y=float(span["y0"]),
                body_x=body_x, body_y=body_y, syntax=str(syntax),
            ))
            continue

        # Detached marker columns: a span containing only an integer aligned
        # just to the left of a text span on the same visual baseline.
        match = re.fullmatch(r"\s*(\d{1,3})\s*", raw)
        if not match:
            continue
        value = int(match.group(1))
        cy = _span_center_y(span)
        companions = [
            other for other in spans
            if float(other["x0"]) >= float(span["x1"]) + 7.0
            and 0.0 <= float(other["x0"]) - float(span["x1"]) <= 95.0
            and abs(_span_center_y(other) - cy) <= 4.8
            and len(str(other["text"]).strip()) >= 2
        ]
        if not companions:
            continue
        companion = min(companions, key=lambda item: float(item["x0"]))
        events.append(_MarkerEvent(
            page=page_number, value=value, marker_x=float(span["x0"]), marker_y=float(span["y0"]),
            body_x=float(companion["x0"]), body_y=float(companion["y0"]), syntax="detached",
        ))
    return events


def _x_cluster(events: Sequence[_MarkerEvent], tolerance: float = 5.0) -> List[_MarkerEvent]:
    """Return the densest marker-margin cluster regardless of punctuation syntax.

    Real bibliographies can switch from ``1 Author`` to a detached ``33`` or
    from ``12)`` to ``13.`` after a page/layout transition.  Stable x geometry
    plus an exact numeric sequence is stronger evidence than punctuation
    uniformity, so syntax is deliberately not part of the cluster key.
    """
    best: List[_MarkerEvent] = []
    for event in events:
        group = [other for other in events if abs(other.marker_x - event.marker_x) <= tolerance]
        if len(group) > len(best):
            best = group
    return sorted(best, key=lambda e: (e.page, e.body_y, e.marker_y))


def _sequence_from_events(events: Sequence[_MarkerEvent]) -> List[_MarkerEvent]:
    """Longest ordered exact prefix 1..N inside one marker-x cluster."""
    starts = [i for i, event in enumerate(events) if int(event.value) == 1]
    best: List[_MarkerEvent] = []
    for start in starts:
        expected = 1
        seq: List[_MarkerEvent] = []
        for event in events[start:]:
            value = int(event.value)
            if value == expected:
                seq.append(event)
                expected += 1
        if len(seq) > len(best):
            best = seq
    return best


def _raw_column_lines(pdf_path: str | Path, zone: AdaptiveLayoutZone, marker_x: float, syntax: str) -> Tuple[List[LayoutLine], Dict]:
    output: List[LayoutLine] = []
    strong_two_column_pages: List[int] = []
    with pymupdf.open(str(pdf_path)) as doc:
        for page_number in range(zone.start_page, min(zone.end_page, doc.page_count) + 1):
            page = doc[page_number - 1]
            raw = _raw_page_lines(page, page_number)
            geom = _column_geometry(raw, float(page.rect.width))
            if geom.get("strong"):
                strong_two_column_pages.append(page_number)
            # If markers live in the right column, selecting x>=marker_x keeps
            # the reference column while discarding the body column.  If they
            # live in the left column of a strong two-column page, this rescue
            # abstains later and delegates to multi-column reflow v2.
            selected = [line for line in raw if float(line.x0) >= marker_x - 7.0]
            selected.sort(key=lambda line: (line.page, line.y0, line.x0))
            output.extend(selected)
    return output, {"strong_two_column_pages": strong_two_column_pages}


def _coalesce_same_baseline(lines: Sequence[LayoutLine], tolerance: float = 2.8) -> List[LayoutLine]:
    """Merge adjacent PDF fragments that share a visual baseline."""
    ordered = sorted(lines, key=lambda line: (line.page, line.y0, line.x0))
    groups: List[List[LayoutLine]] = []
    for line in ordered:
        if groups and int(groups[-1][0].page) == int(line.page) and abs(float(groups[-1][0].y0) - float(line.y0)) <= tolerance:
            groups[-1].append(line)
        else:
            groups.append([line])
    output: List[LayoutLine] = []
    for group in groups:
        parts = sorted(group, key=lambda line: line.x0)
        text = re.sub(r"\s+", " ", " ".join(line.text.strip() for line in parts if line.text.strip())).strip()
        if not text:
            continue
        output.append(LayoutLine(
            page=int(parts[0].page), page_height=float(parts[0].page_height), text=text,
            x0=min(float(x.x0) for x in parts), y0=min(float(x.y0) for x in parts),
            x1=max(float(x.x1) for x in parts), y1=max(float(x.y1) for x in parts),
            median_font_size=float(statistics.median([float(x.median_font_size) for x in parts])),
            fragment_count=sum(int(x.fragment_count) for x in parts),
        ))
    return output


def _segment_from_marker_events(lines: Sequence[LayoutLine], events: Sequence[_MarkerEvent], style: str = "numeric") -> List[Dict]:
    if not events:
        return []
    ordered = list(lines)
    segments: List[Dict] = []
    for index, event in enumerate(events):
        start_key = (int(event.page), float(event.body_y) - 4.0)
        if index + 1 < len(events):
            next_event = events[index + 1]
            end_key = (int(next_event.page), float(next_event.body_y) - 4.0)
            selected = [line for line in ordered if (int(line.page), float(line.y0)) >= start_key and (int(line.page), float(line.y0)) < end_key]
        else:
            # Avoid swallowing a later chapter/publication when the stable zone
            # overextends.  The final entry is allowed to consume the remainder
            # of the page containing its marker only.
            selected = [line for line in ordered if int(line.page) == int(event.page) and float(line.y0) >= float(event.body_y) - 4.0]

        texts: List[str] = []
        for line in selected:
            text = line.text.strip()
            if not text:
                continue
            # Remove a standalone detached marker line.
            if re.fullmatch(rf"\s*{int(event.value)}(?:[.)])?\s*", text):
                continue
            if not texts:
                # Normalize whatever marker syntax the PDF used.
                value, _, remainder = explicit_numeric_marker(text)
                if value == int(event.value):
                    text = remainder
                elif event.syntax == "bare_inline":
                    text = re.sub(rf"^\s*{int(event.value)}\s*", "", text, count=1).strip()
                else:
                    text = re.sub(rf"^\s*{int(event.value)}\s+", "", text).strip()
            if text:
                texts.append(text)
        reference = re.sub(r"\s+", " ", " ".join(texts)).strip()
        if not reference:
            continue
        pages = sorted({int(line.page) for line in selected}) or [int(event.page)]
        segments.append({
            "reference_text": f"{int(event.value)}. {reference}".strip(),
            "annotation_text": "",
            "style": style,
            "reference_start_page": int(event.page),
            "reference_end_page": int(pages[-1]),
            "reference_start_x": round(float(event.marker_x), 2),
            "boundary_evidence": f"raw_layout_{event.syntax}_numeric_marker",
            "audit_flags": "raw_numeric_layout_resegmentation",
        })
    return segments


def _segments_quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(x.get("reference_text", "")).strip() for x in segments if str(x.get("reference_text", "")).strip()]
    words = [len(text.split()) for text in texts]
    evidence = sum(bool(YEAR_OR_SOURCE_RX.search(text)) for text in texts)
    values = [explicit_numeric_marker(text)[0] for text in texts]
    values = [int(v) for v in values if v is not None]
    return {
        "n_segments": len(texts),
        "n_giant_segments": sum(n >= 500 for n in words),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "evidence_ratio": round(evidence / max(1, len(texts)), 3),
        "numeric_values": values,
        "complete_prefix": bool(values == list(range(1, len(values) + 1))),
    }



def extend_numeric_candidate_end_page(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
    max_forward_pages: int = 3,
) -> Dict:
    """Extend a candidate bibliography only when an exact 1..N marker sequence continues.

    Reference-density discovery can stop one page early when the final page is
    short.  For candidate (non-stable) zones, an exact next marker N+1 on the
    immediately following page is stronger structural evidence than density.
    The helper never changes stable zones and never skips a page.
    """
    start_page = int(start_page)
    end_page = int(end_page)
    if start_page <= 0 or end_page < start_page:
        return {"extended": False, "end_page": end_page, "reason": "invalid_page_range"}
    events: List[_MarkerEvent] = []
    with pymupdf.open(str(pdf_path)) as doc:
        capped_end = min(end_page, doc.page_count)
        for page_number in range(start_page, capped_end + 1):
            events.extend(_marker_events_for_page(doc[page_number - 1], page_number))
        if not events:
            return {"extended": False, "end_page": end_page, "reason": "no_numeric_events"}

        clusters: List[List[_MarkerEvent]] = []
        seen = set()
        for event in events:
            key = round(float(event.marker_x) / 5.0)
            if key in seen:
                continue
            seen.add(key)
            cluster = _x_cluster([e for e in events if abs(float(e.marker_x) - float(event.marker_x)) <= 6.0], tolerance=6.0)
            if cluster:
                clusters.append(cluster)
        best_seq: List[_MarkerEvent] = []
        for cluster in clusters:
            seq = _sequence_from_events(cluster)
            if len(seq) > len(best_seq):
                best_seq = seq
        if len(best_seq) < 8 or int(best_seq[0].value) != 1:
            return {"extended": False, "end_page": end_page, "reason": "no_long_exact_prefix"}

        marker_x = float(statistics.median([event.marker_x for event in best_seq]))
        expected = int(best_seq[-1].value) + 1
        extended_end = capped_end
        recovered: List[int] = []
        max_page = min(doc.page_count, capped_end + max(0, int(max_forward_pages)))
        for page_number in range(capped_end + 1, max_page + 1):
            page_events = sorted(
                [
                    event for event in _marker_events_for_page(doc[page_number - 1], page_number)
                    if abs(float(event.marker_x) - marker_x) <= 7.0
                ],
                key=lambda event: (float(event.marker_y), float(event.body_y)),
            )
            start_idx = next((i for i, event in enumerate(page_events) if int(event.value) == expected), None)
            if start_idx is None:
                break
            page_recovered: List[int] = []
            for event in page_events[start_idx:]:
                if int(event.value) == expected:
                    page_recovered.append(expected)
                    expected += 1
            if not page_recovered:
                break
            recovered.extend(page_recovered)
            extended_end = page_number

        return {
            "extended": extended_end > end_page,
            "end_page": int(extended_end),
            "original_end_page": int(end_page),
            "marker_x": round(marker_x, 2),
            "prefix_last": int(best_seq[-1].value),
            "continued_values": recovered,
            "reason": "exact_numeric_marker_continuity" if extended_end > end_page else "no_immediate_next_marker",
        }

def build_numeric_layout_resegmentation(pdf_path: str | Path, zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    """Rebuild a numeric zone from raw PDF marker anchors.

    Supports conventional explicit markers and detached marker columns.  A
    left-column sequence on a strong two-column page is deliberately deferred
    to ``multi_column_reflow_v2`` because page/column order is then essential.
    """
    events: List[_MarkerEvent] = []
    with pymupdf.open(str(pdf_path)) as doc:
        for page_number in range(zone.start_page, min(zone.end_page, doc.page_count) + 1):
            events.extend(_marker_events_for_page(doc[page_number - 1], page_number))
    if not events:
        return {"accepted": False, "reason": "no_raw_numeric_marker_events"}

    # Evaluate x/syntax clusters and keep the cluster producing the longest
    # exact 1..N sequence.
    clusters: List[List[_MarkerEvent]] = []
    seen = set()
    for event in events:
        key = round(event.marker_x / 5.0)
        if key in seen:
            continue
        seen.add(key)
        cluster = _x_cluster([e for e in events if abs(e.marker_x - event.marker_x) <= 6.0], tolerance=6.0)
        if cluster:
            clusters.append(cluster)
    best_seq: List[_MarkerEvent] = []
    for cluster in clusters:
        seq = _sequence_from_events(cluster)
        if len(seq) > len(best_seq):
            best_seq = seq
    if len(best_seq) < 4:
        return {"accepted": False, "reason": "no_complete_raw_numeric_sequence", "n_raw_events": len(events)}

    marker_x = float(statistics.median([event.marker_x for event in best_seq]))
    syntaxes = sorted({event.syntax for event in best_seq})
    syntax = best_seq[0].syntax if len(syntaxes) == 1 else "mixed_numeric"

    # If the next expected marker exists later in the same detected zone but
    # at a materially different x-position, the chosen x-cluster is only one
    # column of a multi-column bibliography.  Returning that partial sequence
    # would be destructive; defer to the column reflow rescue instead.
    last = best_seq[-1]
    next_value = int(last.value) + 1
    later_next_other_column = [
        event for event in events
        if int(event.value) == next_value
        and (int(event.page), float(event.marker_y)) > (int(last.page), float(last.marker_y))
        and abs(float(event.marker_x) - marker_x) > 8.0
    ]
    if later_next_other_column:
        return {
            "accepted": False,
            "reason": "numeric_sequence_continues_in_other_column",
            "n_raw_events": len(events),
            "sequence_length": len(best_seq),
            "sequence_next": next_value,
            "marker_x": round(marker_x, 2),
            "next_marker_x": round(float(later_next_other_column[0].marker_x), 2),
        }

    raw_lines, geom = _raw_column_lines(pdf_path, zone, marker_x, syntax)

    # A sequence occupying a left column on strong two-column pages may have a
    # continuation in the right column.  Defer rather than return a partial
    # candidate (Ball).
    if geom["strong_two_column_pages"]:
        with pymupdf.open(str(pdf_path)) as doc:
            mids = []
            for page_number in geom["strong_two_column_pages"]:
                mids.append(float(doc[page_number - 1].rect.width) / 2.0)
        mid = float(statistics.median(mids)) if mids else 0.0
        if marker_x < mid - 15.0:
            return {
                "accepted": False,
                "reason": "left_column_numeric_sequence_requires_multi_column_reflow",
                "n_raw_events": len(events),
                "sequence_length": len(best_seq),
                "marker_x": round(marker_x, 2),
                **geom,
            }

    visual_lines = _coalesce_same_baseline(raw_lines)
    segments = _segment_from_marker_events(visual_lines, best_seq)
    quality = _segments_quality(segments)
    base_n = len(base_records)
    new_n = len(segments)
    strong_geometry = bool({"detached", "detached_punct"}.intersection(syntaxes)) or new_n >= 8
    # Recovering one missing reference is useful when the raw explicit marker
    # sequence itself is complete.  Reductions remain more conservative: an
    # explicit-layout candidate must remove at least two segments unless the
    # detached-marker geometry provides the stronger anchor.
    changed_enough = bool(
        new_n != base_n
        and (
            (new_n > base_n and (new_n - base_n) >= 1)
            or (new_n < base_n and ((base_n - new_n) >= 2 or ({"detached", "detached_punct"}.intersection(syntaxes) and (base_n - new_n) >= 1)))
        )
    )
    reduction_coverage_ok = bool(new_n >= base_n or new_n >= max(8, int(round(base_n * 0.75))))
    accepted = bool(
        strong_geometry
        and changed_enough
        and reduction_coverage_ok
        and quality["complete_prefix"]
        and quality["n_giant_segments"] == 0
        and quality["evidence_ratio"] >= 0.60
        and 2 <= quality["median_words"] <= 180
    )
    return {
        "accepted": accepted,
        "reason": "raw_numeric_layout_sequence_resegmented" if accepted else "raw_numeric_layout_candidate_failed_gate",
        "mode": ("mixed_numeric_layout" if len(syntaxes) > 1 else ("detached_marker_column" if syntax in {"detached", "detached_punct"} else "explicit_marker_layout")),
        "n_base_segments": base_n,
        "n_enhanced_segments": new_n,
        "sequence_first": 1,
        "sequence_last": len(best_seq),
        "reduction_coverage_ok": reduction_coverage_ok,
        "marker_x": round(marker_x, 2),
        "marker_syntax": syntax,
        "marker_syntaxes": syntaxes,
        "n_raw_events": len(events),
        **geom,
        **{k: v for k, v in quality.items() if k != "numeric_values"},
        "segments": segments,
    }
