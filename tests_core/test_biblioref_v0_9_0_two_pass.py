import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf

from biblioref.adaptive.two_pass import (
    assess_zone_coverage,
    build_two_pass_shadow,
    cheap_page_profiles,
    propose_candidate_windows,
)
from biblioref.core.config import SOFTWARE_VERSION, ALGORITHM_VERSION, ADAPTIVE_ANALYSIS_VERSION, TWO_PASS_ANALYSIS_VERSION
from biblioref.pipeline import process_pdf


class TestV090TwoPassShadow(unittest.TestCase):
    def make_pdf(self, pages):
        tmp=tempfile.NamedTemporaryFile(suffix='.pdf', delete=False); tmp.close()
        doc=pymupdf.open()
        for lines in pages:
            page=doc.new_page()
            y=72
            for text in lines:
                page.insert_text((72,y), text, fontsize=10); y += 16
        doc.save(tmp.name); doc.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_version_is_shadow_experiment_over_effective_algorithm(self):
        self.assertEqual('0.9.10-rc2', SOFTWARE_VERSION)
        self.assertEqual('0.6.21', ALGORITHM_VERSION)
        self.assertEqual('0.8.10-shadow23', ADAPTIVE_ANALYSIS_VERSION)
        self.assertEqual('0.9.0-two-pass-shadow1', TWO_PASS_ANALYSIS_VERSION)

    def test_heading_supported_window(self):
        profiles=[
            {'page':1,'heading_hit':False,'evidence_lines':0,'evidence_density':0,'url_doi_lines':0,'char_count':500},
            {'page':2,'heading_hit':True,'evidence_lines':4,'evidence_density':.4,'url_doi_lines':0,'char_count':500},
            {'page':3,'heading_hit':False,'evidence_lines':5,'evidence_density':.5,'url_doi_lines':1,'char_count':500},
            {'page':4,'heading_hit':False,'evidence_lines':0,'evidence_density':0,'url_doi_lines':0,'char_count':10},
        ]
        out=propose_candidate_windows(profiles)
        self.assertEqual('heading_supported', out['confidence'])
        self.assertTrue(out['safe_to_narrow'])
        self.assertEqual(1, out['windows'][0]['start_page'])
        self.assertEqual(4, out['windows'][0]['end_page'])

    def test_density_only_never_safe_to_narrow(self):
        profiles=[]
        for i in range(1,6):
            profiles.append({'page':i,'heading_hit':False,'evidence_lines':5 if i in {3,4} else 0,'evidence_density':.5 if i in {3,4} else 0,'url_doi_lines':0,'char_count':500})
        out=propose_candidate_windows(profiles)
        self.assertEqual('density_only', out['confidence'])
        self.assertFalse(out['safe_to_narrow'])

    def test_coverage_requires_full_containment(self):
        report={'zones':[{'start_page':10,'end_page':12},{'start_page':20,'end_page':22}]}
        out=assess_zone_coverage([{'start_page':9,'end_page':12},{'start_page':21,'end_page':23}], report)
        self.assertEqual(1.0, out['zone_overlap_recall'])
        self.assertEqual(.5, out['zone_full_coverage_recall'])

    def test_cheap_pass_reads_plain_text(self):
        pdf=self.make_pdf([['Introduccion'],['Bibliografia','Smith, J. (2020). Title. Journal.','Doe, A. (2019). Book. Publisher.','Roe, B. (2018). Work. Press.','Moe, C. (2017). Work. Press.']])
        profiles,_=cheap_page_profiles(pdf)
        self.assertFalse(profiles[0]['heading_hit'])
        self.assertTrue(profiles[1]['heading_hit'])
        self.assertGreaterEqual(profiles[1]['evidence_lines'],4)

    def test_two_pass_field_is_opt_in(self):
        fixture=Path(__file__).parent/'fixtures'/'document_grammar_stress.pdf'
        base=process_pdf(fixture, adaptive_mode='off')
        self.assertNotIn('two_pass_shadow', base)
        shadow=process_pdf(fixture, adaptive_mode='off', two_pass_shadow=True)
        self.assertIn('two_pass_shadow', shadow)
        self.assertTrue(shadow['two_pass_shadow']['diagnostic_only'])
        self.assertFalse(shadow['two_pass_shadow']['auto_apply'])

    def test_effective_output_does_not_depend_on_two_pass(self):
        fixture=Path(__file__).parent/'fixtures'/'document_grammar_stress.pdf'
        a=process_pdf(fixture, adaptive_mode='shadow', two_pass_shadow=False)
        b=process_pdf(fixture, adaptive_mode='shadow', two_pass_shadow=True)
        b=dict(b); b.pop('two_pass_shadow',None)
        self.assertEqual(a,b)

    def test_two_pass_failure_cannot_replace_effective_output(self):
        fixture=Path(__file__).parent/'fixtures'/'document_grammar_stress.pdf'
        with patch('biblioref.pipeline.build_two_pass_shadow', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                process_pdf(fixture, adaptive_mode='off', two_pass_shadow=True)
        # Normal validated path remains independently callable.
        out=process_pdf(fixture, adaptive_mode='off', two_pass_shadow=False)
        self.assertIn('records', out)


if __name__=='__main__': unittest.main()
