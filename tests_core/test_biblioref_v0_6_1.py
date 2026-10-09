# -*- coding: utf-8 -*-
"""Regression and feature gates for BiblioRef v0.6.1."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from biblioref_v0_6 import process_pdf as process_pdf_v06
from biblioref_v0_6_1 import _logical_running_header_groups, process_pdf


def _stable_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "REFERENCIAS", fontsize=15)
    for index in range(8):
        page.insert_text(
            (72, 120 + index * 55),
            f"Autor{index}, A. ({2010 + index}). Titulo {index}. Revista de prueba.",
            fontsize=10.5,
        )
    doc.save(path)
    doc.close()


def _mirrored_pdf(path: Path) -> None:
    doc = pymupdf.open()
    counter = 0
    for page_index in range(5):
        page = doc.new_page()
        if page_index == 0:
            page.insert_text((72, 55), "REFERENCES", fontsize=15)
        x = 72 if page_index % 2 == 0 else 118
        for row in range(6):
            counter += 1
            surname = f"Surname{chr(64 + counter)}"
            page.insert_text(
                (x, 110 + row * 95),
                f"{surname}, A. ({1990 + counter}). Reference title {counter}.",
                fontsize=10.5,
            )
            page.insert_text((x + 18, 128 + row * 95), "Journal continuation, 1(1), 1-9.", fontsize=10.5)
    doc.save(path)
    doc.close()


def _inherited_author_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "BIBLIOGRAFIA", fontsize=15)
    lines = [
        (72, "Freud, S. (1999a). Obra primera. Editorial Uno."),
        (118, "(1999b). Obra segunda. Editorial Dos."),
        (118, "(1999c). Obra tercera. Editorial Tres."),
        (72, "Lacan, J. (2001). Obra cuarta. Editorial Cuatro."),
        (72, "Miller, J. (2002). Obra quinta. Editorial Cinco."),
        (72, "Soler, C. (2003). Obra sexta. Editorial Seis."),
    ]
    for index, (x, text) in enumerate(lines):
        page.insert_text((x, 115 + index * 75), text, fontsize=10.5)
    doc.save(path)
    doc.close()


class TestBiblioRefV061(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="biblioref_v061_")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_stable_output_remains_exact(self):
        pdf = self.root / "stable.pdf"
        _stable_pdf(pdf)
        old = process_pdf_v06(pdf)
        new = process_pdf(pdf)
        self.assertEqual(old["records"], new["records"])
        self.assertEqual(old["zones"], new["zones"])
        self.assertTrue(new["detection_decision"]["stable_output_preserved"])

    def test_mirrored_margins_trigger_repair(self):
        pdf = self.root / "mirrored.pdf"
        _mirrored_pdf(pdf)
        result = process_pdf(pdf)
        self.assertEqual("stable_zone_resegmentation_v0_6_1", result["detection_decision"]["method"])
        self.assertEqual(30, result["n_records_selected"])
        margins = result["segmentation_repairs"][0]["page_start_margins"]
        self.assertNotEqual(margins["1"], margins["2"])

    def test_inherited_author_dates_are_separate_entries(self):
        pdf = self.root / "inherited.pdf"
        _inherited_author_pdf(pdf)
        result = process_pdf(pdf)
        self.assertEqual(6, result["n_records_selected"])
        inherited = [
            row for row in result["records"]
            if row["boundary_evidence"] == "inherited_author+date_only_entry"
        ]
        self.assertEqual(2, len(inherited))

    def test_running_numeric_headers_form_logical_group(self):
        zones = [
            {"zone_id": 1, "heading": "Bibliography", "start_page": 10, "end_page": 10,
             "numeric_first_marker": 1, "numeric_last_marker": 8},
            {"zone_id": 2, "heading": "11 BIBLIOGRAPHY", "start_page": 11, "end_page": 12,
             "numeric_first_marker": 9, "numeric_last_marker": 20},
        ]
        groups = _logical_running_header_groups(zones)
        self.assertEqual(1, len(groups))
        self.assertEqual([1, 2], groups[0]["zone_ids"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
