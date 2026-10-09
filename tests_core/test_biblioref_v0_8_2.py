# -*- coding: utf-8 -*-
"""Bibliography-region verification gate tests for BiblioRef v0.8.2."""

import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref.adaptive.discovery import discover_shadow_regions
from biblioref.adaptive.verification import verify_discovered_region
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, SOFTWARE_VERSION
from biblioref.ingestion import extract_layout_lines
from biblioref.pipeline import process_pdf
from test_biblioref_v0_8_1 import (
    _late_narrative_year_list_pdf,
    _layout_only_unknown_pdf,
)


def _heading_plus_narrative_years(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "REFERENCIAS", fontsize=15)
    items = [
        "El programa Alfa se amplio durante 2018 y cambio su organizacion interna.",
        "La iniciativa Beta se consolido durante 2019 con nuevas actividades locales.",
        "El centro Gamma cambio durante 2020 y sumo nuevos equipos de trabajo.",
        "La red Delta crecio durante 2021 a partir de acuerdos institucionales.",
        "El observatorio Epsilon se reorganizo durante 2022 con nuevas funciones.",
        "El consorcio Zeta continuo durante 2023 con actividades en la region.",
    ]
    for i, text in enumerate(items):
        page.insert_text((72, 115 + i * 70), text, fontsize=10.5)
    doc.save(path)
    doc.close()


def _headingless_author_year_bibliography(path: Path) -> None:
    doc = pymupdf.open()
    for i in range(8):
        p = doc.new_page()
        p.insert_text((72, 60), f"Capitulo {i + 1}", fontsize=14)
        p.insert_text((72, 110), "Contenido narrativo general.", fontsize=10.5)
    page = doc.new_page()
    refs = [
        "Smith, J. (2018). Measurement and evidence. Journal of Methods, 4(1), 10-22.",
        "Brown, A. (2019). Data quality in practice. Journal of Research, 5(2), 20-31.",
        "Garcia, M. (2020). Scientific records. Revista de Estudios, 6(1), 40-53.",
        "Lopez, P. (2021). Document analysis. Revista de Ciencia, 7(3), 55-66.",
        "Martin, L. (2022). Information extraction. Journal of Data, 8(2), 70-82.",
        "Perez, C. (2023). Semi-structured texts. Journal of Methods, 9(4), 90-103.",
    ]
    for i, text in enumerate(refs):
        page.insert_text((72, 100 + i * 70), text, fontsize=10.5)
    doc.save(path)
    doc.close()


class TestBiblioRefV082(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v082_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)

    def test_unknown_bibliography_is_verified_before_shadow_segmentation(self):
        pdf = self.root / "unknown-bibliography.pdf"
        _layout_only_unknown_pdf(pdf)
        result = process_pdf(pdf)
        shadow = result["adaptive_shadow"]
        self.assertEqual("candidate_worth_reviewing", shadow["overall_status"])
        self.assertEqual("required_before_shadow_segmentation", shadow["region_verification_gate"])
        self.assertEqual(1, shadow["n_regions_verified"])
        self.assertEqual(1, shadow["n_zones_analyzed"])
        verification = shadow["region_verifications"][0]["region_verification"]
        self.assertEqual("verified_bibliographic_region", verification["verdict"])
        self.assertIn("heading", verification["signal_families"])
        self.assertIn("source_metadata", verification["signal_families"])
        self.assertTrue(shadow["region_verifications"][0]["segmentation_attempted"])
        self.assertFalse(shadow["auto_apply"])

    def test_narrative_year_list_is_discovered_but_not_segmented(self):
        pdf = self.root / "narrative-list.pdf"
        _late_narrative_year_list_pdf(pdf)
        result = process_pdf(pdf)
        shadow = result["adaptive_shadow"]
        self.assertEqual(1, shadow["n_regions_discovered"])
        self.assertEqual(0, shadow["n_regions_verified"])
        self.assertEqual(0, shadow["n_zones_analyzed"])
        self.assertEqual("bibliographic_region_unverified", shadow["overall_status"])
        verification = shadow["region_verifications"][0]["region_verification"]
        self.assertEqual("insufficient_bibliographic_evidence", verification["verdict"])
        self.assertEqual(1.0, verification["metrics"]["narrative_temporal_context_ratio"])
        self.assertFalse(shadow["region_verifications"][0]["segmentation_attempted"])

    def test_reference_heading_alone_does_not_override_narrative_penalties(self):
        pdf = self.root / "heading-narrative.pdf"
        _heading_plus_narrative_years(pdf)
        lines = extract_layout_lines(pdf)
        regions = discover_shadow_regions(lines, 1)
        self.assertEqual(1, len(regions))
        verification = verify_discovered_region(lines, regions[0])
        self.assertTrue(verification["heading"]["found"])
        self.assertFalse(verification["allows_shadow_segmentation"])
        self.assertNotEqual("verified_bibliographic_region", verification["verdict"])

    def test_headingless_author_year_region_can_be_verified_by_signal_diversity(self):
        pdf = self.root / "headingless-refs.pdf"
        _headingless_author_year_bibliography(pdf)
        lines = extract_layout_lines(pdf)
        regions = discover_shadow_regions(lines, 9)
        self.assertTrue(regions)
        verification = verify_discovered_region(lines, regions[-1])
        self.assertFalse(verification["heading"]["found"])
        self.assertEqual("verified_bibliographic_region", verification["verdict"])
        self.assertIn("author_date", verification["signal_families"])
        self.assertIn("source_metadata", verification["signal_families"])

    def test_verifier_exposes_checks_not_probabilities(self):
        pdf = self.root / "unknown-explainable.pdf"
        _layout_only_unknown_pdf(pdf)
        lines = extract_layout_lines(pdf)
        region = discover_shadow_regions(lines, 1)[0]
        verification = verify_discovered_region(lines, region)
        self.assertNotIn("probability", verification)
        self.assertIsInstance(verification["score_0_12"], float)
        self.assertTrue(verification["score_components"])
        self.assertTrue(all("check" in item and "points" in item for item in verification["score_components"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
