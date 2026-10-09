# -*- coding: utf-8 -*-
"""Core integration tests for the visual audit layer."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd
import pymupdf

from biblioref_audit_core import (
    ManualZoneSpec,
    build_audit_bundle,
    candidate_heading_lines,
    detect_reference_like_regions,
    process_manual_zone,
    render_page_png,
)
from biblioref_v0_3 import extract_layout_lines


UCA_PDF = Path(__file__).resolve().parent.parent / "uca_ausentismo.pdf"


class TestBiblioRefAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if UCA_PDF.exists():
            cls.pdf = UCA_PDF
            cls.start_page, cls.start_y = 369, 86.5
            cls.end_page, cls.end_y = 387, 86.5
            cls.minimum_records = 80
            cls.start_heading = "R EFERENCIAS BIBLIOGRÁFICAS"
            cls.end_heading = "O TRAS REFERENCIAS CONSULTADAS"
        else:
            cls.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_audit_test_")
            cls.pdf = Path(cls.tempdir.name) / "audit_fixture.pdf"
            doc = pymupdf.open()
            page1 = doc.new_page()
            page1.insert_text((72, 72), "TESIS DE PRUEBA", fontsize=16)
            page2 = doc.new_page()
            page2.insert_text((72, 72), "R EFERENCIAS BIBLIOGRÁFICAS", fontsize=16)
            for y, text in (
                (115, "Acosta, J. (2020). Primera referencia."),
                (155, "Beria, M. (2021). Segunda referencia."),
                (195, "Göran Öst, P. (2022). Tercera referencia."),
            ):
                page2.insert_text((72, y), text, fontsize=11)
            page3 = doc.new_page()
            page3.insert_text((72, 72), "O TRAS REFERENCIAS CONSULTADAS", fontsize=16)
            page3.insert_text((72, 115), "Manual, A. (2023). Referencia consultada.", fontsize=11)
            doc.save(cls.pdf)
            doc.close()
            cls.start_page, cls.start_y = 2, 72.0
            cls.end_page, cls.end_y = 3, 72.0
            cls.minimum_records = 3
            cls.start_heading = "R EFERENCIAS BIBLIOGRÁFICAS"
            cls.end_heading = "O TRAS REFERENCIAS CONSULTADAS"
        cls.lines = extract_layout_lines(cls.pdf)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tempdir"):
            cls.tempdir.cleanup()

    def test_candidate_headings_include_both_uca_zones(self):
        candidates = candidate_heading_lines(self.lines)
        texts = " | ".join(item["text"] for item in candidates)
        self.assertIn(self.start_heading, texts)
        self.assertIn(self.end_heading, texts)

    def test_manual_zone_and_bundle(self):
        spec = ManualZoneSpec(
            start_page=self.start_page,
            start_y=self.start_y,
            end_page=self.end_page,
            end_y=self.end_y,
            heading_text="REFERENCIAS BIBLIOGRÁFICAS",
        )
        result = process_manual_zone(self.pdf, spec, self.lines)
        self.assertGreaterEqual(len(result["records"]), self.minimum_records)
        self.assertEqual("manual_boundary", result["zone"]["termination_reason"])

        refs = pd.DataFrame(result["records"])
        zones = pd.DataFrame([result["zone"]])
        clicks = pd.DataFrame([{"kind": "start", "page": self.start_page, "y_pdf": self.start_y}])
        bundle = build_audit_bundle(
            self.pdf,
            {"software_version": "0.4.5"},
            refs,
            zones,
            clicks,
            [self.start_page, self.end_page],
        )
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            names = set(archive.namelist())
            self.assertIn("biblioref_audit.xlsx", names)
            self.assertIn("processing_report_audited.json", names)
            self.assertIn(f"screenshots/page_{self.start_page:04d}.png", names)
            report = json.loads(archive.read("processing_report_audited.json"))
            self.assertEqual("0.6.1-audit", report["audit_app_version"])

    def test_reference_like_region_without_heading(self):
        lines = [line for line in self.lines if line.page == self.start_page]
        regions = detect_reference_like_regions(lines, page_count=self.start_page)
        self.assertTrue(regions)
        self.assertTrue(regions[0]["requires_confirmation"])

    def test_page_render(self):
        data = render_page_png(self.pdf, self.start_page, zoom=1.0)
        self.assertTrue(data.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
