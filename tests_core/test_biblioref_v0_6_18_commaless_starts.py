# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.18: inicios de referencia sin coma antes del año.

La resegmentación v0.6.1 (``enhanced_start``) sólo aceptaba un inicio con una
coma antes del año («Apellido, I. (año)»). En una bibliografía con sangría
francesa perfecta se pegaban a la referencia de arriba: un autor corporativo
(«Convergencia (1998)»), un nombre sin coma («Etchvers Martín (2010)», «Nava
Murcia (2012)») y un punto en lugar de coma («González. O. (2016)»).

La señal nueva: pocas palabras de nombre seguidas de «(año)», en el margen de
inicio, cuando la línea anterior está sangrada (continuación) o cierra con
puntuación final. Una línea de prosa como «Buenos Aires (2010) fue …» dentro
de una referencia no cumple la segunda condición.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref_v0_3 import LayoutLine
from biblioref_v0_4 import detect_adaptive_layout_zones
from biblioref.extraction.resegmentation import segment_enhanced_zone

START, HANG = 85.1, 141.7


def line(page, text, x0, y0):
    return LayoutLine(page=page, page_height=842.0, text=text, x0=x0, y0=y0,
                      x1=x0 + 5.2 * len(text), y1=y0 + 14, median_font_size=12.0)


def zone_segments(entries):
    lines = [line(149, "BIBLIOGRAFÍA", 260, 60)]
    y = 90.0
    for x, text in entries:
        lines.append(line(149, text, x, y))
        y += 14
    zone = detect_adaptive_layout_zones(lines)[0]
    segments, _ = segment_enhanced_zone(zone)
    return [s["reference_text"] for s in segments]


BASE = [
    (START, "Clavreul, J. (1983). El orden médico . Barcelona, Argot."),
    (START, "Cohen, V. (2010). El cuerpo y lo sexual. laPsus Calami , 1. pp. 13-14"),
    (START, "Braunstein, N. (1994). La clínica del goce. Buenos Aires: Siglo XXI."),
    (START, "------------- (2013). Clasificar en psiquiatría. México: Siglo XXI."),
    (START, "Colovini, M. Teresa (2004). Tesis de Doctorado: “Amor, locura y femineidad. La"),
    (HANG, "erotomanía, el delirio de ser amada” Facultad de"),
    (HANG, "Psicología. UNR. Inédita."),
    (START, "Convergencia (1998). Acta de fundación (3 de octubre de 1998) . Recuperado de:"),
    (HANG, "http://www.convergenciafreudlacan.org/actas/acta.html"),
    (START, "Eribon, Didier et al. (2004). El infrecuentable Michel Foucault. Renovación del"),
    (HANG, "pensamiento crítico. Buenos Aires. Letra Viva+Edelp."),
    (START, "Etchvers Martín (2010). Combinación de Tratamientos y complementariedad"),
    (HANG, "Terapéutica en el abordaje de los trastornos depresivos. Recuperado en:"),
    (HANG, "Recuperado de:"),
    (HANG, "http://www.revistauaricha.umich.mx/Articulos/uaricha_1022_114-126.pdf ."),
    (START, "González. O. (2016). Momento de concluir y subjetividad . Jornadas de la Escuela"),
    (HANG, "Freudiana de Buenos Aires. Inédito."),
    (START, "Muñoz, P. (2009). La invención lacaniana del pasaje al acto. Buenos Aires: Manantial."),
    (START, "------------- (2012). El problema del diagnóstico. Revista Borromeo , 3. Recuperado de:"),
    (START, "http://borromeo.kennedy.edu.ar/Artculos/DiagnosticoMunoz.pdf."),
    (START, "Nava Murcia (2012). El mal de archivo en la escritura de la historia. Historia y"),
    (HANG, "Grafía, 38. pp. 95-126."),
]


class CommalessStarts(unittest.TestCase):
    def test_each_commaless_start_opens_its_own_reference(self):
        texts = zone_segments(BASE)
        for start in ["Convergencia (1998)", "Etchvers Martín (2010)", "González. O. (2016)", "Nava Murcia (2012)"]:
            with self.subTest(start=start):
                self.assertTrue(any(t.startswith(start) for t in texts), texts)
        self.assertEqual(12, len(texts), texts)

    def test_repeated_author_marks_still_open(self):
        texts = zone_segments(BASE)
        self.assertEqual(2, sum(t.startswith("-------------") for t in texts), texts)

    def test_a_name_and_year_inside_an_open_sentence_does_not_split(self):
        texts = zone_segments([
            (START, "Pérez, J. (2010). La ciudad y sus márgenes. Estudio de caso en"),
            (START, "Buenos Aires (2001) y sus consecuencias. Buenos Aires: Paidós."),
            (START, "Gómez, A. (2012). Otra obra. Madrid: Síntesis."),
        ])
        self.assertEqual(2, len(texts), texts)


