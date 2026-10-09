# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.10: tres condiciones del núcleo de extracción.

Los tres defectos salieron del corpus de 121 tesis doctorales de Psicología
(`BIBLIOREF_DATASET_TESIS_PSICOLOGIA_DIAGNOSTICO_V0_1.md`):

  - dos líneas entre corchetes convertían una bibliografía autor-año entera en
    ``bracket_key`` y la vaciaban;
  - el folio impreso pegado al encabezado dejaba tesis enteras en cero, porque
    el test de vocabulario está anclado con ``fullmatch``;
  - la regla del «año en la línea 2» cancelaba bordes correctos en bibliografías
    con sangría francesa, pegando dos y tres referencias en un registro;
  - el apoyo geométrico de un borde débil asumía siempre sangría francesa, así
    que en las bibliografías con sangría de primera línea lo negaba siempre.

Los casos negativos son el punto de la suite: la relajación del encabezado no
puede abrir zonas desde el índice, y la excepción de la sangría francesa no
puede activarse cuando la geometría no distingue el registro.
"""
import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from biblioref.core.config import ALGORITHM_VERSION
from biblioref_v0_2 import diagnose_style, is_ref_heading
from biblioref_v0_3 import LayoutLine, LayoutProfile, _is_reference_heading
from biblioref_v0_4 import (
    _hanging_indent_opens_new_record,
    _reverse_indent_regime,
    segment_adaptive_layout_zone,
)
from biblioref_v0_4 import diagnose_adaptive_style


def line(page, y, x, text, h=800.0, width=250.0):
    return LayoutLine(
        page=page, page_height=h, text=text, x0=x, y0=y,
        x1=x + width, y1=y + 11, median_font_size=11.0, fragment_count=1,
    )


class HeadingVocabularyTests(unittest.TestCase):
    """``referencias`` admite calificador, como ``bibliografia`` ya hacía."""

    def test_new_qualifiers_match(self):
        for text in ("Referencias generales", "Referencias documentales",
                     "Referencias finales", "Otras referencias generales",
                     "REFERENCIAS GENERALES", "5. Referencias generales"):
            self.assertTrue(is_ref_heading(text), text)

    def test_previously_covered_headings_still_match(self):
        for text in ("Referencias", "Referencias bibliográficas", "Bibliografía",
                     "References", "Obras citadas", "Otras referencias"):
            self.assertTrue(is_ref_heading(text), text)

    def test_prose_and_unrelated_sections_still_refused(self):
        for text in ("algunas referencias a la obra de Freud", "Referencias del lector",
                     "Marco teórico", "Anexo I", "referencias cruzadas entre capítulos"):
            self.assertFalse(is_ref_heading(text), text)


class TrailingFolioTests(unittest.TestCase):
    """El folio impreso fusionado con el título no puede anular el encabezado."""

    def test_heading_with_trailing_printed_folio(self):
        # T0025 p290, T0084 p279: el numeral es el folio de la página leída.
        self.assertTrue(_is_reference_heading(line(290, 120, 85, "Referencias bibliográficas 151")))
        self.assertTrue(_is_reference_heading(line(279, 120, 70, "5. Referencias bibliográficas 138 .")))

    def test_index_entry_pointing_forward_is_refused(self):
        # T0016 p9, T0104 p3: el numeral es la página destino, no el folio.
        self.assertFalse(_is_reference_heading(line(9, 428, 85, "BIBLIOGRAFÍA: 304")))
        self.assertFalse(_is_reference_heading(line(3, 200, 90, "Referencias bibliográficas 291")))

    def test_index_entry_with_leader_dots_is_refused(self):
        self.assertFalse(_is_reference_heading(
            line(9, 428, 85, "BIBLIOGRAFÍA: ............................................ 304")))
        self.assertFalse(_is_reference_heading(
            line(6, 300, 70, "5. Referencias bibliográficas …………………………… 279")))

    def test_plain_heading_is_unaffected(self):
        self.assertTrue(_is_reference_heading(line(290, 120, 85, "Referencias bibliográficas")))
        self.assertFalse(_is_reference_heading(line(120, 300, 85, "Marco teórico 45")))


class ReverseIndentRegimeTests(unittest.TestCase):
    """Sangría de primera línea: la continuación cae a la izquierda."""

    @staticmethod
    def profile(start_margin, hanging=False):
        return LayoutProfile(
            start_margin=start_margin, start_margin_tolerance=12.0,
            bibliography_font_size=11.0, continuation_margin=None,
            candidate_support=10, hanging_indent_detected=hanging,
        )

    def test_first_line_indent_is_detected(self):
        # T0117: registros a 120.5, continuaciones a 85.1.
        lines = []
        for index in range(4):
            y = 100 + index * 60
            lines.append(line(243, y, 120.5, "Autor, A. (2016). Título del trabajo"))
            lines.append(line(243, y + 20, 85.1, "continuación de la referencia"))
            lines.append(line(243, y + 40, 85.1, "segunda continuación"))
        self.assertTrue(_reverse_indent_regime(lines, self.profile(120.5)))

    def test_hanging_indent_is_not_mistaken_for_it(self):
        lines = []
        for index in range(4):
            y = 100 + index * 40
            lines.append(line(102, y, 85.1, "Autor, A. (2016). Título del trabajo"))
            lines.append(line(102, y + 20, 120.5, "continuación de la referencia"))
        self.assertFalse(_reverse_indent_regime(lines, self.profile(85.1, hanging=True)))

    def test_block_bibliography_has_no_regime(self):
        lines = [line(102, 100 + i * 20, 85.1, "Autor, A. (2016). Título") for i in range(8)]
        self.assertFalse(_reverse_indent_regime(lines, self.profile(85.1)))


class YearOnSecondLineTests(unittest.TestCase):
    """La cancelación no puede comerse un borde que la geometría ya distingue."""

    @staticmethod
    def zone(lines):
        heading = line(102, 60, 85.1, "BIBLIOGRAFÍA")
        style = diagnose_adaptive_style([item.text for item in lines])
        return SimpleNamespace(lines=lines, heading=heading, style=style)

    def test_hanging_indent_keeps_each_record(self):
        # T0034 p102: el borde tiene margen de inicio y fecha entre paréntesis,
        # y la línea de arriba es la continuación, sangrada a 120.5.
        lines = [
            line(102, 182, 85.1, "Adolphs, R. (1999). Social cognition and the human brain. Trends in Cognitive"),
            line(102, 201, 120.5, "Sciences, 3 (12), 469-479."),
            line(102, 220, 85.1, "Adolphs, R. (2001). The neurobiology of social cognition. Current Opinion in"),
            line(102, 239, 120.5, "Neurobiology, 11 , 231-239."),
            line(102, 258, 85.1, "Adolphs, R. (2003). Recognizing Emotion From Facial Expressions: Psychological"),
            line(102, 277, 120.5, "Neurological Mechanisms. Behavioral and Cognitive Neuroscience reviews, 21-61."),
        ]
        segments = segment_adaptive_layout_zone(self.zone(lines))
        self.assertEqual(3, len(segments))
        for segment, year in zip(segments, ("1999", "2001", "2003")):
            self.assertTrue(segment["reference_text"].startswith("Adolphs, R. (%s)" % year))

    def test_exception_needs_the_three_geometric_conditions(self):
        profile = LayoutProfile(
            start_margin=85.1, start_margin_tolerance=12.0, bibliography_font_size=11.0,
            continuation_margin=120.5, candidate_support=20, hanging_indent_detected=True,
        )
        at_margin = line(102, 220, 85.1, "Adolphs, R. (2001). The neurobiology of")
        indented_previous = line(102, 201, 120.5, "Sciences, 3 (12), 469-479.")
        self.assertTrue(_hanging_indent_opens_new_record(at_margin, indented_previous, profile))

        # Sin sangría francesa en el documento no hay excepción: la línea 2
        # sigue perteneciendo al párrafo abierto arriba.
        block = LayoutProfile(
            start_margin=85.1, start_margin_tolerance=12.0, bibliography_font_size=11.0,
            continuation_margin=None, candidate_support=20, hanging_indent_detected=False,
        )
        self.assertFalse(_hanging_indent_opens_new_record(at_margin, indented_previous, block))

        # La línea anterior en el mismo margen no distingue nada.
        same_margin_previous = line(102, 201, 85.1, "Sciences, 3 (12), 469-479.")
        self.assertFalse(
            _hanging_indent_opens_new_record(at_margin, same_margin_previous, profile))

        # El candidato fuera del margen de inicio tampoco.
        off_margin = line(102, 220, 120.5, "Adolphs, R. (2001). The neurobiology of")
        self.assertFalse(
            _hanging_indent_opens_new_record(off_margin, indented_previous, profile))


class MarkerStyleEvidenceTests(unittest.TestCase):
    """Un marcador anecdótico no le gana a la evidencia autor-año."""

    def test_two_bracket_lines_do_not_win_over_ninety_nine_author_year(self):
        # T0016: dos líneas "[on-line] en:" contra 99 con forma autor-año.
        lines = ["[on-line] en:", "[on-line] en: http://www.revistaaen.es/index.php"]
        lines += [f"Autor{i}, N. ({1990 + i % 30}). Un título cualquiera. Editorial."
                  for i in range(99)]
        self.assertEqual("author_year_comma", diagnose_style(lines).style)

    def test_three_retrieval_brackets_do_not_win_over_bullets(self):
        # T0104: tres "[Recuperado] …" contra 25 viñetas.
        lines = [f"[Recuperado] {d} de junio de 2015 de la World Wide Web:" for d in (1, 15, 25)]
        lines += [f" Autor{i}, N. (2010). Un título. Editorial." for i in range(25)]
        self.assertEqual("bulleted", diagnose_style(lines).style)

    def test_a_real_bracket_key_bibliography_is_untouched(self):
        lines = [f"[Aut{i:02d}] Autor{i}, N. (2010). Un título cualquiera. Editorial."
                 for i in range(30)]
        self.assertEqual("bracket_key", diagnose_style(lines).style)

    def test_a_small_numeric_bibliography_keeps_its_marker(self):
        # T0056: seis marcadores numéricos en secuencia, sin alternativa fuerte.
        lines = [f"{i}. Autor{i}, N. Un título cualquiera. Editorial, 2010." for i in range(1, 7)]
        self.assertEqual("numeric", diagnose_style(lines).style)


class DeclarationTests(unittest.TestCase):
    """El cambio del núcleo se declara, con su equivalencia sobre el corpus."""

    MANIFEST = Path(__file__).resolve().parent.parent / "EXTRACTION_CORE_NONREGRESSION_V0611_SHA256.json"

    def setUp(self):
        self.assertTrue(self.MANIFEST.exists(), "falta la declaración del algoritmo 0.6.11")
        self.manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    # Las versiones posteriores vuelven a declarar algunos archivos en su propio
    # manifiesto; el resto de lo declarado aquí sigue byte a byte.

    def test_algorithm_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.11", "0.6.12", "0.6.13", "0.6.14", "0.6.15", "0.6.16", "0.6.17", "0.6.18", "0.6.19", "0.6.20"})

    def test_only_the_declared_files_changed(self):
        self.assertEqual(
            {"biblioref_v0_2.py", "biblioref_v0_3.py", "biblioref_v0_4.py",
             "biblioref/core/config.py", "biblioref/core/patterns.py",
             "biblioref/detection/signals.py",
             "biblioref/extraction/boundary_reconciliation.py",
             "biblioref/extraction/resegmentation.py",
             "biblioref/audit/coverage.py"},
            {f["file"] for f in self.manifest["deliberately_changed"]},
        )
        self.assertTrue(self.manifest["all_identical"])

    def test_declared_hashes_match_the_tree(self):
        root = self.MANIFEST.parent
        redeclared = set()
        for later in [*root.glob("EXTRACTION_CORE_NONREGRESSION_V061[2-9]_SHA256.json"), *root.glob("EXTRACTION_CORE_NONREGRESSION_V062[0-9]_SHA256.json")]:
            redeclared |= {f["file"] for f in json.loads(later.read_text(encoding="utf-8"))["deliberately_changed"]}
        for entry in self.manifest["deliberately_changed"] + self.manifest["files"]:
            if entry["file"] in redeclared:
                continue
            digest = hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest()
            self.assertEqual(entry["release_sha256"], digest, entry["file"])

    def test_corpus_equivalence_is_recorded(self):
        equivalence = self.manifest["corpus_equivalence"]
        self.assertGreaterEqual(equivalence["n_documents"], 100)
        self.assertGreater(equivalence["delta_records"], 0)

    def test_quality_counters_do_not_worsen(self):
        """El conteo de registros no alcanza: baja cuando se fusionan fragmentos.

        Lo que la declaración tiene que garantizar es que no se pierde texto y
        que los indicadores de segmentación rota mejoran.
        """
        antes = self.manifest["quality"]["baseline"]
        despues = self.manifest["quality"]["release"]
        self.assertGreaterEqual(
            despues["n_total_characters"], antes["n_total_characters"]
        )
        self.assertLessEqual(
            despues["n_fragments_under_60_chars"], antes["n_fragments_under_60_chars"]
        )
        self.assertLessEqual(
            despues["n_prose_over_800_chars"], antes["n_prose_over_800_chars"]
        )
        self.assertLessEqual(
            despues["n_not_opening_as_author"], antes["n_not_opening_as_author"]
        )


if __name__ == "__main__":
    unittest.main()
