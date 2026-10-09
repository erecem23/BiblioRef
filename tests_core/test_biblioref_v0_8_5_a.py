import unittest

from biblioref.adaptive.order_profile import infer_order_profile
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, SOFTWARE_VERSION
from biblioref.grammar import GrammarPrimitive, infer_author_inheritance
from biblioref.grammar.repeated_author import detect_repeated_author_marker
from biblioref.grammar.signatures import line_grammar_signature
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


class TestBiblioRefV085A(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_repeated_author_marker_is_grammar_not_narrative_dash(self):
        for raw in ['——————. Título B.', '------. Título B.', '_______. Título B.']:
            self.assertTrue(detect_repeated_author_marker(raw)['is_repeated_author_marker'])
        self.assertFalse(detect_repeated_author_marker('— primer objetivo')['is_repeated_author_marker'])

    def test_date_only_and_dash_inheritance_are_explicit_but_non_destructive(self):
        date = infer_author_inheritance('(1999b [1919]). Título B.', 'freud s', 10, True)
        self.assertTrue(date['inheritance_candidate'])
        self.assertEqual(date['inheritance_type'], 'date_only_after_explicit_author')
        self.assertEqual(date['resolved_author'], 'freud s')
        dash = infer_author_inheritance('——————. Título B.', 'arguelhes diego', 11, True)
        self.assertTrue(dash['inheritance_candidate'])
        self.assertEqual(dash['inheritance_type'], 'repeated_author_marker')
        self.assertEqual(dash['resolved_author'], 'arguelhes diego')

    def test_line_signature_uses_transferable_primitives(self):
        sig = line_grammar_signature('Althusser, L. 1965. Pour Marx.')
        self.assertIn(GrammarPrimitive.AUTHOR_EXPLICIT.value, sig['signals'])
        self.assertIn(GrammarPrimitive.YEAR_BARE.value, sig['signals'])
        repeated = line_grammar_signature('_______. Título siguiente.')
        self.assertIn(GrammarPrimitive.REPEATED_AUTHOR_MARKER.value, repeated['signals'])

    def test_strong_numeric_regime_precedes_strong_or_weak_alphabetical_pattern(self):
        lines = [
            ll('1. ALPHA, A. First.', 100),
            ll('Brown, B. 1958. continuation-like metadata.', 112, x0=96),
            ll('2. BETA, B. Second.', 130),
            ll('Clark, C. 1959. continuation-like metadata.', 142, x0=96),
            ll('3. GAMMA, G. Third.', 160),
            ll('Davis, D. 1960. continuation-like metadata.', 172, x0=96),
            ll('4. DELTA, D. Fourth.', 190),
            ll('Evans, E. 1961. continuation-like metadata.', 202, x0=96),
            ll('5. EPSILON, E. Fifth.', 220),
        ]
        profile = infer_order_profile(lines)
        self.assertEqual(profile['dominant_regime'], 'numeric')
        self.assertEqual(profile['order_type'], 'numeric_order')
        self.assertGreaterEqual(profile['numeric_consistency'], .8)
        self.assertTrue(profile['diagnostic_only'])

    def test_numeric_regime_penalizes_unmarked_author_year_continuation(self):
        lines = [
            ll('1. ALPHA, A. First reference.', 100),
            ll('Brown, B. 1958. Journal continuation.', 112, x0=96),
            ll('2. BETA, B. Second reference.', 130),
            ll('3. GAMMA, G. Third reference.', 150),
            ll('4. DELTA, D. Fourth reference.', 170),
            ll('5. EPSILON, E. Fifth reference.', 190),
        ]
        candidates = collect_boundary_candidates(zone(lines))
        continuation = next(x for x in candidates if x['text_preview'].startswith('Brown, B.'))
        self.assertEqual(continuation['features']['dominant_regime'], 'numeric')
        self.assertTrue(continuation['features']['numeric_regime_missing_marker'])
        self.assertFalse(continuation['active_shadow_boundary'])
        numbered = [x for x in candidates if x['features']['numeric_marker']]
        self.assertEqual(len(numbered), 5)
        self.assertTrue(all(x['active_shadow_boundary'] for x in numbered))

    def test_bracket_key_regime_is_represented_separately(self):
        lines = [
            ll('[Smith20] Smith, J. Reference.', 100),
            ll('[Brown21] Brown, P. Reference.', 120),
            ll('[Clark22] Clark, R. Reference.', 140),
            ll('[Davis23] Davis, M. Reference.', 160),
        ]
        profile = infer_order_profile(lines)
        self.assertEqual(profile['dominant_regime'], 'bracket_key')
        self.assertEqual(profile['order_type'], 'bracket_key_order')
        self.assertEqual(profile['n_bracket_keys'], 4)


if __name__ == '__main__':
    unittest.main()
