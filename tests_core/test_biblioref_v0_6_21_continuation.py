# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.21: listas numeradas cortadas en un salto de página (C1).

Un encabezado de página que repite el título del capítulo parece un título, y la
zona numerada terminaba en el primer salto de página aunque la lista siguiera
(Cortell Fuster 2024: 15 de 54, 6 de 26 y 12 de 23; tesis de química de
Exactas-UBA con una lista por capítulo). 0.6.21 mira la página siguiente: si,
después del folio y del encabezado, abre con el número que sigue al último de la
zona, la zona se extiende mientras la secuencia continúe, y una zona que el mismo
encabezado abrió con ese número se une a ella.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref.extraction.continuation import continue_numbered_zones, marker_of
from biblioref_v0_3 import LayoutLine


def line(page, text, y0, x0=90.0, size=10.0):
    return LayoutLine(page=page, page_height=842.0, text=text, x0=x0, y0=y0,
                      x1=x0 + 4.8 * len(text), y1=y0 + 11, median_font_size=size)


def record(zone_id, n, text, page):
    return {"zone_id": zone_id, "ref_in_zone": n, "reference_text": text,
            "reference_start_page": page, "reference_end_page": page, "zone_end_page": page}


def chapter_list():
    """Page 10: heading and entries 1-3; page 11: header, folio, entries 4-5 and a new chapter."""
    lines = [
        line(10, "References", 60, size=14.0),
        line(10, "(1) Curatolo P. Tuberous sclerosis. Lancet 2008;372:657-668.", 90),
        line(10, "(2) Salido R. Current options. Actas Dermosifiliogr 2014;105:558-568.", 104),
        line(10, "(3) Jozwiak S. Topical use of mTOR inhibitors. Pediatr Neurol", 118),
        line(10, "2016;61:21-27.", 132, x0=105.0),
        line(10, "86 | Página", 800),
        line(11, "Capítulo Primero", 40),
        line(11, "87 | Página", 52),
        line(11, "(4) Gallardo A. Control of epilepsy. Rev Neurol 2013;56:562-566.", 90),
        line(11, "(5) Narayanan V. Tuberous sclerosis complex: genetics to", 104),
        line(11, "pathogenesis. Pediatr Neurol 2003;29:404-409.", 118, x0=105.0),
        line(11, "Capítulo 2. Objetivos", 160, size=16.0),
        line(11, "El objetivo de esta tesis es evaluar la formulación tópica.", 190),
    ]
    zones = [{"zone_id": 1, "heading": "References", "start_page": 10, "end_page": 10, "n_segments": 3,
              "termination_reason": "layout_confirmed_stop_heading", "numeric_last_marker": 3}]
    records = [
        record(1, 1, "(1) Curatolo P. Tuberous sclerosis. Lancet 2008;372:657-668.", 10),
        record(1, 2, "(2) Salido R. Current options. Actas Dermosifiliogr 2014;105:558-568.", 10),
        record(1, 3, "(3) Jozwiak S. Topical use of mTOR inhibitors. Pediatr Neurol 2016;61:21-27.", 10),
    ]
    return zones, records, lines


class ContinuationTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(ALGORITHM_VERSION, "0.6.21")

    def test_marker_forms(self):
        self.assertEqual(marker_of("(12) Author"), 12)
        self.assertEqual(marker_of("[7] Author"), 7)
        self.assertEqual(marker_of("16.Álvarez"), 16)
        self.assertIsNone(marker_of("1.5 Methods"))

    def test_a_list_cut_at_a_running_header_is_extended(self):
        zones, records, lines = chapter_list()
        new_zones, new_records, repairs = continue_numbered_zones(zones, records, lines)
        texts = [r["reference_text"] for r in new_records]
        self.assertEqual(len(texts), 5)
        self.assertTrue(texts[3].startswith("(4) Gallardo"))
        self.assertTrue(texts[4].endswith("2003;29:404-409."))
        self.assertEqual(new_zones[0]["end_page"], 11)
        self.assertEqual(new_zones[0]["numeric_last_marker"], 5)
        self.assertEqual(new_zones[0]["termination_reason"], "numeric_continuation_extended")
        self.assertEqual(repairs[0]["records_added"], 2)

    def test_header_folio_and_next_chapter_stay_out(self):
        zones, records, lines = chapter_list()
        _, new_records, _ = continue_numbered_zones(zones, records, lines)
        joined = " ".join(r["reference_text"] for r in new_records)
        for furniture in ("Capítulo Primero", "87 | Página", "Capítulo 2", "objetivo"):
            self.assertNotIn(furniture, joined)

    def test_a_page_that_does_not_continue_the_sequence_changes_nothing(self):
        zones, records, lines = chapter_list()
        lines = [l for l in lines if l.page == 10] + [
            line(11, "Capítulo Primero", 40),
            line(11, "1. Introducción al problema de la piel.", 90),
        ]
        new_zones, new_records, repairs = continue_numbered_zones(zones, records, lines)
        self.assertEqual(repairs, [])
        self.assertEqual(len(new_records), 3)
        self.assertEqual(new_zones[0]["end_page"], 10)

    def test_a_zone_opened_by_the_header_is_merged(self):
        zones, records, lines = chapter_list()
        zones.append({"zone_id": 2, "heading": "Capítulo Primero", "start_page": 11, "end_page": 11, "n_segments": 2,
                      "termination_reason": "layout_confirmed_stop_heading", "numeric_first_marker": 4})
        records += [
            record(2, 1, "(4) Gallardo A. Control of epilepsy. Rev Neurol 2013;56:562-566.", 11),
            record(2, 2, "(5) Narayanan V. Tuberous sclerosis complex: genetics to pathogenesis. Pediatr Neurol 2003;29:404-409.", 11),
        ]
        new_zones, new_records, repairs = continue_numbered_zones(zones, records, lines)
        self.assertEqual(len(new_zones), 1)
        self.assertEqual([r["ref_in_zone"] for r in new_records], [1, 2, 3, 4, 5])
        self.assertEqual(repairs[0]["zones_merged"], [2])


class DeclarationTests(unittest.TestCase):
    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0621_SHA256.json"

    def setUp(self):
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in root.glob("EXTRACTION_CORE_NONREGRESSION_V062[2-9]_SHA256.json"):
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_development_corpus_is_unchanged(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        self.assertEqual(equivalence["n_identical"], equivalence["n_documents"])


if __name__ == "__main__":
    unittest.main()
