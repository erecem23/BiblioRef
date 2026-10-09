import unittest

from biblioref.adaptive.order_profile import infer_order_profile
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.grammar.numeric import infer_prefix_numeric, prefix_numeric_entry
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style


def ll(i, text, page=1, x0=72.0):
    y = 70 + i * 14
    return LayoutLine(page=page, page_height=800.0, text=text, x0=x0, y0=y, x1=520.0,
                      y1=y+10, median_font_size=11.0, fragment_count=1)


def zone(lines):
    style = diagnose_adaptive_style([x.text for x in lines])
    layout = diagnose_adaptive_layout(lines, style)
    return AdaptiveLayoutZone(
        heading=ll(0, 'References'), lines=lines, start_page=1, end_page=max(x.page for x in lines),
        style=style, layout=layout, termination_reason='test', confidence_score=0,
        confidence_label='test', confidence_reasons=[], start_confidence_score=0,
        start_confidence_label='test', start_confidence_reasons=[], end_confidence_score=0,
        end_confidence_label='test', end_confidence_reasons=[], zone_completeness='test',
        adaptive_soft_limit_pages=0, zone_span_pages=max(x.page for x in lines), adaptive_limit_exceeded=False,
    )


class TestBiblioRefV085G(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_prefix_numeric_requires_global_sequence(self):
        lines = [
            ll(0, '1 World Health Organization. (2020) World malaria report.'),
            ll(1, '2 Smith, J. (2019) Malaria epidemiology. Journal 4:1-9.'),
            ll(2, '3 Brown, P. (2018) Parasite biology. Nature 2:10-20.'),
            ll(3, '4 Jones, R. (2017) Vector control. Lancet 5:1-8.'),
        ]
        p = infer_prefix_numeric(lines)
        self.assertTrue(p['detected'])
        self.assertEqual(p['values'], [1,2,3,4])
        self.assertEqual(p['line_to_value'], {0:1,1:2,2:3,3:4})

    def test_numbered_headings_are_not_prefix_numeric_bibliography(self):
        lines = [ll(0,'1 Introduction'), ll(1,'2 Methods'), ll(2,'3 Results'), ll(3,'4 Discussion')]
        self.assertFalse(infer_prefix_numeric(lines)['detected'])

    def test_single_numeric_prefix_is_not_authority(self):
        lines = [ll(0,'12 Results 2024'), ll(1,'ordinary prose'), ll(2,'Smith, J. (2020). Ref.')]
        self.assertFalse(infer_prefix_numeric(lines)['detected'])
        self.assertEqual(prefix_numeric_entry('12 Results 2024'), (12, 'Results 2024'))

    def test_prefix_numeric_drives_all_boundaries_and_regime(self):
        lines = [
            ll(0, '1 World Health Organization. (2020) World malaria report.'),
            ll(1, '2 Teklehaimanot, A. (2008) Malaria and poverty. Ann NY Acad Sci 1136:32-37.'),
            ll(2, '3 Blasco, B. (2017) Antimalarial drug resistance. Nat Med 23:917.'),
            ll(3, '4 Howes, R. (2016) Global epidemiology. Am J Trop Med Hyg 95:15-34.'),
            ll(4, '5 Cowman, A. (2016) Malaria biology and disease. Cell 167:610-624.'),
        ]
        profile = infer_order_profile(lines)
        self.assertEqual(profile['dominant_regime'], 'numeric')
        self.assertTrue(profile['prefix_numeric']['detected'])
        cands = collect_boundary_candidates(zone(lines))
        active = [c['line_index'] for c in cands if c['active_shadow_boundary']]
        self.assertEqual(active, [0,1,2,3,4])
        self.assertTrue(all(c['features']['numeric_prefix_marker'] for c in cands))

    def test_year_led_prose_does_not_form_sequence_without_body_support(self):
        lines = [
            ll(0, '2019 Results from the first survey'),
            ll(1, '2020 Results from the second survey'),
            ll(2, '2021 Results from the third survey'),
            ll(3, '2022 Results from the fourth survey'),
        ]
        self.assertFalse(infer_prefix_numeric(lines)['detected'])


if __name__ == '__main__':
    unittest.main()
