# -*- coding: utf-8 -*-
"""Core helpers for the BiblioRef visual audit application."""
from __future__ import annotations

import io
import json
import re
import statistics
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import pymupdf

from biblioref_v0_2 import (
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    BULLET_RX,
    NUMERIC_MARKER_RX,
    _annotate_duplicates,
    _strip_heading_prefix,
    is_ref_heading,
)
from biblioref_v0_3 import (
    LayoutLine,
    _is_footer,
    _is_small_font_noise,
    extract_layout_lines,
)
from biblioref_v0_4 import (
    AdaptiveLayoutZone,
    _has_bare_author_year,
    _has_early_bibliographic_date,
    _numeric_sequence_diagnostics,
    classify_zone_role,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    segment_adaptive_layout_zone,
)


AUDIT_APP_VERSION = "0.6.1-audit"


@dataclass
class ManualZoneSpec:
    start_page: int
    start_y: float
    end_page: int
    end_y: Optional[float] = None
    heading_text: str = "Manual bibliography zone"
    note: str = ""

    def validate(self, page_count: int) -> None:
        if not 1 <= self.start_page <= page_count:
            raise ValueError("La página inicial está fuera del PDF.")
        if not self.start_page <= self.end_page <= page_count:
            raise ValueError("La página final debe ser igual o posterior a la inicial.")
        if self.end_page == self.start_page and self.end_y is not None:
            if self.end_y <= self.start_y:
                raise ValueError("El final debe estar debajo del inicio en una zona de una página.")


