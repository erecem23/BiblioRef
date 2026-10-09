import json
import unittest
from pathlib import Path

from biblioref.adaptive.continuity import wrapped_author_continuation, numeric_page_continuation
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.adaptive.hypotheses import assess_shadow_zone_quality
from biblioref.grammar.numeric import infer_marker_only_numeric, marker_only_number
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'fixtures' / 'v089_former_v088_holdout_regression.json').read_text(encoding='utf-8'))


def mk(spec):
    out = []
    y = {}
    for pg, text in spec:
        yy = y.get(pg, 70.0)
        y[pg] = yy + 14.0
        out.append(LayoutLine(page=pg, page_height=800, text=text, x0=72, y0=yy, x1=520, y1=yy + 10, median_font_size=11, fragment_count=1))
    return out


def zone(lines):
    style = diagnose_adaptive_style([x.text for x in lines])
    layout = diagnose_adaptive_layout(lines, style)
    return AdaptiveLayoutZone(
        heading=LayoutLine(page=lines[0].page, page_height=800, text='References', x0=72, y0=40, x1=200, y1=50, median_font_size=11, fragment_count=1),
        lines=lines, start_page=lines[0].page, end_page=lines[-1].page, style=style, layout=layout,
        termination_reason='v089_regression', confidence_score=0, confidence_label='regression', confidence_reasons=[],
        start_confidence_score=0, start_confidence_label='regression', start_confidence_reasons=[],
        end_confidence_score=0, end_confidence_label='regression', end_confidence_reasons=[],
        zone_completeness='regression', adaptive_soft_limit_pages=0,
        zone_span_pages=len(set(x.page for x in lines)), adaptive_limit_exceeded=False,
    )


class TestV089DottedMarkerOnlyNumeric(unittest.TestCase):
    def test_dotted_marker_is_observable(self):
        self.assertEqual(2, marker_only_number('2.'))
        self.assertEqual(17, marker_only_number(' 17. '))

    def test_dotted_sequence_requires_regional_evidence(self):
        lines = mk([
            (1, '1.'), (1, 'Alpha, A. 2001. Journal of Tests 2: 1-4.'),
            (1, '2.'), (1, 'Beta, B. 2002. University Press.'),
            (1, '3.'), (1, 'Gamma, C. 2003. Review 7: 8-9.'),
            (1, '4.'), (1, 'Delta, D. 2004. https://example.org/item'),
        ])
        profile = infer_marker_only_numeric(lines)
        self.assertTrue(profile['detected'])
        self.assertEqual({0: 1, 2: 2, 4: 3, 6: 4}, profile['line_to_value'])

    def test_single_year_like_dotted_number_is_not_a_regime(self):
        lines = mk([
            (1, 'Narrative paragraph.'),
            (1, '2008.'),
            (1, 'Another narrative paragraph with no bibliography sequence.'),
        ])
        profile = infer_marker_only_numeric(lines)
        self.assertFalse(profile['detected'])
        self.assertEqual({}, profile['line_to_value'])


class TestV089WrappedAuthorYearTitleContinuation(unittest.TestCase):
    def test_bare_year_plus_title_after_long_author_list_is_continuation(self):
        lines = mk([
            (1, 'Andriessen, P.A.M., Helmens, K.F., Hooghiemstra, H., Riezebos, P.A., Vanderhammen, T.'),
            (1, '1993. Absolute chronology of the Pliocene-Quaternary sediment sequence of the'),
            (1, 'Bogota area, Colombia. Quaternary Science Reviews, 12, 483–501.'),
        ])
        self.assertTrue(wrapped_author_continuation(1, lines))

    def test_year_led_title_without_prior_author_list_is_not_suppressed(self):
        lines = mk([
            (1, 'Previous complete source. Journal 12, 44-51.'),
            (1, '1993. Absolute chronology of a separate title entry.'),
        ])
        self.assertFalse(wrapped_author_continuation(1, lines))


