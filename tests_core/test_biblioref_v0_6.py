# -*- coding: utf-8 -*-
"""Regression gates for BiblioRef v0.6 stable-first routing."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref_v0_4 import process_pdf as process_pdf_stable
from biblioref_v0_6 import process_pdf


def _make_pdf(path: Path, with_heading: bool, narrative: bool = False) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "TESIS DE PRUEBA", fontsize=16)
    page = doc.new_page()
    if narrative:
        for index, text in enumerate((
            "El trabajo analiza un problema general de investigación.",
            "Durante 2020 se realizaron entrevistas a distintos participantes.",
            "Los resultados se presentan a continuación como parte del capítulo.",
        )):
            page.insert_text((72, 120 + index * 35), text, fontsize=11)
    else:
        if with_heading:
            page.insert_text((72, 72), "REFERENCIAS", fontsize=16)
        for index, text in enumerate((
            "Acosta, J. (2018). Primera referencia. Editorial Uno.",
            "Beria, M. (2019). Segunda referencia. Revista Dos, 2(1), 1-10.",
            "Castro, L. (2020). Tercera referencia. https://example.org/tres",
            "Díaz, P. (2021). Cuarta referencia. Editorial Cuatro.",
            "Estévez, R. (2022). Quinta referencia. Revista Cinco, 5(2), 20-30.",
            "Funes, A. (2023). Sexta referencia. doi:10.1000/example",
        )):
            page.insert_text((72, 120 + index * 55), text, fontsize=10.5)
    doc.save(path)
    doc.close()


class TestBiblioRefV06(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v06_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_stable_records_and_zones_are_identical(self):
        pdf = self.root / "stable.pdf"
        _make_pdf(pdf, with_heading=True)
        old = process_pdf_stable(pdf)
        new = process_pdf(pdf)
        self.assertEqual(old["records"], new["records"])
        self.assertEqual(old["zones"], new["zones"])
        self.assertEqual("stable_v0_5_3_route", new["detection_decision"]["method"])
        self.assertTrue(new["detection_decision"]["stable_output_preserved"])

    def test_strong_headingless_region_uses_labelled_fallback(self):
        pdf = self.root / "headingless.pdf"
        _make_pdf(pdf, with_heading=False)
        result = process_pdf(pdf)
        self.assertEqual("inferred_unknown_style", result["detection_decision"]["method"])
        self.assertEqual(6, result["n_records_selected"])
        self.assertTrue(result["zones"][0]["requires_confirmation"])
        self.assertTrue(all(
            record["detection_method"] == "inferred_unknown_style"
            for record in result["records"]
        ))

    def test_narrative_does_not_trigger_fallback(self):
        pdf = self.root / "narrative.pdf"
        _make_pdf(pdf, with_heading=False, narrative=True)
        result = process_pdf(pdf)
        self.assertEqual("audit_required", result["detection_decision"]["method"])
        self.assertEqual(0, result["n_records_selected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
