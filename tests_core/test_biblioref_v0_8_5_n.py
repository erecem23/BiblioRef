import unittest

from biblioref.adaptive.continuity import (
    embedded_access_metadata_continuation,
    source_with_link_continuation,
    web_resource_start,
)
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.grammar.continuation_roles import classify_continuation_role
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout


def ll(i, text):
    return LayoutLine(page=1, page_height=800, text=text, x0=72, y0=70+i*14,
                      x1=520, y1=80+i*14, median_font_size=11, fragment_count=1)


def zone(lines):
    st = diagnose_adaptive_style([x.text for x in lines])
    la = diagnose_adaptive_layout(lines, st)
    return AdaptiveLayoutZone(
        heading=ll(0, 'References'), lines=lines, start_page=1, end_page=1,
        style=st, layout=la, termination_reason='test', confidence_score=0,
        confidence_label='test', confidence_reasons=[], start_confidence_score=0,
        start_confidence_label='test', start_confidence_reasons=[],
        end_confidence_score=0, end_confidence_label='test', end_confidence_reasons=[],
        zone_completeness='test', adaptive_soft_limit_pages=0, zone_span_pages=1,
        adaptive_limit_exceeded=False,
    )


def candidate(lines, i):
    return next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index'] == i)


class TestN(unittest.TestCase):
    def test_version(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_retrived_typo_after_thesis_institution_is_continuation(self):
        lines = [
            ll(0, 'Dona, S. (2011). Study title (Thesis, Andalas'),
            ll(1, 'University). Retrived from http://repository.example.edu/item'),
            ll(2, 'Dwi, T. N. (2012). Next reference.'),
        ]
        self.assertTrue(embedded_access_metadata_continuation(1, lines))
        self.assertFalse(web_resource_start(1, lines))
        self.assertFalse(candidate(lines, 1)['active_shadow_boundary'])

    def test_retrived_typo_after_linking_word_is_continuation(self):
        lines = [
            ll(0, 'Dwi, T. N. (2012). Study (Thesis, Muhammadiyah University of'),
            ll(1, 'Surakarta). Retrived from http://example.edu/18413'),
            ll(2, 'Firana, A. (2012). Next reference.'),
        ]
        self.assertTrue(embedded_access_metadata_continuation(1, lines))
        self.assertFalse(candidate(lines, 1)['active_shadow_boundary'])

    def test_publisher_tail_with_doi_is_continuation(self):
        lines = [
            ll(0, 'Adams, T. E. (2017). Entry. International Encyclopaedia. John Wiley'),
            ll(1, '& Sons. https://doi.org/10.1002/example'),
            ll(2, 'Anderson, J. (2019). Next reference.'),
        ]
        self.assertTrue(source_with_link_continuation(1, lines))
        role = classify_continuation_role(1, lines)
        self.assertIn('source_with_link', role['roles'])
        self.assertTrue(role['is_continuation'])
        self.assertFalse(candidate(lines, 1)['active_shadow_boundary'])

    def test_complete_institutional_web_reference_is_not_swallowed(self):
        lines = [
            ll(0, 'Previous, P. (2019). Previous.'),
            ll(1, 'John Wiley & Sons. (2020). Handbook. https://doi.org/10.1002/handbook'),
            ll(2, 'Next, N. (2021). Next.'),
        ]
        self.assertFalse(source_with_link_continuation(1, lines))
        self.assertTrue(candidate(lines, 1)['active_shadow_boundary'])

    def test_publisher_tail_requires_incomplete_previous_line(self):
        lines = [
            ll(0, 'Previous reference is complete.'),
            ll(1, '& Sons. https://doi.org/10.1002/example'),
            ll(2, 'Next, N. (2021). Next.'),
        ]
        self.assertFalse(source_with_link_continuation(1, lines))

    def test_retrived_without_link_is_not_forced_continuation(self):
        lines = [
            ll(0, 'Previous, P. (2019). Previous.'),
            ll(1, 'University). Retrived from archival notes'),
            ll(2, 'Next, N. (2021). Next.'),
        ]
        self.assertFalse(embedded_access_metadata_continuation(1, lines))

    def test_person_author_with_link_remains_start(self):
        lines = [
            ll(0, 'Previous, P. (2019). Previous.'),
            ll(1, 'Smith, A. (2020). Resource. Retrieved from https://example.org'),
            ll(2, 'Next, N. (2021). Next.'),
        ]
        self.assertFalse(source_with_link_continuation(1, lines))
        self.assertTrue(candidate(lines, 1)['active_shadow_boundary'])


if __name__ == '__main__':
    unittest.main()
