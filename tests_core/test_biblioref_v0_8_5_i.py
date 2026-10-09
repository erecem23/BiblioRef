import unittest
from biblioref.adaptive.continuity import access_metadata_continuation, web_resource_start
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, diagnose_adaptive_layout, diagnose_adaptive_style

def ll(i, text, x0=72):
    y = 70 + i * 14
    return LayoutLine(page=1, page_height=800, text=text, x0=x0, y0=y, x1=520, y1=y+10, median_font_size=11, fragment_count=1)

def zone(lines):
    st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
    return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)

class TestBiblioRefV085I(unittest.TestCase):
    def test_version(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_real_retrieved_date_from_is_continuation(self):
        lines=[
            ll(0, 'American Psychological Association. (n.d.). APA dictionary of psychology.'),
            ll(1, 'Retrieved 23rd July 2023 from https://dictionary.apa.org/feedback'),
            ll(2, 'An, M., Kim, Y., & Cho, W. K. (2019). Next reference.'),
        ]
        self.assertTrue(access_metadata_continuation(1, lines))
        self.assertFalse(web_resource_start(1, lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==1)
        self.assertTrue(cand['features']['access_metadata_continuation'])
        self.assertFalse(cand['active_shadow_boundary'])

    def test_access_metadata_with_url_on_next_line(self):
        lines=[
            ll(0, 'UNICEF. (2020). Global report.'),
            ll(1, 'Available from:'),
            ll(2, 'https://www.unicef.org/report'),
            ll(3, 'World Health Organization. (2021). Next.'),
        ]
        self.assertTrue(access_metadata_continuation(1, lines))
        cand=next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==1)
        self.assertFalse(cand['active_shadow_boundary'])

    def test_multilingual_access_metadata(self):
        examples=[
            'Disponível em: https://example.org/x',
            'Disponible en: https://example.org/x',
            'Acesso em: https://example.org/x',
            'Consultado en: https://example.org/x',
            'Recuperado de https://example.org/x',
            'Accessed on 12 May 2024: https://example.org/x',
        ]
        for text in examples:
            with self.subTest(text=text):
                lines=[ll(0,'Organization. (2020). Report.'), ll(1,text), ll(2,'Smith, J. (2021). Next.')]
                self.assertTrue(access_metadata_continuation(1, lines))

    def test_prefix_without_link_is_not_forced_continuation(self):
        lines=[ll(0,'Smith, J. (2020). Previous.'), ll(1,'Retrieved memories and archival fragments.'), ll(2,'Brown, P. (2021). Next.')]
        self.assertFalse(access_metadata_continuation(1, lines))

    def test_existing_open_set_web_start_still_works(self):
        lines=[
            ll(0,'Online references:'),
            ll(1,'About IBC https://ibc-international.se/en/about-ibc/ (Accessed 2022-01-26)'),
            ll(2,'Europe commission: “About the EN Eurocodes”,'),
            ll(3,'https://eurocodes.jrc.ec.europa.eu/showpage.php?id=13 (Accessed 2022-03-20)',x0=96),
        ]
        self.assertTrue(web_resource_start(1, lines))
        self.assertTrue(web_resource_start(2, lines))

if __name__=='__main__': unittest.main()
