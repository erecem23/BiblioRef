import unittest

from biblioref.adaptive.continuity import (
    dot_initial_author_date,
    implicit_inherited_title_start,
    institutional_author_date,
    source_metadata_continuation,
)
from biblioref.adaptive.order_profile import infer_order_profile, local_order_evidence
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.grammar.dates import undated_author_start
from biblioref.grammar.numeric import infer_marker_only_numeric
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


class TestBiblioRefV085F(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_marker_only_numeric_requires_sequence_and_body_support(self):
        lines=[]
        for n in range(1,6):
            lines.extend([ll(len(lines), str(n)), ll(len(lines)+1, f'Smith {n}. Article title. Journal 202{n};12:10-20.')])
        profile=infer_marker_only_numeric(lines)
        self.assertTrue(profile['detected'])
        self.assertEqual(profile['values'], [1,2,3,4,5])
        self.assertGreaterEqual(profile['body_support_ratio'], .8)

    def test_isolated_numbers_do_not_become_marker_only_regime(self):
        lines=[ll(0,'12'), ll(1,'Chapter heading'), ll(2,'13'), ll(3,'ordinary prose'), ll(4,'14')]
        profile=infer_marker_only_numeric(lines)
        self.assertFalse(profile['detected'])

    def test_marker_only_numeric_drives_boundaries_and_suppresses_body_starts(self):
        lines=[]
        for n, body in [
            (1,'Institute of Medicine. Report. Washington DC: Press, 2001.'),
            (2,'Smedley BD, Stith AY. Unequal treatment. Academy Press, 2003.'),
            (3,'Department of Health. Equity report. London, 2007.'),
            (4,'Goddard M, Smith P. Equity of access. Soc Sci Med 2001;53:1149-62.'),
        ]:
            lines.extend([ll(len(lines),str(n)), ll(len(lines)+1,body)])
        cands=collect_boundary_candidates(zone(lines))
        active=[c['line_index'] for c in cands if c['active_shadow_boundary']]
        self.assertEqual(active,[0,2,4,6])
        self.assertTrue(all(c['features']['dominant_regime']=='numeric' for c in cands))

    def test_undated_multilingual_author_start(self):
        self.assertTrue(undated_author_start('Beer, J. (no date) To Write the Larger Scene.'))
        self.assertTrue(undated_author_start('Beer, J. (n.d.) To Write the Larger Scene.'))
        self.assertTrue(undated_author_start('Beer, J. (s.f.) Título.'))
        self.assertTrue(undated_author_start('Beer, J. (sem data) Título.'))

    def test_dot_initial_person_author_is_supported(self):
        self.assertTrue(dot_initial_author_date('Amunetegui. D. (1909). Las encomiendas de indígenas en Chile.'))

    def test_institutional_name_with_function_words_is_supported(self):
        self.assertTrue(institutional_author_date('Congreso de la República de Chile (1935) Ley 5604.'))

    def test_title_only_successor_can_start_new_inherited_record(self):
        lines=[
            ll(0,'ALTAMIRANO, Carlos. “Raymond Williams” (En: Punto de Vista, 1981; pp. 20-23).'),
            ll(1,'“Lecciones de una guerra” (En: Punto de Vista, Nº 15. Buenos Aires,'),
            ll(2,'agosto/octubre de 1982; pp. 3-5).'),
        ]
        self.assertTrue(implicit_inherited_title_start(1,lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==1)
        self.assertTrue(cand['active_shadow_boundary'])

    def test_imprint_is_not_title_only_successor(self):
        lines=[
            ll(0,'Bakhtin, M. (1984) Rabelais and His World. Translated by Hélène Iswolsky.'),
            ll(1,'Bloomington: Indiana University Press.'),
            ll(2,'Baraitser, L. (2016). Next reference.'),
        ]
        self.assertFalse(implicit_inherited_title_start(1,lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==1)
        self.assertFalse(cand['active_shadow_boundary'])

    def test_wrapped_thesis_title_is_continuation_not_author(self):
        lines=[
            ll(0,'Butler, T. (2005) Writing at the Edge of the Person: Lyric Subjectivity in Cambridge'),
            ll(1,'Poetry, 1966-1993. PhD thesis. University of Notre Dame, Indiana. Available at:'),
            ll(2,'https://example.org/thesis'),
        ]
        self.assertTrue(source_metadata_continuation(1,lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==1)
        self.assertFalse(cand['active_shadow_boundary'])

    def test_soft_alphabetical_order_does_not_create_hard_inversion(self):
        lines=[
            ll(0,'Artusi, A. (2001). Ref.'),
            ll(1,'Codazzi, A. (2003). Ref.'),
            ll(2,'Balkaran, S. (2014). Ref.'),
            ll(3,'Bartuska, T. (2015). Ref.'),
            ll(4,'Bravo, G. (2016). Ref.'),
            ll(5,'Brown, P. (2017). Ref.'),
        ]
        profile=infer_order_profile(lines)
        # Even if the region is mostly alphabetical, one C->B anomaly is not a
        # veto unless consistency/margin are exceptionally strong.
        ev=local_order_evidence(2,profile)
        self.assertFalse(ev['inversion'])


if __name__ == '__main__':
    unittest.main()
