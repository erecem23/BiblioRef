# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.11: las reglas que abren registro sin mirar el margen.

Medir P6 aislado mostró que no era un parche suelto. Tres reglas distintas
abrían registro fuera del margen de inicio, y arreglar una sola dejaba a las
otras dos haciendo el mismo daño con otra etiqueta:

  - ``author+bare_year+local_geometry`` miraba ``hanging_indent_detected``, que
    es del documento y no de la línea;
  - el marcador numérico valía como borde explícito en cualquier estilo, así que
    ``60. https://doi.org/…`` —el número de página de una continuación— abría
    registro;
  - ``inherited_author+date_only_entry`` heredaba el autor de arriba aunque el
    de arriba fuera sólo la lista de autores de esta misma referencia, con el
    año pasado a la línea siguiente.

El cuarto caso es el simétrico: los apellidos con partícula minúscula nunca
abrían registro porque se exigía mayúscula inicial.
"""
import unittest
from types import SimpleNamespace

from biblioref.core.patterns import AUTHOR_LIST_TAIL_RX
from biblioref.detection.signals import enhanced_start
from biblioref_v0_2 import StyleProfile
from biblioref_v0_3 import LayoutLine, LayoutProfile
from biblioref_v0_4 import SURNAME_PARTICLE_RX, is_adaptive_reference_start


def line(page, y, x, text, h=800.0, width=250.0):
    return LayoutLine(
        page=page, page_height=h, text=text, x0=x, y0=y,
        x1=x + width, y1=y + 11, median_font_size=11.0, fragment_count=1,
    )


def style(name):
    return StyleProfile(style=name, n_lines=40, numeric_starts=0, bracket_key_starts=0,
                        author_comma_year_starts=30, author_initial_year_starts=0,
                        institutional_year_starts=0, bullet_starts=0,
                        numeric_sequence_score=0.0)


class AuthorListTailTests(unittest.TestCase):
    """Una referencia completa no termina en "& Apellido, X."."""

    def test_unterminated_author_list_is_recognised(self):
        for text in (
            "Andrieu, S., Guyonnet, S., Coley, N., Bordes, S. & Olivier-Abbal, P.",
            "Barcelo-Coblijn, G., Hőgyes, E., Kitajka, K.,&Farkas, T.",
            "Colliot, O., Chételat, G., Benali, H., ... & Lehéricy, S.",
            "Kalaria, R. N., Maestre, G. E., Hall, K., ... & Antuono, P.",
        ):
            self.assertTrue(AUTHOR_LIST_TAIL_RX.search(text), text)

    def test_complete_references_are_not(self):
        for text in (
            "Journal of Autism and Developmental Disorders, 29, 407-418.",
            "Madrid: Alianza Editorial.",
            "Psicothema, 20 (4), 896–901.",
            "https://doi.org/10.1016/j.jsr.2010.02.005",
            "Aberastury, A. (1968). El niño y sus juegos. Buenos Aires: Paidós.",
        ):
            self.assertFalse(AUTHOR_LIST_TAIL_RX.search(text), text)


class NumericMarkerMarginTests(unittest.TestCase):
    """El marcador numérico sólo ignora el margen en una zona numerada."""

    @staticmethod
    def zone(style_name, lines):
        return SimpleNamespace(lines=lines, style=style(style_name),
                               heading=line(104, 60, 36.1, "Referencias"))

    def test_page_number_on_a_continuation_does_not_open_a_record(self):
        # T0017: "60. https://doi.org/…" a 72.15, con el margen en 36.1.
        lines = [line(107, 200, 72.15, "60. https://doi.org/10.1016/j.neuarg.2017.11.002")]
        zone = self.zone("author_year_comma", lines)
        start, _ = enhanced_start(0, zone, {107: 36.1}, 36.1)
        self.assertFalse(start)

    def test_numeric_marker_at_the_margin_still_opens_a_record(self):
        lines = [line(107, 200, 36.1, "60. Autor, N. (2017). Un título cualquiera.")]
        zone = self.zone("author_year_comma", lines)
        start, evidence = enhanced_start(0, zone, {107: 36.1}, 36.1)
        self.assertTrue(start)
        self.assertEqual("numeric_marker", evidence)

    def test_a_numbered_bibliography_keeps_ignoring_the_margin(self):
        # El motivo original de la regla: la primera página de la zona puede
        # usar otro margen.
        lines = [line(107, 200, 72.15, "60. Autor, N. Un título cualquiera. Editorial, 2017.")]
        zone = self.zone("numeric", lines)
        start, evidence = enhanced_start(0, zone, {107: 36.1}, 36.1)
        self.assertTrue(start)
        self.assertEqual("numeric_marker", evidence)


class SurnameParticleTests(unittest.TestCase):
    """``van Dijk`` abre registro como cualquier otro apellido."""

    @staticmethod
    def layout():
        return LayoutProfile(start_margin=72.0, start_margin_tolerance=12.0,
                             bibliography_font_size=11.0, continuation_margin=110.0,
                             candidate_support=20, hanging_indent_detected=True)

    def test_particles_are_recognised(self):
        for text in ("van Dijk, J.", "de Asúa, M.", "del Valle, M. V.",
                     "von Foerster, H.", "da Silva, J.", "van der Heijden, A."):
            self.assertTrue(SURNAME_PARTICLE_RX.match(text), text)

    def test_prose_starting_with_a_particle_is_not(self):
        for text in ("de la misma manera que", "del mismo modo", "van a considerarse",
                     "de acuerdo con lo anterior"):
            self.assertFalse(SURNAME_PARTICLE_RX.match(text), text)

    def test_a_particle_surname_at_the_margin_opens_a_record(self):
        candidate = line(
            160, 300, 72.0,
            "van Dijk, J., van Kesteren, J., & Smit, P. (2007). Criminal Victimisation.",
        )
        start, evidence = is_adaptive_reference_start(
            candidate, style("author_year_comma"), self.layout())
        self.assertTrue(start)
        self.assertIn("start_margin", evidence)

    def test_a_particle_surname_off_the_margin_does_not(self):
        candidate = line(
            160, 300, 110.0,
            "van Dijk, J., van Kesteren, J., & Smit, P. (2007). Criminal Victimisation.",
        )
        start, _ = is_adaptive_reference_start(
            candidate, style("author_year_comma"), self.layout())
        self.assertFalse(start)


if __name__ == "__main__":
    unittest.main()
