"""Evidence-gated two-column bibliography reflow.

This module never changes global PDF ingestion.  It constructs an alternative
reading order only inside an already detected bibliography zone, and callers
must still apply an explicit quality gate before replacing stable records.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import statistics
from typing import Dict, List, Sequence, Tuple

from biblioref.ingestion.backend_context import pymupdf

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    NUMERIC_MARKER_RX,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    segment_adaptive_layout_zone,
)
from biblioref.detection.repair import repair_decision
from biblioref.adaptive.continuity import wrapped_author_continuation
from biblioref_v0_2 import _numeric_marker_value


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _raw_page_lines(page, page_number: int) -> List[LayoutLine]:
    output: List[LayoutLine] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for raw_line in block.get("lines", []):
            spans = [s for s in raw_line.get("spans", []) if str(s.get("text", "")).strip()]
            if not spans:
                continue
            text = _clean(" ".join(str(s.get("text", "")) for s in spans))
            if not text:
                continue
            sizes = [float(s.get("size", 0.0)) for s in spans if float(s.get("size", 0.0)) > 0]
            output.append(LayoutLine(
                page=page_number,
                page_height=float(page.rect.height),
                text=text,
                x0=min(float(s["bbox"][0]) for s in spans),
                y0=min(float(s["bbox"][1]) for s in spans),
                x1=max(float(s["bbox"][2]) for s in spans),
                y1=max(float(s["bbox"][3]) for s in spans),
                median_font_size=statistics.median(sizes) if sizes else 0.0,
                fragment_count=1,
            ))
    return output


def _low_mode(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    pool = vals[: max(3, int(len(vals) * 0.55))]
    best: List[float] = []
    for center in pool:
        members = [v for v in pool if abs(v - center) <= 5.0]
        if len(members) > len(best):
            best = members
    return statistics.median(best or pool)


def _vertical_gutter_candidate(lines: Sequence[LayoutLine], page_width: float) -> Dict | None:
    """Find a persistent low-occupancy vertical corridor between text columns.

    The former detector required the two x-modes to be separated by 32% of the
    page width.  That was simple but brittle: a genuine two-column bibliography
    at 31.5% separation was rejected.  v0.6.5 instead looks for the geometric
    object that actually defines columns: a vertical gutter with text on both
    sides and very few lines crossing it.
    """
    if len(lines) < 16 or page_width <= 0:
        return None
    lo, hi = page_width * 0.24, page_width * 0.76
    step = 2.0
    xs = []
    x = lo
    while x <= hi:
        xs.append(x)
        x += step
    if not xs:
        return None

    # Occupancy is intentionally tolerant of an occasional full-width heading.
    occupancy = []
    for x in xs:
        count = sum(float(line.x0) + 2.0 < x < float(line.x1) - 2.0 for line in lines)
        occupancy.append(count)
    low_limit = max(1, int(round(len(lines) * 0.06)))

    runs = []
    start = None
    for i, count in enumerate(occupancy + [low_limit + 1]):
        if count <= low_limit and start is None:
            start = i
        elif count > low_limit and start is not None:
            end = i - 1
            width = xs[end] - xs[start] + step
            if width >= 10.0:
                runs.append((start, end, width))
            start = None
    if not runs:
        return None

    best = None
    for start, end, width in runs:
        g0, g1 = xs[start], xs[end] + step
        center = (g0 + g1) / 2.0
        left = [line for line in lines if float(line.x1) <= g1 + 2.0 and float(line.x0) < center]
        right = [line for line in lines if float(line.x0) >= g0 - 2.0 and float(line.x1) > center]
        crossing = [line for line in lines if float(line.x0) < g0 - 2.0 and float(line.x1) > g1 + 2.0]
        if len(left) < 8 or len(right) < 8:
            continue
        crossing_ratio = len(crossing) / max(len(lines), 1)
        if crossing_ratio > 0.16:
            continue
        left_mode = _low_mode([line.x0 for line in left])
        right_mode = _low_mode([line.x0 for line in right])
        shift = right_mode - left_mode
        # A gutter plus two populated sides is primary evidence.  The modest
        # 22% mode-separation floor only prevents dense one-column indents from
        # masquerading as columns.
        if shift < page_width * 0.22:
            continue
        balance = min(len(left), len(right)) / max(len(left), len(right))
        score = width + 18.0 * balance - 40.0 * crossing_ratio
        candidate = {
            "gutter_start": g0, "gutter_end": g1, "gutter_center": center,
            "gutter_width": width, "crossing_ratio": crossing_ratio,
            "left": left, "right": right, "left_mode": left_mode,
            "right_mode": right_mode, "shift": shift, "score": score,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    return best


def _column_geometry(lines: Sequence[LayoutLine], page_width: float) -> Dict:
    body = [
        line for line in lines
        if 0.06 * line.page_height <= line.y0 <= 0.94 * line.page_height
        and len(line.text.strip()) >= 2
    ]
    gutter = _vertical_gutter_candidate(body, page_width)
    if gutter is not None:
        return {
            "strong": True,
            "method": "persistent_vertical_gutter_v0_6_5",
            "mid": float(gutter["gutter_center"]),
            "left": gutter["left"],
            "right": gutter["right"],
            "shift": float(gutter["shift"]),
            "left_mode": float(gutter["left_mode"]),
            "right_mode": float(gutter["right_mode"]),
            "gutter_start": round(float(gutter["gutter_start"]), 2),
            "gutter_end": round(float(gutter["gutter_end"]), 2),
            "gutter_width": round(float(gutter["gutter_width"]), 2),
            "gutter_crossing_ratio": round(float(gutter["crossing_ratio"]), 3),
        }

    # Compatibility fallback for layouts whose text boxes do not expose a clean
    # gutter.  Keep the historical test unchanged here; the new path above is
    # what broadens recall.
    mid = page_width / 2.0
    left = [line for line in body if line.x0 < mid - 8 and line.x1 <= mid + 12]
    right = [line for line in body if line.x0 >= mid - 12]
    strong = len(left) >= 8 and len(right) >= 8
    left_mode = _low_mode([line.x0 for line in left])
    right_mode = _low_mode([line.x0 for line in right])
    shift = right_mode - left_mode
    if shift < page_width * 0.32:
        strong = False
    return {
        "strong": strong,
        "method": "legacy_mode_separation",
        "mid": mid,
        "left": left,
        "right": right,
        "shift": shift,
        "left_mode": left_mode,
        "right_mode": right_mode,
    }


def _normalized(line: LayoutLine, shift: float = 0.0) -> LayoutLine:
    return LayoutLine(
        page=line.page,
        page_height=line.page_height,
        text=line.text,
        x0=line.x0 - shift,
        y0=line.y0,
        x1=line.x1 - shift,
        y1=line.y1,
        median_font_size=line.median_font_size,
        fragment_count=line.fragment_count,
    )


def _obvious_new_section(lines: Sequence[LayoutLine]) -> bool:
    for line in lines[:18]:
        text = _clean(line.text)
        if re.match(r"^(?:\d+\s+)?Publication\s+[IVX\d]+\b", text, re.I):
            return True
        if re.match(r"^(?:APPENDIX|ANEXO|SECTION)\b", text, re.I):
            return True
    return False


def _rough_reference_starts(lines: Sequence[LayoutLine]) -> int:
    count = 0
    for line in lines:
        text = line.text.strip()
        if NUMERIC_MARKER_RX.match(text):
            count += 1
        elif re.match(r"^[A-ZÁÉÍÓÚÑÜ][^,\n]{0,90},", text) and re.search(r"\((?:18|19|20)\d{2}", text[:260]):
            count += 1
    return count


def reflow_two_column_zone(pdf_path: str | Path, zone: AdaptiveLayoutZone) -> Tuple[List[LayoutLine], Dict]:
    """Build a column-major alternative order for one detected bibliography zone."""
    output: List[LayoutLine] = []
    column_pages: List[int] = []
    stopped_at_page = None
    with pymupdf.open(str(pdf_path)) as doc:
        for page_number in range(zone.start_page, min(zone.end_page, doc.page_count) + 1):
            page = doc[page_number - 1]
            raw = _raw_page_lines(page, page_number)
            geom = _column_geometry(raw, float(page.rect.width))
            if geom["strong"]:
                column_pages.append(page_number)
                left = sorted(geom["left"], key=lambda line: (line.y0, line.x0))
                right = sorted(geom["right"], key=lambda line: (line.y0, line.x0))
                if page_number == zone.start_page:
                    heading_right = zone.heading.x0 >= geom["mid"] - 12
                    if heading_right:
                        chosen = [
                            _normalized(line, geom["shift"])
                            for line in right
                            if line.y0 > zone.heading.y1 + 0.5
                        ]
                    else:
                        chosen = [line for line in left if line.y0 > zone.heading.y1 + 0.5]
                        chosen += [_normalized(line, geom["shift"]) for line in right]
                else:
                    chosen = list(left) + [_normalized(line, geom["shift"]) for line in right]
                output.extend(chosen)
                continue

            # Once a clearly two-column reference section reaches a new one-column
            # publication/appendix page with no reference starts, do not absorb it.
            if column_pages and _obvious_new_section(raw):
                stopped_at_page = page_number
                break
            if column_pages and _rough_reference_starts(raw) == 0:
                stopped_at_page = page_number
                break

            page_lines = sorted(raw, key=lambda line: (line.y0, line.x0))
            if page_number == zone.start_page:
                page_lines = [line for line in page_lines if line.y0 > zone.heading.y1 + 0.5]
            output.extend(page_lines)

    return output, {
        "eligible": len(column_pages) >= 2,
        "column_pages": column_pages,
        "n_column_pages": len(column_pages),
        "stopped_at_page": stopped_at_page,
        "n_reflow_lines": len(output),
    }


def _merge_wrapped_author_lines(lines: Sequence[LayoutLine]) -> List[LayoutLine]:
    """Join author lists split immediately before the final author + year.

    This guard is applied only to the evidence-gated column-reflow candidate,
    not to the global stable reading order.
    """
    merged: List[LayoutLine] = []
    for line in lines:
        probe = merged + [line]
        if len(probe) >= 2 and wrapped_author_continuation(len(probe) - 1, probe):
            previous = merged.pop()
            merged.append(LayoutLine(
                page=previous.page,
                page_height=previous.page_height,
                text=_clean(previous.text + " " + line.text),
                x0=previous.x0,
                y0=previous.y0,
                x1=max(previous.x1, line.x1),
                y1=line.y1 if line.page == previous.page else previous.y1,
                median_font_size=statistics.median([previous.median_font_size, line.median_font_size]),
                fragment_count=previous.fragment_count + line.fragment_count,
            ))
            continue
        merged.append(line)
    return merged


def _segment_quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(item.get("reference_text", "")).strip() for item in segments if str(item.get("reference_text", "")).strip()]
    words = [len(text.split()) for text in texts]
    evidence = sum(bool(YEAR_OR_SOURCE_RX.search(text) or NUMERIC_MARKER_RX.match(text)) for text in texts)
    return {
        "n_giant_segments": sum(value >= 500 for value in words),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "evidence_ratio": round(evidence / max(len(texts), 1), 3),
        "n_inherited_date_starts": 0,
    }


def _numeric_values(segments: Sequence[Dict]) -> List[int]:
    values: List[int] = []
    for item in segments:
        value = _numeric_marker_value(str(item.get("reference_text", "")))
        if value is not None:
            values.append(int(value))
    return values


def _numeric_sequence_score(values: Sequence[int]) -> float:
    if len(values) < 2:
        return 0.0
    pairs = list(zip(values, values[1:]))
    return sum(b == a + 1 for a, b in pairs) / len(pairs)


def build_column_reflow_repair(
    pdf_path: str | Path,
    zone: AdaptiveLayoutZone,
    base_records: Sequence[Dict],
) -> Dict:
    lines, geometry = reflow_two_column_zone(pdf_path, zone)
    if not geometry["eligible"] or len(lines) < 8:
        return {"accepted": False, "reason": "no_strong_two_column_geometry", **geometry}

    lines = _merge_wrapped_author_lines(lines)
    style = diagnose_adaptive_style([line.text for line in lines])
    layout = diagnose_adaptive_layout(lines, style)
    candidate_zone = replace(
        zone,
        lines=lines,
        end_page=max((line.page for line in lines), default=zone.start_page),
        style=style,
        layout=layout,
    )
    segments = segment_adaptive_layout_zone(candidate_zone)
    quality = _segment_quality(segments)
    base_values = _numeric_values(base_records)
    new_values = _numeric_values(segments)

    if style.style == "numeric" and len(new_values) >= 4:
        seq = _numeric_sequence_score(new_values)
        base_seq = _numeric_sequence_score(base_values)
        accepted = bool(
            len(segments) >= len(base_records) + 5
            and len(new_values) >= 8
            and seq >= 0.90
            and quality["n_giant_segments"] == 0
            and quality["evidence_ratio"] >= 0.75
        )
        decision = {
            "accepted": accepted,
            "reason": "two_column_numeric_sequence_recovered" if accepted else "numeric_reflow_failed_gate",
            "n_base_segments": len(base_records),
            "n_enhanced_segments": len(segments),
            "base_numeric_sequence_score": round(base_seq, 3),
            "enhanced_numeric_sequence_score": round(seq, 3),
            "base_numeric_first": base_values[0] if base_values else None,
            "base_numeric_last": base_values[-1] if base_values else None,
            "enhanced_numeric_first": new_values[0] if new_values else None,
            "enhanced_numeric_last": new_values[-1] if new_values else None,
            **quality,
        }
    else:
        decision = repair_decision(base_records, segments, quality)
        decision["reason"] = (
            "two_column_author_year_recovered" if decision.get("accepted")
            else "author_year_reflow_failed_gate"
        )

    return {
        **geometry,
        **decision,
        "candidate_style": style.style,
        "segments": segments,
    }

# ---------------------------------------------------------------------------
# v0.9.3 column reflow v2

_EXPLICIT_NUMERIC_LINE_RX = re.compile(
    r"^\s*(?:\[(?P<bracket>\d{1,4})\]|\((?P<paren>\d{1,4})\)|(?P<dot>\d{1,4})[.)])\s+(?P<body>.*)$"
)

_PUBLICATION_BIO_START_RX = re.compile(
    r"^(?:[A-Z][A-Z .\-']{4,}\s+\([^)]*(?:IEEE|Fellow|Member|Senior Member)[^)]*\)\s+(?:was born|received|is|joined)|"
    r"[A-Z][A-Z .\-']{4,}\s+(?:was born|received the|is a|is an|joined the))",
    re.I,
)


def _trim_publication_biography_tail(chunk: Sequence[LayoutLine]) -> List[LayoutLine]:
    """Stop a final reference before an embedded article author biography.

    Publication PDFs often place biographies immediately after the final
    reference, sometimes at the top of the adjacent column.  The trigger is
    lexical (biographical prose) plus prior citation evidence, so ordinary
    reference continuations are preserved.
    """
    if len(chunk) < 2:
        return list(chunk)
    kept: List[LayoutLine] = []
    accumulated = ""
    for line in chunk:
        text = str(line.text or "").strip()
        if kept and _PUBLICATION_BIO_START_RX.search(text) and YEAR_OR_SOURCE_RX.search(accumulated):
            break
        kept.append(line)
        accumulated = (accumulated + " " + text).strip()
    return kept



def _coalesce_reflow_order(lines: Sequence[LayoutLine], tolerance: float = 2.8) -> List[LayoutLine]:
    """Merge adjacent same-baseline fragments without destroying column order.

    ``reflow_two_column_zone`` already returns column-major order.  Sorting the
    whole page by y again would interleave columns and recreate the original
    failure.  Therefore only *adjacent* fragments are coalesced here.
    """
    output: List[LayoutLine] = []
    group: List[LayoutLine] = []

    def flush() -> None:
        nonlocal group
        if not group:
            return
        parts = sorted(group, key=lambda line: line.x0)
        text = _clean(" ".join(line.text.strip() for line in parts if line.text.strip()))
        if text:
            output.append(LayoutLine(
                page=int(parts[0].page), page_height=float(parts[0].page_height), text=text,
                x0=min(float(x.x0) for x in parts), y0=min(float(x.y0) for x in parts),
                x1=max(float(x.x1) for x in parts), y1=max(float(x.y1) for x in parts),
                median_font_size=float(statistics.median([float(x.median_font_size) for x in parts])),
                fragment_count=sum(int(x.fragment_count) for x in parts),
            ))
        group = []

    for line in lines:
        if group:
            same_page = int(line.page) == int(group[0].page)
            same_baseline = abs(float(line.y0) - float(group[0].y0)) <= tolerance
            x_monotonic = float(line.x0) >= float(group[-1].x0) - 2.0
            if not (same_page and same_baseline and x_monotonic):
                flush()
        group.append(line)
    flush()
    return output


def _explicit_line_marker(text: str) -> tuple[int | None, str]:
    match = _EXPLICIT_NUMERIC_LINE_RX.match(str(text or ""))
    if not match:
        return None, str(text or "").strip()
    value = next(int(match.group(name)) for name in ("bracket", "paren", "dot") if match.group(name))
    return value, match.group("body").strip()


def _numeric_prefix_events(lines: Sequence[LayoutLine]) -> List[tuple[int, int]]:
    markers: List[tuple[int, int]] = []
    for index, line in enumerate(lines):
        value, _ = _explicit_line_marker(line.text)
        if value is not None:
            markers.append((index, int(value)))
    starts = [i for i, (_, value) in enumerate(markers) if value == 1]
    best: List[tuple[int, int]] = []
    for start in starts:
        expected = 1
        seq: List[tuple[int, int]] = []
        for index, value in markers[start:]:
            if value == expected:
                seq.append((index, value))
                expected += 1
        if len(seq) > len(best):
            best = seq
    return best


def _segments_from_reflow_prefix(lines: Sequence[LayoutLine], events: Sequence[tuple[int, int]]) -> List[Dict]:
    segments: List[Dict] = []
    if not events:
        return segments
    marker_indices = [index for index, _ in events]
    all_marker_indices = [i for i, line in enumerate(lines) if _explicit_line_marker(line.text)[0] is not None]
    after_last_marker = next((i for i in all_marker_indices if i > marker_indices[-1]), None)

    for pos, (index, value) in enumerate(events):
        end = marker_indices[pos + 1] if pos + 1 < len(marker_indices) else (after_last_marker or len(lines))
        chunk = list(lines[index:end])
        # For the final reference, do not absorb later pages after the last
        # explicit marker; publication biographies/new paper body commonly
        # follow immediately (Ball).
        if pos == len(events) - 1:
            marker_page = int(lines[index].page)
            chunk = [line for line in chunk if int(line.page) == marker_page]
            chunk = _trim_publication_biography_tail(chunk)
        if not chunk:
            continue
        first_value, first_body = _explicit_line_marker(chunk[0].text)
        texts = [first_body if first_value == value else chunk[0].text.strip()]
        texts.extend(line.text.strip() for line in chunk[1:] if line.text.strip())
        text = _clean(" ".join(part for part in texts if part))
        if not text:
            continue
        pages = sorted({int(line.page) for line in chunk})
        segments.append({
            "reference_text": f"{value}. {text}",
            "annotation_text": "",
            "style": "numeric",
            "reference_start_page": int(lines[index].page),
            "reference_end_page": pages[-1] if pages else int(lines[index].page),
            "reference_start_x": round(float(lines[index].x0), 2),
            "boundary_evidence": "two_column_reflow_v2+explicit_numeric_sequence",
            "audit_flags": "two_column_reflow_v2",
        })
    return segments




_REPEATED_AUTHOR_REF_RX = re.compile(r"^\s*[—–-]{1,8}\s*(?:\((?:18|19|20)\d{2}|(?:18|19|20)\d{2})")

def _is_page_number_line(line: LayoutLine) -> bool:
    text = str(line.text or "").strip()
    return bool(re.fullmatch(r"\d{1,4}", text) and float(line.y0) >= float(line.page_height) * 0.82)

def _local_bibliographic_evidence(index: int, lines: Sequence[LayoutLine], width: int = 4) -> bool:
    chunk = []
    page = int(lines[index].page)
    for line in lines[index:index + width]:
        if int(line.page) != page and chunk:
            break
        if _is_page_number_line(line):
            continue
        chunk.append(str(line.text or ""))
    text = _clean(" ".join(chunk))
    return bool(YEAR_OR_SOURCE_RX.search(text))

def _paragraph_gap_column_segments(lines: Sequence[LayoutLine]) -> List[Dict]:
    """Segment a column-major bibliography from local paragraph geometry.

    Within the UNR architecture case, continuation baselines are roughly
    contiguous while new references are separated by a visibly larger vertical
    gap.  This helper generalizes that observation: gap evidence is accepted
    only when the following paragraph contains bibliographic evidence.  A large
    backwards y jump on the same page denotes the transition to the next column.
    Repeated-author em-dash entries are explicit starts even without a blank gap.
    """
    visual = [line for line in _coalesce_reflow_order(lines) if not _is_page_number_line(line)]
    if len(visual) < 8:
        return []
    starts: List[int] = []
    for i, line in enumerate(visual):
        text = str(line.text or "").strip()
        if not text:
            continue
        if i == 0:
            if _local_bibliographic_evidence(i, visual):
                starts.append(i)
            continue
        prev = visual[i - 1]
        same_page = int(prev.page) == int(line.page)
        column_restart = bool(same_page and float(line.y0) < float(prev.y0) - 60.0)
        page_restart = bool(not same_page and _local_bibliographic_evidence(i, visual))
        gap = float(line.y0) - float(prev.y1) if same_page else -999.0
        paragraph_restart = bool(gap >= 7.0 and _local_bibliographic_evidence(i, visual))
        repeated_author = bool(_REPEATED_AUTHOR_REF_RX.match(text) and _local_bibliographic_evidence(i, visual))
        if column_restart or page_restart or paragraph_restart or repeated_author:
            starts.append(i)
    starts = sorted(set(starts))
    if len(starts) < 5:
        return []

    segments: List[Dict] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(visual)
        chunk = visual[start:end]
        text = _clean(" ".join(str(line.text or "") for line in chunk if not _is_page_number_line(line)))
        if not text:
            continue
        pages = sorted({int(line.page) for line in chunk})
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": "author_year_layout",
            "reference_start_page": int(chunk[0].page),
            "reference_end_page": int(pages[-1]),
            "reference_start_x": round(float(chunk[0].x0), 2),
            "boundary_evidence": "column_paragraph_gap_or_repeated_author",
            "audit_flags": "column_layout_regime_v0_6_5",
        })
    return segments

def build_column_reflow_repair_v2(
    pdf_path: str | Path,
    zone: AdaptiveLayoutZone,
    base_records: Sequence[Dict],
) -> Dict:
    """Second-generation optional reflow for publication-style bibliographies.

    v2 first exploits an explicit numeric 1..N sequence *after* column-major
    ordering and same-baseline coalescing.  This directly addresses cases where
    stable segmentation and the v1 style detector are confused by article body
    text.  Author-year two-column zones fall back to the conservative v1 gate.
    """
    reflowed, geometry = reflow_two_column_zone(pdf_path, zone)
    if not geometry.get("eligible") or len(reflowed) < 8:
        return {"accepted": False, "reason": "no_strong_two_column_geometry_v2", **geometry}

    visual = _coalesce_reflow_order(reflowed)
    events = _numeric_prefix_events(visual)
    if len(events) >= 8:
        candidate = _segments_from_reflow_prefix(visual, events)
        quality = _segment_quality(candidate)
        values = _numeric_values(candidate)
        complete = values == list(range(1, len(values) + 1))
        base_n = len(base_records)
        new_n = len(candidate)
        gain = new_n - base_n
        accepted = bool(
            complete
            and new_n >= 8
            and gain >= max(3, int(round(max(1, base_n) * 0.08)))
            and quality["n_giant_segments"] == 0
            and quality["evidence_ratio"] >= 0.70
            and 2 <= quality["median_words"] <= 180
        )
        if accepted:
            return {
                **geometry,
                "accepted": True,
                "reason": "two_column_numeric_prefix_recovered_v2",
                "candidate_style": "numeric",
                "n_base_segments": base_n,
                "n_enhanced_segments": new_n,
                "numeric_first": 1,
                "numeric_last": new_n,
                "numeric_sequence_score": 1.0,
                **quality,
                "segments": candidate,
            }

    # Author-year / humanities bibliographies may have no explicit numeric
    # markers.  Before falling back to the old style detector, use paragraph
    # geometry inside the already-proven column-major order.
    paragraph_candidate = _paragraph_gap_column_segments(reflowed)
    if paragraph_candidate:
        paragraph_quality = _segment_quality(paragraph_candidate)
        base_n = len(base_records)
        new_n = len(paragraph_candidate)
        accepted_paragraph = bool(
            new_n >= base_n + max(3, int(round(max(1, base_n) * 0.05)))
            and paragraph_quality["n_giant_segments"] == 0
            and paragraph_quality["evidence_ratio"] >= 0.88
            and 3 <= paragraph_quality["median_words"] <= 140
        )
        if accepted_paragraph:
            return {
                **geometry,
                "accepted": True,
                "reason": "two_column_paragraph_geometry_recovered_v0_6_5",
                "candidate_style": "author_year_layout",
                "n_base_segments": base_n,
                "n_enhanced_segments": new_n,
                **paragraph_quality,
                "segments": paragraph_candidate,
            }

    # Retain v1 as a fallback for author-year two-column references such as a
    # journal article whose references have no explicit numeric anchors.
    legacy = build_column_reflow_repair(pdf_path, zone, base_records)
    if legacy.get("accepted"):
        return {**legacy, "reason": "two_column_author_year_recovered_v2_fallback", "v2_fallback": True}

    return {
        **geometry,
        "accepted": False,
        "reason": "two_column_reflow_v2_failed_gate",
        "numeric_prefix_length": len(events),
        "legacy_reason": legacy.get("reason"),
        "legacy_candidate_style": legacy.get("candidate_style"),
        "legacy_n_enhanced_segments": legacy.get("n_enhanced_segments"),
        "paragraph_candidate_segments": len(paragraph_candidate),
    }
