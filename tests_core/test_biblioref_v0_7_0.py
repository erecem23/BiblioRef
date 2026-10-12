# -*- coding: utf-8 -*-
"""Architecture and exact-regression gates inherited from the modular v0.7.0 release."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from biblioref import SOFTWARE_VERSION, process_pdf as modular_process_pdf
from biblioref.audit import (
    AUDIT_APP_VERSION,
    ManualZoneSpec,
    build_audit_bundle,
    candidate_heading_lines as modular_candidate_headings,
    process_manual_zone as modular_process_manual_zone,
)
from biblioref.exporters import write_result_files
from biblioref.ingestion import extract_layout_lines
from biblioref_v0_6_1 import process_pdf as legacy_process_pdf
from test_biblioref_v0_6 import _make_pdf
from test_biblioref_v0_6_1 import _inherited_author_pdf, _mirrored_pdf, _stable_pdf


class TestBiblioRefV070(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v070_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _assert_algorithm_equivalence(self, pdf: Path) -> dict:
        legacy = legacy_process_pdf(pdf)
        modular = modular_process_pdf(pdf)
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
            self.assertEqual(legacy.get(field), modular.get(field), field)
        return modular

    def test_public_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.9.3-audit", AUDIT_APP_VERSION)

    def test_stable_route_is_exact(self):
        pdf = self.root / "stable.pdf"
        _stable_pdf(pdf)
        result = self._assert_algorithm_equivalence(pdf)
        self.assertEqual("0.9.10-rc2", result["software_version"])
        self.assertEqual("0.6.21", result["algorithm_version"])
        self.assertEqual("modular_v13_candidate_region_marker_layout_regimes", result["architecture"])

    def test_mirrored_margin_repair_is_exact(self):
        pdf = self.root / "mirrored.pdf"
        _mirrored_pdf(pdf)
        result = self._assert_algorithm_equivalence(pdf)
        self.assertEqual(30, result["n_records_selected"])

    def test_inherited_author_repair_is_exact(self):
        pdf = self.root / "inherited.pdf"
        _inherited_author_pdf(pdf)
        result = self._assert_algorithm_equivalence(pdf)
        self.assertEqual(6, result["n_records_selected"])

    def test_headingless_fallback_is_exact(self):
        pdf = self.root / "headingless.pdf"
        _make_pdf(pdf, with_heading=False)
        result = self._assert_algorithm_equivalence(pdf)
        self.assertEqual(
            "inferred_unknown_style",
            result["detection_decision"]["method"],
        )

    def test_narrative_abstention_is_exact(self):
        pdf = self.root / "narrative.pdf"
        _make_pdf(pdf, with_heading=False, narrative=True)
        result = self._assert_algorithm_equivalence(pdf)
        self.assertEqual("audit_required", result["detection_decision"]["method"])

    def test_audit_heading_detection_is_exact(self):
        pdf = self.root / "audit.pdf"
        _stable_pdf(pdf)
        lines = extract_layout_lines(pdf)
        from biblioref_audit_core import candidate_heading_lines as legacy_candidate_headings

        self.assertEqual(
            legacy_candidate_headings(lines),
            modular_candidate_headings(lines),
        )

    def test_manual_audit_and_bundle_are_modular(self):
        pdf = self.root / "manual-audit.pdf"
        _stable_pdf(pdf)
        lines = extract_layout_lines(pdf)
        spec = ManualZoneSpec(
            start_page=1,
            start_y=72.0,
            end_page=1,
            heading_text="REFERENCIAS",
        )
        modular = modular_process_manual_zone(pdf, spec, lines)
        from biblioref_audit_core import process_manual_zone as legacy_process_manual_zone

        legacy = legacy_process_manual_zone(pdf, spec, lines)
        self.assertEqual(legacy["records"], modular["records"])
        self.assertEqual(legacy["zone"], modular["zone"])

        refs = pd.DataFrame(modular["records"])
        zones = pd.DataFrame([modular["zone"]])
        clicks = pd.DataFrame()
        bundle = build_audit_bundle(
            pdf,
            {"software_version": "0.9.9"},
            refs,
            zones,
            clicks,
            [1],
        )
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            report = json.loads(archive.read("processing_report_audited.json"))
            self.assertEqual("0.9.3-audit", report["audit_app_version"])

    def test_exporters_are_independent_from_pipeline(self):
        result = {
            "records": [{"reference_text": "Autor, A. (2020). Título."}],
            "zones": [{"zone_id": 1, "heading": "Referencias"}],
        }
        json_path = self.root / "result.json"
        refs_path = self.root / "references.csv"
        zones_path = self.root / "zones.csv"
        written = write_result_files(
            result,
            json_out=json_path,
            csv_out=refs_path,
            zones_out=zones_path,
        )
        self.assertEqual(result, json.loads(json_path.read_text(encoding="utf-8")))
        self.assertTrue(refs_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue(zones_path.exists())
        self.assertEqual(json_path, written["json"])

    def test_invalid_scope_fails_before_processing(self):
        with self.assertRaises(ValueError):
            modular_process_pdf(self.root / "missing.pdf", scope="not-a-scope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