class ReverseIndentUppercaseContinuation(unittest.TestCase):
    """Con sangría invertida (comienzo a la derecha, continuación a la izquierda),
    una continuación que empieza con una sigla («MERCOSUR, Facultad…», «UBA.»)
    no es un comienzo ABNT: el margen izquierdo es el de las continuaciones."""

    def test_acronym_continuations_stay_with_their_reference(self):
        from biblioref_v0_4 import segment_adaptive_layout_zone

        def ln(text, x, y):
            return LayoutLine(page=198, page_height=842.0, text=text, x0=x, y0=y,
                              x1=x + 5.2 * len(text), y1=y + 12, median_font_size=12.0)
        lines = [ln("Bibliografía", 260, 50)]
        y = 80
        for i in range(10):
            lines.append(ln(f"Autor{chr(65 + i)}, C. ({2001 + i}). Estrategias colectivas ante la vulnerabilización", 127.7, y)); y += 18
            lines.append(ln("social. Memorias II Jornadas de Investigación y Encuentro del", 99.2, y)); y += 18
            lines.append(ln("MERCOSUR, Facultad de Psicología, UBA. Buenos Aires.", 99.2, y)); y += 24
        zone = detect_adaptive_layout_zones(lines)[0]
        texts = [s["reference_text"] for s in segment_adaptive_layout_zone(zone)]
        self.assertEqual(10, len(texts), texts)


class DominantMarginDropsRunningHeaders(unittest.TestCase):
    """La reconciliación de margen dominante lee las líneas crudas de la zona.

    Una firma repetida arriba de cada página («Lic. N. N.») al 7,8 % de la
    altura quedaba fuera de su banda del 7,5 % y se pegaba a las referencias.
    """

    def test_repeated_signature_is_not_zone_text(self):
        from biblioref.extraction.dominant_margin_reconciliation import _physical_zone_lines

        def ln(page, text, x, y):
            return LayoutLine(page=page, page_height=842.0, text=text, x0=x, y0=y,
                              x1=x + 5.2 * len(text), y1=y + 12, median_font_size=12.0)
        doc = [ln(226, "REFERENCIAS", 85, 40)]
        for page in range(226, 231):
            doc.append(ln(page, "Lic. Nicolás Campodónico", 453.3, 66))
            doc.append(ln(page, f"AUTOR, A. ({1990 + page - 226}). Obra. Buenos Aires: Paidós.", 92, 100))
        zone = detect_adaptive_layout_zones(doc)[0]
        texts = [l.text for l in _physical_zone_lines(doc, zone)]
        self.assertNotIn("Lic. Nicolás Campodónico", texts)
        self.assertEqual(5, sum(t.startswith("AUTOR") for t in texts))


class SmallFontUrls(unittest.TestCase):
    """Un hipervínculo en cuerpo menor no es ruido de letra chica.

    El filtro de ruido sacaba de la zona las URLs escritas en 11 pt dentro de
    una bibliografía en 12 pt, y la referencia quedaba en «Disponible en:».
    """

    def test_small_font_url_lines_stay_in_the_zone(self):
        def ln(text, x, y, size=12.0):
            return LayoutLine(page=202, page_height=842.0, text=text, x0=x, y0=y,
                              x1=x + 5.2 * len(text), y1=y + 14, median_font_size=size)
        lines = [ln("Bibliografía", 260, 60)]
        y = 90
        for i in range(8):
            lines.append(ln(f"Autor{chr(65 + i)}, G. ({2000 + i}). Obra número {i}. Disponible en:", 127.7, y)); y += 14
            lines.append(ln(f"http://www.iisg.nl/labouragain/documents/obra_{i}_", 99.2, y, 11.0)); y += 14
            lines.append(ln(f"completa-{i}.pdf", 99.2, y, 11.0)); y += 14
        zone = detect_adaptive_layout_zones(lines)[0]
        texts = [s["reference_text"] for s in segment_enhanced_zone(zone)[0]]
        self.assertEqual(8, len(texts), texts)
        self.assertTrue(all(".pdf" in t and "http://" in t for t in texts), texts)

    def test_small_print_notes_are_still_dropped(self):
        def ln(text, x, y, size=12.0):
            return LayoutLine(page=10, page_height=842.0, text=text, x0=x, y0=y,
                              x1=x + 5.2 * len(text), y1=y + 14, median_font_size=size)
        lines = [ln("Referencias", 85, 60)] + [
            ln(f"Autor{chr(65 + i)}, G. ({2000 + i}). Obra número {i}. Buenos Aires: Paidós.", 85, 90 + 14 * i) for i in range(8)
        ] + [ln("1 Nota al pie en letra chica con comentario del autor.", 85, 780, 9.0)]
        zone = detect_adaptive_layout_zones(lines)[0]
        self.assertFalse(any("Nota al pie" in l.text for l in zone.lines))


class DeclarationTests(unittest.TestCase):
    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0618_SHA256.json"

    def setUp(self):
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.18", "0.6.19", "0.6.20", "0.6.21"})

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V0619_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_change_is_recorded(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        self.assertEqual(equivalence["n_documents"], equivalence["n_identical"] + equivalence["n_changed"])


if __name__ == "__main__":
    unittest.main()
