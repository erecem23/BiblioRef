import unittest

from biblioref.adaptive.input_hygiene import detect_input_decorations, decoration_status
from biblioref.adaptive.page_flow import analyze_page_flows, CONTINUATION_START_RX
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.adaptive.continuity import institutional_author_date, source_metadata_continuation
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.grammar.signatures import line_grammar_signature
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style


def ll(page, text, y, x0=72.0, y1=None):
    return LayoutLine(page=page, page_height=800.0, text=text, x0=x0, y0=y, x1=x0+420,
                      y1=y+10 if y1 is None else y1, median_font_size=11.0, fragment_count=1)


def zone(lines):
    style = diagnose_adaptive_style([x.text for x in lines])
    layout = diagnose_adaptive_layout(lines, style)
    return AdaptiveLayoutZone(
        heading=ll(1, 'References', 40), lines=lines, start_page=min(x.page for x in lines),
        end_page=max(x.page for x in lines), style=style, layout=layout,
        termination_reason='test', confidence_score=0, confidence_label='test', confidence_reasons=[],
        start_confidence_score=0, start_confidence_label='test', start_confidence_reasons=[],
        end_confidence_score=0, end_confidence_label='test', end_confidence_reasons=[],
        zone_completeness='test', adaptive_soft_limit_pages=0,
        zone_span_pages=max(x.page for x in lines)-min(x.page for x in lines)+1,
        adaptive_limit_exceeded=False,
    )