class TestV089BulletedBibliographyStarts(unittest.TestCase):
    def test_private_use_and_dash_bullets_are_boundaries_in_bulleted_bibliography(self):
        lines = mk([
            (1, '\uf001 Alpha, A. (2001). First article. Journal of Tests, 1, 1-9.'),
            (1, '\uf001 Beta, B. (2002). Second article. Review, 2, 10-19.'),
            (1, '-Gamma, C. (2003). Third article. University Press.'),
            (1, '-Delta, D. (2004). Fourth article. Journal, 4, 20-29.'),
        ])
        self.assertEqual('bulleted', diagnose_adaptive_style([x.text for x in lines]).style)
        pred = {c['line_index'] for c in collect_boundary_candidates(zone(lines)) if c['active_shadow_boundary']}
        pred.add(0)
        self.assertEqual({0, 1, 2, 3}, pred)

    def test_nonbibliographic_bullets_do_not_gain_marker_authority(self):
        lines = mk([
            (1, '-First task for participants'),
            (1, '-Second task for participants'),
            (1, '-Third task for participants'),
            (1, '-Fourth task for participants'),
        ])
        candidates = collect_boundary_candidates(zone(lines))
        for c in candidates:
            self.assertFalse(c['features'].get('bullet_marker', False))


class TestV089PageDoiTail(unittest.TestCase):
    def test_page_number_plus_doi_after_incomplete_journal_tail_is_continuation(self):
        lines = mk([
            (1, 'Bellah, R. N. (1970). Christianity and Symbolic Realism. Journal for the Scientific Study of Religion, 9 (2),'),
            (1, '89. http://doi.org/10.2307/1384973'),
        ])
        self.assertTrue(numeric_page_continuation(1, lines))

    def test_numeric_web_bibliography_keeps_genuine_numbered_boundaries(self):
        lines = mk([
            (1, '88. http://example.org/a'),
            (1, '89. http://example.org/b'),
            (1, '90. http://example.org/c'),
            (1, '91. http://example.org/d'),
        ])
        pred = {c['line_index'] for c in collect_boundary_candidates(zone(lines)) if c['active_shadow_boundary']}
        pred.add(0)
        self.assertEqual({0, 1, 2, 3}, pred)


class TestV089FormerV088ExternalHoldoutRegression(unittest.TestCase):
    def test_former_v088_holdout_is_exact_48_of_48(self):
        totals = {'gt': 0, 'tp': 0, 'fp': 0, 'fn': 0}
        failures = []
        for case in DATA['cases']:
            lines = mk(case['lines'])
            candidates = collect_boundary_candidates(zone(lines))
            pred = {c['line_index'] for c in candidates if c['active_shadow_boundary']}
            pred.add(0)
            gt = set(case['gt'])
            totals['gt'] += len(gt)
            totals['tp'] += len(pred & gt)
            totals['fp'] += len(pred - gt)
            totals['fn'] += len(gt - pred)
            if pred != gt:
                failures.append((case['case'], sorted(pred - gt), sorted(gt - pred)))
        self.assertEqual([], failures)
        self.assertEqual({'gt': 48, 'tp': 48, 'fp': 0, 'fn': 0}, totals)


class TestV089Dev2BulletedContinuationGuard(unittest.TestCase):
    def test_nonmarker_source_line_inside_bulleted_zone_is_continuation(self):
        lines = mk([
            (1, '\uf001 Abelin, E. (1971). The role of the father. Journal, 1, 1-9.'),
            (1, 'En M. Burin & E. Dio Bleichmar (Comp.), Género, psicoanálisis, subjetividad (pp. 31-60).'),
            (1, '\uf001 Abelleira, H. (2006). Divorcio y violencia. Revista, 9, 6-33.'),
            (1, '\uf001 Acosta, J. (2007). Another reference. Review, 2, 9-20.'),
        ])
        z = zone(lines)
        self.assertEqual('bulleted', z.style.style)
        pred = {c['line_index'] for c in collect_boundary_candidates(z) if c['active_shadow_boundary']}
        pred.add(0)
        self.assertEqual({0, 2, 3}, pred)

    def test_unbulleted_strong_person_start_is_preserved(self):
        lines = mk([
            (1, '\uf001 Alpha, A. (2001). First article. Journal, 1, 1-9.'),
            (1, 'Durán, A., Romé, M. & Martínez, A. (2008). Investigaciones sobre desarrollo. Revista, 2, 10-20.'),
            (1, '\uf001 Beta, B. (2009). Second article. Review, 3, 21-30.'),
            (1, '\uf001 Gamma, C. (2010). Third article. Review, 4, 31-40.'),
        ])
        z = zone(lines)
        pred = {c['line_index'] for c in collect_boundary_candidates(z) if c['active_shadow_boundary']}
        pred.add(0)
        self.assertIn(1, pred)


