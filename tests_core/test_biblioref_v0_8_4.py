import unittest

from biblioref.adaptive.continuity import (
    backward_expansion_start,
    institutional_author_date,
    numeric_page_continuation,
    particle_author_date,
    source_metadata_continuation,
    wrapped_author_continuation,
)
from biblioref.adaptive.order_profile import infer_order_profile, local_order_evidence
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, SOFTWARE_VERSION
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style


def ll(text, y, x0=72.0, page=1):
    return LayoutLine(page=page, page_height=800.0, text=text, x0=x0, y0=y, x1=x0+420, y1=y+10,
                      median_font_size=11.0, fragment_count=1)


def zone(lines):
    style = diagnose_adaptive_style([x.text for x in lines])
    layout = diagnose_adaptive_layout(lines, style)
    return AdaptiveLayoutZone(
        heading=ll('References', 40), lines=lines, start_page=1, end_page=1,
        style=style, layout=layout, termination_reason='test', confidence_score=0,
        confidence_label='test', confidence_reasons=[], start_confidence_score=0,
        start_confidence_label='test', start_confidence_reasons=[], end_confidence_score=0,
        end_confidence_label='test', end_confidence_reasons=[], zone_completeness='test',
        adaptive_soft_limit_pages=0, zone_span_pages=1, adaptive_limit_exceeded=False,
    )


class TestBiblioRefV084(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_particle_surname_is_author_not_lowercase_continuation(self):
        text = 'de Hooge, I. E., Breugelmans, S. M. (2018). The social side of shame.'
        self.assertTrue(particle_author_date(text))

    def test_numeric_page_plus_doi_is_continuation(self):
        lines = [ll('British Journal of Psychology, 95(4), 509-', 100), ll('521. doi:10.1348/0007126042369802', 114)]
        self.assertTrue(numeric_page_continuation(1, lines))

    def test_wrapped_author_list_is_continuation(self):
        lines = [
            ll('Agudelo, D., Bretón-López, J., Ortiz-Recio, G., Poveda-Vera, J., Teva, I., Valor-Segura, I., y', 100),
            ll('Vico, C. (2003). Análisis de la productividad científica.', 114),
        ]
        self.assertTrue(wrapped_author_continuation(1, lines))
        controls = [
            ll('Research, Practice and Policy, 4, 551-559. DOI:10.1037/a0027900', 100),
            ll('de Hooge, I. E., Breugelmans, S. M. (2018). The social side of shame.', 119),
        ]
        self.assertFalse(wrapped_author_continuation(1, controls))

    def test_source_metadata_continuations_are_guarded(self):
        lines = [
            ll('aprimorando a proposta dos núcleos de significação. Revista Brasileira de Estudos', 100),
            ll('Pedagógicos, Brasília, v. 94, n. 236, p. 236-322, jan./abr., 2013. Disponível em:', 114),
        ]
        self.assertTrue(source_metadata_continuation(1, lines))
        lines2 = [ll('In: Formação docente:', 100), ll('Mercado das Letras, 2021. p. 161-181.', 114)]
        self.assertTrue(source_metadata_continuation(1, lines2))

    def test_institutional_author_date(self):
        self.assertTrue(institutional_author_date('ANECA Agencia Nacional de Evaluación de la Calidad y Acreditación (2011). Programa de Mención.'))
        self.assertTrue(institutional_author_date('American Psychiatric Association (2022). Diagnostic manual.'))
        self.assertFalse(institutional_author_date('The results of the study (2022) were discussed in detail.'))

    def test_order_profile_supports_alphabetical_candidates(self):
        lines = [
            ll('Abramovitch, A. (2021). X.', 100),
            ll('Aburn, G. (2016). X.', 120),
            ll('Adamczyk, A. (2022). X.', 140),
            ll('Albein-Urios, N. (2018). X.', 160),
            ll('Allison, C. (2012). X.', 180),
            ll('Alvaro, P. (2013). X.', 200),
        ]
        profile = infer_order_profile(lines)
        self.assertEqual(profile['order_type'], 'strong_alphabetical_order')
        self.assertGreaterEqual(profile['alphabetical_consistency'], .8)
        self.assertTrue(local_order_evidence(2, profile)['support'])

    def test_order_profile_flags_inserted_source_title(self):
        lines = [
            ll('Adamczyk, A. (2022). Title.', 100),
            ll('Psychology, 171, 108327. https://doi.org/10.1/x', 114),
            ll('Albein-Urios, N. (2018). Title.', 133),
            ll('Allison, C. (2012). Title.', 152),
            ll('Alvaro, P. (2013). Title.', 171),
            ll('Amaral, D. (2023). Title.', 190),
        ]
        profile = infer_order_profile(lines)
        # The source line is not accepted as a clean author key under the stricter profile.
        self.assertNotIn('psychology', profile['key_sequence'])

    def test_backward_expansion_recovers_abnt_start_but_not_narrative(self):
        lines = [
            ll('REFERÊNCIAS', 50),
            ll('AGUIAR, Wanda Maria Junqueira. Reflexões a partir da psicologia sócio-histórica sobre a', 100),
            ll('categoria consciência. Cadernos de Pesquisa, n. 110, p. 125-142, jul., 2000.', 114),
            ll('ALARCÃO, Isabel. Professores reflexivos em uma escola reflexiva. São Paulo: Cortez,', 140),
            ll('2003.', 154),
        ]
        result = backward_expansion_start(lines, 1, 114)
        self.assertTrue(result['expanded'])
        self.assertEqual(result['start_y'], 100.0)
        narrative = [
            ll('REFERENCES', 50),
            ll('The references below are grouped according to the studies discussed in this thesis.', 90),
            ll('Abramovitch, A. (2021). Title.', 130),
        ]
        result2 = backward_expansion_start(narrative, 1, 130)
        self.assertFalse(result2['expanded'])

    def test_continuity_guards_change_shadow_scores_not_validated_output(self):
        lines = [
            ll('Adamczyk, A. K., Wyczesany, M., & van Peer, J. M. (2022). High working memory load impairs', 100),
            ll('reappraisal but facilitates distraction. Biological', 114),
            ll('Psychology, 171, 108327. https://doi.org/10.1016/j.biopsycho.2022.108327', 128),
            ll('Albein-Urios, N., Youssef, G. J. (2018). Autism Spectrum Traits.', 147),
        ]
        candidates = collect_boundary_candidates(zone(lines))
        bad = next(item for item in candidates if item['text_preview'].startswith('Psychology,'))
        self.assertTrue(bad['features']['source_metadata_continuation'])
        self.assertFalse(bad['active_shadow_boundary'])


if __name__ == '__main__':
    unittest.main()
