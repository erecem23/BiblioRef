import json
import unittest
from pathlib import Path

from biblioref.adaptive.continuity import split_location_publisher_continuation, strong_person_author_date
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'fixtures'/'v088_former_v087_holdout_regression.json').read_text(encoding='utf-8'))


def mk(spec):
    out=[]; y={}
    for pg,t in spec:
        yy=y.get(pg,70.0); y[pg]=yy+14.0
        out.append(LayoutLine(page=pg,page_height=800,text=t,x0=72,y0=yy,x1=520,y1=yy+10,median_font_size=11,fragment_count=1))
    return out


def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(
        heading=LayoutLine(page=lines[0].page,page_height=800,text='References',x0=72,y0=40,x1=200,y1=50,median_font_size=11,fragment_count=1),
        lines=lines,start_page=lines[0].page,end_page=lines[-1].page,style=st,layout=la,
        termination_reason='v088_regression',confidence_score=0,confidence_label='regression',confidence_reasons=[],
        start_confidence_score=0,start_confidence_label='regression',start_confidence_reasons=[],
        end_confidence_score=0,end_confidence_label='regression',end_confidence_reasons=[],
        zone_completeness='regression',adaptive_soft_limit_pages=0,zone_span_pages=len(set(x.page for x in lines)),adaptive_limit_exceeded=False,
    )


class TestV088LocationPublisherProtection(unittest.TestCase):
    def test_strong_author_year_overrides_open_location_publisher_tail(self):
        lines=mk([
            (1,'Principles Within A Customer-Based Design Method, MPHIL Thesis, South Bank University,'),
            (1,'Cleary, T. (1988) The art of war: by Sun Tzu. New York:Random'),
            (1,'House.'),
        ])
        self.assertTrue(strong_person_author_date(lines[1].text))
        self.assertFalse(split_location_publisher_continuation(1,lines))

    def test_former_v087_holdout_is_exact_48_of_48(self):
        totals={'gt':0,'tp':0,'fp':0,'fn':0}; failures=[]
        for case in DATA['cases']:
            lines=mk(case['lines'])
            candidates=collect_boundary_candidates(zone(lines))
            pred={c['line_index'] for c in candidates if c['active_shadow_boundary']}; pred.add(0)
            gt=set(case['gt'])
            totals['gt']+=len(gt); totals['tp']+=len(pred&gt); totals['fp']+=len(pred-gt); totals['fn']+=len(gt-pred)
            if pred!=gt: failures.append((case['case'],sorted(pred-gt),sorted(gt-pred)))
        self.assertEqual([],failures)
        self.assertEqual({'gt':48,'tp':48,'fp':0,'fn':0},totals)

if __name__=='__main__': unittest.main()
