# -*- coding: utf-8 -*-
"""Adaptive shadow gates for BiblioRef v0.8.1."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref import SOFTWARE_VERSION, process_pdf
from biblioref.adaptive.annotations import build_boundary_training_rows, write_boundary_training_csv
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, AUDIT_APP_VERSION
from biblioref.ingestion import extract_layout_lines
from biblioref.legacy.engine import detect_adaptive_layout_zones
from biblioref_v0_6_1 import process_pdf as validated_process_pdf
from test_biblioref_v0_6 import _make_pdf
from test_biblioref_v0_6_1 import _inherited_author_pdf, _mirrored_pdf, _stable_pdf


def _layout_only_unknown_pdf(path: Path) -> None:
    """Unknown author format: no comma, but repeated layout + years."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "REFERENCIAS", fontsize=15)
    items = [
        "Proyecto Alfa. 2018. Informe anual de resultados. Editorial Uno.",
        "Programa Beta. 2019. Documento metodologico. Editorial Dos.",
        "Centro Gamma. 2020. Manual de procedimientos. Editorial Tres.",
        "Observatorio Delta. 2021. Reporte estadistico. Editorial Cuatro.",
        "Red Epsilon. 2022. Informe de investigacion. Editorial Cinco.",
        "Consorcio Zeta. 2023. Documento tecnico. Editorial Seis.",
    ]
    for index, text in enumerate(items):
        page.insert_text((72, 115 + index * 70), text, fontsize=10.5)
    doc.save(path)
    doc.close()


def _late_narrative_year_list_pdf(path: Path) -> None:
    """Negative control: repeated late layout with years, but ordinary prose."""
    doc = pymupdf.open()
    for page_index in range(9):
        page = doc.new_page()
        page.insert_text((72, 60), f"Capitulo {page_index + 1}", fontsize=14)
        page.insert_text((72, 115), "Texto narrativo sin bibliografia explicita.", fontsize=10.5)
    page = doc.new_page()
    page.insert_text((72, 60), "Resultados historicos", fontsize=15)
    items = [
        "El programa Alfa comenzo en 2018 y produjo cambios institucionales.",
        "El programa Beta fue ampliado en 2019 mediante nuevas acciones.",
        "El centro Gamma modifico su estructura durante 2020 de forma gradual.",
        "El observatorio Delta presento resultados durante 2021 en varias areas.",
        "La red Epsilon incorporo nuevos equipos de trabajo durante 2022.",
        "El consorcio Zeta continuo sus actividades durante 2023 en la region.",
    ]
    for index, text in enumerate(items):
        page.insert_text((72, 115 + index * 70), text, fontsize=10.5)
    doc.save(path)
    doc.close()


