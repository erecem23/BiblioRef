"""Numbered lists cut at a page break (check C1, algorithm 0.6.21).

A running header that repeats a chapter or section title looks like a heading,
so a numbered zone could end at the first page break although its list goes on:
the next page opens, after the folio and the header, with the marker that follows
the zone's last one (T-cases: Cortell Fuster 2024, Exactas-UBA chemistry theses).

When that is the case the zone is extended over the following pages for as long
as they keep the sequence, and a zone that the same header opened on those pages
with the next marker is merged into it. Nothing else changes: a zone whose next
page does not open with the next marker is left as it was.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

CONTINUATION_VERSION = "0.6.21-continuation-1"
MARKER = re.compile(r"^\s*(?:\[(\d{1,3})\]|\((\d{1,3})\)|(\d{1,3})[.)])(?=\s|$|[^\d.,)\]])")
YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
#: A folio line ("86", "86 | Página", "- 13 -", "Page 4") is page furniture, not part of an entry.
FOLIO = re.compile(r"[\s\-–|·]*(?:(?:p[aá]g(?:ina)?|page)\.?\s*)?\d{1,4}[\s\-–|·]*(?:p[aá]g(?:ina)?|page)?\.?[\s\-–|·]*", re.I)
#: Lines that may precede the next marker at the top of a page: folio and running header.
MAX_HEADER_LINES = 4
MAX_HEADER_CHARS = 90
#: A line this much larger than the list's text is a heading: the list has ended.
HEADING_FONT_RATIO = 1.15
MAX_EXTENSION_PAGES = 60


def marker_of(text: str) -> Optional[int]:
    match = MARKER.match(text or "")
    if not match:
        return None
    return int(next(group for group in match.groups() if group))


def _norm_header(text: str) -> str:
    return re.sub(r"[\d\W_]+", " ", (text or "").casefold()).strip()


def _lines_by_page(lines) -> Dict[int, list]:
    pages: Dict[int, list] = defaultdict(list)
    for line in lines or []:
        if str(getattr(line, "text", "")).strip():
            pages[int(line.page)].append(line)
    for page in pages.values():
        page.sort(key=lambda l: (round(float(l.y0), 1), float(l.x0)))
    return pages


def _opening(page_lines, expected: int, headers: set) -> Optional[int]:
    """Index of the line with ``expected`` at the top of a page, after folio/header lines."""
    for index, line in enumerate(page_lines[: MAX_HEADER_LINES + 1]):
        text = str(line.text).strip()
        if marker_of(text) == expected:
            return index
        if len(text) > MAX_HEADER_CHARS and _norm_header(text) not in headers:
            return None
    return None


def _skip_header(page_lines, headers: set) -> int:
    index = 0
    while index < min(len(page_lines), MAX_HEADER_LINES):
        text = str(page_lines[index].text).strip()
        if marker_of(text) is not None:
            break
        if not (_norm_header(text) in headers or not _norm_header(text)):
            break
        index += 1
    return index


def _zone_font(records_lines) -> float:
    sizes = sorted(float(getattr(l, "median_font_size", 0) or 0) for l in records_lines if getattr(l, "median_font_size", 0))
    return sizes[len(sizes) // 2] if sizes else 0.0


def continue_numbered_zones(zones: Sequence[Dict], records: Sequence[Dict], lines) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Return (zones, records, repairs) with numbered zones extended over their continuation."""
    pages = _lines_by_page(lines)
    by_zone: Dict[int, List[Dict]] = defaultdict(list)
    for record in records:
        by_zone[int(record.get("zone_id") or 0)].append(record)
    zones = [dict(z) for z in zones]
    absorbed: set = set()
    repairs: List[Dict] = []
    out_records: Dict[int, List[Dict]] = {zid: list(recs) for zid, recs in by_zone.items()}

    for zone in zones:
        zid = int(zone.get("zone_id") or 0)
        if zid in absorbed:
            continue
        recs = out_records.get(zid, [])
        markers = [marker_of(str(r.get("reference_text") or "")) for r in recs]
        if len(recs) < 3 or None in markers[-3:] or markers[-1] != markers[-2] + 1:
            continue
        expected = markers[-1] + 1
        page = int(zone.get("end_page") or 0) + 1
        if page not in pages:
            continue
        first = _opening(pages[page], expected, set())
        if first is None:
            continue
        headers = {_norm_header(str(l.text)) for l in pages[page][:first]} - {""}
        list_lines = [l for l in (lines or []) if int(zone.get("start_page") or 0) <= int(l.page) <= int(zone.get("end_page") or 0)]
        font = _zone_font(list_lines)
        new_entries: List[List] = []
        merged_ids: List[int] = []
        used_pages: List[int] = []
        start = first
        stop = False
        while page in pages and len(used_pages) < MAX_EXTENSION_PAGES and not stop:
            page_lines = pages[page]
            if used_pages:
                start = _skip_header(page_lines, headers)
                if not any(marker_of(str(l.text)) == expected for l in page_lines[start:]) and not new_entries:
                    break
            other = next((z for z in zones if int(z.get("zone_id") or 0) not in absorbed | {zid}
                          and int(z.get("start_page") or 0) <= page <= int(z.get("end_page") or 0)), None)
            if other is not None:
                other_id = int(other["zone_id"])
                other_recs = out_records.get(other_id, [])
                first_marker = marker_of(str(other_recs[0].get("reference_text") or "")) if other_recs else None
                if first_marker != expected or new_entries:
                    break
                # The header opened a zone of its own on this page: the two are one list.
                merged_ids.append(other_id)
                absorbed.add(other_id)
                out_records[zid] = out_records.get(zid, []) + other_recs
                tail = [marker_of(str(r.get("reference_text") or "")) for r in other_recs]
                last_known = next((m for m in reversed(tail) if m is not None), expected)
                expected = last_known + 1
                zone["end_page"] = other.get("end_page")
                page = int(other.get("end_page") or page) + 1
                used_pages.append(page - 1)
                if page not in pages or _opening(pages[page], expected, headers) is None:
                    break
                continue
            for line in page_lines[start:]:
                text = str(line.text).strip()
                size = float(getattr(line, "median_font_size", 0) or 0)
                number = marker_of(text)
                if font and size > HEADING_FONT_RATIO * font and number is None:
                    stop = True
                    break
                if FOLIO.fullmatch(text):
                    continue
                if number == expected:
                    new_entries.append([line])
                    expected += 1
                elif number == 1 and new_entries:
                    stop = True
                    break
                elif new_entries:
                    if _norm_header(text) in headers or not _norm_header(text):
                        continue
                    new_entries[-1].append(line)
            used_pages.append(page)
            page += 1
            if page in pages and not stop:
                nxt = _skip_header(pages[page], headers)
                upcoming = pages[page][nxt:]
                if not upcoming or (marker_of(str(upcoming[0].text)) not in (None, expected)):
                    break
        if not new_entries and not merged_ids:
            continue
        template = dict(out_records[zid][-1])
        added = []
        for entry in new_entries:
            text = " ".join(str(l.text).strip() for l in entry)
            entry_pages = sorted({int(l.page) for l in entry})
            flags = []
            if len(entry_pages) > 1:
                flags.append("cross_page")
            if not YEAR.search(text):
                flags.append("no_year")
            record = dict(template)
            record.update({
                "reference_text": re.sub(r"\s+", " ", text).strip(),
                "reference_start_page": entry_pages[0],
                "reference_end_page": entry_pages[-1],
                "reference_start_x": round(float(entry[0].x0), 2),
                "boundary_evidence": "numeric_marker_continuation",
                "audit_flags": ";".join(flags),
            })
            added.append(record)
        out_records[zid] = out_records[zid] + added
        if added:
            zone["end_page"] = max(int(zone.get("end_page") or 0), added[-1]["reference_end_page"])
        for index, record in enumerate(out_records[zid], 1):
            record["ref_in_zone"] = index
            record["zone_id"] = zid
            record["zone_end_page"] = zone["end_page"]
        all_markers = [marker_of(str(r.get("reference_text") or "")) for r in out_records[zid]]
        known = [m for m in all_markers if m is not None]
        zone["n_segments"] = len(out_records[zid])
        if known:
            zone["numeric_last_marker"] = known[-1]
        zone["termination_reason"] = "numeric_continuation_extended"
        repairs.append({
            "zone_id": zid,
            "version": CONTINUATION_VERSION,
            "pages_added": used_pages,
            "records_added": len(added),
            "zones_merged": merged_ids,
            "last_marker_before": markers[-1],
            "last_marker_after": known[-1] if known else None,
        })

    kept = [z for z in zones if int(z.get("zone_id") or 0) not in absorbed]
    renumber = {int(z["zone_id"]): new_id for new_id, z in enumerate(kept, 1)}
    final_records: List[Dict] = []
    for zone in kept:
        old = int(zone["zone_id"])
        zone["zone_id"] = renumber[old]
        for record in out_records.get(old, []):
            record = dict(record)
            record["zone_id"] = renumber[old]
            final_records.append(record)
    for repair in repairs:
        repair["zone_id"] = renumber.get(repair["zone_id"], repair["zone_id"])
    return kept, final_records, repairs
