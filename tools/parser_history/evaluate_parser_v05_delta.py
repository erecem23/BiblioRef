import csv,difflib,json,re,unicodedata
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from biblioref.parsing.v04 import parse_reference as p04
from biblioref.parsing.v05 import parse_reference as p05, _parse_abnt

def norm(x):
 s=str(x or '').casefold().replace('&',' and '); s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c)); s=re.sub(r'[^a-z0-9]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def fuzzy(a,b):
 a,b=norm(a),norm(b); return difflib.SequenceMatcher(None,a,b).ratio() if a and b else 0
def high(x):
 return {'articulo_revista':'articulo','articulo_revista_probable':'articulo','libro':'monografia','capitulo_libro':'monografia','capitulo':'monografia','material_web':'web','recurso_web':'web','tesis':'tesis','conference_paper':'conferencia','conferencia':'conferencia','documento_guia_manual':'otro','informe_documento':'otro','no_referencia_fragmento':'otro','documento_legal':'otro','documento_institucional':'otro','sin_clasificar':'otro','otro':'otro'}.get(str(x or ''),'otro')
rows=list(csv.DictReader(open('PARSER_V0_2_DIFFERENTIAL_29470.csv',encoding='utf-8-sig')))
affected=[]
for i,r in enumerate(rows):
 if _parse_abnt(re.sub(r'\s+',' ',r['raw_citation']).strip()): affected.append(i)
print('affected',len(affected))
base=json.load(open('PARSER_V0_4_DEVELOPMENT_EVALUATION.json'))
new=dict(base)
deltas={'journal_hit':0,'journal_cov':0,'type_hit':0,'pub_hit':0,'pub_cov':0}
changed=[]
paired={'journal':{'improved':0,'regressed':0},'publisher':{'improved':0,'regressed':0},'type':{'improved':0,'regressed':0}}
for k,i in enumerate(affected):
 r=rows[i]; a=p04(r['raw_citation']); b=p05(r['raw_citation'])
 targetj=r['target_journal']; targetp=r['target_publisher_v2']; targett=r['target_type_v2']
 if norm(targetj):
  oa=fuzzy(a.get('journal'),targetj)>=.9; nb=fuzzy(b.get('journal'),targetj)>=.9
  deltas['journal_hit'] += int(nb)-int(oa); deltas['journal_cov'] += int(bool(norm(b.get('journal'))))-int(bool(norm(a.get('journal'))))
  paired['journal']['improved'] += int((not oa) and nb); paired['journal']['regressed'] += int(oa and not nb)
 oa=high(a.get('publication_type'))==high(targett); nb=high(b.get('publication_type'))==high(targett)
 deltas['type_hit'] += int(nb)-int(oa); paired['type']['improved'] += int((not oa) and nb); paired['type']['regressed'] += int(oa and not nb)
 if norm(targetp):
  oa=norm(a.get('publisher'))==norm(targetp); nb=norm(b.get('publisher'))==norm(targetp)
  deltas['pub_hit'] += int(nb)-int(oa); deltas['pub_cov'] += int(bool(norm(b.get('publisher'))))-int(bool(norm(a.get('publisher'))))
  paired['publisher']['improved'] += int((not oa) and nb); paired['publisher']['regressed'] += int(oa and not nb)
 ch=[f for f in ['author','authors','year','publication_type','title','journal','publisher','publisher_observed','doi'] if (a.get(f) or '')!=(b.get(f) or '')]
 changed.append({'ref_uid':r['ref_uid'],'raw_citation':r['raw_citation'],'changed_fields':'|'.join(ch),'target_type':targett,'old_type':a.get('publication_type'),'new_type':b.get('publication_type'),'target_journal':targetj,'old_journal':a.get('journal'),'new_journal':b.get('journal'),'target_publisher':targetp,'old_publisher':a.get('publisher'),'new_publisher':b.get('publisher')})
for key in ['journal_hit','journal_cov','type_hit','pub_hit','pub_cov']:
 new[key]=base[key]+deltas[key]
new['journal_fuzzy90']=new['journal_hit']/base['journal_gold']; new['journal_coverage']=new['journal_cov']/base['journal_gold']; new['type_high_accuracy']=new['type_hit']/base['type_target']; new['publisher_exact']=new['pub_hit']/base['pub_gold']; new['publisher_coverage']=new['pub_cov']/base['pub_gold']
out={'affected_rows':len(affected),'baseline_v04':base,'candidate_v05':new,'deltas':deltas,'paired_on_affected_targets':paired}
open('PARSER_V0_5_DEVELOPMENT_EVALUATION_PRE_HOLDOUT.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2))
fieldnames=['ref_uid','raw_citation','changed_fields','target_type','old_type','new_type','target_journal','old_journal','new_journal','target_publisher','old_publisher','new_publisher']
with open('PARSER_V0_5_DEVELOPMENT_DIFFERENTIAL.csv','w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(changed)
print(json.dumps(out,ensure_ascii=False,indent=2))
for r in changed[:80]: print(r['ref_uid'],r['changed_fields'],r['old_type'],'=>',r['new_type'],'|',r['raw_citation'][:180])
