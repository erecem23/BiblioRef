# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.17: URLs partidas por el salto de línea.

El segmentador une las líneas de una referencia con un espacio. Cuando una URL
cruza el renglón, ese espacio queda dentro («…/obligatorias/0 42_ttedm2c2/…»,
«?sequence=1&isAllo wed=y»). Una URL no tiene espacios: si lo que sigue al
espacio es continuación de URL (lleva / = & % ? # _ o una extensión, o es un
tramo hexadecimal) se une. Nunca se une otra URL, una fecha ni prosa.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref.extraction.url_rejoin import rejoin_broken_urls


class BrokenUrlsAreRejoined(unittest.TestCase):
    def test_line_breaks_inside_urls(self):
        cases = [
            ("https://www.psicoterapiarelacional.es/eJournalCeIR/V6N2_2012/01_Benjamin_ Tercero-Reconocimiento_CeIR_V6N2.pdf",
             "https://www.psicoterapiarelacional.es/eJournalCeIR/V6N2_2012/01_Benjamin_Tercero-Reconocimiento_CeIR_V6N2.pdf"),
            ("http://www.psi.uba.ar/sitios_catedras/obligatorias/0 42_ttedm2c2/material/fichas/klein.pdf",
             "http://www.psi.uba.ar/sitios_catedras/obligatorias/042_ttedm2c2/material/fichas/klein.pdf"),
            ("https://tesis.pucp.edu.pe/server/api/core/bitstreams/fdc1c071-ef5c-45dd-b69d- 5052902a77a5/content",
             "https://tesis.pucp.edu.pe/server/api/core/bitstreams/fdc1c071-ef5c-45dd-b69d-5052902a77a5/content"),
            ("http://m.rpsico.mdp.edu.ar/bitstream/handle/123456789/70/MA04.pdf?sequence=1&isAllo wed=y",
             "http://m.rpsico.mdp.edu.ar/bitstream/handle/123456789/70/MA04.pdf?sequence=1&isAllowed=y"),
            ("https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1851- 16862014000200013&lng=es&tlng=es",
             "https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1851-16862014000200013&lng=es&tlng=es"),
            ("https://www.psi.uba.ar/sitios_catedras/practicas_pro fesionales/820_clinica/material/libertad.pdf",
             "https://www.psi.uba.ar/sitios_catedras/practicas_profesionales/820_clinica/material/libertad.pdf"),
            ("https://www.revistafroi.com/post/la-paradoja-en-winnicott-o-la- perturbaci%C3%B3n-del-orden-establecido",
             "https://www.revistafroi.com/post/la-paradoja-en-winnicott-o-la-perturbaci%C3%B3n-del-orden-establecido"),
            ("https://racimo.usal.edu.ar/4376/1/P%C3%A1ginas%20desdeTesis.El%2 0ni%C3%B1o%20y%20el%20significante.pdf",
             "https://racimo.usal.edu.ar/4376/1/P%C3%A1ginas%20desdeTesis.El%20ni%C3%B1o%20y%20el%20significante.pdf"),
            ("https://repositoriosdigitales.mincyt.gob.ar/vufind/Record/RDIUBA_4f23a266e769f0f2ae1d b311921d441e",
             "https://repositoriosdigitales.mincyt.gob.ar/vufind/Record/RDIUBA_4f23a266e769f0f2ae1db311921d441e"),
            ("https://tdx.cat/bitstream/handle/10803/360584/Tesi.pdf;jsessionid= 27DB55C74EEF9348B5E1A877130ABEE8?sequence=1",
             "https://tdx.cat/bitstream/handle/10803/360584/Tesi.pdf;jsessionid=27DB55C74EEF9348B5E1A877130ABEE8?sequence=1"),
            ("https://www.x.org/Volumen-1-1-Junio- 2007/CeIR_V1N1_2007_1CR_Sutil",
             "https://www.x.org/Volumen-1-1-Junio-2007/CeIR_V1N1_2007_1CR_Sutil"),
        ]
        for broken, whole in cases:
            with self.subTest(broken=broken):
                prefix = "Pérez, J. (2020). Un título. Revista, 3, 1-9. "
                self.assertEqual(prefix + whole, rejoin_broken_urls(prefix + broken))

    def test_doi_is_kept(self):
        text = "González, M. (2015). Violencia en la familia. https://doi.org/10.35537/10915/46553"
        self.assertEqual(text, rejoin_broken_urls(text))

    def test_prose_dates_and_other_urls_after_a_url_are_not_joined(self):
        for text in [
            "Pérez, J. (2020). Título. https://www.x.org/a/b Consultado el 12 de marzo de 2021.",
            "Pérez, J. (2020). Título. https://www.x.org/a/b 12/03/2021",
            "Pérez, J. (2020). Título. https://www.x.org/a/b https://www.y.org/c",
            "Pérez, J. (2020). Título. https://www.x.org/index.html. Buenos Aires: Paidós.",
            "Pérez, J. (2020). Título. Recuperado de www.x.org en marzo de 2021.",
            "Pérez, J. (2020). Título. https://www.x.org/a (p. 3).",
        ]:
            with self.subTest(text=text):
                self.assertEqual(text, rejoin_broken_urls(text))


