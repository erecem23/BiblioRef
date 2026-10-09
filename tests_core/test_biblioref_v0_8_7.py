import json
import unittest
from pathlib import Path

from biblioref.adaptive.continuity import (
    late_author_title_start,
    late_source_tail_continuation,
    strong_comma_person_lead,
    initial_first_person_lead,
    institutional_comma_title_lead,
    title_led_reference_start,
)
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'fixtures' / 'v087_former_v086_holdout_regression.json').read_text(encoding='utf-8'))
CASES = DATA['cases']


def mk(spec):
    out=[]; y={}
    for pg,t in spec:
        yy=y.get(pg,70.0); y[pg]=yy+14
        out.append(LayoutLine(page=pg,page_height=800,text=t,x0=72,y0=yy,x1=520,y1=yy+10,median_font_size=11,fragment_count=1))
    return out


def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(
        heading=LayoutLine(page=lines[0].page,page_height=800,text='References',x0=72,y0=40,x1=200,y1=50,median_font_size=11,fragment_count=1),
        lines=lines,start_page=lines[0].page,end_page=lines[-1].page,style=st,layout=la,
        termination_reason='v087_regression',confidence_score=0,confidence_label='regression',confidence_reasons=[],
        start_confidence_score=0,start_confidence_label='regression',start_confidence_reasons=[],
        end_confidence_score=0,end_confidence_label='regression',end_confidence_reasons=[],
        zone_completeness='regression',adaptive_soft_limit_pages=0,zone_span_pages=len(set(x.page for x in lines)),adaptive_limit_exceeded=False,
    )


class TestV087Primitives(unittest.TestCase):
    def test_comma_person_with_late_date(self):
        lines=mk([(1,'Götte, Ulli, Wiederholung – eine fundamentale musikalische Kategorie,'),(1,'(Unpublished manuscript: January 24, 2015), PDF file.')])
        self.assertTrue(strong_comma_person_lead(lines[0].text))
        self.assertTrue(late_author_title_start(0, lines))

    def test_initial_first_multi_author_with_late_date(self):
        lines=mk([(1,'H.A. Bachor and T.C. Ralph, A guide to experiments in quantum optics (Third Edition),'),(1,'Wiley and Sons (2019).')])
        self.assertTrue(initial_first_person_lead(lines[0].text))
        self.assertTrue(late_author_title_start(0, lines))

    def test_institutional_title_with_late_date(self):
        lines=mk([(1,'National Cyber Security Centre (NCSC, UK), Preparing for Quantum-Safe Cryptography,'),(1,'Whitepaper, https://example.org/whitepaper (2020)')])
        self.assertTrue(institutional_comma_title_lead(lines[0].text))
        self.assertTrue(late_author_title_start(0, lines))

    def test_source_tail_is_not_person(self):
        lines=mk([(1,'Gottschalk, Jennie, Experimental Music Since 1970, (London and New York: Bloomsbury'),(1,'Academic, 2016).')])
        self.assertTrue(late_source_tail_continuation(1, lines))
        self.assertFalse(strong_comma_person_lead(lines[1].text))

    def test_journal_tail_is_not_person(self):
        lines=mk([(1,'Hanninen, Dora A., ‘A Theory of Recontextualization in Music: Analyzing Phenomenal'),(1,'Transformations of Repetition’, Music Theory Spectrum, Vol. 25, No. 1 (2003), 59-97')])
        self.assertTrue(late_source_tail_continuation(1, lines))

    def test_title_led_web_reference(self):
        lines=mk([(1,'Theory, research, applications, (New York: Oxford University Press, 2010), 575-604'),(1,'’Interview with Laurence Crane’, Another Timbre,'),(1,'http://www.anothertimbre.com/craneinterview.html, accessed on 30 January'),(1,'2020')])
        self.assertTrue(title_led_reference_start(1, lines))


class TestV087FormerV086HoldoutRegression(unittest.TestCase):
    def test_four_former_v086_holdout_documents_are_exact(self):
        failures=[]
        totals={'gt':0,'tp':0,'fp':0,'fn':0}
        for case in CASES:
            lines=mk(case['lines'])
            candidates=collect_boundary_candidates(zone(lines))
            pred={c['line_index'] for c in candidates if c['active_shadow_boundary']}
            pred.add(0)
            gt=set(case['gt'])
            totals['gt'] += len(gt); totals['tp'] += len(pred & gt); totals['fp'] += len(pred-gt); totals['fn'] += len(gt-pred)
            if pred != gt:
                failures.append((case['case'], sorted(pred-gt), sorted(gt-pred)))
        self.assertEqual([], failures)
        self.assertEqual({'gt':48,'tp':48,'fp':0,'fn':0}, totals)


if __name__ == '__main__':
    unittest.main()