class TestV089Dev2HangingIndentContinuationCluster(unittest.TestCase):
    def _line(self, text, x0, y):
        return LayoutLine(page=1, page_height=800, text=text, x0=x0, y0=y, x1=520, y1=y+10, median_font_size=11, fragment_count=1)

    def test_indented_source_tails_do_not_open_records(self):
        lines = [
            self._line('Abdel-Khalek, A. M. (2009). Religiosity and well-being.', 72, 70),
            self._line('Mental Health, Religion & Culture, 12(8), 803-815. http://doi.org/10.1/a', 96, 84),
            self._line('Hattie, J. (1992). Self-Concept.', 72, 98),
            self._line('Hillsdale: Psychology Press.', 96, 112),
            self._line('Kassin, S. (2003). Psychology.', 72, 126),
            self._line('New York: Prentice-Hall.', 96, 140),
            self._line('Yalom, I. (1980). Existential psychotherapy.', 72, 154),
            self._line('University Press, 28(1), 117-124.', 96, 168),
        ]
        pred = {c['line_index'] for c in collect_boundary_candidates(zone(lines)) if c['active_shadow_boundary']}
        pred.add(0)
        self.assertEqual({0, 2, 4, 6}, pred)

    def test_strong_person_start_survives_even_at_continuation_cluster(self):
        lines = [
            self._line('Alpha, A. (2001). First reference.', 72, 70),
            self._line('Journal of Tests, 1, 1-9.', 96, 84),
            self._line('Beta, B. (2002). Second reference.', 72, 98),
            self._line('Gamma, C. (2003). Legitimate shifted start.', 96, 112),
            self._line('Delta, D. (2004). Fourth reference.', 72, 126),
            self._line('Review, 4, 20-29.', 96, 140),
            self._line('Epsilon, E. (2005). Fifth reference.', 72, 154),
            self._line('Press, 2005.', 96, 168),
        ]
        pred = {c['line_index'] for c in collect_boundary_candidates(zone(lines)) if c['active_shadow_boundary']}
        self.assertIn(3, pred)


class TestV089Dev2ShadowZoneQuality(unittest.TestCase):
    def test_giant_segment_share_quarantines_narrative_zone(self):
        shadow = [
            {'reference_text': ' '.join(['narrative'] * 260)},
            {'reference_text': ' '.join(['chapter'] * 210)},
            {'reference_text': ' '.join(['body'] * 180)},
            {'reference_text': 'Short plausible item 2020 Journal.'},
            {'reference_text': 'Another short plausible item 2021 Press.'},
        ]
        q = assess_shadow_zone_quality(shadow, [{'active_shadow_boundary': True}] * 5)
        self.assertFalse(q['candidate_dataset_eligible'])
        self.assertEqual('narrative_contamination_requires_review', q['verdict'])

    def test_one_long_reference_does_not_quarantine_large_bibliography(self):
        shadow = [{'reference_text': 'Author, A. (2020). Normal reference. Journal.'} for _ in range(19)]
        shadow.append({'reference_text': ' '.join(['long'] * 220)})
        q = assess_shadow_zone_quality(shadow, [{'active_shadow_boundary': True}] * 20)
        self.assertTrue(q['candidate_dataset_eligible'])


if __name__ == '__main__':
    unittest.main()