class TestBiblioRefV085C(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_uppercase_start_is_not_lowercase_continuation(self):
        self.assertFalse(bool(CONTINUATION_START_RX.match('Endeavor South Africa. (2012). Report.')))
        self.assertTrue(bool(CONTINUATION_START_RX.match('its continuation. Journal, 4, 1-10.')))

    def test_parametric_running_decorations_are_confirmed_and_skipped(self):
        lines = [
            ll(1, 'Fei, H. (2009). Complete reference.', 720),
            ll(1, '52 Master Thesis', 780),
            ll(2, 'L. Bun 0996465', 20),
            ll(2, 'Guerriero, F., & Guido, R. (2011). New reference.', 70),
            ll(2, '53 Master Thesis', 780),
            ll(3, 'L. Bun 0996465', 20),
            ll(3, 'Hulshof, P. J. H. (2012). Another reference.', 70),
            ll(3, '54 Master Thesis', 780),
        ]
        report = detect_input_decorations(lines)
        self.assertGreaterEqual(report['n_confirmed'], 2)
        self.assertEqual(decoration_status(lines[1], report), 'DECORATION_CONFIRMED')
        self.assertEqual(decoration_status(lines[2], report), 'DECORATION_CONFIRMED')
        flows = analyze_page_flows(lines, candidates=[], decoration_report=report)
        first = next(x for x in flows if x['from_page'] == 1)
        self.assertEqual(first['next_text_preview'], 'Guerriero, F., & Guido, R. (2011). New reference.')
        self.assertEqual(first['flow_state'], 'likely_new_reference')
        self.assertIn('page_top_decoration_skipped', first['signals'])

    def test_institutional_author_is_strong_page_start(self):
        self.assertTrue(institutional_author_date('Endeavor South Africa. (2012). The entrepreneurial dialogues.'))
        self.assertTrue(institutional_author_date('Grobid. (2008–2023).'))
        sig = line_grammar_signature('Endeavor South Africa. (2012). The entrepreneurial dialogues.')
        self.assertEqual(sig['reference_start_kind'], 'institutional_author')
        lines = [
            ll(1, 'Edinburg Group. (2015). Complete reference.', 760, y1=790),
            ll(2, 'Endeavor South Africa. (2012). The entrepreneurial dialogues.', 70),
        ]
        flows = analyze_page_flows(lines, candidates=[])
        self.assertEqual(flows[0]['flow_state'], 'likely_new_reference')
        self.assertIn('institutional_author_date_at_next_page_start', flows[0]['signals'])

    def test_wrapped_author_list_first_line_becomes_boundary_candidate(self):
        lines = [
            ll(1, 'Smith, A. (2009). Previous reference.', 90),
            ll(1, 'Andersen, L. J., Randers, M., Westh, K., Martone, D., Hansen, P. R., Junge, A., Dvorak, J.,', 120),
            ll(1, 'Bangsbo, J., & Krustrup, P. (2010). Effect of football training.', 132, x0=96),
            ll(1, 'Brown, P. (2011). Next reference.', 160),
        ]
        candidates = collect_boundary_candidates(zone(lines))
        first = next(x for x in candidates if x['text_preview'].startswith('Andersen'))
        continuation = next(x for x in candidates if x['text_preview'].startswith('Bangsbo'))
        self.assertTrue(first['features']['wrapped_author_start'])
        self.assertTrue(first['active_shadow_boundary'])
        self.assertTrue(continuation['features']['wrapped_author_continuation'])
        self.assertFalse(continuation['active_shadow_boundary'])

    def test_publisher_year_and_conference_lines_are_continuations(self):
        publisher = [
            ll(1, 'Ribeirão Preto: Legis /', 100),
            ll(1, 'Summa, 2015.', 112),
        ]
        self.assertTrue(source_metadata_continuation(1, publisher))
        cands = collect_boundary_candidates(zone(publisher + [ll(1, 'SILVA, JOAO. Titulo. 2016.', 140)]))
        summa = next(x for x in cands if x['text_preview'].startswith('Summa'))
        self.assertTrue(summa['features']['source_metadata_continuation'])
        self.assertTrue(summa['features']['publisher_year_continuation'])
        self.assertFalse(summa['active_shadow_boundary'])

        event = [
            ll(1, 'In: FORMACAO DE PROFISSIONAIS E A CRIANCA-SUJEITO,', 100),
            ll(1, 'DE PROFISSIONAIS E A CRIANCA-SUJEITO, 7, 2008, Sao Paulo. Proceedings online.', 112),
        ]
        self.assertTrue(source_metadata_continuation(1, event))
        event_cands = collect_boundary_candidates(zone(event + [ll(1, 'SILVA, JOAO. Titulo. 2016.', 140)]))
        event_line = next(x for x in event_cands if x['text_preview'].startswith('DE PROFISSIONAIS'))
        self.assertTrue(event_line['features']['conference_event_continuation'])
        self.assertFalse(event_line['active_shadow_boundary'])

    def test_date_only_after_wrapped_authors_is_continuation(self):
        lines = [
            ll(1, 'Guo, L.-q., Chen, Y., Mi, B.-b., Dang, S.-n., Zhao, D.-d., Liu, R., Wang, H.-l., & Yan, H.', 100),
            ll(1, '(2019). Retracted article: Ambient air pollution and adverse birth outcomes.', 112, x0=96),
            ll(1, 'Jones, P. (2020). Next reference.', 140),
        ]
        cands = collect_boundary_candidates(zone(lines))
        date = next(x for x in cands if x['text_preview'].startswith('(2019)'))
        self.assertTrue(date['features']['wrapped_date_continuation'])
        self.assertFalse(date['active_shadow_boundary'])

    def test_open_set_web_resource_starts_are_supported(self):
        lines = [
            ll(1, 'Online references:', 90),
            ll(1, 'About IBC https://ibc-international.se/en/about-ibc/ (Accessed 2022-01-26)', 110),
            ll(1, 'Europe commission: “About the EN Eurocodes”,', 140),
            ll(1, 'https://eurocodes.jrc.ec.europa.eu/showpage.php?id=13 (Accessed 2022-03-20)', 152, x0=96),
        ]
        cands = collect_boundary_candidates(zone(lines))
        about = next(x for x in cands if x['text_preview'].startswith('About IBC'))
        europe = next(x for x in cands if x['text_preview'].startswith('Europe commission'))
        self.assertTrue(about['features']['web_resource_start'])
        self.assertTrue(europe['features']['web_resource_start'])
        self.assertTrue(about['active_shadow_boundary'])
        self.assertTrue(europe['active_shadow_boundary'])


if __name__ == '__main__':
    unittest.main()
