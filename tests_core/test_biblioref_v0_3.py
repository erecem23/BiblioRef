# -*- coding: utf-8 -*-
"""Executable regression tests for BiblioRef v0.3."""
from collections import Counter
from pathlib import Path
from unittest import SkipTest

from biblioref_v0_2 import diagnose_style, is_reference_start
from biblioref_v0_3 import (
    LayoutLine,
    LayoutZone,
    detect_layout_zones,
    diagnose_layout,
    extract_layout_lines,
    process_pdf,
    segment_layout_zone,
)
from test_biblioref_v0_2 import CASES


PDF = Path(__file__).resolve().parent / (
    "2024_Agrazar_El tratamiento psicoanalítico de las psicosis en el HZGA Gral. "
    "Manuel Belgrano y la Fundación Brizna Historia y clínica (1).pdf"
)
EXPECTED_ZONE_COUNTS = {
    1: 9, 2: 40, 3: 53, 4: 26, 5: 38, 6: 30, 7: 21,
    8: 38, 9: 36, 10: 39, 11: 25, 12: 32, 13: 33, 14: 12,
}


def _require_agrazar_pdf() -> None:
    if not PDF.exists():
        raise SkipTest(
            "Optional historical Agrazar PDF fixture is not bundled with this distribution."
        )


def _fixture_zone(case: dict) -> LayoutZone:
    style = diagnose_style(case["lines"])
    lines = []
    y = 100.0
    for text in case["lines"]:
        is_start = is_reference_start(text, style)
        lines.append(LayoutLine(
            page=1,
            page_height=842.0,
            text=text,
            x0=85.0 if is_start else 121.0,
            y0=y,
            x1=500.0,
            y1=y + 14.0,
            median_font_size=12.0,
        ))
        y += 20.0
    layout = diagnose_layout(lines)
    heading = LayoutLine(1, 842.0, "Referencias", 85.0, 70.0, 180.0, 84.0, 12.0)
    return LayoutZone(
        heading=heading,
        lines=lines,
        start_page=1,
        end_page=1,
        style=style,
        layout=layout,
        termination_reason="fixture",
        confidence_score=1.0,
        confidence_label="high",
        confidence_reasons=[],
    )


def test_development_style_fixtures():
    for name, case in CASES.items():
        zone = _fixture_zone(case)
        segments = segment_layout_zone(zone)
        assert zone.style.style == case["style"], (name, zone.style)
        assert len(segments) == case["gold_starts"], (name, len(segments))
        if name == "sanz_bracket_key":
            assert sum(bool(row["annotation_text"]) for row in segments) == case["gold_annotations"]


def test_agrazar_layout_regression():
    _require_agrazar_pdf()
    result = process_pdf(PDF)
    counts = Counter(int(row["zone_id"]) for row in result["records"])
    assert result["n_zones"] == 14
    assert result["n_occurrences_all_zones"] == 432
    assert result["n_unique_references"] == 387
    assert counts == Counter(EXPECTED_ZONE_COUNTS)


def test_agrazar_contamination_removed():
    _require_agrazar_pdf()
    result = process_pdf(PDF)
    text = "\n".join(row["reference_text"] for row in result["records"])
    assert "En el apartado sobre lo real y la verdad" not in text
    assert "Capítulo 2" not in text
    assert "Capítulo 3" not in text
    assert "parte/12388" in text  # retained as bibliographic URL, not a stop heading


if __name__ == "__main__":
    test_development_style_fixtures()
    test_agrazar_layout_regression()
    test_agrazar_contamination_removed()
    print("OK: 3 BiblioRef v0.3 regression groups passed")
