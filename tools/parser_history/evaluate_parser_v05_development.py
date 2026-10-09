import csv, difflib, json, re, unicodedata
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from biblioref.parsing.v04 import parse_reference as p04
from biblioref.parsing.v05 import parse_reference as p05

SRC='PARSER_V0_2_DIFFERENTIAL_29470.csv'

def norm(x):
    s=str(x or '').casefold().replace('&',' and ')
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()
def fuzzy(a,b):
    a,b=norm(a),norm(b)
    return difflib.SequenceMatcher(None,a,b).ratio() if a and b else 0.0
def high(x):
    return {'articulo_revista':'articulo','articulo_revista_probable':'articulo','libro':'monografia','capitulo_libro':'monografia','capitulo':'monografia','material_web':'web','recurso_web':'web','tesis':'tesis','conference_paper':'conferencia','conferencia':'conferencia','documento_guia_manual':'otro','informe_documento':'otro','no_referencia_fragmento':'otro','documento_legal':'otro','documento_institucional':'otro','sin_clasificar':'otro','otro':'otro'}.get(str(x or ''),'otro')
rows=list(csv.DictReader(open(SRC,encoding='utf-8-sig')))
old=[]; new=[]
for r in rows:
    old.append(p04(r['raw_citation'])); new.append(p05(r['raw_citation']))

def metrics(pred):
    n=len(rows)
    jidx=[i for i,r in enumerate(rows) if norm(r['target_journal'])]
    pidx=[i for i,r in enumerate(rows) if norm(r['target_publisher_v2'])]
    return {
      'n':n,
      'journal_gold':len(jidx),
      'journal_hit':sum(fuzzy(pred[i].get('journal'),rows[i]['target_journal'])>=.9 for i in jidx),
      'journal_cov':sum(bool(norm(pred[i].get('journal'))) for i in jidx),
      'journal_fuzzy90':sum(fuzzy(pred[i].get('journal'),rows[i]['target_journal'])>=.9 for i in jidx)/len(jidx),
      'journal_coverage':sum(bool(norm(pred[i].get('journal'))) for i in jidx)/len(jidx),
      'type_hit':sum(high(pred[i].get('publication_type'))==high(rows[i]['target_type_v2']) for i in range(n)),
      'type_high_accuracy':sum(high(pred[i].get('publication_type'))==high(rows[i]['target_type_v2']) for i in range(n))/n,
      'pub_gold':len(pidx),
      'pub_hit':sum(norm(pred[i].get('publisher'))==norm(rows[i]['target_publisher_v2']) for i in pidx),
      'pub_cov':sum(bool(norm(pred[i].get('publisher'))) for i in pidx),
      'publisher_exact':sum(norm(pred[i].get('publisher'))==norm(rows[i]['target_publisher_v2']) for i in pidx)/len(pidx),
      'publisher_coverage':sum(bool(norm(pred[i].get('publisher'))) for i in pidx)/len(pidx),
    }
mo,mn=metrics(old),metrics(new)
fields=['author','authors','year','publication_type','title','journal','publisher','publisher_observed','doi']
changed=[]
for i,(a,b) in enumerate(zip(old,new)):
    ch=[f for f in fields if (a.get(f) or '')!=(b.get(f) or '')]
    if ch:
        changed.append({'i':i,'ref_uid':rows[i]['ref_uid'],'raw_citation':rows[i]['raw_citation'],'changed_fields':'|'.join(ch),'old_style':a.get('parse_style'),'new_style':b.get('parse_style'),'old_type':a.get('publication_type'),'new_type':b.get('publication_type'),'target_type':rows[i]['target_type_v2'],'old_title':a.get('title'),'new_title':b.get('title'),'old_journal':a.get('journal'),'new_journal':b.get('journal'),'target_journal':rows[i]['target_journal'],'old_publisher':a.get('publisher'),'new_publisher':b.get('publisher'),'target_publisher':rows[i]['target_publisher_v2']})
styles=Counter(x.get('parse_style') for x in new)
# paired target correctness changes for route-affected rows only
paired={}
for field in ['journal','publisher','type']:
    imp=reg=bothright=bothwrong=0
    for i in range(len(rows)):
        if field=='journal':
            if not norm(rows[i]['target_journal']): continue
            oa=fuzzy(old[i].get('journal'),rows[i]['target_journal'])>=.9; nb=fuzzy(new[i].get('journal'),rows[i]['target_journal'])>=.9
        elif field=='publisher':
            if not norm(rows[i]['target_publisher_v2']): continue
            oa=norm(old[i].get('publisher'))==norm(rows[i]['target_publisher_v2']); nb=norm(new[i].get('publisher'))==norm(rows[i]['target_publisher_v2'])
        else:
            oa=high(old[i].get('publication_type'))==high(rows[i]['target_type_v2']); nb=high(new[i].get('publication_type'))==high(rows[i]['target_type_v2'])
        imp+=not oa and nb; reg+=oa and not nb; bothright+=oa and nb; bothwrong+=not oa and not nb
    paired[field]={'improved':imp,'regressed':reg,'both_right':bothright,'both_wrong':bothwrong}
out={'baseline_v04':mo,'candidate_v05':mn,'styles':styles,'changed_rows':len(changed),'paired':paired}
open('PARSER_V0_5_DEVELOPMENT_EVALUATION_PRE_HOLDOUT.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:dict(x)))
with open('PARSER_V0_5_DEVELOPMENT_DIFFERENTIAL.csv','w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(changed[0]) if changed else ['i']); w.writeheader(); w.writerows(changed)
print(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:dict(x)))
print('\nCHANGED EXAMPLES')
for r in changed[:30]: print(r['ref_uid'],r['changed_fields'],r['raw_citation'][:220])
