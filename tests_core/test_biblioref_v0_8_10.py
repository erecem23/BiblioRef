# -*- coding: utf-8 -*-
"""Regression tests for v0.8.10 stable-conflict diagnostics.

Fixtures are synthetic reductions of failure families observed during the
v0.8.9 SEDICI-HUM audit.  They are development fixtures for v0.8.10 and are not
an independent validation set for this version.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref.adaptive.stable_conflicts import (
    build_effective_zone_conflict_diagnostics,
    combine_stable_conflict_diagnostics,
    diagnose_stable_context_conflict,
    diagnose_stable_segmentation_conflict,
)
from biblioref.core.config import (
    ADAPTIVE_ANALYSIS_VERSION,
    ALGORITHM_VERSION,
    SOFTWARE_VERSION,
)
from biblioref.legacy.engine import (
    AdaptiveLayoutZone,
    LayoutLine,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
)
from biblioref.pipeline import process_pdf

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "fixtures" / "v0810_stable_conflict_failure_families.json").read_text(encoding="utf-8"))


def mk_line(page: int, text: str, y: float, x0: float = 72.0, size: float = 11.0) -> LayoutLine:
    return LayoutLine(
        page=page,
        page_height=800.0,
        text=text,
        x0=x0,
        y0=y,
        x1=min(540.0, x0 + max(80.0, len(text) * 4.8)),
        y1=y + 11.0,
        median_font_size=size,
        fragment_count=1,
    )


def make_zone(case: dict, start_page: int = 5) -> tuple[list[LayoutLine], AdaptiveLayoutZone, dict, list[dict]]:
    preceding = list(case.get("preceding", []))
    document_lines = []
    y = 35.0
    for text in preceding:
        document_lines.append(mk_line(start_page, text, y, size=13 if "INDICE" in text.upper() or "ÍNDICE" in text.upper() else 11))
        y += 24.0
    heading = mk_line(start_page, case.get("heading", "Referencias"), max(y, 110.0), size=14.0)
    document_lines.append(heading)
    y = heading.y0 + 42.0
    zone_lines = []
    for idx, text in enumerate(case.get("zone_lines", [])):
        # Put an explicit body transition on the next page to exercise span logic.
        page = start_page + (1 if idx >= 3 and str(text).upper().startswith("IV.") else 0)
        if page != start_page:
            y = 80.0 + (idx - 3) * 24.0
        line = mk_line(page, text, y)
        zone_lines.append(line)
        document_lines.append(line)
        y += 24.0

    texts = [line.text for line in zone_lines]
    style = diagnose_adaptive_style(texts)
    layout = diagnose_adaptive_layout(zone_lines, style)
    start, end = case.get("summary_span", [start_page, max([line.page for line in zone_lines] or [start_page])])
    zone = AdaptiveLayoutZone(
        heading=heading,
        lines=zone_lines,
        start_page=start,
        end_page=end,
        style=style,
        layout=layout,
        termination_reason="end_of_document",
        confidence_score=0.9,
        confidence_label="high",
        confidence_reasons=[],
        start_confidence_score=0.9,
        start_confidence_label="high",
        start_confidence_reasons=[],
        end_confidence_score=0.9,
        end_confidence_label="high",
        end_confidence_reasons=[],
        zone_completeness="complete",
        adaptive_soft_limit_pages=25,
        zone_span_pages=end - start + 1,
        adaptive_limit_exceeded=False,
    )
    summary = {"zone_id": 1, "heading": heading.text, "start_page": start, "end_page": end, "style": style.style}
    summaries = [summary]
    if "other_span" in case:
        ostart, oend = case["other_span"]
        summaries.append({"zone_id": 2, "heading": "Referencias", "start_page": ostart, "end_page": oend, "style": "author_date"})
    return document_lines, zone, summary, summaries


def fake_records(word_counts: list[int]) -> list[dict]:
    return [{"reference_text": " ".join(["token"] * int(n))} for n in word_counts]


def fake_shadow(case: dict) -> dict:
    return {
        "shadow_candidate": {"n_segments": int(case.get("shadow_segments", 0))},
        "comparison": {
            "status": case.get("shadow_status", "stable_preferred"),
            "candidate_passes_safety_checks": bool(case.get("shadow_safe", False)),
        },
    }


class TestV0810StableConflictFixtures(unittest.TestCase):
    def test_version_lock_keeps_effective_algorithm(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.6.21", ALGORITHM_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)

    def test_context_failure_family_fixtures(self):
        names = {
            "map_legend_generic_references",
            "toc_bibliography_entry",
            "abbreviation_reference_key",
            "embedded_syllabus_bibliography",
            "overlap_and_body_transition",
        }
        for case in DATA["cases"]:
            if case["case"] not in names:
                continue
            with self.subTest(case=case["case"]):
                document_lines, zone, summary, summaries = make_zone(case)
                diag = diagnose_stable_context_conflict(document_lines, zone, summary, summaries, 1)
                self.assertTrue(diag["requires_review"])
                signals = {item["signal"] for item in diag["signals"]}
                self.assertIn(case["expected_signal"], signals)
                self.assertIn(case["family"], diag["failure_families"])
                self.assertFalse(diag["auto_apply"])

    def test_segmentation_failure_family_fixtures(self):
        names = {
            "numeric_style_hijacks_author_year",
            "ocr_degraded_giant_unresolved",
            "legacy_allcaps_bare_author",
        }
        for case in DATA["cases"]:
            if case["case"] not in names:
                continue
            with self.subTest(case=case["case"]):
                _, zone, _, _ = make_zone(case)
                diag = diagnose_stable_segmentation_conflict(
                    zone,
                    fake_records(case["stable_word_counts"]),
                    fake_shadow(case),
                )
                self.assertTrue(diag["requires_review"])
                self.assertIn(case["family"], diag["failure_families"])
                self.assertFalse(diag["auto_apply"])


    def test_fallback_effective_zone_bridge_reuses_discovered_shadow(self):
        case = next(item for item in DATA["cases"] if item["case"] == "numeric_style_hijacks_author_year")
        document_lines, zone, summary, summaries = make_zone(case)
        discovered = {
            "zones": [{
                "discovered_region": {
                    "region_id": 77,
                    "start_page": summary["start_page"],
                    "end_page": summary["end_page"],
                },
                "shadow_candidate": {"n_segments": int(case["shadow_segments"])},
                "comparison": {
                    "status": case["shadow_status"],
                    "candidate_passes_safety_checks": bool(case["shadow_safe"]),
                },
            }]
        }
        diag = build_effective_zone_conflict_diagnostics(
            document_lines,
            [zone],
            summaries,
            {1: fake_records(case["stable_word_counts"])},
            discovered_shadow_report=discovered,
        )
        self.assertEqual([1], diag["stable_segmentation_conflict_zone_ids"])
        self.assertIn("stable_style_hijack_missed_author_year", diag["failure_families"])
        self.assertEqual(77, diag["zones"][0]["matched_discovered_region_id"])
        self.assertFalse(diag["auto_apply"])

    def test_clean_final_bibliography_is_negative_control(self):
        case = next(item for item in DATA["cases"] if item["case"] == "negative_clean_final_bibliography")
        document_lines, zone, summary, summaries = make_zone(case)
        context = diagnose_stable_context_conflict(document_lines, zone, summary, summaries, 1)
        segmentation = diagnose_stable_segmentation_conflict(
            zone, fake_records(case["stable_word_counts"]), fake_shadow(case)
        )
        combined = combine_stable_conflict_diagnostics(context, segmentation)
        self.assertFalse(combined["requires_review"])
        self.assertEqual("stable_structurally_plausible", combined["verdict"])

    def test_clean_long_body_is_not_mislabeled_as_ocr(self):
        # Regression for the SEDICI-HUM-092 calibration issue: an overextended
        # zone can be very long and weakly bibliographic without having a
        # corrupted text layer.  Length alone must not imply OCR degradation.
        case = {
            "heading": "Referencias",
            "zone_lines": [
                f"Este es texto normal del marco teorico con palabras plenamente legibles numero {i}."
                for i in range(80)
            ],
        }
        _, zone, _, _ = make_zone(case)
        diag = diagnose_stable_segmentation_conflict(
            zone,
            fake_records([1500]),
            {
                "shadow_candidate": {"n_segments": 2},
                "comparison": {
                    "status": "manual_review_required",
                    "candidate_passes_safety_checks": False,
                },
            },
        )
        self.assertNotIn("ocr_degraded_scanned_bibliography", diag["failure_families"])
        self.assertLess(diag["metrics"]["corrupted_token_ratio"], 0.08)

    def test_shadow_mode_does_not_change_effective_records_or_zones(self):
        with tempfile.TemporaryDirectory(prefix="biblioref_v0810_") as td:
            pdf = Path(td) / "stable.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 60), "REFERENCIAS", fontsize=15)
            refs = [
                "Alpha, A. (2018). First article. Journal of Methods, 1, 1-10.",
                "Beta, B. (2019). Second article. Research Review, 2, 11-20.",
                "Gamma, C. (2020). Third article. University Press.",
                "Delta, D. (2021). Fourth article. Journal of Data, 4, 31-40.",
                "Epsilon, E. (2022). Fifth article. Review, 5, 41-50.",
            ]
            y = 110
            for ref in refs:
                page.insert_text((72, y), ref, fontsize=10.5)
                y += 55
            doc.save(pdf)
            doc.close()

            off = process_pdf(pdf, adaptive_mode="off")
            shadow = process_pdf(pdf, adaptive_mode="shadow")
            for key in ("records", "zones", "duplicate_groups", "n_records_selected", "detection_decision"):
                self.assertEqual(off.get(key), shadow.get(key), key)
            self.assertEqual("modular_v13_candidate_region_marker_layout_regimes", shadow["architecture"])
            if shadow.get("adaptive_shadow", {}).get("zones"):
                diag = shadow["adaptive_shadow"]["zones"][0]["stable_conflict_diagnostics"]
                self.assertFalse(diag["auto_apply"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
