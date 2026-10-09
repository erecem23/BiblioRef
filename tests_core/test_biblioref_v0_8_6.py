import json
import unittest
from pathlib import Path

from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.adaptive.continuity import (
    author_title_start,
    compact_person_author_year_start,
    journal_volume_pages_link_continuation,
    publisher_year_continuation,
    wrapped_author_start,
    wrapped_author_continuation,
)
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

ROOT = Path(__file__).resolve().parent
CASES = json.loads((ROOT / 'fixtures' / 'v086_repository_independent_regression.json').read_text(encoding='utf-8'))
FORMER_M = json.loads((ROOT / 'fixtures' / 'v086_former_m_regression.json').read_text(encoding='utf-8'))
FORMER_N = json.loads((ROOT / 'fixtures' / 'v086_former_n_regression.json').read_text(encoding='utf-8'))

def mk(spec):
    out=[]; y={}
    for pg,t in spec:
        yy=y.get(pg,70.0); y[pg]=yy+14
        out.append(LayoutLine(page=pg,page_height=800,text=t,x0=72,y0=yy,x1=520,y1=yy+10,median_font_size=11,fragment_count=1))
    return out

def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(heading=LayoutLine(page=lines[0].page,page_height=800,text='References',x0=72,y0=40,x1=200,y1=50,median_font_size=11,fragment_count=1),lines=lines,start_page=lines[0].page,end_page=lines[-1].page,style=st,layout=la,termination_reason='v086_regression',confidence_score=0,confidence_label='regression',confidence_reasons=[],start_confidence_score=0,start_confidence_label='regression',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='regression',end_confidence_reasons=[],zone_completeness='regression',adaptive_soft_limit_pages=0,zone_span_pages=len(set(x.page for x in lines)),adaptive_limit_exceeded=False)

class TestV086Primitives(unittest.TestCase):
    def test_author_title_start_mla(self):
        lines=mk([(1,'Adams, J. Stuart. ‘Fairness for All in a Post-Obergefell World: The Utah Compromise'),(1,'Model.’ The University of Illinois Law Review, vol. 2016, no. 4, 2016, 1651-1664.')])
        self.assertTrue(author_title_start(0, lines))

    def test_long_wrapped_author_pair(self):
        lines=mk([(1,'Babst F., Poulter, B., Trouet V., Tan K., Neuwirth B., Wilson R., Carrer M., Grabner M.,'),(1,'Tegel W., Levanic T., Panayotov M., Urbinati C., Bouriaud O., Ciais P., Frank D. 2013.')])
        self.assertTrue(wrapped_author_start(0, lines))
        self.assertTrue(wrapped_author_continuation(1, lines))

    def test_journal_volume_pages_link_tail(self):
        lines=mk([(1,'availability on the productivity of Norway spruce in northern and southern Sweden.'),(1,'Forest ecology and management 119: 51-62. http://dx.doi.org/10.1016/S0378-')])
        self.assertTrue(journal_volume_pages_link_continuation(1, lines))

    def test_publisher_year_tail(self):
        lines=mk([(1,'Archer, Kenneth J. A Pentecostal Hermeneutic: Spirit, Scripture and Community. CPT'),(1,'Press, 2009.')])
        self.assertTrue(publisher_year_continuation(1, lines))

    def test_compact_person_author_year(self):
        self.assertTrue(compact_person_author_year_start('Cajander AK. 1926. The theory of forest types.'))
        self.assertFalse(compact_person_author_year_start('Environment 140: 625–638. http://dx.doi.org/x'))

class TestV086FormerHoldoutRegression(unittest.TestCase):
    def test_all_four_former_holdout_cases_are_exact(self):
        failures=[]
        for case in CASES:
            lines=mk(case['lines'])
            candidates=collect_boundary_candidates(zone(lines))
            pred={c['line_index'] for c in candidates if c['active_shadow_boundary']}
            pred.add(0)
            gt=set(case['gt'])
            if pred != gt:
                failures.append((case['case'], sorted(pred-gt), sorted(gt-pred)))
        self.assertEqual([], failures)

    def test_former_n_document_new_holdout_is_exact_regression(self):
        failures=[]
        for case in FORMER_N:
            lines=mk(case['lines'])
            candidates=collect_boundary_candidates(zone(lines))
            pred={c['line_index'] for c in candidates if c['active_shadow_boundary']}
            pred.add(0)
            gt=set(case['gt'])
            if pred != gt:
                failures.append((case['case'], sorted(pred-gt), sorted(gt-pred)))
        self.assertEqual([], failures)

    def test_former_m_regression_has_no_errors_beyond_known_two(self):
        allowed_fp={'glasgow_aldlgan': {49}}
        allowed_fn={'twente_nettersheim': {44}}
        totals={'tp':0,'fp':0,'fn':0}
        unexpected=[]
        for case in FORMER_M:
            lines=mk(case['lines'])
            candidates=collect_boundary_candidates(zone(lines))
            pred={c['line_index'] for c in candidates if c['active_shadow_boundary']}
            pred.add(0)
            gt=set(case['gt'])
            fp=pred-gt; fn=gt-pred
            totals['tp'] += len(pred & gt); totals['fp'] += len(fp); totals['fn'] += len(fn)
            if not fp.issubset(allowed_fp.get(case['case'], set())) or not fn.issubset(allowed_fn.get(case['case'], set())):
                unexpected.append((case['case'], sorted(fp), sorted(fn)))
        self.assertEqual([], unexpected)
        self.assertGreaterEqual(totals['tp'], 60)
        self.assertLessEqual(totals['fp'], 1)
        self.assertLessEqual(totals['fn'], 1)

if __name__ == '__main__':
    unittest.main()
