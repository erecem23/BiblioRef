# -*- coding: utf-8 -*-
"""v0.9.7: dash separators in chapter numbering and dash-attached markers.

Both changes widen a character class.  The tests below check the widening, and
above all the controls that must not move: the ``re.fullmatch`` anchoring of
the heading test, the stop-heading vocabulary, prose that merely contains a
bibliographic word, and markers that were already recognised.
"""
import json
import unittest
from pathlib import Path

import biblioref_v0_2 as b2
from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION

ROOT = Path(__file__).resolve().parent.parent


class TestV097Versions(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.6.20", ALGORITHM_VERSION)


class TestV097HeadingDashPrefix(unittest.TestCase):
    """A chapter number may be joined to the heading by any Unicode dash."""

    def test_en_dash_prefix_is_stripped(self):
        for raw in (
            "IV–5-BIBLIOGRAFÍA.",
            "V–5-BIBLIOGRAFÍA.",
            "II–7-REFERENCIAS BIBLIOGRÁFICAS.",
            "VI – 4-REFERENCIAS BIBLIOGRÁFICAS.",
            "III—2—Bibliografía",
        ):
            self.assertTrue(b2.is_ref_heading(raw), raw)

    def test_ascii_hyphen_prefix_still_works(self):
        self.assertTrue(b2.is_ref_heading("I-5- BIBLIOGRAFÍA."))
        self.assertTrue(b2.is_ref_heading("5. Referencias"))
        self.assertTrue(b2.is_ref_heading("V. BIBLIOGRAFIA"))
        self.assertTrue(b2.is_ref_heading("1.2.3 Referencias"))

    def test_dash_prefix_does_not_relax_the_anchoring(self):
        """Only a complete heading matches; a dash cannot rescue prose."""
        for raw in (
            "IV–5-Bibliografía consultada durante el trabajo de campo y el análisis",
            "se puede observar en la bibliografía y en los anexos",
            "En el recorrido por la bibliografía nos encontramos con un gran número",
            "IV–5-Resultados",
        ):
            self.assertFalse(b2.is_ref_heading(raw), raw)

    def test_roman_numeral_words_keep_their_text(self):
        self.assertEqual("literatura", b2._strip_heading_prefix("literatura"))
        self.assertEqual("literatura citada", b2._strip_heading_prefix("Literatura citada"))
        self.assertFalse(b2.is_ref_heading("literatura"))

    def test_stop_headings_are_unchanged(self):
        self.assertTrue(b2.is_stop_heading("Capitulo V. Anexo I"))
        self.assertTrue(b2.is_stop_heading("ANEXO I"))
        self.assertTrue(b2.is_stop_heading("Conclusiones"))
        self.assertTrue(b2.is_stop_heading("CAPÍTULO IV – Hidrogenación de furfural"))
        self.assertFalse(b2.is_stop_heading("V–5-BIBLIOGRAFÍA."))


class TestV097DashAttachedNumericMarker(unittest.TestCase):
    """``[1]-Author`` is a numbered reference start, not prose."""

    def test_dash_attached_markers_are_recognised(self):
        self.assertEqual(1, b2._numeric_marker_value("[1]-N.M. Bertero, Tesis Doctoral (2007)."))
        self.assertEqual(23, b2._numeric_marker_value("[23]- O.S. Alexeev, B.C. Gates; Ind. Eng."))
        self.assertEqual(7, b2._numeric_marker_value("7.-A. Giroir-Fendler; Catal. Lett. 5 (1990) 175."))
        self.assertEqual(4, b2._numeric_marker_value("(4)–P. Gallezot; Catal. Rev. 40 (1998) 81."))

    def test_previously_recognised_markers_are_unchanged(self):
        self.assertEqual(1, b2._numeric_marker_value("[1] Smith, J. (2010). Title."))
        self.assertEqual(12, b2._numeric_marker_value("[12] Doe, A. Title."))
        self.assertEqual(23, b2._numeric_marker_value("23. Doe, A. Title."))
        self.assertEqual(4, b2._numeric_marker_value("(4) Smith, J. Title."))

    def test_non_markers_stay_unrecognised(self):
        for raw in (
            "Smith, J. (2010). Title.",
            "Catal. A: Gen. 356 (2009) 113 y referencias allí citadas.",
            "p. 241 y referencias allí citadas.",
            "[Smith2010] A citation key.",
            "texto corriente sin marcador",
        ):
            self.assertIsNone(b2._numeric_marker_value(raw), raw)

    def test_dash_attached_block_is_diagnosed_as_numeric(self):
        lines = [
            "[1]-H-U. Blazer, M. Studer; Appl. Catal. A: General 189 (1999) 191.",
            "[2]-M. Campanati, G. Fornasari, A. Vaccari; Catal. Today 77 (2003) 299.",
            "[3]-P.N. Raylander, Catalytic hydrogenation, Academia Press New York (1979).",
            "[4]-P. Gallezot, D. Richard; Catal. Rev Sci. Eng. 40 (1998) 81.",
            "[5]-F. Delbecq, P. Sautet; J. Catal. 152 (1995) 217.",
        ]
        profile = b2.diagnose_style(lines)
        self.assertEqual("numeric", profile.style)
        self.assertEqual(5, profile.numeric_starts)
        self.assertGreaterEqual(profile.numeric_sequence_score, 0.9)

    def test_author_year_bibliography_is_still_author_year(self):
        lines = [
            "Adams, M. J. (1990). Beginning to read. Cambridge: MIT Press.",
            "Alegría, J. (2006). Por un enfoque psicolingüístico. Infancia y Aprendizaje, 29(1), 93.",
            "Blachman, B. A. (1994). Kindergarten teachers develop phoneme awareness.",
            "Borzone, A. M. (1999). Conocimientos y estrategias en el aprendizaje inicial.",
        ]
        self.assertEqual("author_year_comma", b2.diagnose_style(lines).style)


class TestV097FixtureNonRegression(unittest.TestCase):
    """The authentic bibliography lines shipped in fixtures must not move."""

    @staticmethod
    def _fixture_lines():
        lines = []

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "lines" and isinstance(v, list):
                        for item in v:
                            if isinstance(item, list) and len(item) >= 2:
                                lines.append(str(item[1]))
                            elif isinstance(item, str):
                                lines.append(item)
                    else:
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for f in sorted((ROOT / "fixtures").glob("*.json")):
            walk(json.loads(f.read_text(encoding="utf-8")))
        return lines

    def test_style_profile_over_authentic_lines_is_identical_to_v096(self):
        lines = self._fixture_lines()
        self.assertEqual(752, len(lines))
        p = b2.diagnose_style(lines)
        self.assertEqual("bracket_key", p.style)
        self.assertEqual(81, p.numeric_starts)
        self.assertEqual(12, p.bracket_key_starts)
        self.assertEqual(242, p.author_comma_year_starts)
        self.assertEqual(7, p.author_initial_year_starts)
        self.assertEqual(0, p.institutional_year_starts)
        self.assertEqual(1, p.bullet_starts)
        self.assertEqual(0.85, p.numeric_sequence_score)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
