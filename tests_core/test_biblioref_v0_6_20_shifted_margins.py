# -*- coding: utf-8 -*-
"""Tests del algoritmo 0.6.20: libro escaneado con el margen corrido (T0145).

T0145 es un libro escaneado con su propia capa de OCR. Salían 19 referencias de
unas cien, con 72 posibles faltantes, por dos motivos encadenados:

* el OCR leyó cada «———» (autor repetido) como «·», y 19 «viñetas» ganaban el
  estilo aunque 75 líneas abrieran con «Apellido, N.»;
* el año cierra cada entrada, así que las líneas con año son continuaciones
  («DC, APA, 1987.») y fijaban el margen de inicio una sangría a la derecha; además
  el margen cambia de página en página (x≈7, x≈90, x≈24) y una página está torcida
  (los inicios bajan de x=98 a x=77).

0.6.20: las viñetas pierden contra el triple de inicios de autor, y en una página
donde la geometría local no coincide con el margen (corrido una sangría o con los
inicios desparramados) un renglón abre entrada si no hay otro más a la izquierda
cerca y sí una continuación sangrada. Sobre 149 documentos cambian T0145 y T0137
(el mismo libro, 19 -> 72) y T0073, una zona de prosa que ya estaba mal.
"""
import unittest

from biblioref.core.config import ALGORITHM_VERSION
from biblioref.detection.signals import local_hanging_starts
from biblioref.extraction.resegmentation import segment_enhanced_zone
from biblioref_v0_2 import diagnose_style
from biblioref_v0_3 import LayoutLine
from biblioref_v0_4 import detect_adaptive_layout_zones


def line(page, text, x0, y0):
    return LayoutLine(page=page, page_height=595.0, text=text, x0=x0, y0=y0,
                      x1=x0 + 4.8 * len(text), y1=y0 + 11, median_font_size=10.0)


# Página 81 de T0145: inicios en x≈7 sin año, continuaciones en x≈28 que cierran con el año.
PAGE_81 = [
    (8.4, "American Psychiatric Association: Diagnostic and Statistical Manual of"),
    (28.6, "Disorders, 2° edición, Washington DC, APA, 1968."),
    (7.9, "· Diagnostic and Statistical Manual of Mental Disorders, 3° edición, Washington"),
    (28.8, "DC, APA, 1987."),
    (7.4, "Aulagner, Piera: Los destinos del placer, Ediciones Petrel, Barcelona,"),
    (28.3, "Editorial Petrel, Barcelona, 1980."),
    (7.4, "Ayuso Gutiérrez, J. L. y Salvador Carulla: Manual de Psiquiatría, Ed. McGraw Hill,"),
    (28.3, "Universidad Complutense de Madrid, 1992."),
    (7.4, "Baumeyer, E: ·Der psychogene akute Herzanfall·, Ztschr Psychosom Med Psychoanal,"),
    (29.3, "Band 12, Göttingen, 1966."),
    (7.0, "Beck, A. T.: Cognitive Therapy and the Emotional Disorders, International"),
    (28.3, "Universities Press, New York, 1976."),
    (7.0, "Behr, E; Croca, L. y C. Vauterin: ·Sémiologie des conduites de fugue·, Encycl."),
    (27.8, "Méd. Chir. Psychiatrie, 37113 A, 2, Paris, France, 1985."),
    (6.5, "Cassano, G. B.; Perugi, G. y L. Musetti: ·Comorbidity in Panic Disorder·, Psychiatric"),
    (27.8, "Annals 20-9, 1990."),
]

