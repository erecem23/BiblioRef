# -*- coding: utf-8 -*-
"""Tests del filtro de cortes de la cola de avisos.

El detector de avisos busca párrafos del PDF que no estén en ninguna referencia
extraída. Cuando el párrafo aparece *adentro* de una, el aviso ofrece dividir esa
referencia justo ahí. Eso es correcto si dos referencias quedaron pegadas, y es
un falso positivo si el párrafo era la segunda línea de una sola referencia:
dividir ahí la parte en dos.

Medido sobre los 583 avisos de pegada del corpus de tesis de Psicología, el
filtro saca 178 (31 %) y conserva las 326 pegadas reales y las 230 que el
extractor 0.6.11 corta por su cuenta.
"""
import unittest

from biblioref.audit.coverage import cut_opens_a_record


class AbreRegistroTests(unittest.TestCase):
    """Cortes reales: lo que sigue abre una referencia nueva."""

    def test_author_year_record(self):
        self.assertTrue(cut_opens_a_record(
            "Adolphs, R. (2001). The neurobiology of social cognition. "
            "Current Opinion in Neurobiology, 11, 231-239."))

    def test_surname_with_lowercase_particle(self):
        self.assertTrue(cut_opens_a_record(
            "van Dijk, J., van Kesteren, J., & Smit, P. (2007). "
            "Criminal Victimisation in International Perspective."))

    def test_institutional_author(self):
        self.assertTrue(cut_opens_a_record(
            "UN DESA, United Nations Department of Economic and Social Affairs. "
            "The Sustainable Development Goals Report. New York: UN, 2018."))

    def test_legal_instrument(self):
        self.assertTrue(cut_opens_a_record(
            "Código Civil y Comercial de la Nación [CCyC]. Ley 26994 de 2014. "
            "Artículo 58. 8 de octubre de 2014 (Argentina)."))

    def test_full_given_name_with_year_at_the_end(self):
        # Estilo Chicago, el de T0061.
        self.assertTrue(cut_opens_a_record(
            "Anzieu, Didier. «Los significantes formales y el yo-piel.» "
            "En Las envolturas psíquicas, de Didier Anzieu. Buenos Aires: Amorrortu, 1987."))

    def test_author_list_without_a_date_is_enough(self):
        # Una referencia sin año existe; un nombre de revista partido en dos
        # líneas nunca tiene forma de lista de autores con iniciales.
        self.assertTrue(cut_opens_a_record(
            "Castro, D. M., & Allegri, R. F. Olvidos: ¿normal envejecimiento o "
            "síntomas de enfermedad? Alzheimer, Capítulo II pp-49."))

    def test_short_unterminated_tail_stays_actionable(self):
        # Cortada antes de llegar a su fecha: no hay con qué decidir.
        self.assertTrue(cut_opens_a_record(
            "Ortegón, E; Pacheco, J.F; Prieto, A. Metodología del marco lógico"))


class ContinuacionTests(unittest.TestCase):
    """Falsos positivos: el corte cae adentro de una sola referencia."""

    def test_place_and_publisher(self):
        self.assertFalse(cut_opens_a_record("Hillsdale, NJ: Lawrence Erlbaum Associated."))

    def test_journal_name_split_across_lines(self):
        self.assertFalse(cut_opens_a_record("Computer Mediated Communication , 2 (1), 12-22."))

    def test_journal_with_volume_and_doi(self):
        self.assertFalse(cut_opens_a_record(
            "Disorders, 5 (1): 368 - 376. https://doi.org/10.1016/j.rasd.2010.05.002"))
        self.assertFalse(cut_opens_a_record(
            "Differences, 42 (6), 1069-1079. doi: 10.1016/j.paid.2006.09.014"))

    def test_lowercase_continuation(self):
        self.assertFalse(cut_opens_a_record(
            "y la construcción de la identidad profesional en el período estudiado."))

    def test_prose_swallowed_by_a_false_zone(self):
        self.assertFalse(cut_opens_a_record(
            "El sujeto, una cosa compleja, frágil, de la que es tan difícil hablar, "
            "y sin la cual no podemos hablar (Foucault, 1999, p. 169)."))

    def test_too_short_to_judge(self):
        self.assertFalse(cut_opens_a_record("Paidós."))
        self.assertFalse(cut_opens_a_record(""))


class AmbiguedadTests(unittest.TestCase):
    """Un numeral pegado al nombre distingue la revista del apellido."""

    def test_a_year_after_the_name_is_a_record(self):
        self.assertTrue(cut_opens_a_record(
            "OMS, 2010. Informe sobre la salud en el mundo. Ginebra: OMS."))

    def test_a_volume_after_the_name_is_a_journal(self):
        self.assertFalse(cut_opens_a_record(
            "Psicothema, 20 (4), 896-901. doi: 10.7334/psicothema2015.1"))


if __name__ == "__main__":
    unittest.main()
