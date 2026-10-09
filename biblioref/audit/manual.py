"""Manual, user-confirmed zone processing."""

from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from biblioref.audit.models import ManualZoneSpec
from biblioref.ingestion import LayoutLine, extract_layout_lines, pdf_page_count
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    _annotate_duplicates,
    _is_footer,
    _is_small_font_noise,
    _numeric_sequence_diagnostics,
    classify_zone_role,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    segment_adaptive_layout_zone,
)


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
        line
        for line in all_lines
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
