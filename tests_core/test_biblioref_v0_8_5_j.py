import unittest
from biblioref.adaptive.continuity import embedded_access_metadata_continuation, web_resource_start
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style

def ll(i,text,x0=72):
    y=70+i*14
    return LayoutLine(page=1,page_height=800,text=text,x0=x0,y0=y,x1=520,y1=y+10,median_font_size=11,fragment_count=1)

def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)

class TestBiblioRefV085J(unittest.TestCase):
    def test_version(self):
        self.assertEqual(SOFTWARE_VERSION,'0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION,'0.8.10-shadow23')

    def _assert_continuation(self, lines, idx):
        self.assertTrue(embedded_access_metadata_continuation(idx, lines))
        self.assertFalse(web_resource_start(idx, lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==idx)
        self.assertTrue(cand['features']['embedded_access_metadata_continuation'])
        self.assertFalse(cand['active_shadow_boundary'])

    def test_embedded_retrieved_after_institutional_metadata(self):
        lines=[
            ll(0,'Bush, J. (2010). Marangoni Flows. Lecture Slides from Interfacial'),
            ll(1,'Phenomena, Department of Mathematics, MIT, USA. Retrieved from <http://ocw.mit.edu/file.pdf>'),
            ll(2,'Castrejón-Pita, J. R. (2013). Next reference.'),
        ]
        self._assert_continuation(lines,1)

    def test_embedded_online_available_after_journal_pages(self):
        lines=[
            ll(0,'Crossan, F. 2003. Research philosophy: towards an understanding. Nurse'),
            ll(1,'Researcher, 11(1):46-55. [Online] Available from:'),
            ll(2,'http://example.org/paper.pdf'),
            ll(3,'Davis, F.D. 1989. Next reference.'),
        ]
        self._assert_continuation(lines,1)

    def test_embedded_available_after_page_range(self):
        lines=[
            ll(0,'technology: a comparison of two theoretical models, Management Science, 35(8):'),
            ll(1,'982-1003. [Online] Available from: JSTOR: http://www.jstor.org/stable/2632151'),
            ll(2,'Dimmick, J. (2010). Next reference.'),
        ]
        self._assert_continuation(lines,1)

    def test_online_available_at_line_start(self):
        lines=[
            ll(0,'niches of mobile media in space and time. New Media & Society, 13(1):23-39.'),
            ll(1,'[Online] Available from: http://example.org/article'),
            ll(2,'Dominick, J.R. 2009. Next reference.'),
        ]
        self._assert_continuation(lines,1)

    def test_legitimate_author_web_reference_remains_start(self):
        lines=[
            ll(0,'Previous, P. (2018). Previous reference.'),
            ll(1,'Breinlinger, T. (n.d.). Inkjet Example. Retrieved from <http://example.org/inkjet> [Accessed 21/06/2019].'),
            ll(2,'Brown, P. (2020). Next reference.'),
        ]
        self.assertFalse(embedded_access_metadata_continuation(1,lines))

    def test_url_before_accessed_is_not_embedded_continuation(self):
        lines=[
            ll(0,'Online references:'),
            ll(1,'About IBC https://ibc-international.se/en/about-ibc/ (Accessed 2022-01-26)'),
            ll(2,'Europe commission: About the EN Eurocodes,'),
        ]
        self.assertFalse(embedded_access_metadata_continuation(1,lines))
        self.assertTrue(web_resource_start(1,lines))

    def test_embedded_phrase_without_link_is_not_forced(self):
        lines=[ll(0,'Previous reference complete.'),ll(1,'Phenomena discussed were retrieved from archival memory.'),ll(2,'Brown, P. (2020). Next.')]
        self.assertFalse(embedded_access_metadata_continuation(1,lines))

if __name__=='__main__': unittest.main()