class PageBoundaryWithListMarkers(unittest.TestCase):
    """Un borde de página entre dos referencias con viñeta no es dudoso.

    El evaluador no reconocía «○ Bareiro, J. (2021)…» como comienzo de
    referencia ni ignoraba el folio «292» al pie: los 12 bordes de una
    bibliografía con viñetas salían «review» sin evidencia en ningún sentido.
    """

    def test_bulleted_reference_after_a_folio_is_a_split(self):
        from biblioref_page_boundary import evaluate_page_boundary
        ev = evaluate_page_boundary(
            ["○ Bareiro, J. (2018). Winnicott y Heidegger. Hacia una metapsicología .", "Biblos.", "292"],
            ["○ Bareiro, J. (2021). Técnica y tratamiento en psicoanálisis, en J.",
             "Bareiro (Comp.). Winnicott en discusión (pp. 43-57). Letra Viva."],
        )
        self.assertEqual("split", ev["verdict"])

    def test_numbered_and_dashed_markers_too(self):
        from biblioref_page_boundary import evaluate_page_boundary
        for head in ["[12] Pérez, J. (2001). Título. Revista, 3, 1-9.", "12. Pérez, J. (2001). Título.",
                     "- Pérez, J. (2001). Título.", "• Pérez, J. (2001). Título."]:
            with self.subTest(head=head):
                self.assertEqual("split", evaluate_page_boundary(["Buenos Aires: Paidós.", "- 17 -"], [head])["verdict"])

    def test_a_continuation_after_a_folio_is_still_a_continuation(self):
        from biblioref_page_boundary import evaluate_page_boundary
        ev = evaluate_page_boundary(["○ Calzada, J. G. (2009). La clínica de lo cotidiano en", "293"],
                                    ["el acompañamiento terapéutico. Letra Viva."])
        self.assertEqual("continue", ev["verdict"])

    def test_a_url_at_the_top_of_the_page_continues_the_reference(self):
        from biblioref_page_boundary import evaluate_page_boundary
        ev = evaluate_page_boundary(["Revista digital de Trabajo Social , 1 (2), 188-196.", "293"],
                                    ["https://revistas.unc.edu.ar/index.php/ConCienciaSocial/article/view/19948",
                                     "Giberti, E. (2006, octubre). Hijos del rock."])
        self.assertEqual("continue", ev["verdict"])

    def test_a_url_ending_in_a_slash_is_not_an_open_line(self):
        from biblioref_page_boundary import evaluate_page_boundary
        ev = evaluate_page_boundary(["http://www.x.org/transhipocratismo/", "302"],
                                    ["Lakatos, I. (1989). La metodología de los programas de investigación.",
                                     "Madrid. Alianza Universitaria."])
        self.assertEqual("split", ev["verdict"])


class DeclarationTests(unittest.TestCase):
    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0617_SHA256.json"

    def setUp(self):
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.17", "0.6.18", "0.6.19", "0.6.20", "0.6.21"})

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[89]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_only_removes_spaces_inside_urls(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertTrue(equivalence["only_spaces_inside_urls_removed"])
        self.assertTrue(all(c["delta"] == 0 for c in equivalence["changed"]))


if __name__ == "__main__":
    unittest.main()
