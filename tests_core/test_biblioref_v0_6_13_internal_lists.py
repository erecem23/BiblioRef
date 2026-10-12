# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.13: los «Bibliografía:» repetidos dentro del cuerpo.

T0136 (González, 2025) transcribe programas de materias; cada uno trae su
«Bibliografía:», y cada uno abría una zona con lecturas y hasta los puntos
numerados del programa («5. La educación sexual…»), antes de la bibliografía
real de la tesis («Referencias Bibliográficas:», 565 referencias).

Las bibliografías por capítulo se ven igual, así que los negativos cuentan tanto
como el positivo: sin bibliografía final grande, con el título repetido después
de ella, o con zonas que pesan más de un décimo, no se descarta nada.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref.pipeline import _drop_repeated_internal_lists


def result(zones):
    """zones: (heading, start_page, n_records)."""
    out = {"zones": [], "records": [], "n_records_selected": 0}
    for zone_id, (heading, page, n) in enumerate(zones, 1):
        out["zones"].append({"zone_id": zone_id, "heading": heading, "start_page": page, "end_page": page + 1})
        out["records"].extend({"zone_id": zone_id, "reference_text": f"r{zone_id}.{i}"} for i in range(n))
    out["n_records_selected"] = len(out["records"])
    return out


T0136 = [("Bibliografía:", 316, 0), ("Bibliografía:", 316, 0), ("Bibliografía:", 316, 0),
         ("Bibliografía:", 316, 2), ("Bibliografía:", 317, 16), ("Bibliografía:", 396, 0),
         ("Bibliografía:", 397, 1), ("Referencias Bibliográficas:", 475, 565)]


class InternalListTests(unittest.TestCase):
    def test_syllabus_bibliographies_before_the_final_one_are_dropped(self):
        out = _drop_repeated_internal_lists(result(T0136))
        self.assertEqual([8], [z["zone_id"] for z in out["zones"]])
        self.assertEqual(565, len(out["records"]))
        self.assertEqual(565, out["n_records_selected"])
        self.assertEqual(7, len(out["internal_list_zones_dropped"]))
        self.assertEqual(19, sum(z["n_records"] for z in out["internal_list_zones_dropped"]))

    def test_chapter_bibliographies_without_a_final_one_stay(self):
        chapters = [("Referencias", 40, 60), ("Referencias", 90, 55), ("Referencias", 140, 70)]
        out = _drop_repeated_internal_lists(result(chapters))
        self.assertEqual(3, len(out["zones"]))
        self.assertNotIn("internal_list_zones_dropped", out)

    def test_chapter_bibliographies_that_weigh_more_than_a_tenth_stay(self):
        zones = [("Referencias", 40, 30), ("Referencias", 90, 25), ("Referencias", 140, 20),
                 ("Bibliografía general", 200, 300)]
        out = _drop_repeated_internal_lists(result(zones))
        self.assertEqual(4, len(out["zones"]))

    def test_two_repeats_are_not_enough(self):
        zones = [("Bibliografía:", 100, 3), ("Bibliografía:", 150, 2), ("Referencias", 300, 400)]
        self.assertEqual(3, len(_drop_repeated_internal_lists(result(zones))["zones"]))

    def test_a_zone_after_the_largest_one_blocks_the_rule(self):
        zones = T0136 + [("Anexo: fuentes", 510, 20)]
        self.assertEqual(len(zones), len(_drop_repeated_internal_lists(result(zones))["zones"]))

    def test_a_small_final_bibliography_blocks_the_rule(self):
        zones = [("Bibliografía:", 10, 1), ("Bibliografía:", 20, 1), ("Bibliografía:", 30, 1),
                 ("Referencias", 90, 40)]
        self.assertEqual(4, len(_drop_repeated_internal_lists(result(zones))["zones"]))


class DeclarationTests(unittest.TestCase):
    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0613_SHA256.json"

    def setUp(self):
        self.assertTrue(self.MANIFEST.exists(), "falta la declaración del algoritmo 0.6.13")
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.13", "0.6.14", "0.6.15", "0.6.16", "0.6.17", "0.6.18", "0.6.19", "0.6.20", "0.6.21"})

    def test_only_the_declared_files_changed(self):
        self.assertEqual({"biblioref/pipeline.py", "biblioref/core/config.py"},
                         {f["file"] for f in self.manifest["deliberately_changed"]})
        self.assertTrue(self.manifest["all_identical"])

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[4-9]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_is_recorded(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        self.assertIn("T0136", {c["thesis_id"] for c in equivalence["changed"]})


if __name__ == "__main__":
    unittest.main()
