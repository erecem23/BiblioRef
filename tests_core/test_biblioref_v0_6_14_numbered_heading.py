# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.14: el numeral del encabezado es un token entero.

``_strip_heading_prefix`` quitaba la numeración jerárquica («5.», «III.2.1.»)
pero, en los niveles que siguen al primero, no exigía que el numeral romano
terminara ahí. En «5. Lista de referencias» tomaba «Li» como un segundo nivel y
dejaba «sta de referencias»; lo mismo con «5. List of references» y
«5. Literatura citada». Sin número adelante ya se reconocían (0.6.12). Tampoco
se reconocían los enumeradores con paréntesis o con letra: T0137 titula su
bibliografía «G) BIBLIOGRAFIA GENERAL» y quedaba en cero.

Un numeral sólo se quita si es un token entero seguido de separador, espacio o
fin; nunca el comienzo de una palabra. Los enumeradores con «)» y la letra con
«.» se quitan sólo para el test de encabezado bibliográfico: «10) Parte de la
ley» es una referencia numerada y no puede volverse un encabezado de corte.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref_v0_2 import _strip_heading_prefix, is_ref_heading, is_stop_heading


class NumberedHeadingTests(unittest.TestCase):
    def test_numbered_list_headings_open_a_zone(self):
        for text in ["5. Lista de referencias", "5. List of references", "V. List of references",
                     "II. Referencias", "5. Literatura citada", "III.2.1. Lista de referencias",
                     "5 Lista de referencias", "Lista de referencias",
                     "G) BIBLIOGRAFIA GENERAL", "7) Referencias", "b) Referencias", "A. Bibliografía"]:
            with self.subTest(text=text):
                self.assertTrue(is_ref_heading(text))

    def test_the_numeral_never_eats_the_start_of_a_word(self):
        self.assertEqual("lista de referencias", _strip_heading_prefix("5. Lista de referencias"))
        self.assertEqual("list of references", _strip_heading_prefix("V. List of references"))
        self.assertEqual("literatura citada", _strip_heading_prefix("5. Literatura citada"))
        self.assertEqual("lista de tablas", _strip_heading_prefix("5. Lista de tablas"))

    def test_whole_numerals_are_still_stripped(self):
        for text in ["II. Referencias", "5. Referencias", "III.2.1. Referencias",
                     "IV–5- Referencias", "5.2: Referencias"]:
            with self.subTest(text=text):
                self.assertEqual("referencias", _strip_heading_prefix(text))

    def test_table_of_contents_entry_and_other_lists_do_not(self):
        for text in ["5. Lista de referencias 97", "V. List of references 214",
                     "Lista de tablas", "5. Lista de tablas", "II. Lista de figuras"]:
            with self.subTest(text=text):
                self.assertFalse(is_ref_heading(text))

    def test_parenthesis_enumerators_stay_out_of_the_shared_prefix(self):
        # «10) Parte de la ley» es una referencia numerada: si el prefijo
        # compartido quitara «10)», is_stop_heading la leería como «Parte ...».
        self.assertEqual("10) parte de la ley 12.912.-", _strip_heading_prefix("10) Parte de la ley 12.912.-"))
        self.assertFalse(is_stop_heading("10) Parte de la ley 12.912.-"))
        self.assertFalse(is_stop_heading("b) Parte de la ley 12.912.-"))

    def test_a_letter_that_is_a_word_is_kept(self):
        self.assertEqual("a la memoria de mi padre", _strip_heading_prefix("A la memoria de mi padre"))
        self.assertEqual("y referencias bibliograficas", _strip_heading_prefix("Y referencias bibliográficas"))
        for text in ["A la memoria de mi padre", "Y referencias bibliográficas"]:
            with self.subTest(text=text):
                self.assertFalse(is_ref_heading(text))


class DeclarationTests(unittest.TestCase):
    """El cambio se declara con su equivalencia sobre el corpus completo."""

    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0614_SHA256.json"

    def setUp(self):
        self.assertTrue(self.MANIFEST.exists(), "falta la declaración del algoritmo 0.6.14")
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.14", "0.6.15", "0.6.16", "0.6.17", "0.6.18", "0.6.19", "0.6.20"})

    def test_only_the_declared_files_changed(self):
        self.assertEqual({"biblioref_v0_2.py", "biblioref/core/config.py"},
                         {f["file"] for f in self.manifest["deliberately_changed"]})
        self.assertTrue(self.manifest["all_identical"])

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[5-9]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_only_adds_references(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        for changed in equivalence["changed"]:
            self.assertGreaterEqual(changed["delta"], 0, changed["thesis_id"])


if __name__ == "__main__":
    unittest.main()
