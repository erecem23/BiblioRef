import unittest
from biblioref.adaptive.order_profile import infer_order_profile
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.grammar.numeric import comma_numeric_entry, infer_comma_numeric
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style

def ll(i,text):
    y=70+i*14
    return LayoutLine(page=1,page_height=800,text=text,x0=72,y0=y,x1=520,y1=y+10,median_font_size=11,fragment_count=1)
def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)

class TestBiblioRefV085K(unittest.TestCase):
    def test_version(self):
        self.assertEqual(SOFTWARE_VERSION,'0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION,'0.8.10-shadow23')
    def test_comma_numeric_requires_global_sequence(self):
        lines=[ll(0,'1, A.F. Wells. J Chem Soc 1970, 1, 2.'),ll(1,'2, J.T.R. Dunsmuir. Nature 1971, 2, 3.'),ll(2,'3, R.J.H. Clark. Spectrochim Acta 1972, 3, 4.'),ll(3,'4, H.M. Powell. Chem Rev 1973, 4, 5.')]
        p=infer_comma_numeric(lines)
        self.assertTrue(p['detected']); self.assertEqual(p['line_to_value'],{0:1,1:2,2:3,3:4})
    def test_comma_numeric_drives_regime_and_boundaries(self):
        lines=[ll(0,'1, A.F. Wells. J Chem Soc 1970, 1, 2.'),ll(1,'2, J.T.R. Dunsmuir. Nature 1971, 2, 3.'),ll(2,'3, R.J.H. Clark. Spectrochim Acta 1972, 3, 4.'),ll(3,'4, H.M. Powell. Chem Rev 1973, 4, 5.'),ll(4,'5, G.N. Papatheodorou. J Phys Chem 1974, 5, 6.')]
        prof=infer_order_profile(lines); self.assertEqual(prof['dominant_regime'],'numeric'); self.assertTrue(prof['comma_numeric']['detected'])
        c=collect_boundary_candidates(zone(lines)); active=[x['line_index'] for x in c if x['active_shadow_boundary']]
        self.assertEqual(active,[0,1,2,3,4]); self.assertTrue(all(x['features']['numeric_comma_marker'] for x in c))
    def test_single_comma_number_is_not_authority(self):
        lines=[ll(0,'12, Results from the study 2024'),ll(1,'ordinary prose'),ll(2,'Smith, J. (2020). Ref.')]
        self.assertFalse(infer_comma_numeric(lines)['detected']); self.assertEqual(comma_numeric_entry('12, Results from the study 2024'),(12,'Results from the study 2024'))
    def test_year_led_comma_prose_is_not_numeric_bibliography(self):
        lines=[ll(0,'2019, Results from first survey'),ll(1,'2020, Results from second survey'),ll(2,'2021, Results from third survey'),ll(3,'2022, Results from fourth survey')]
        self.assertFalse(infer_comma_numeric(lines)['detected'])
    def test_non_monotonic_comma_numbers_rejected(self):
        lines=[ll(0,'1, Smith. Journal 2020.'),ll(1,'4, Brown. Journal 2021.'),ll(2,'2, Jones. Journal 2022.'),ll(3,'9, White. Journal 2023.')]
        self.assertFalse(infer_comma_numeric(lines)['detected'])

if __name__=='__main__': unittest.main()
