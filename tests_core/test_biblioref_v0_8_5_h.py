import unittest
from biblioref.adaptive.continuity import institutional_author_late_date, standard_document_start
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style

def ll(i,text):
    y=70+i*14
    return LayoutLine(page=1,page_height=800,text=text,x0=72,y0=y,x1=520,y1=y+10,median_font_size=11,fragment_count=1)

def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)

class TestBiblioRefV085H(unittest.TestCase):
    def test_version(self):
        self.assertEqual(SOFTWARE_VERSION,'0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION,'0.8.10-shadow23')
    def test_institutional_late_date(self):
        self.assertTrue(institutional_author_late_date('ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. NBR 8681: Ações e segurança. Rio de Janeiro, 2003.'))
        self.assertTrue(institutional_author_late_date('World Health Organization. Global report. Geneva, 2019.'))
        self.assertFalse(institutional_author_late_date('Journal of Applied Science. Volume 2, 2019.'))
    def test_standard_document_start(self):
        self.assertTrue(standard_document_start('ABNT NBR 6118:2014 Comentários e Exemplos de Aplicação. Ed.: IBRACON, 2015.'))
        self.assertFalse(standard_document_start('2014 results and discussion.'))
    def test_repeated_institutional_standards_are_boundaries(self):
        lines=[
            ll(0,'ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. NBR 6118: Projeto. Rio de Janeiro, 2023.'),
            ll(1,'ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. NBR 8681: Ações. Rio de Janeiro, 2003.'),
            ll(2,'ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. NBR 6120: Ações. Rio de Janeiro, 2019.'),
            ll(3,'ABNT NBR 6118:2014 Comentários e Exemplos. Ed.: IBRACON, 2015.'),
            ll(4,'CARVALHO, Roberto. Cálculo estrutural. São Paulo, 2022.'),
        ]
        active=[c['line_index'] for c in collect_boundary_candidates(zone(lines)) if c['active_shadow_boundary']]
        self.assertEqual(active,[0,1,2,3,4])
    def test_real_alphabetical_inversion_does_not_veto_strong_author_date(self):
        lines=[
            ll(0,'Agriman, M. (2020). Ref.'), ll(1,'Aisenstein, A. (2006). Ref.'),
            ll(2,'Barbero, J. (1997). Ref.'), ll(3,'Bayer, C. (1992). Ref.'),
            ll(4,'Berton, J. (2018). Tesis de Maestría.'), ll(5,'Berthorld, F. (2012). Ref.'),
            ll(6,'Bourdieu, P. (1990). Ref.'), ll(7,'Bourdieu, P. (1995). Ref.'),
            ll(8,'Bourdieu, P. (1998). Ref.'), ll(9,'Carballo, C. (2015). Ref.'),
            ll(10,'Cohen, J. (2002). Ref.'),
        ]
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==4)
        self.assertTrue(cand['features']['strong_alphabetical_inversion'])
        self.assertTrue(cand['active_shadow_boundary'])

if __name__=='__main__': unittest.main()