def pdf_page_count(pdf_path: str | Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def render_page_png(pdf_path: str | Path, page_number: int, zoom: float = 1.6) -> bytes:
    """Render a 1-based PDF page as PNG."""
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError("Página fuera de rango.")
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def page_dimensions(pdf_path: str | Path, page_number: int) -> Tuple[float, float]:
    with pymupdf.open(pdf_path) as doc:
        rect = doc[page_number - 1].rect
        return float(rect.width), float(rect.height)


def candidate_heading_lines(lines: Sequence[LayoutLine]) -> List[dict]:
    """Rank heading candidates without matching incidental prose."""
    lexical = re.compile(
        r"\b(?:referencias?|bibliograf(?:ia|y)|fuentes?|literatura\s+citada|"
        r"obras\s+citadas|works\s+cited|literature\s+cited|cited\s+literature)\b",
        re.I,
    )
    page_font_medians: Dict[int, float] = {}
    for page in sorted({line.page for line in lines}):
        sizes = [line.median_font_size for line in lines if line.page == page and line.median_font_size > 0]
        page_font_medians[page] = statistics.median(sizes) if sizes else 0.0
    candidates: List[dict] = []
    seen = set()
    for line_index, line in enumerate(lines):
        text = line.text.strip()
        if not text or len(text) > 140:
            continue
        # Entries from the table of contents often contain dot leaders and a
        # terminal page number.  They are navigation text, not the real
        # bibliography heading.
        if re.search(r"(?:\.{4,}|…{2,}).*\d{1,4}\s*$", text):
            continue
        exact = is_ref_heading(text)
        if not exact and not lexical.search(text):
            continue
        letters = [char for char in text if char.isalpha()]
        upper_ratio = sum(char.isupper() for char in letters) / max(len(letters), 1)
        larger_font = line.median_font_size >= page_font_medians.get(line.page, 0.0) + 0.8
        compact = len(text) <= 70
        heading_like = exact or (
            compact and (upper_ratio >= 0.65 or (larger_font and upper_ratio >= 0.40))
        )
        if not heading_like:
            continue
        key = (line.page, round(line.y0, 1), text)
        if key in seen:
            continue
        seen.add(key)
        score = 1.0 if exact else round(0.62 + 0.12 * larger_font + 0.10 * (upper_ratio >= 0.65), 2)
        candidates.append({
            "page": line.page,
            "y": round(line.y0, 2),
            "text": text,
            "score": score,
            "reason": "recognized_heading" if exact else "heading_like_layout",
            "font_size": round(line.median_font_size, 2),
            "_line_index": line_index,
        })

    # When the same heading appears in a numbered contents block and later as
    # the actual section title, keep only the latter in the audit selector.
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
        numbered = sum(bool(re.match(
            r"^(?:(?:[ivxlcdm]+|\d+)(?:[\.\-:]|\s))", value, flags=re.I
        )) for value in previous)
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
        if (
            previous
            and item["page"] <= previous["page"] + 3
            and item["y"] <= 120
        ):
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
    """Propose dense reference-like regions even when no heading is present.

    These are audit suggestions, not automatically accepted bibliography zones.
    """
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
        structural = sum(counts.get(key, 0) for key in ("bullet", "numeric", "bracket_key"))
        near_end = page >= max(1, int(page_count * 0.55))
        strong = (
            len(signaled) >= 3
            and (structural >= 2 or counts.get("author_year", 0) >= 3)
            and (near_end or len(signaled) >= 6)
        )
        if not strong:
            continue
        dominance = dominant_count / len(signaled)
        score = min(0.98, 0.58 + 0.045 * len(signaled) + 0.10 * dominance + 0.07 * near_end)
        style = "legal_bulleted" if dominant == "bullet" and legal_count >= max(2, len(signaled) // 3) else dominant
        profiles[page] = {
            "page": page,
            "start_y": min(line.y0 for line, _ in signaled),
            "last_y": max(line.y1 for line, _ in signaled),
            "n_starts": len(signaled),
            "style_guess": style,
            "score": round(score, 3),
            "evidence": ";".join(f"{key}:{value}" for key, value in sorted(counts.items())),
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
        # Include a single intervening continuation page when strong pages
        # appear on both sides.
        start_page, end_page = min(group), max(group)
        total_starts = sum(profiles[page]["n_starts"] for page in group)
        dominant_style = max(
            (profiles[page]["style_guess"] for page in group),
            key=lambda value: sum(profiles[p]["style_guess"] == value for p in group),
        )
        score = round(sum(profiles[page]["score"] for page in group) / len(group), 3)
        regions.append({
            "region_id": index,
            "start_page": start_page,
            "start_y": round(profiles[start_page]["start_y"], 2),
            "end_page": end_page,
            "style_guess": dominant_style,
            "n_boundary_signals": total_starts,
            "confidence_score": score,
            "evidence": " | ".join(profiles[page]["evidence"] for page in group[:4]),
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


def _line_in_manual_zone(line: LayoutLine, spec: ManualZoneSpec) -> bool:
    page = line.page
    if page < spec.start_page or page > spec.end_page:
        return False
    if page == spec.start_page and line.y0 <= spec.start_y + 1.0:
        return False
    if page == spec.end_page and spec.end_y is not None and line.y0 >= spec.end_y - 1.0:
        return False
    return True


def process_manual_zone(
    pdf_path: str | Path,
    spec: ManualZoneSpec,
    lines: Optional[Sequence[LayoutLine]] = None,
    zone_id: int = 1,
) -> Dict:
    """Segment a user-delimited zone without applying an automatic closing rule."""
    page_count = pdf_page_count(pdf_path)
    spec.validate(page_count)
    all_lines = list(lines) if lines is not None else extract_layout_lines(pdf_path)
    body = [
        line for line in all_lines
        if _line_in_manual_zone(line, spec) and not _is_footer(line)
    ]
    if not body:
        raise ValueError("La zona manual no contiene líneas de texto extraíbles.")

    style = diagnose_adaptive_style([line.text for line in body[:400]])
    layout = diagnose_adaptive_layout(body[:400], style)
    body = [line for line in body if not _is_small_font_noise(line, layout)]
    if not body:
        raise ValueError("Todas las líneas de la zona fueron clasificadas como ruido.")

    heading = LayoutLine(
        page=spec.start_page,
        page_height=body[0].page_height,
        text=spec.heading_text,
        x0=body[0].x0,
        y0=spec.start_y,
        x1=body[0].x1,
        y1=spec.start_y + max(body[0].median_font_size, 10.0),
        median_font_size=body[0].median_font_size,
        fragment_count=1,
    )
    span = spec.end_page - spec.start_page + 1
    zone = AdaptiveLayoutZone(
        heading=heading,
        lines=body,
        start_page=spec.start_page,
        end_page=spec.end_page,
        style=style,
        layout=layout,
        termination_reason="manual_boundary",
        confidence_score=1.0,
        confidence_label="manual",
        confidence_reasons=["user_confirmed_start", "user_confirmed_end"],
        start_confidence_score=1.0,
        start_confidence_label="manual",
        start_confidence_reasons=["user_confirmed_start"],
        end_confidence_score=1.0,
        end_confidence_label="manual",
        end_confidence_reasons=["user_confirmed_end"],
        zone_completeness="manually_delimited",
        adaptive_soft_limit_pages=0,
        zone_span_pages=span,
        adaptive_limit_exceeded=False,
    )
    segments = segment_adaptive_layout_zone(zone)
    zone_role = classify_zone_role(spec.heading_text)
    numeric_diagnostics = _numeric_sequence_diagnostics(segments)
    records: List[dict] = []
    for ref_in_zone, segment in enumerate(segments, 1):
        record = dict(segment)
        record.update({
            "zone_id": zone_id,
            "ref_in_zone": ref_in_zone,
            "zone_heading": spec.heading_text,
            "zone_role": zone_role,
            "zone_start_page": spec.start_page,
            "zone_end_page": spec.end_page,
            "zone_start_confidence_score": 1.0,
            "zone_start_confidence_label": "manual",
            "zone_end_confidence_score": 1.0,
            "zone_end_confidence_label": "manual",
            "zone_completeness": "manually_delimited",
            "zone_termination_reason": "manual_boundary",
            "zone_adaptive_limit_exceeded": False,
            "manual_zone": True,
            "accepted": True,
            "audit_status": "pending_review",
            "audit_note": "",
        })
        records.append(record)
    records, duplicate_groups = _annotate_duplicates(records)
    zone_summary = {
        "zone_id": zone_id,
        "heading": spec.heading_text,
        "zone_role": zone_role,
        "start_page": spec.start_page,
        "start_y": round(spec.start_y, 2),
        "end_page": spec.end_page,
        "end_y": round(spec.end_y, 2) if spec.end_y is not None else None,
        "style": style.style,
        "n_segments": len(records),
        "termination_reason": "manual_boundary",
        "zone_completeness": "manually_delimited",
        "combined_confidence_label": "manual",
        "manual_zone": True,
        "note": spec.note,
        **numeric_diagnostics,
    }
    return {
        "zone": zone_summary,
        "records": records,
        "duplicate_groups": duplicate_groups,
        "spec": asdict(spec),
    }


def add_audit_columns(records: Iterable[dict]) -> List[dict]:
    output: List[dict] = []
    for record in records:
        item = dict(record)
        item.setdefault("manual_zone", False)
        item.setdefault("accepted", True)
        item.setdefault("audit_status", "pending_review")
        item.setdefault("audit_note", "")
        output.append(item)
    return output


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def workbook_bytes(
    references: pd.DataFrame,
    zones: pd.DataFrame,
    manual_clicks: pd.DataFrame,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        references.to_excel(writer, sheet_name="References", index=False)
        zones.to_excel(writer, sheet_name="Zones", index=False)
        manual_clicks.to_excel(writer, sheet_name="Manual clicks", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                letter = column[0].column_letter
                width = min(max(len(str(cell.value or "")) for cell in column) + 2, 70)
                sheet.column_dimensions[letter].width = max(width, 12)
    return buffer.getvalue()


def build_audit_bundle(
    pdf_path: str | Path,
    report: dict,
    references: pd.DataFrame,
    zones: pd.DataFrame,
    manual_clicks: pd.DataFrame,
    screenshot_pages: Sequence[int],
) -> bytes:
    """Create a portable audit ZIP that can be inspected without the app."""
    report_copy = dict(report)
    report_copy.update({
        "audit_app_version": AUDIT_APP_VERSION,
        "audit_exported_at": datetime.now(timezone.utc).isoformat(),
        "n_records_after_audit": int(len(references)),
        "n_records_accepted": int(references.get("accepted", pd.Series(dtype=bool)).fillna(False).sum())
        if not references.empty else 0,
        "n_manual_clicks": int(len(manual_clicks)),
    })
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("references_audited.csv", dataframe_csv_bytes(references))
        archive.writestr("bibliography_zones_audited.csv", dataframe_csv_bytes(zones))
        archive.writestr("manual_clicks.csv", dataframe_csv_bytes(manual_clicks))
        archive.writestr("processing_report_audited.json", json.dumps(report_copy, ensure_ascii=False, indent=2))
        archive.writestr("biblioref_audit.xlsx", workbook_bytes(references, zones, manual_clicks))
        for page_number in sorted(set(int(page) for page in screenshot_pages if page))[:30]:
            archive.writestr(
                f"screenshots/page_{page_number:04d}.png",
                render_page_png(pdf_path, page_number, zoom=1.35),
            )
    return output.getvalue()