class TestBiblioRefV081(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v080_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _assert_validated_output_preserved(self, pdf: Path) -> dict:
        old = validated_process_pdf(pdf)
        new = process_pdf(pdf, adaptive_mode="shadow")
        for field in (
            "records",
            "zones",
            "duplicate_groups",
            "logical_zone_groups",
            "segmentation_repairs",
            "detection_decision",
            "n_records_selected",
            "n_zones",
        ):
            self.assertEqual(old.get(field), new.get(field), field)
        return new

    def test_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)
        self.assertEqual("0.9.3-audit", AUDIT_APP_VERSION)

    def test_stable_output_is_unchanged_with_shadow(self):
        pdf = self.root / "stable.pdf"
        _stable_pdf(pdf)
        result = self._assert_validated_output_preserved(pdf)
        self.assertEqual("modular_v13_candidate_region_marker_layout_regimes", result["architecture"])
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, result["adaptive_shadow"]["version"])
        self.assertFalse(result["adaptive_shadow"]["probabilities_used"])
        self.assertFalse(result["adaptive_shadow"]["auto_apply"])
        self.assertEqual(1, result["adaptive_shadow"]["n_zones_analyzed"])

    def test_v061_repair_is_unchanged_with_shadow(self):
        for name, maker, expected in (
            ("mirrored", _mirrored_pdf, 30),
            ("inherited", _inherited_author_pdf, 6),
        ):
            with self.subTest(name=name):
                pdf = self.root / f"{name}.pdf"
                maker(pdf)
                result = self._assert_validated_output_preserved(pdf)
                self.assertEqual(expected, result["n_records_selected"])
                self.assertIn("adaptive_shadow", result)

    def test_off_mode_does_not_add_shadow_report(self):
        pdf = self.root / "stable-off.pdf"
        _stable_pdf(pdf)
        result = process_pdf(pdf, adaptive_mode="off")
        self.assertNotIn("adaptive_shadow", result)

    def test_nonstable_route_abstains_from_shadow(self):
        pdf = self.root / "narrative.pdf"
        _make_pdf(pdf, with_heading=False, narrative=True)
        result = process_pdf(pdf, adaptive_mode="shadow")
        self.assertEqual("audit_required", result["detection_decision"]["method"])
        self.assertEqual("not_run", result["adaptive_shadow"]["overall_status"])

    def test_boundary_scores_are_explainable_not_probabilities(self):
        pdf = self.root / "stable-signals.pdf"
        _inherited_author_pdf(pdf)
        zones = detect_adaptive_layout_zones(extract_layout_lines(pdf))
        candidates = collect_boundary_candidates(zones[0])
        active = [item for item in candidates if item["active_shadow_boundary"]]
        self.assertGreaterEqual(len(active), 6)
        first = active[0]
        self.assertIsInstance(first["score"], float)
        self.assertTrue(first["contributions"])
        self.assertTrue(all("signal" in item and "weight" in item for item in first["contributions"]))


    def test_shadow_can_surface_unknown_layout_without_auto_extracting(self):
        pdf = self.root / "layout-only-unknown.pdf"
        _layout_only_unknown_pdf(pdf)
        result = process_pdf(pdf, adaptive_mode="shadow")
        self.assertEqual("audit_required", result["detection_decision"]["method"])
        self.assertEqual(0, result["n_records_selected"])
        shadow = result["adaptive_shadow"]
        self.assertEqual("candidate_worth_reviewing", shadow["overall_status"])
        self.assertFalse(shadow["auto_apply"])
        self.assertEqual(1, shadow["n_regions_discovered"])
        self.assertEqual(1, shadow["n_regions_verified"])
        self.assertEqual(1, shadow["n_zones_analyzed"])
        verification = shadow["region_verifications"][0]["region_verification"]
        self.assertEqual("verified_bibliographic_region", verification["verdict"])
        self.assertTrue(verification["allows_shadow_segmentation"])
        zone = shadow["zones"][0]
        self.assertEqual(6, zone["shadow_candidate"]["n_segments"])
        self.assertEqual("candidate_worth_reviewing", zone["comparison"]["status"])
        self.assertIn(
            "candidate_is_structurally_plausible_but_no_baseline_exists",
            zone["comparison"]["reasons"],
        )



    def test_shadow_negative_control_remains_review_only(self):
        pdf = self.root / "late-narrative-year-list.pdf"
        _late_narrative_year_list_pdf(pdf)
        result = process_pdf(pdf, adaptive_mode="shadow")
        self.assertEqual("audit_required", result["detection_decision"]["method"])
        self.assertEqual(0, result["n_records_selected"])
        shadow = result["adaptive_shadow"]
        self.assertFalse(shadow["auto_apply"])
        self.assertEqual("bibliographic_region_unverified", shadow["overall_status"])
        self.assertEqual(1, shadow["n_regions_discovered"])
        self.assertEqual(0, shadow["n_regions_verified"])
        self.assertEqual(0, shadow["n_zones_analyzed"])
        self.assertEqual([], shadow["zones"])
        verification = shadow["region_verifications"][0]["region_verification"]
        self.assertEqual("insufficient_bibliographic_evidence", verification["verdict"])
        self.assertFalse(verification["allows_shadow_segmentation"])

    def test_human_labels_can_be_exported_as_future_training_rows(self):
        pdf = self.root / "annotation-source.pdf"
        _inherited_author_pdf(pdf)
        zones = detect_adaptive_layout_zones(extract_layout_lines(pdf))
        candidates = collect_boundary_candidates(zones[0])
        active_indices = [item["line_index"] for item in candidates if item["active_shadow_boundary"]]
        labels = {index: True for index in active_indices[:2]}
        labels[candidates[-1]["line_index"]] = False
        rows = build_boundary_training_rows("synthetic-inherited", zones[0], labels)
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("feature_at_page_margin", rows[0])
        self.assertIn(rows[0]["boundary_label"], {0, 1})
        output = write_boundary_training_csv(rows, self.root / "boundary_training_dataset.csv")
        self.assertTrue(output.exists())
        self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_invalid_adaptive_mode_fails_before_processing(self):
        with self.assertRaises(ValueError):
            process_pdf(self.root / "missing.pdf", adaptive_mode="probabilistic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
