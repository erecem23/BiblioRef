# -*- coding: utf-8 -*-
"""Regression and synthetic tests for BiblioRef v0.4."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from biblioref_v0_2 import diagnose_style, is_ref_heading
from biblioref_v0_3 import LayoutLine, diagnose_layout
from biblioref_v0_4 import (
    AdaptiveLayoutZone,
    _has_early_bibliographic_date,
    _numeric_sequence_diagnostics,
    classify_zone_role,
    detect_adaptive_layout_zones,
    process_pdf,
    segment_adaptive_layout_zone,
)
from test_biblioref_v0_2 import CASES
from test_biblioref_v0_3 import _fixture_zone


def line(
    page: int,
    text: str,
    x0: float = 85.0,
    y0: float = 100.0,
    font_size: float = 12.0,
) -> LayoutLine:
    return LayoutLine(
        page=page,
        page_height=842.0,
        text=text,
        x0=x0,
        y0=y0,
        x1=510.0,
        y1=y0 + 14.0,
        median_font_size=font_size,
    )


class TestBiblioRefV04(unittest.TestCase):
    def test_date_variants(self):
        variants = [
            "Autor (2019). Título.",
            "Autor (1952-1953a). Título.",
            "Autor (Septiembre, 2018a). Título.",
            "Autor (7 de Agosto de 2002). Título.",
            "Autor (19-04-2020). Video.",
            "Autor (/2015). Título.",
            "Autor (s/f). Título.",
            "Autor (En prensa). Título.",
        ]
        for value in variants:
            self.assertTrue(_has_early_bibliographic_date(value), value)
        self.assertFalse(_has_early_bibliographic_date("Papers, No. 2013/4, OECD."))
        self.assertFalse(_has_early_bibliographic_date("Ministerio (Argentina 1974-1975)."))

    def test_reference_heading_variants(self):
        variants = [
            "LITERATURA CITADA",
            "Literatura consultada",
            "Literatura citada y consultada",
            "Fuentes citadas",
            "Literature cited",
            "Cited literature",
            "Works cited",
            "Otras referencias consultadas",
            "R EFERENCIAS BIBLIOGRÁFICAS",
            "O TRAS REFERENCIAS CONSULTADAS",
            "VII- ANEXO: Fuentes.-",
            "Fuentes jurisprudenciales",
            "Fallos citados",
        ]
        for value in variants:
            self.assertTrue(is_ref_heading(value), value)
        self.assertFalse(is_ref_heading("Fuentes"))

    def test_literatura_citada_stops_before_annex(self):
        lines = [
            line(1, "LITERATURA CITADA", y0=60.0),
            line(1, "Alanis-Pavón, A. (2025). Permian ammonoids.", y0=100.0),
            line(1, "Böse, E. (1919). The Permo-Carboniferous ammonoids.", y0=130.0),
            line(2, "ANEXOS OBLIGATORIOS", x0=170.0, y0=60.0),
            line(2, "Alanis-Pavón, A. (2024). Mandatory annex publication.", y0=100.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual("layout_confirmed_stop_heading", zones[0].termination_reason)
        segments = segment_adaptive_layout_zone(zones[0])
        self.assertEqual(2, len(segments))
        self.assertNotIn("Mandatory annex", " ".join(x["reference_text"] for x in segments))

    def test_bare_author_year_style(self):
        lines = [
            line(1, "Referencias", y0=60.0),
            line(1, "Acker, Kevin, Deborah Bräutigam, y Yufan Huang. 2020. Debt Relief.", y0=100.0),
            line(1, "African Union Commission, OCDE, y OCDE. 2025. Executive Summary.", y0=130.0),
            line(1, "Agbebi, Motolani, y Petri Virtanen. 2017. Dependency Theory.", y0=160.0),
            line(1, "Álvarez Acosta, María Elena, ed. 2011a. África subsahariana.", y0=190.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("author_year_bare", zones[0].style.style)
        self.assertEqual(4, len(segment_adaptive_layout_zone(zones[0])))

    def test_mixed_parenthetical_and_bare_years(self):
        lines = [
            line(1, "REFERENCIAS BIBLIOGRÁFICAS", y0=60.0),
            line(1, "ACOSTA, J. Gestión de estrés. Barcelona: Bresca Editorial, 2008.", y0=100.0),
            line(1, "ANDRÉU Abela, J.; García-Nieto, A. (2007). Evolución de la teoría.", y0=130.0),
            line(1, "ASOCIACIÓN de Empresarios. Estudio sobre el trabajo, 2009.", y0=160.0),
            line(1, "BENAVIDES, M. Cultura organizacional, 2011.", y0=190.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("author_year_bare", zones[0].style.style)
        self.assertEqual(4, len(segment_adaptive_layout_zone(zones[0])))

    def test_bulleted_legal_sources(self):
        lines = [
            line(47, "VII- ANEXO: Fuentes.-", y0=60.0),
            line(47, "Cámara Contencioso Administrativo y Tributaria", y0=90.0),
            line(47, "Sala I.-", y0=120.0),
            line(47, "\uf0a8 Corbeira Constanza c/ GCBA s/ amparo, EXP 5842/0", x0=106.0, y0=150.0, font_size=9.5),
            line(47, "Ciudad de Buenos Aires, marzo de 2004.", x0=124.0, y0=170.0),
            line(47, "\uf0a8 Ameri Héctor c/ GCBA s/ amparo, Expte. 8866/12", x0=106.0, y0=200.0),
            line(48, "Sala II.-", y0=90.0),
            line(48, "\uf071 Caballero Sergio c/ GCBA s/ empleo público", x0=106.0, y0=120.0),
            line(48, "\uf071 Cámara José c/ GCBA s/ amparo, 28/4/05", x0=106.0, y0=150.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual("bulleted", zones[0].style.style)
        self.assertEqual("legal_sources", classify_zone_role(zones[0].heading.text))
        self.assertEqual(4, len(segment_adaptive_layout_zone(zones[0])))

    def test_attached_dash_and_named_web_sources(self):
        lines = [
            line(10, "REFERENCIAS", y0=60.0),
            line(10, "-Alonso, R. (2008). Primera obra.", y0=100.0),
            line(10, "-Aumont, J. (1992). Segunda obra.", y0=130.0),
            line(10, "Alberto Goldenstein: http://example.org/alberto", y0=160.0),
            line(10, "Esteban Pastorino:", y0=190.0),
            line(10, "http://example.org/esteban", y0=210.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("bulleted", zones[0].style.style)
        segments = segment_adaptive_layout_zone(zones[0])
        self.assertEqual(4, len(segments))
        self.assertIn("Alberto Goldenstein", segments[2]["reference_text"])
        self.assertIn("example.org/esteban", segments[3]["reference_text"])

    def test_abnt_uppercase_and_repeated_author(self):
        lines = [
            line(1, "REFERÊNCIAS", x0=180.0, y0=60.0),
            line(1, "AGÊNCIA EUROPEIA PARA O DESENVOLVIMENTO DA", x0=70.0, y0=90.0),
            line(1, "EDUCAÇÃO ESPECIAL. Recomendações para decisores.", x0=70.0, y0=104.0),
            line(1, "Odense, Denmark, 2009.", x0=70.0, y0=118.0),
            line(1, "ALMEIDA, Djair Lázaro de. Educação Moral e Cívica", x0=70.0, y0=150.0),
            line(1, "na ditadura militar. São Carlos, 2009.", x0=70.0, y0=164.0),
            line(1, "ASSIS, Denise. Propaganda e cinema.", x0=70.0, y0=196.0),
            line(1, "Rio de Janeiro: Mauad, 2001.", x0=70.0, y0=210.0),
            line(1, "BECKER, Howard S. Uma teoria da ação coletiva.", x0=70.0, y0=242.0),
            line(1, "Rio de Janeiro: Zahar, 1977.", x0=70.0, y0=256.0),
            line(1, "______. Outsiders: estudos da sociologia do desvio.", x0=70.0, y0=288.0),
            line(1, "Rio de Janeiro: Zahar, 2009.", x0=70.0, y0=302.0),
            line(2, "APÊNDICES", x0=190.0, y0=60.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual("author_year_bare", zones[0].style.style)
        segments = segment_adaptive_layout_zone(zones[0])
        self.assertEqual(5, len(segments))
        self.assertIn("Odense, Denmark, 2009", segments[0]["reference_text"])
        self.assertIn("Outsiders", segments[-1]["reference_text"])

    def test_repeated_running_reference_heading_is_one_zone(self):
        lines = [
            line(10, "REFERENCIAS", x0=190.0, y0=60.0),
            line(10, "Apostol, T. (1984). Primera obra.", y0=100.0),
            line(11, "254 REFERENCIAS", x0=190.0, y0=40.0),
            line(11, "Ausubel, D. (1963). Segunda obra.", y0=100.0),
            line(12, "255 REFERENCIAS", x0=190.0, y0=40.0),
            line(12, "Baker, J. (2000). Tercera obra.", y0=100.0),
            line(13, "ANEXO", x0=190.0, y0=60.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual(3, len(segment_adaptive_layout_zone(zones[0])))

    def test_sites_subsection_is_segmented_before_annex(self):
        lines = [
            line(20, "REFERENCIAS", x0=180.0, y0=60.0),
            line(20, "Autor, A. (2020). Obra académica.", x0=70.0, y0=100.0),
            line(20, "Sites", x0=70.0, y0=145.0),
            line(20, "Diario Uno. Nota web.", x0=70.0, y0=180.0),
            line(20, "https://example.org/uno. 2 de mayo de 2020.", x0=70.0, y0=194.0),
            line(20, "Handy Inclusiva. En la siguiente dirección:", x0=70.0, y0=225.0),
            line(20, "https://example.org/dos. 3 de mayo de 2020.", x0=70.0, y0=239.0),
            line(21, "ANEXO", x0=180.0, y0=60.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        segments = segment_adaptive_layout_zone(zones[0])
        self.assertEqual(3, len(segments))
        self.assertIn("Diario Uno", segments[1]["reference_text"])
        self.assertIn("Handy Inclusiva", segments[2]["reference_text"])

    def test_numbered_observations_close_annex_bibliography(self):
        lines = [
            line(30, "BIBLIOGRAFÍA COMPLEMENTARIA", y0=60.0),
            line(30, "Fabra, L. (2019). Primera referencia.", y0=100.0, font_size=10.0),
            line(30, "Trincheri, A. (2016). Segunda referencia.", y0=140.0, font_size=10.0),
            line(31, "6. Observaciones", x0=20.0, y0=60.0, font_size=12.0),
            line(31, "7) Juegan un 3 vs 2.", x0=60.0, y0=100.0, font_size=6.8),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(30, zones[0].end_page)
        self.assertEqual(2, len(segment_adaptive_layout_zone(zones[0])))

    def test_contents_duplicate_does_not_open_a_zone(self):
        lines = [
            line(2, "I.- Presentación", y0=100.0),
            line(2, "II.- Marco normativo", y0=130.0),
            line(2, "III.- Jurisprudencia", y0=160.0),
            line(2, "IV.- Conclusión", y0=190.0),
            line(2, "VII. Anexo: Fuentes", y0=220.0),
            line(47, "VII- ANEXO: Fuentes.-", y0=60.0),
            line(47, "\uf0a8 Primer fallo", x0=106.0, y0=100.0),
            line(47, "\uf0a8 Segundo fallo", x0=106.0, y0=130.0),
            line(47, "\uf0a8 Tercer fallo", x0=106.0, y0=160.0),
        ]
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual(47, zones[0].start_page)

    def test_numeric_markers_survive_page_margin_change(self):
        lines = [line(43, "7. Bibliografía", y0=60.0)]
        for number in range(1, 4):
            lines.append(line(43, f"{number}. Autor {number}. Título; 20{number:02d}.", x0=56.0, y0=90 + 30 * number))
        for number in range(4, 9):
            lines.append(line(44, f"{number}. Autor {number}. Título; 20{number:02d}.", x0=79.0, y0=70 + 30 * number))
        zones = detect_adaptive_layout_zones(lines)
        segments = segment_adaptive_layout_zone(zones[0])
        self.assertEqual(8, len(segments))
        diagnostics = _numeric_sequence_diagnostics(segments)
        self.assertEqual(1, diagnostics["numeric_first_marker"])
        self.assertEqual("", diagnostics["numeric_sequence_warning"])

    def test_numeric_sequence_warns_when_beginning_is_missing(self):
        segments = [{"reference_text": f"{number}. Autor. Título."} for number in range(12, 16)]
        diagnostics = _numeric_sequence_diagnostics(segments)
        self.assertEqual(12, diagnostics["numeric_first_marker"])
        self.assertIn("first_detected_marker_is_12", diagnostics["numeric_sequence_warning"])

    def test_development_style_fixtures(self):
        total = 0
        for name, case in CASES.items():
            zone = _fixture_zone(case)
            segments = segment_adaptive_layout_zone(zone)  # compatible layout fields
            self.assertEqual(case["gold_starts"], len(segments), name)
            total += len(segments)
        self.assertEqual(46, total)

    def test_weak_continuation_is_not_split(self):
        body = [
            line(1, "Auriol, L. (2010). Careers of Doctorate Holders. Paris:"),
            line(1, "Organización para la Cooperación y el Desarrollo Económicos."),
            line(1, "Barba, F. E. (1972). Nota sobre los orígenes de la Universidad."),
        ]
        style = diagnose_style(x.text for x in body)
        layout = diagnose_layout(body)
        zone = AdaptiveLayoutZone(
            heading=line(1, "Bibliografía", y0=60.0),
            lines=body,
            start_page=1,
            end_page=1,
            style=style,
            layout=layout,
            termination_reason="end_of_document",
            confidence_score=1.0,
            confidence_label="high",
            confidence_reasons=[],
            start_confidence_score=1.0,
            start_confidence_label="high",
            start_confidence_reasons=[],
            end_confidence_score=1.0,
            end_confidence_label="high",
            end_confidence_reasons=[],
            zone_completeness="complete",
            adaptive_soft_limit_pages=25,
            zone_span_pages=1,
            adaptive_limit_exceeded=False,
        )
        segments = segment_adaptive_layout_zone(zone)
        self.assertEqual(2, len(segments))
        self.assertIn("Organización para la Cooperación", segments[0]["reference_text"])

    def test_long_zone_is_not_cut_at_25_pages(self):
        lines = [line(1, "Bibliografía", y0=60.0)]
        for page in range(2, 36):
            lines.append(line(page, f"Apellido{page}, A. ({1980 + page}). Referencia {page}."))
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(1, len(zones))
        self.assertEqual(35, zones[0].end_page)
        self.assertEqual(34, len(segment_adaptive_layout_zone(zones[0])))
        self.assertTrue(zones[0].adaptive_limit_exceeded)
        self.assertEqual("complete", zones[0].zone_completeness)

    def test_trailing_cover_is_removed(self):
        lines = [line(1, "Referencias", y0=60.0)]
        for page in range(2, 8):
            lines.append(line(page, f"Autor{page}, A. ({2000 + page}). Título."))
        lines.append(line(8, "Texto promocional de contratapa sin referencias.", x0=120.0))
        zones = detect_adaptive_layout_zones(lines)
        self.assertEqual(7, zones[0].end_page)
        self.assertEqual("trailing_reference_density_drop", zones[0].termination_reason)
        self.assertEqual("probably_complete", zones[0].zone_completeness)

    def test_optional_agrazar_integration(self):
        default_pdf = Path(__file__).with_name(
            "2024_Agrazar_El tratamiento psicoanalítico de las psicosis en el HZGA Gral. "
            "Manuel Belgrano y la Fundación Brizna Historia y clínica (1).pdf"
        )
        pdf = Path(os.environ.get("BIBLIOREF_TEST_PDF", default_pdf))
        if not pdf.exists():
            self.skipTest("Set BIBLIOREF_TEST_PDF to run the optional PDF integration test")
        result = process_pdf(pdf)
        self.assertEqual(14, result["n_zones"])
        self.assertEqual(432, result["n_occurrences_all_zones"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
