"""Spreadsheet and portable bundle exporters for human audit."""

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from biblioref.core.config import AUDIT_APP_VERSION
from biblioref.ingestion import render_page_png


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
    resolution: Optional[pd.DataFrame] = None,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        references.to_excel(writer, sheet_name="References", index=False)
        zones.to_excel(writer, sheet_name="Zones", index=False)
        manual_clicks.to_excel(writer, sheet_name="Manual clicks", index=False)
        if resolution is not None:
            resolution.to_excel(writer, sheet_name="Resolution", index=False)
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
    resolution: Optional[pd.DataFrame] = None,
) -> bytes:
    """Create a portable audit ZIP that can be inspected without the app."""
    report_copy = dict(report)
    report_copy.update({
        "audit_app_version": AUDIT_APP_VERSION,
        "audit_exported_at": datetime.now(timezone.utc).isoformat(),
        "n_records_after_audit": int(len(references)),
        "n_records_accepted": int(
            references.get("accepted", pd.Series(dtype=bool)).fillna(False).sum()
        )
        if not references.empty
        else 0,
        "n_manual_clicks": int(len(manual_clicks)),
    })
    if resolution is not None:
        report_copy["n_resolution_rows"] = int(len(resolution))
        if "resolution_review_required" in resolution.columns:
            report_copy["n_resolution_review_required"] = int(
                resolution["resolution_review_required"].fillna(False).astype(bool).sum()
            )
        if "resolution_status" in resolution.columns:
            report_copy["resolution_status_counts"] = {
                str(key): int(value)
                for key, value in resolution["resolution_status"].fillna("UNKNOWN").value_counts().to_dict().items()
            }

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("references_audited.csv", dataframe_csv_bytes(references))
        archive.writestr("bibliography_zones_audited.csv", dataframe_csv_bytes(zones))
        archive.writestr("manual_clicks.csv", dataframe_csv_bytes(manual_clicks))
        if resolution is not None:
            archive.writestr("resolution_decisions.csv", dataframe_csv_bytes(resolution))
        archive.writestr(
            "processing_report_audited.json",
            json.dumps(report_copy, ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "biblioref_audit.xlsx",
            workbook_bytes(references, zones, manual_clicks, resolution=resolution),
        )
        for page_number in sorted(
            set(int(page) for page in screenshot_pages if page)
        )[:30]:
            archive.writestr(
                f"screenshots/page_{page_number:04d}.png",
                render_page_png(pdf_path, page_number, zoom=1.35),
            )
    return output.getvalue()
