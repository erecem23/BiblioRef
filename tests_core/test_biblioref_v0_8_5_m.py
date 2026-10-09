import unittest
from biblioref.adaptive.continuity import reference_with_access_metadata_start, embedded_access_metadata_continuation
from biblioref.grammar.continuation_roles import classify_continuation_role
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

def ll(i,t): return LayoutLine(page=1,page_height=800,text=t,x0=72,y0=70+i*14,x1=520,y1=80+i*14,median_font_size=11,fragment_count=1)
def zone(lines):
 st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
 return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)
def candidate(lines,i): return next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==i)

class TestM(unittest.TestCase):
 def test_version(self):
  self.assertEqual(SOFTWARE_VERSION,'0.9.10-rc2'); self.assertEqual(ADAPTIVE_ANALYSIS_VERSION,'0.8.10-shadow23')
 def test_anon_year_same_line_access_is_new_reference(self):
  lines=[ll(0,'Previous, A. 2003. Previous.'),ll(1,'Anon. 2004. Safety and Swiss cheese. [Online] Available from:'),ll(2,'https://example.org/safety'),ll(3,'Andersen, B. 2005. Next.')]
  self.assertTrue(reference_with_access_metadata_start(1,lines)); self.assertFalse(embedded_access_metadata_continuation(1,lines))
  r=classify_continuation_role(1,lines); self.assertTrue(r['start_protected']); self.assertEqual(r['start_kind'],'reference_with_access_metadata'); self.assertTrue(candidate(lines,1)['active_shadow_boundary'])
 def test_person_undated_same_line_access_is_new_reference(self):
  lines=[ll(0,'Ammerman, P. 2001. Previous.'),ll(1,'Bacal, R. n.d. Diagnosing performance problems. [Online] Available from:'),ll(2,'https://example.org/performance'),ll(3,'Baker, C. 2004. Next.')]
  self.assertTrue(reference_with_access_metadata_start(1,lines)); self.assertTrue(candidate(lines,1)['active_shadow_boundary'])
 def test_institution_undated_same_line_access_is_new_reference(self):
  lines=[ll(0,'Previous, P. 2010. Previous.'),ll(1,'CHI Publishers. n.d. Introduction to quality. [Online] Available from:'),ll(2,'https://example.org/quality'),ll(3,'Council, D. 2011. Next.')]
  self.assertTrue(reference_with_access_metadata_start(1,lines)); self.assertTrue(candidate(lines,1)['active_shadow_boundary'])
 def test_embedded_journal_metadata_stays_continuation(self):
  lines=[ll(0,'Author, A. (2020). Article title. Journal of Testing,'),ll(1,'Researcher, 11(1):46-55. [Online] Available from:'),ll(2,'https://example.org/article'),ll(3,'Next, B. (2021). Next.')]
  self.assertFalse(reference_with_access_metadata_start(1,lines)); self.assertTrue(embedded_access_metadata_continuation(1,lines)); self.assertFalse(candidate(lines,1)['active_shadow_boundary'])
 def test_page_range_access_stays_continuation(self):
  lines=[ll(0,'Author, A. (2020). Article. Journal, 11(1),'),ll(1,'982-1003. [Online] Available from: https://example.org/article'),ll(2,'Next, B. (2021). Next.')]
  self.assertFalse(reference_with_access_metadata_start(1,lines)); self.assertTrue(embedded_access_metadata_continuation(1,lines)); self.assertFalse(candidate(lines,1)['active_shadow_boundary'])
 def test_existing_person_author_with_retrieved_is_protected(self):
  lines=[ll(0,'Previous, P. (2018). Previous.'),ll(1,'Breinlinger, T. (n.d.). Resource title. Retrieved from https://example.org/resource'),ll(2,'Next, N. (2020). Next.')]
  self.assertTrue(reference_with_access_metadata_start(1,lines)); self.assertTrue(candidate(lines,1)['active_shadow_boundary'])
 def test_access_words_without_link_are_not_enough(self):
  lines=[ll(0,'Previous, P. 2001. Previous.'),ll(1,'Anon. 2004. Safety and Swiss cheese. Available from memory.'),ll(2,'Next, N. 2005. Next.')]
  self.assertFalse(reference_with_access_metadata_start(1,lines))

if __name__=='__main__': unittest.main()
