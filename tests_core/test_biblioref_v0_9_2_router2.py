import unittest
from biblioref.rescue import (
    RESCUE_PROFILES,
    VALID_RESCUE_PROFILES,
    _numeric_sequence_candidate,
    _numeric_sequence_support,
)
from biblioref.core.config import SOFTWARE_VERSION, RESCUE_ROUTER_VERSION


def rec(text, i):
    return {
        'reference_text': text,
        'zone_id': 1,
        'ref_in_zone': i,
        'reference_start_page': 1,
        'reference_end_page': 1,
        'audit_flags': '',
    }


class TestV092Router2(unittest.TestCase):
    def test_versions(self):
        self.assertEqual('0.9.10-rc2', SOFTWARE_VERSION)
        self.assertEqual('0.9.4-selective-router3-plausibility', RESCUE_ROUTER_VERSION)

    def test_new_profiles_are_explicit_menu_options(self):
        self.assertIn('numeric_sequence', VALID_RESCUE_PROFILES)
        self.assertIn('multi_column_reflow', VALID_RESCUE_PROFILES)
        self.assertNotIn('numeric_sequence', RESCUE_PROFILES)
        self.assertNotIn('multi_column_reflow', RESCUE_PROFILES)
        self.assertEqual('stable', RESCUE_PROFILES[0])

    def test_dominant_numeric_sequence_detects_isolated_layout_numbers(self):
        rows=[]
        vals=[1,2,3,110,4,5,6,7,8,9,473,10,11,12,88,13,14,15]
        for i,v in enumerate(vals,1):
            if v in {110,473,88}:
                rows.append(rec(f'{v}. [ Google Scholar ] [ CrossRef ]', i))
            else:
                rows.append(rec(f'{v}. Author, A. (2020). Reference title {v}. Journal.', i))
        support=_numeric_sequence_support(rows)
        self.assertTrue(support['eligible'])
        self.assertEqual([110,473,88], [x['value'] for x in support['outliers']])
        candidate=_numeric_sequence_candidate(rows)
        self.assertTrue(candidate['accepted'])
        self.assertEqual(15, candidate['n_enhanced_segments'])
        self.assertGreaterEqual(candidate['enhanced_sequence_score'], .9)

    def test_numeric_sequence_does_not_guess_without_dominant_backbone(self):
        vals=[1,4,8,12,18,27,39,55,72]
        rows=[rec(f'{v}. Author, A. (2020). Title.', i) for i,v in enumerate(vals,1)]
        self.assertFalse(_numeric_sequence_support(rows)['eligible'])
        self.assertFalse(_numeric_sequence_candidate(rows)['accepted'])


if __name__ == '__main__':
    unittest.main()
