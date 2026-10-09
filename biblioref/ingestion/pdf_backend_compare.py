"""Differential validation between stable PyMuPDF and experimental PDFium."""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Dict, Sequence

from biblioref.ingestion.pdf import extract_layout_lines_range, pdf_page_count
from biblioref.ingestion.pdfium_backend import extract_layout_lines_pdfium, pdf_page_count_pdfium


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _line_key(line) -> tuple[int, str]:
    return int(line.page), str(line.text)


def compare_pdf_backends(
    pdf_path: str | Path,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    geometry_tolerance: float = 2.5,
) -> Dict[str, Any]:
    """Compare both engines without changing BiblioRef's stable extraction route."""
    path = Path(pdf_path)
    pymupdf_pages = pdf_page_count(path)
    pdfium_pages = pdf_page_count_pdfium(path)
    if end_page is None:
        end_page = min(pymupdf_pages, pdfium_pages)

    stable = extract_layout_lines_range(path, start_page, end_page)
    candidate = extract_layout_lines_pdfium(path, start_page, end_page)
    stable_keys = [_line_key(line) for line in stable]
    candidate_keys = [_line_key(line) for line in candidate]
    exact_line_sequence = stable_keys == candidate_keys

    geometry_deltas = []
    font_deltas = []
    page_height_deltas = []
    compared_lines = 0
    out_of_tolerance = 0
    if exact_line_sequence:
        for left, right in zip(stable, candidate):
            deltas = {
                "x0": abs(float(left.x0) - float(right.x0)),
                "y0": abs(float(left.y0) - float(right.y0)),
                "x1": abs(float(left.x1) - float(right.x1)),
                "y1": abs(float(left.y1) - float(right.y1)),
            }
            geometry_deltas.extend(deltas.values())
            font_deltas.append(abs(float(left.median_font_size) - float(right.median_font_size)))
            page_height_deltas.append(abs(float(left.page_height) - float(right.page_height)))
            compared_lines += 1
            if max(deltas.values()) > geometry_tolerance:
                out_of_tolerance += 1

    first_text_mismatch = None
    if not exact_line_sequence:
        for index in range(max(len(stable_keys), len(candidate_keys))):
            left = stable_keys[index] if index < len(stable_keys) else None
            right = candidate_keys[index] if index < len(candidate_keys) else None
            if left != right:
                first_text_mismatch = {"index": index, "pymupdf": left, "pdfium": right}
                break

    return {
        "pdf": str(path),
        "range": {"start_page": start_page, "end_page": end_page},
        "page_count": {
            "pymupdf": pymupdf_pages,
            "pdfium": pdfium_pages,
            "equal": pymupdf_pages == pdfium_pages,
        },
        "layout_lines": {
            "pymupdf": len(stable),
            "pdfium": len(candidate),
            "exact_text_sequence": exact_line_sequence,
            "first_text_mismatch": first_text_mismatch,
        },
        "geometry": {
            "compared_lines": compared_lines,
            "tolerance_pt": float(geometry_tolerance),
            "median_abs_delta_pt": round(_median(geometry_deltas), 6),
            "max_abs_delta_pt": round(max(geometry_deltas), 6) if geometry_deltas else None,
            "lines_over_tolerance": out_of_tolerance,
            "median_font_size_delta_pt": round(_median(font_deltas), 6),
            "max_font_size_delta_pt": round(max(font_deltas), 6) if font_deltas else None,
            "max_page_height_delta_pt": round(max(page_height_deltas), 6) if page_height_deltas else None,
        },
        "candidate_ready_for_algorithm_diff": bool(
            pymupdf_pages == pdfium_pages and exact_line_sequence
        ),
        "stable_backend_changed": False,
    }
