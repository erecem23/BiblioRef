"""Tests for the v0.9.5 heading-vocabulary and prefix coverage.

Diagnosing the six unexplained zero-output failures of the TDX suplentes holdout
showed a single dominant cause, and it was not layout: legitimate bibliographic
headings that the vocabulary simply did not contain.

  - Catalan plurals (``Referències bibliogràfiques``) — TDX is *Tesis Doctorals
    en Xarxa*, so Catalan is structural there, not exotic;
  - ordinary English variants (``List of references``);
  - a chapter-titled heading (``Chapter 7: References``);
  - a font that maps the space character onto a printable glyph.

The anchoring is what keeps this safe: the vocabulary grew, the ``fullmatch``
discipline did not change.  The negative cases below are the point of the suite.
"""
import unittest

from biblioref_v0_2 import is_ref_heading, is_stop_heading


class TestHeadingVocabulary(unittest.TestCase):

    def assert_heading(self, text, expected, msg=""):
        self.assertEqual(expected, is_ref_heading(text), f"{text!r} {msg}")

    # ---------- previamente cubierto: no debe romperse ----------

    def test_previously_covered_headings_still_match(self):
        for t in ("Referencias bibliográficas", "Bibliografía", "References",
                  "Bibliography", "Referências bibliográficas", "Obras citadas",
                  "Literatura citada", "Works cited", "7.- BIBLIOGRAFÍA",
                  "III.2.1. Bibliografía", "R EFERENCIAS"):
            self.assert_heading(t, True)

    # ---------- catalan ----------

    def test_catalan_plural_forms(self):
        for t in ("Referències", "Referències bibliogràfiques", "Referències citades",
                  "Altres referències", "Obres citades", "Fonts i bibliografia",
                  "Fonts consultades", "Fonts documentals", "11. Referències"):
            self.assert_heading(t, True)

    def test_catalan_bibliografia_was_already_covered(self):
        """Spelled as in Spanish, so it needed no new entry."""
        self.assert_heading("Bibliografia", True)

    def test_bare_fonts_stays_excluded(self):
        """Same reasoning as bare ``Fuentes``: usually a methodology subsection."""
        self.assert_heading("Fonts", False)

    # ---------- ingles ----------

    def test_english_variants(self):
        for t in ("List of references", "Reference list", "List of works cited"):
            self.assert_heading(t, True)

    def test_publication_lists_are_not_bibliographies(self):
        """A thesis' own publication list must never become a bibliography zone."""
        for t in ("List of publications", "Publications", "List of figures",
                  "List of tables", "List of abbreviations"):
            self.assert_heading(t, False)

    # ---------- prefijo de capitulo ----------

    def test_chapter_titled_headings(self):
        for t in ("Chapter 7: References", "Chapter 7. References",
                  "Capítulo 7: Referencias", "Capítol 9. Referències",
                  "CHAPTER VII - BIBLIOGRAPHY"):
            self.assert_heading(t, True)

    def test_ordinary_chapters_are_not_headings(self):
        for t in ("Chapter 3: Results", "Capítulo 7: Metodología",
                  "Chapter 1. Introduction", "Capítol 2. Marc teòric"):
            self.assert_heading(t, False)

    def test_a_chapter_that_is_the_bibliography_does_not_stop_the_zone(self):
        """Precedence guard.

        ``is_stop_heading`` returns True for anything starting with ``capitulo``.
        Without this rule a chapter-titled bibliography would open and close the
        same zone.
        """
        self.assertFalse(is_stop_heading("Capítulo 7: Referencias"))
        self.assertFalse(is_stop_heading("Capítol 9. Referències"))

    def test_ordinary_chapter_still_stops_the_zone(self):
        """The shared prefix stripper must keep treating a chapter as a chapter."""
        for t in ("Capítulo 7: Metodología", "Capítulo 8. Conclusiones",
                  "Capítulo V. Anexo I", "Anexo I"):
            self.assertTrue(is_stop_heading(t), t)

    # ---------- glifo separador ----------

    def test_space_glyph_substitution_is_repaired(self):
        """A font mapping the space onto a printable glyph glues the words.

        Accent stripping would turn such a glyph into a letter, so the repair has
        to happen before normalization.  The anchored vocabulary still decides.
        """
        self.assert_heading("Chapterȱ7:ȱReferencesȱ", True)
        self.assert_heading("Referȱncies", False, "una sola aparicion no repara")

    def test_glyph_repair_cannot_invent_a_heading(self):
        """The repair may only produce an exact bibliographic heading."""
        for t in ("Resultȱsȱandȱdiscussion", "Chapterȱ3:ȱResultsȱ"):
            self.assert_heading(t, False)

    # ---------- prosa: el anclaje es lo que protege ----------

    def test_prose_never_becomes_a_heading(self):
        for t in ("algunas referencias a la obra de X",
                  "Referencias a la normativa vigente",
                  "Les referències d'aquest capítol",
                  "Bibliographic databases used in this review",
                  "Reference values for the control group",
                  "This chapter references the previous one"):
            self.assert_heading(t, False)



class TestRunningHeaderGuard(unittest.TestCase):
    """A chapter-titled bibliographic heading is also what its running header says.

    Without geometry the two are the same string, so accepting the prefixed form
    everywhere opened one spurious zone per page of the bibliography.
    """

    def _line(self, text, y0, page_height=842.0):
        from biblioref.legacy.engine import LayoutLine
        return LayoutLine(page=1, page_height=page_height, text=text,
                          x0=85.0, y0=y0, x1=300.0, y1=y0 + 12.0,
                          median_font_size=11.0, fragment_count=1)

    def test_chapter_prefixed_heading_is_rejected_in_the_header_band(self):
        from biblioref.legacy.engine import _is_reference_heading
        self.assertFalse(_is_reference_heading(self._line("Capítol 6: Referències", 52.1)))
        self.assertFalse(_is_reference_heading(self._line("Chapter 7: References", 35.3)))

    def test_chapter_prefixed_heading_is_rejected_low_on_the_page(self):
        """A table-of-contents entry names the chapter without starting it.

        The TOC line and the real heading are the same string; only the vertical
        position separates them.  Without this the zone starts in the index.
        """
        from biblioref.legacy.engine import _is_reference_heading
        self.assertFalse(_is_reference_heading(self._line("Chapter 7: References", 726.0)))
        self.assertFalse(_is_reference_heading(self._line("Capítulo 7: Referencias", 800.0)))

    def test_chapter_prefixed_heading_is_accepted_in_the_body(self):
        from biblioref.legacy.engine import _is_reference_heading
        self.assertTrue(_is_reference_heading(self._line("Chapter 7: References", 86.0)))
        self.assertTrue(_is_reference_heading(self._line("Capítol 9. Referències", 190.0)))

    def test_plain_headings_are_unaffected_by_the_band(self):
        """Only the chapter-prefixed form is geometry-gated."""
        from biblioref.legacy.engine import _is_reference_heading
        for y in (20.0, 52.1, 86.0, 400.0):
            self.assertTrue(_is_reference_heading(self._line("REFERÈNCIES", y)), y)
            self.assertTrue(_is_reference_heading(self._line("Bibliografía", y)), y)

    def test_text_only_callers_keep_the_permissive_default(self):
        self.assertTrue(is_ref_heading("Chapter 7: References"))
        self.assertFalse(is_ref_heading("Chapter 7: References", allow_chapter_prefix=False))


if __name__ == "__main__":
    unittest.main()