# Página 82: torcida, los inicios bajan de x=98 a x=78 y el autor repetido quedó como «·».
PAGE_82 = [
    (98.4, "Coryell, W.; Noyes, R. and J. D. House: ·Mortality among outpatients with Panic"),
    (121.4, "disorder·, American Journal of Psychiatry, 143, 1986."),
    (95.0, "Cotterell, Arthur: Diccionario de Mitología Universal, Editorial Ariel,"),
    (118.1, "Barcelona, 1988."),
    (93.1, "Chemama, Roland: Diccionario del Psicoanálisis, Amorrortu Editores, Buenos"),
    (117.1, "Aires, 1998."),
    (90.2, "Eaton, W. W. et al.: ·The epidemiology of panic attacks and panic disorders·, Am."),
    (112.8, "J. Epidem., 1985."),
    (86.9, "· (1894): ·La neurastenia y la neurosis de angustia: sobre la justificación de"),
    (110.4, "separar de la neurastenia cierto complejo de síntomas·, Madrid, 1967."),
    (84.0, "· (1896): ·Nuevas observaciones sobre las neuropsicosis de defensa·, tomo 1,"),
    (108.0, "Editorial Biblioteca Nueva, Madrid, 1968."),
    (81.1, "· (1914): ·Introducción al narcisismo·, tomo 1, Editorial Biblioteca Nueva,"),
    (105.1, "Madrid, 1968."),
    (77.7, "· (1921): ·Massenpsychologie und Ich-Analyse·, Bd. IX. Fischer Verlag. Frankfurt"),
    (101.7, "am Main, 1971."),
]


def page(number, entries, top=60.0):
    return [line(number, text, x, top + 13.0 * i) for i, (x, text) in enumerate(entries)]


def segments(pages):
    lines = [line(81, "G) BIBLIOGRAFIA GENERAL", 63.3, 30.0)]
    for p in pages:
        lines += p
    zone = detect_adaptive_layout_zones(lines)[0]
    segs, _ = segment_enhanced_zone(zone)
    return [s["reference_text"] for s in segs]


class ShiftedMarginTests(unittest.TestCase):
    def test_version(self):
        self.assertIn(ALGORITHM_VERSION, {"0.6.20", "0.6.21"})

    def test_misread_marks_do_not_make_a_bulleted_list(self):
        texts = [t for _, t in PAGE_81 + PAGE_82]
        self.assertNotEqual("bulleted", diagnose_style(texts).style)

    def test_a_real_bulleted_list_stays_bulleted(self):
        texts = [f"• Autor{i}, A. ({2000 + i}). Título {i}. Editorial." for i in range(10)]
        texts += ["Pérez, J. (2001). Una línea suelta.", "Gómez, L. (2002). Otra."]
        self.assertEqual("bulleted", diagnose_style(texts).style)

    def test_starts_on_a_shifted_page_are_the_left_lines(self):
        lines = page(81, PAGE_81)
        starts = local_hanging_starts(lines, margin=28.3)
        self.assertEqual([x for x, _ in PAGE_81 if x < 20], [s.x0 for s in starts])

    def test_starts_on_a_tilted_page(self):
        lines = page(82, PAGE_82)
        starts = local_hanging_starts(lines, margin=110.0)
        self.assertEqual(8, len(starts))
        self.assertTrue(all(s.text.startswith(("Coryell", "Cotterell", "Chemama", "Eaton", "·")) for s in starts))

    def test_a_regular_hanging_indent_page_is_left_alone(self):
        entries = []
        for i in range(8):
            entries += [(85.0, f"Autor{i}, A. ({2000 + i}). Un título bastante largo para la línea {i}"),
                        (113.0, "continuación de la referencia, Editorial, Ciudad.")]
        self.assertEqual([], local_hanging_starts(page(90, entries), margin=85.0))

    def test_shifted_page_splits_one_entry_per_start(self):
        texts = segments([page(81, PAGE_81)])
        self.assertEqual(8, len(texts))
        self.assertTrue(texts[0].startswith("American Psychiatric Association") and texts[0].endswith("APA, 1968."))
        self.assertTrue(texts[2].startswith("Aulagner, Piera") and texts[2].endswith("1980."))
        self.assertTrue(texts[3].endswith("Universidad Complutense de Madrid, 1992."))
        self.assertTrue(texts[-1].startswith("Cassano") and texts[-1].endswith("Annals 20-9, 1990."))


if __name__ == "__main__":
    unittest.main()
