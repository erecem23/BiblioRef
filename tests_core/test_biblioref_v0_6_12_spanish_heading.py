# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.12: «Lista de referencias» abre la bibliografía.

El vocabulario ya aceptaba «List of references» y «Reference list», pero no su
forma en español. T0130 (Dematteis, 2025) titula así su bibliografía, en negrita
y centrada en la página 97, y quedaba con cero referencias aunque el índice la
anunciaba.

Los negativos importan tanto como el positivo: la entrada del índice con su folio
no es un encabezado, y una frase que sólo empieza igual tampoco.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref_v0_2 import is_ref_heading
from biblioref_v0_3 import LayoutLine, _is_reference_heading


def line(text, y=87.0, h=842.0, page=97):
    return LayoutLine(page=page, page_height=h, text=text, x0=252.0, y0=y,
                      x1=352.0, y1=y + 11, median_font_size=11.0, fragment_count=1)


class SpanishListHeadingTests(unittest.TestCase):
    def test_spanish_list_headings_open_a_zone(self):
        for text in ["Lista de Referencias", "LISTA DE REFERENCIAS", "Lista de referencias bibliográficas",
                     "Listado de referencias", "Lista de obras citadas"]:
            with self.subTest(text=text):
                self.assertTrue(is_ref_heading(text))
        self.assertTrue(_is_reference_heading(line("Lista de Referencias")))

    def test_table_of_contents_entry_and_prose_do_not(self):
        for text in ["Lista de Referencias 97", "Lista de referencias de la escala",
                     "Lista de tablas", "Lista de figuras", "Lista de abreviaturas"]:
            with self.subTest(text=text):
                self.assertFalse(is_ref_heading(text))


class DeclarationTests(unittest.TestCase):
    """El cambio se declara con su equivalencia sobre el corpus completo."""

    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0612_SHA256.json"

    def setUp(self):
        self.assertTrue(self.MANIFEST.exists(), "falta la declaración del algoritmo 0.6.12")
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.12", "0.6.13", "0.6.14", "0.6.15", "0.6.16", "0.6.17", "0.6.18", "0.6.19", "0.6.20"})

    def test_only_the_declared_files_changed(self):
        self.assertEqual({"biblioref_v0_2.py", "biblioref/core/config.py"},
                         {f["file"] for f in self.manifest["deliberately_changed"]})
        self.assertTrue(self.manifest["all_identical"])

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[3-9]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_only_adds_references(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        self.assertIn("T0130", {c["thesis_id"] for c in equivalence["changed"]})
        for changed in equivalence["changed"]:
            self.assertGreaterEqual(changed["delta"], 0, changed["thesis_id"])


if __name__ == "__main__":
    unittest.main()
