# -*- coding: utf-8 -*-
"""Document-context and relative-geometry shadow tests for BiblioRef v0.8.4."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref.adaptive.context import classify_document_pages, region_document_context
from biblioref.adaptive.discovery import discover_shadow_regions
from biblioref.adaptive.geometry import (
    detect_repeated_decorations,
    local_bibliographic_density,
    vertical_gap_profile,
    x0_cluster_profile,
)
from biblioref.adaptive.verification import verify_discovered_region
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, AUDIT_APP_VERSION, SOFTWARE_VERSION
from biblioref.ingestion import extract_layout_lines
from biblioref.pipeline import process_pdf
from test_biblioref_v0_6_1 import _stable_pdf


REFS = [
    "Smith, J. (2018). Measurement and evidence. Journal of Methods, 4(1), 10-22.",
    "Brown, A. (2019). Data quality in practice. Journal of Research, 5(2), 20-31.",
    "Garcia, M. (2020). Scientific records. Revista de Estudios, 6(1), 40-53.",
    "Lopez, P. (2021). Document analysis. Revista de Ciencia, 7(3), 55-66.",
    "Martin, L. (2022). Information extraction. Journal of Data, 8(2), 70-82.",
    "Perez, C. (2023). Semi-structured texts. Journal of Methods, 9(4), 90-103.",
]


def _insert_header_footer(page, page_no: int) -> None:
    page.insert_text((72, 30), "Doctoral Thesis - Example University", fontsize=8)
    page.insert_text((280, 810), f"Page {page_no}", fontsize=8)


def _document_grammar_stress_pdf(path: Path) -> None:
    doc = pymupdf.open()

    page = doc.new_page()
    page.insert_text((72, 90), "Neural Systems and Document Analysis", fontsize=18)
    page.insert_text((72, 150), "Doctoral thesis", fontsize=12)

    page = doc.new_page()
    page.insert_text((72, 60), "Publications", fontsize=15)
    for i, text in enumerate(REFS):
        page.insert_text((72, 115 + i * 70), text, fontsize=10.5)

    page = doc.new_page()
    page.insert_text((72, 60), "Contents", fontsize=15)
    page.insert_text((72, 120), "Chapter 1 ................................ 4", fontsize=10.5)
    page.insert_text((72, 155), "Chapter 2 ................................ 6", fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 4)
    page.insert_text((72, 65), "Chapter 1 Methods", fontsize=15)
    page.insert_text((72, 125), "Narrative body text without bibliographic structure.", fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 5)
    for i, text in enumerate(REFS):
        page.insert_text((72, 105 + i * 70), text, fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 6)
    page.insert_text((72, 65), "Chapter 2 Results", fontsize=15)
    page.insert_text((72, 125), "Narrative body text for the second chapter.", fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 7)
    page.insert_text((72, 65), "Conclusions", fontsize=15)
    page.insert_text((72, 125), "Narrative conclusions and discussion.", fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 8)
    for i, text in enumerate(REFS):
        page.insert_text((72, 105 + i * 70), text, fontsize=10.5)

    page = doc.new_page()
    _insert_header_footer(page, 9)
    page.insert_text((72, 65), "Curriculum Vitae", fontsize=15)
    page.insert_text((72, 125), "Academic biography and appointments.", fontsize=10.5)

    doc.save(path)
    doc.close()


def _hanging_indent_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 55), "REFERENCIAS", fontsize=15)
    y = 105
    for idx in range(5):
        page.insert_text((72, y), f"Smith, J. ({2018 + idx}). A long title for reference {idx + 1}.", fontsize=10.5)
        page.insert_text((96, y + 18), f"Journal of Methods, {idx + 4}(1), {10 + idx}-{22 + idx}.", fontsize=10.5)
        y += 62
    doc.save(path)
    doc.close()


class TestBiblioRefV083(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v083_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)
        self.assertEqual("0.9.3-audit", AUDIT_APP_VERSION)

    def test_document_roles_distinguish_publications_and_chapters(self):
        pdf = self.root / "grammar.pdf"
        _document_grammar_stress_pdf(pdf)
        lines = extract_layout_lines(pdf)
        roles = classify_document_pages(lines)
        self.assertEqual("cover", roles[1]["role"])
        self.assertEqual("publications", roles[2]["role"])
        self.assertEqual("toc", roles[3]["role"])
        self.assertEqual("chapter_open", roles[4]["role"])
        self.assertEqual("body", roles[5]["role"])
        self.assertEqual("chapter_open", roles[6]["role"])
        self.assertEqual("back_matter", roles[9]["role"])

    def test_publications_region_is_blocked_by_document_context(self):
        pdf = self.root / "grammar-publications.pdf"
        _document_grammar_stress_pdf(pdf)
        lines = extract_layout_lines(pdf)
        regions = discover_shadow_regions(lines, 9)
        by_page = {region["start_page"]: region for region in regions}
        self.assertIn(2, by_page)
        verification = verify_discovered_region(lines, by_page[2])
        self.assertEqual("context_conflict_requires_review", verification["verdict"])
        self.assertFalse(verification["allows_shadow_segmentation"])
        self.assertEqual("publications", verification["document_context"]["dominant_role"])
        self.assertTrue(verification["document_context"]["strong_negative"])

    def test_chapter_end_and_final_reference_regions_are_context_compatible(self):
        pdf = self.root / "grammar-positive.pdf"
        _document_grammar_stress_pdf(pdf)
        lines = extract_layout_lines(pdf)
        regions = discover_shadow_regions(lines, 9)
        by_page = {region["start_page"]: region for region in regions}
        self.assertIn(5, by_page)
        self.assertIn(8, by_page)

        chapter_refs = verify_discovered_region(lines, by_page[5])
        self.assertEqual("verified_bibliographic_region", chapter_refs["verdict"])
        self.assertEqual("chapter_open", chapter_refs["document_context"]["next_structural_role"])
        self.assertTrue(chapter_refs["document_context"]["positive_evidence"])

        final_refs = verify_discovered_region(lines, by_page[8])
        self.assertEqual("verified_bibliographic_region", final_refs["verdict"])
        self.assertEqual("back_matter", final_refs["document_context"]["next_structural_role"])
        self.assertTrue(final_refs["document_context"]["positive_evidence"])

    def test_repeated_headers_and_footers_are_detected(self):
        pdf = self.root / "decorations.pdf"
        _document_grammar_stress_pdf(pdf)
        lines = extract_layout_lines(pdf)
        report = detect_repeated_decorations(lines)
        self.assertGreaterEqual(report["n_repeated_decorations"], 2)
        examples = {item["example_text"] for item in report["items"]}
        self.assertIn("Doctoral Thesis - Example University", examples)

    def test_relative_geometry_detects_hanging_indent_and_robust_gaps(self):
        pdf = self.root / "hanging.pdf"
        _hanging_indent_pdf(pdf)
        lines = extract_layout_lines(pdf)
        body = [line for line in lines if line.y0 > 80]
        x0 = x0_cluster_profile(body)
        gaps = vertical_gap_profile(body)
        self.assertTrue(x0["hanging_indent_detected"])
        self.assertAlmostEqual(72.0, x0["left_cluster_center"], delta=2.0)
        self.assertAlmostEqual(96.0, x0["continuation_cluster_center"], delta=2.0)
        self.assertGreater(gaps["adaptive_large_gap_threshold"], gaps["median_gap"])
        densities = [local_bibliographic_density(i, body) for i in range(len(body))]
        self.assertGreater(max(densities), 0.6)

    def test_v083_still_does_not_modify_validated_output(self):
        pdf = self.root / "stable.pdf"
        _stable_pdf(pdf)
        baseline = process_pdf(pdf, adaptive_mode="off")
        shadow = process_pdf(pdf, adaptive_mode="shadow")
        for field in ("records", "zones", "duplicate_groups", "detection_decision", "n_records_selected"):
            self.assertEqual(baseline.get(field), shadow.get(field), field)
        self.assertEqual("modular_v13_candidate_region_marker_layout_regimes", shadow["architecture"])
        self.assertFalse(shadow["adaptive_shadow"]["auto_apply"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
