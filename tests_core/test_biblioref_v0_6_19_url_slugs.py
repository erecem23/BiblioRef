"""0.6.19: URLs cut after «=» or inside a hyphenated file name.

Development case with hanging indent (orden 6 and 16): the line break falls
inside the query value («download.php?gal_id= 479») or between two words of a
file slug («actas-de-las primeras-jornadas-del-departamento de
psicoanálisis-2.pdf»). Only spaces inside a recognized URL are touched.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref.extraction.url_rejoin import rejoin_broken_urls


class QueryValuesAndSlugs(unittest.TestCase):
    def test_query_value_after_equals_is_joined(self):
        self.assertEqual(
            "Recuperado de: http://www.convergenciafreudlacan.org/inove4/php/download.php?gal_id=479",
            rejoin_broken_urls("Recuperado de: http://www.convergenciafreudlacan.org/inove4/php/download.php?gal_id= 479"),
        )

    def test_a_word_after_equals_is_prose(self):
        self.assertEqual("http://x.org/?id= Consultado el 3", rejoin_broken_urls("http://x.org/?id= Consultado el 3"))

    def test_hyphenated_file_slug_is_rebuilt_up_to_its_extension(self):
        self.assertEqual(
            "Recuperado de: http://www.fpsico.unr.edu.ar/wp-content/uploads/2016/02/"
            "actas-de-las-primeras-jornadas-del-departamento-de-psicoanálisis-2.pdf.",
            rejoin_broken_urls("Recuperado de: http://www.fpsico.unr.edu.ar/wp-content/uploads/2016/02/"
                               "actas-de-las primeras-jornadas-del-departamento de psicoanálisis-2.pdf."),
        )

    def test_prose_after_a_slug_is_not_joined(self):
        for text in [
            "Ver http://x.org/notas-de-campo y luego otra cosa.pdf",
            "http://x.org/a-b sobre la clínica en el hospital. Buenos Aires.",
            "http://x.org/a-b sobre-la clínica en el hospital. Buenos Aires.",
        ]:
            self.assertEqual(text, rejoin_broken_urls(text))


class DeclarationTests(unittest.TestCase):
    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0619_SHA256.json"

    def setUp(self):
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.19", "0.6.20"})

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json"):
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_only_touches_urls(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertEqual(equivalence["n_documents"], equivalence["n_identical"] + equivalence["n_changed"])
        self.assertTrue(all(c["delta"] == 0 for c in equivalence["changed"]))


if __name__ == "__main__":
    unittest.main()
