import unittest
from biblioref.grammar.continuation_roles import classify_continuation_role
from biblioref.adaptive.scoring import collect_boundary_candidates
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import LayoutLine, AdaptiveLayoutZone, diagnose_adaptive_style, diagnose_adaptive_layout

def ll(i,t): return LayoutLine(page=1,page_height=800,text=t,x0=72,y0=70+i*14,x1=520,y1=80+i*14,median_font_size=11,fragment_count=1)
def zone(lines):
 st=diagnose_adaptive_style([x.text for x in lines]); la=diagnose_adaptive_layout(lines,st)
 return AdaptiveLayoutZone(heading=ll(0,'References'),lines=lines,start_page=1,end_page=1,style=st,layout=la,termination_reason='test',confidence_score=0,confidence_label='test',confidence_reasons=[],start_confidence_score=0,start_confidence_label='test',start_confidence_reasons=[],end_confidence_score=0,end_confidence_label='test',end_confidence_reasons=[],zone_completeness='test',adaptive_soft_limit_pages=0,zone_span_pages=1,adaptive_limit_exceeded=False)

def active(lines,i):
 return next(c for c in collect_boundary_candidates(zone(lines)) if c['line_index']==i)['active_shadow_boundary']

class TestL(unittest.TestCase):
 def test_version(self):
  self.assertEqual(SOFTWARE_VERSION,'0.9.10-rc2'); self.assertEqual(ADAPTIVE_ANALYSIS_VERSION,'0.8.10-shadow23')
 def test_location_publisher_is_continuation(self):
  lines=[ll(0,'ALGARTE, Waldir Fernandes. O movimento da qualidade no Brasil. 1. ed. p, 11.'),ll(1,'São Paulo: Edelbra, 2011.'),ll(2,'ATKINSON, Anthony. Contabilidade gerencial. São Paulo, 2015.')]
  r=classify_continuation_role(1,lines); self.assertIn('location_publisher',r['roles']); self.assertFalse(active(lines,1))
 def test_thesis_institution_is_continuation(self):
  lines=[ll(0,'COSTA, N. Eliminação de desperdícios. Monografia.'),ll(1,'Universidade Tecnológica Federal do Paraná. Ponta Grossa, PR, 2017.'),ll(2,'DALLA, W. Produção enxuta. 2006.')]
  self.assertIn('thesis_institution',classify_continuation_role(1,lines)['roles']); self.assertFalse(active(lines,1))
 def test_journal_metadata_doi_is_continuation(self):
  lines=[ll(0,'Castañeda Rentería, L. I. (2019). Mujeres profesionistas sin hijos. Desacatos. Revista De Ciencias'),ll(1,'Sociales, (60), 134–149. https://doi.org/10.29340/60.2095'),ll(2,'Castellá, G. (2007). Next.')]
  self.assertTrue(classify_continuation_role(1,lines)['is_continuation']); self.assertFalse(active(lines,1))
 def test_wrapped_date_after_authors_is_continuation(self):
  lines=[ll(0,'Granero Gallegos A., Gómez López M., Abraldes Valeiras J.A. y Rodríguez-Suárez N.'),ll(1,'(2011). Motivos de práctica en el ámbito de la actividad física no competitiva. Espiral.'),ll(2,'Revista Digital del Centro del Profesorado Cuevas-Olula (Almería). Facultad de Ciencias')]
  self.assertIn('wrapped_author_date',classify_continuation_role(1,lines)['roles']); self.assertFalse(active(lines,1))
 def test_legal_start_is_protected(self):
  lines=[ll(0,'Acordada N° 12.124. Salta, Argentina. 2016.'),ll(1,'Acordada N° 12.704 (2018). Protocolo de organización y actuación.'),ll(2,'Acordada N° 12.705 (2019). Next.')]
  r=classify_continuation_role(1,lines); self.assertTrue(r['start_protected']); self.assertTrue(active(lines,1))
 def test_institution_available_start_is_protected(self):
  lines=[ll(0,'Babbie, E. 2018. Fundamentals of social research.'),ll(1,'Berkeley Library, University of California. 2021. Available:'),ll(2,'https://www.lib.berkeley.edu/ [2021, November 16].')]
  r=classify_continuation_role(1,lines); self.assertTrue(r['start_protected']); self.assertTrue(active(lines,1))
 def test_document_title_with_date_next_line_is_protected(self):
  lines=[ll(0,'Araoz Díaz, C. (s/f). Previous.'),ll(1,'Código de ética de la Federación de Psicólogos de la República Argentina (Fe.P.R.A).'),ll(2,'Modificado por la Asamblea Extraordinaria el 30 de noviembre de 2013.'),ll(3,'Código Penal de la Nación Argentina. Reformado el 17 de junio de 2018.')]
  r=classify_continuation_role(1,lines); self.assertTrue(r['start_protected']); self.assertTrue(active(lines,1)); self.assertFalse(active(lines,2))
 def test_genuine_person_author_not_continuation(self):
  lines=[ll(0,'Previous, P. (2018). Previous.'),ll(1,'Brown, A. (2020). Journal article. Journal, 2, 10-20.'),ll(2,'Next, B. (2021). Next.')]
  self.assertFalse(classify_continuation_role(1,lines)['is_continuation']); self.assertTrue(active(lines,1))

if __name__=='__main__': unittest.main()
