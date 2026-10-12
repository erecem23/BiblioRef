# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.15: guardas de contexto al abrir una zona.

Tres errores de detección de zona vistos en el benchmark consolidado, cada uno
en más de una tesis:

1. El final de una oración de prosa («... no ha sido reportado en la /
   bibliografía.») cae solo en una línea y el vocabulario lo acepta como
   encabezado. Abre una zona de prosa en medio del cuerpo.
2. Una portadilla «Bibliografía / y / Anexos» abre una zona que «Anexos» corta
   de inmediato, y el encabezado real de la página siguiente se descarta como
   encabezado corrido repetido. La bibliografía entera queda sin zona.
3. «REFERENCIAS» como celda de una tabla abre una zona sobre la tabla.

Las guardas usan geometría y contexto, no vocabulario: minúscula inicial más
línea previa del mismo párrafo sin puntuación final; ausencia de contenido entre
dos encabezados iguales; celdas vecinas en la misma banda horizontal.
"""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION
from biblioref_v0_3 import LayoutLine
from biblioref_v0_4 import detect_adaptive_layout_zones

PAGE_H = 842.0


def line(page, text, x0, y0, width=None, height=12.0, size=11.0):
    width = width if width is not None else 5.2 * len(text)
    return LayoutLine(page=page, page_height=PAGE_H, text=text, x0=x0, y0=y0,
                      x1=x0 + width, y1=y0 + height, median_font_size=size)


def prose_page(page, sentences, y=90.0, tail=None):
    out = []
    for text in sentences:
        out.append(line(page, text, 85, y, width=430))
        y += 16
    if tail:
        out.append(line(page, tail, 85, y))
        y += 16
    out.append(line(page, str(page), 300, 800, width=12))
    return out


PROSE = [
    "En este capítulo se presentan los resultados obtenidos con los catalizadores",
    "preparados, que muestran una actividad elevada durante los tres ciclos de",
    "reacción y una selectividad que no se modifica de manera apreciable entre",
    "los ensayos realizados, algo que hasta el momento no ha sido reportado en la",
]

REFERENCES = [
    ("Acebal, A., Fabiani, L. y Martínez, M. (2016). Reflexiones teórico-epistemológicas", "sobre la construcción de políticas urbanas. Mar del Plata: Eudem."),
    ("Aguirre, S. (1995). La otra escena. En Hacia una articulación de la clínica y la", "teoría. Buenos Aires: Ediciones Tres Lunas."),
    ("Akselrad, R. y Levit, C. (2002). Acompañamiento terapéutico y autismo. En Rossi,", "G. (Comp.), Eficacia clínica. Buenos Aires: Polemos."),
    ("Apollon, W. (1997). Introducción. En Apollon, W., Bergeron, D. y Cantin, L.,", "Tratar la psicosis. Buenos Aires: Polemos."),
    ("Araujo, F. (2013). Um passeio esquizo pelo acompanhamento terapeutico. Rio de", "Janeiro: Fabio Araujo."),
    ("Argañaraz, J. (2007). El freudismo reformista: 1926-1976. Córdoba: Brujas.", None),
    ("Baremblitt, G. (1991). Compendio de análisis institucional. Buenos Aires: Ediciones", "Madres de Plaza de Mayo."),
    ("Bessón, A. (2018). La clínica de lo cotidiano. Revista de Psicología, 12(2),", "45-60."),
    ("Cabral, K. (2005). Acompanhamento terapêutico como dispositivo da reforma", "psiquiátrica. Porto Alegre: UFRGS."),
    ("Dozza de Mendonça, L. (2014). O acompanhamento terapêutico. São Paulo: Escuta.", None),
    ("Kalina, E. (1985). Psicoterapia de adolescentes. Buenos Aires: Amorrortu.", None),
    ("Lancetti, A. (2008). Clínica peripatética. São Paulo: Hucitec.", None),
]


def reference_lines(page, y=110.0):
    out = []
    for first, rest in REFERENCES:
        out.append(line(page, first, 85, y, width=430))
        y += 16
        if rest:
            out.append(line(page, rest, 120, y, width=300))
            y += 16
    out.append(line(page, str(page), 300, 800, width=12))
    return out


def annex_page(page):
    return [
        line(page, "ANEXOS", 260, 90, width=70),
        line(page, "Anexo 1. Consentimiento informado utilizado en las entrevistas.", 85, 130, width=400),
        line(page, str(page), 300, 800, width=12),
    ]


class ProseTailIsNotAHeading(unittest.TestCase):
    def test_sentence_ending_in_bibliography_does_not_open_a_zone(self):
        lines = (
            prose_page(10, PROSE, tail="bibliografía.")
            + prose_page(11, PROSE)
            + [line(20, "Referencias", 85, 80, width=80)]
            + reference_lines(20)
        )
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual([20], [z.start_page for z in zones])

    def test_a_lowercase_heading_after_a_closed_paragraph_still_opens(self):
        closed = PROSE[:-1] + ["los ensayos realizados en las condiciones habituales."]
        lines = prose_page(19, closed) + [line(20, "referencias", 85, 80, width=80)] + reference_lines(20)
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual([20], [z.start_page for z in zones])


class DividerPageBeforeTheBibliography(unittest.TestCase):
    def test_the_real_heading_after_a_divider_opens_the_zone(self):
        lines = (
            prose_page(283, PROSE)
            + [
                line(284, "Bibliografía", 237, 252, width=80, size=20),
                line(284, "y", 304, 303, width=6, size=20),
                line(284, "Anexos", 262, 355, width=60, size=20),
                line(284, "284", 300, 800, width=12),
                line(285, "Bibliografía", 282, 85, width=80),
            ]
            + reference_lines(285, y=113)
            + reference_lines(286, y=60)
            + annex_page(290)
        )
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual(285, zones[0].start_page)
        self.assertGreaterEqual(zones[0].end_page, 286)

    def test_running_header_after_the_real_heading_is_still_deduplicated(self):
        lines = (
            prose_page(99, PROSE)
            + [line(100, "Referencias", 85, 300, width=80)]
            + reference_lines(100, y=330)
            + [line(101, "Referencias", 85, 40, width=80)]
            + reference_lines(101, y=70)
        )
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual([100], [z.start_page for z in zones])


class TableCellIsNotAHeading(unittest.TestCase):
    def test_heading_word_inside_a_table_row(self):
        table = [
            line(182, "REFERENCIAS TRANSVERSALES GÉNERO", 240, 346, width=220),
            line(182, "PORCENTAJE DE", 412, 370, width=92, height=14),
            line(182, "AÑO NÚMERO ARTÍCULOS SIN ARTÍCULOS CON", 85, 376, width=311, height=14),
            line(182, "ARTÍCULOS CON", 413, 382, width=90, height=14),
            line(182, "REFERENCIAS REFERENCIAS", 205, 388, width=186, height=14),
            line(182, "REFERENCIAS", 418, 394, width=79, height=14),
            line(182, "DE GÉNERO DE GÉNERO", 212, 400, width=169, height=14),
            line(182, "DE GÉNERO", 426, 406, width=62, height=14),
        ] + [line(182, f"{1964 + i} {i + 1} {6 + i} {i % 2} {i * 3}%", 86, 431 + 25 * i, width=378) for i in range(10)]
        lines = prose_page(181, PROSE) + table + prose_page(183, PROSE)
        self.assertEqual([], [z.start_page for z in detect_adaptive_layout_zones(lines)])

    def test_scan_edge_noise_beside_a_heading_is_not_a_table(self):
        # OCR de una página escaneada: «·» del borde izquierdo y «|» del derecho
        # caen en la banda del encabezado. No son celdas.
        lines = (
            prose_page(120, PROSE)
            + [line(121, "·", 6, 120, width=5, height=18),
               line(121, "Referencias bibliográficas:", 115, 122, width=197, height=16),
               line(121, "|", 590, 124, width=1, height=12)]
            + reference_lines(121, y=156)
        )
        self.assertEqual([121], [z.start_page for z in detect_adaptive_layout_zones(lines)])

    def test_heading_beside_its_folio_still_opens(self):
        lines = (
            prose_page(213, PROSE)
            + [line(214, "8. REFERENCIAS BIBLIOGRÁFICAS", 72, 23, width=200),
               line(214, "214", 517, 24, width=18)]
            + reference_lines(214, y=122)
        )
        self.assertEqual([214], [z.start_page for z in detect_adaptive_layout_zones(lines)])


class AccessTailStaysWithItsReference(unittest.TestCase):
    """«Recuperado de: http://…» es la cola de la referencia anterior.

    En estilo con viñetas cada registro abre con su marca; la línea de acceso no
    la tiene, pero ``NAMED_WEB_SOURCE_RX`` («Nombre: http://…») la tomaba como
    una fuente web con nombre, y la regla «autor + recuperado de» abría registro
    con una continuación como «Zeitschrift , 21 (3-43). Recuperado de www…».
    """

    def segments(self, body):
        from biblioref_v0_4 import segment_adaptive_layout_zone
        lines = [line(10, "REFERENCIAS", 85, 60, width=90)]
        y, page = 90.0, 10
        for text in body:
            if text == "<PAGE>":
                page, y = page + 1, 70.0
                continue
            lines.append(line(page, text, 90, y, width=420))
            y += 14
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("bulleted", zones[0].style.style)
        return [s["reference_text"] for s in segment_adaptive_layout_zone(zones[0])]

    def test_retrieval_lines_are_not_records(self):
        texts = self.segments([
            "-Ávila, M. (2011). Teoría e historia del movimiento feminista.",
            "Recuperado de: www.example.org/feminismo_2011-2012.pdf",
            "-Bertone, C. (2006). Las revistas se publicaron con la plata. Ramona, 62, 53-66.",
            "Disponible en: http://www.example.org/files/R62.pdf",
            "-Bonino, L. (1998). Micromachismos: la violencia invisible en la",
            "pareja. Recuperado de: http://www.example.org/pdf/mM96.pdf",
            "-Gómez, P. (2008). Familia y matrimonio. Gazeta de Antropología, 24(1), 00-",
            "00. Recuperado de: http://hdl.handle.net/10481/7073",
            "-Stahnisch, F. (2010). German-speaking émigré neuroscientists. Zeitschrift für",
            "Geschichtswissenschaften , 21 (3-43). Recuperado de www.example.org",
            "-Stock, A. (2014). Schumann's wheel tachistoscope. Retrieved from",
            "https://example.org/stock",
        ])
        self.assertEqual(6, len(texts), texts)
        self.assertIn("feminismo_2011", texts[0])
        self.assertIn("hdl.handle.net", texts[3])
        self.assertIn("Geschichtswissenschaften", texts[4])

    def test_access_phrase_split_across_lines_or_pages(self):
        texts = self.segments([
            "-Andréu, J. (2001). Las técnicas de análisis de contenido. Andalucía: Fundación. Recuperado",
            "de: http://public.example.es/pdfs/S200103.pdf",
            "-Ávila, M. (2011). Teoría e historia del movimiento feminista.",
            "<PAGE>",
            "Recuperado de: www.example.es/.../feminismo_2011-",
            "2012.pdf",
            "-Aulagnier, P. (1979). Los destinos del placer. Buenos Aires: Paidós.",
        ])
        self.assertEqual(3, len(texts), texts)

    def test_named_web_sources_still_open_records(self):
        texts = self.segments([
            "-Alonso, R. (2008). Primera obra.",
            "-Aumont, J. (1992). Segunda obra.",
            "Alberto Goldenstein: http://example.org/alberto",
            "Museo de Arte Moderno: https://example.org/museo",
        ])
        self.assertEqual(4, len(texts), texts)

    def test_author_with_retrieval_statement_still_opens(self):
        texts = self.segments([
            "-Alonso, R. (2008). Primera obra.",
            "Danziger, K. Towards a Polycentric History of Psychology. Recuperado de:",
            "www.example.org/paper9",
            "-Degand, L. (1951). La Psychologie de l'art.",
        ])
        self.assertEqual(3, len(texts), texts)


class NumberedListContinuations(unittest.TestCase):
    """En una lista ``[n]`` la línea que sigue es continuación, no un registro.

    Sin sangría francesa, «(2005) 1.» se leía como el marcador «(n)» y
    «Chem. 184 (2002) 431.» abría registro por «palabra + año entre paréntesis».
    «[1 ]-» con espacio no se reconocía y la primera referencia se perdía.
    """

    def segments(self, body):
        from biblioref_v0_4 import segment_adaptive_layout_zone
        lines = [line(52, "II–7-REFERENCIAS BIBLIOGRÁFICAS.", 85, 572, width=200)]
        y = 610.0
        page = 52
        for text in body:
            if y > 780:
                page, y = page + 1, 80.0
            lines.append(line(page, text, 85, y, width=420))
            y += 19
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("numeric", zones[0].style.style)
        return [s["reference_text"] for s in segment_adaptive_layout_zone(zones[0])]

    def test_continuation_lines_stay_in_their_reference(self):
        texts = self.segments([
            "[1 ]-J.-M. Basset, R. Psaro, D. Roberto, R. Ugo; Modern Surface Organometallic",
            "Chemistry, Wiley - VCH Verlag GmbH , Weinheim (2009).",
            "[2]- O.A. Ferretti, M.L. Casella; Lat. Ame. Appl. Res. 25 (1995) 125.",
            "[3]-P. Reyes, M.C. Aguirre, J.L.G. Fierro, G. Santori; J. Molec. Catal. A:",
            "Chem.184 (2002) 431.",
            "[4]-J. L. Margitfalvi, I. Borbáth, M. Hegedüs, A. Tompos; Appl. Catal. A: Gen. 229",
            "(2002) 35.",
            "[5]-L. Sordelli, R. Psaro, G. Vlaic, A. Cepparo, S. Recchia, C. Dossi;",
            "J. Catal. 182 (1999) 186.",
            "[6]-P. Claus, Top. Catal. 5 (1998) 51.",
        ])
        self.assertEqual(6, len(texts), texts)
        self.assertTrue(texts[0].startswith("[1 ]-J.-M. Basset"), texts[0])
        self.assertIn("Chem.184 (2002) 431.", texts[2])
        self.assertIn("(2002) 35.", texts[3])

    def test_author_year_lines_before_the_first_marker_still_open(self):
        texts = self.segments([
            "Macionis, J. y Plummer, K. (2011). Sociología. Madrid: Pearson.",
            "Giddens, Anthony (1999). Sociología. Madrid: Alianza Editorial.",
            "Soriano, Ramón (2011). Sociología del Derecho. Barcelona: Ariel.",
            "[1]-P. Claus, Top. Catal. 5 (1998) 51.",
            "[2]-A. Corma, S. Iborra, A. Velty; Chem. Rev. 107 (2007) 2411.",
            "[3]-J. L. Margitfalvi, I. Borbáth; Appl. Catal. A: Gen. 229",
            "(2002) 35.",
        ])
        self.assertEqual(6, len(texts), texts)
        self.assertTrue(texts[1].startswith("Giddens"), texts)

    def test_a_few_numbered_lines_do_not_make_an_author_year_list_numeric(self):
        from biblioref_v0_4 import diagnose_adaptive_style
        texts = []
        for i in range(40):
            texts.append(f"Autor{chr(65 + i % 26)}, B. ({1980 + i}). Título de la obra número {i}. Buenos Aires: Paidós.")
            texts.append("continuación del título y datos editoriales.")
        texts += [f"{n}. Kuras, S. ({1985 + n}). Libro de la lista del anexo." for n in range(1, 8)]
        self.assertEqual("author_year_comma", diagnose_adaptive_style(texts).style)

    def test_a_numbered_list_with_some_author_lines_stays_numeric(self):
        from biblioref_v0_4 import diagnose_adaptive_style
        texts = []
        for n in range(1, 12):
            texts.append(f"[{n}]-P. Autor, D. Otro; J. Catal. {100 + n} ({1990 + n}) {n * 7}.")
            texts.append(f"Chem. {n} ({2000 + n}) 41.")
        self.assertEqual("numeric", diagnose_adaptive_style(texts).style)

    def test_parenthesised_small_numbers_are_still_markers(self):
        from biblioref_v0_2 import _numeric_marker_value
        self.assertEqual(12, _numeric_marker_value("(12) Smith, J. Title."))
        self.assertEqual(3, _numeric_marker_value("[ 3 ] Smith, J. Title."))


class DecoratedFolio(unittest.TestCase):
    """«[303]», «- 24 -», «-105-» al pie son el número de página, no texto.

    Sólo se reconocían folios de dígitos pelados; los decorados se pegaban a la
    última referencia de cada página («… Córdoba, Argentina. [303]»).
    """

    def test_decorated_folios_in_the_page_band_are_footers(self):
        from biblioref_v0_3 import _is_footer
        for text in ["[303]", "- 24 -", "-105-", "— 12 —", "[ 7 ]", "303", "xii"]:
            with self.subTest(text=text):
                self.assertTrue(_is_footer(line(303, text, 300, 795, width=20)))

    def test_markers_in_the_body_or_parenthesised_are_not(self):
        from biblioref_v0_3 import _is_footer
        self.assertFalse(_is_footer(line(303, "[303]", 85, 400, width=20)))
        self.assertFalse(_is_footer(line(303, "(12)", 300, 795, width=20)))
        self.assertFalse(_is_footer(line(303, "[12] Smith, J. (2001). Title.", 85, 795, width=300)))


class DictionaryRunningHeader(unittest.TestCase):
    """«REFERENCIAS BIBLIOGRÁFICAS» + rango «A/B» arriba de cada página.

    El encabezado cae al 12 % de la altura, fuera de la banda del 8 % donde se
    buscan decoraciones, y el rango de letras se funde con la primera línea de
    la página («A/B - Alonso, J. …»). Uno partía una URL entre páginas.
    """

    def pages(self):
        from biblioref_v0_3 import LayoutLine
        firsts = ["A/B - Alonso, J. (2010). Comunicación y cuerpo. Madrid: Síntesis.",
                  "B/E - Blanco, L. (2007). Del espacio euclídeo. Buenos Aires: Paidós.",
                  "E/F gentina: Paidós.",
                  "P/S rias.psi.uba.ar/index.aspx?anio=2012"]
        out = []
        for offset, first in enumerate(firsts):
            page = 232 + offset
            out.append(LayoutLine(page, 842.0, "REFERENCIAS BIBLIOGRÁFICAS", 216, 103, 420, 124, 14.6))
            out.append(LayoutLine(page, 842.0, first, 90, 140, 500, 152, 11.0))
            out.append(LayoutLine(page, 842.0, "- Freud, S. (1905). Tres ensayos. Buenos Aires: Amorrortu.", 90, 170, 500, 182, 11.0))
        return out

    def test_header_and_guide_words_are_removed(self):
        from biblioref_page_decorations import filter_repeated_page_decorations
        kept, removed = filter_repeated_page_decorations(self.pages())
        texts = [line.text for line in kept]
        self.assertNotIn("REFERENCIAS BIBLIOGRÁFICAS", texts)
        self.assertIn("- Alonso, J. (2010). Comunicación y cuerpo. Madrid: Síntesis.", texts)
        self.assertIn("rias.psi.uba.ar/index.aspx?anio=2012", texts)
        self.assertEqual(4, sum(1 for t in texts if t.startswith("- Freud")))

    def test_a_single_slash_reference_is_not_touched(self):
        from biblioref_v0_3 import LayoutLine
        from biblioref_page_decorations import filter_repeated_page_decorations
        lines = [LayoutLine(10, 842.0, "A/B testing en psicología. Revista, 3, 1-9.", 90, 140, 500, 152, 11.0)]
        kept, _ = filter_repeated_page_decorations(lines)
        self.assertEqual(lines, kept)



class DeclarationTests(unittest.TestCase):
    """El cambio se declara con su equivalencia sobre el corpus completo."""

    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0615_SHA256.json"

    def setUp(self):
        self.assertTrue(self.MANIFEST.exists(), "falta la declaración del algoritmo 0.6.15")
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.15", "0.6.16", "0.6.17", "0.6.18", "0.6.19", "0.6.20", "0.6.21"})

    def test_only_the_declared_files_changed(self):
        self.assertEqual({"biblioref_v0_2.py", "biblioref_v0_3.py", "biblioref_v0_4.py",
                          "biblioref_page_decorations.py", "biblioref/core/config.py"},
                         {f["file"] for f in self.manifest["deliberately_changed"]})
        self.assertTrue(self.manifest["all_identical"])

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[6-9]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
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
        self.assertIn("T0026", {c["thesis_id"] for c in equivalence["changed"]})


if __name__ == "__main__":
    unittest.main()
