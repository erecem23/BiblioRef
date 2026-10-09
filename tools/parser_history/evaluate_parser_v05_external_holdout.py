import csv, json, re, unicodedata, difflib, hashlib
from collections import defaultdict
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from biblioref.parsing.v04 import parse_reference as parse_v04
from biblioref.parsing.v05 import parse_reference as parse_v05
ROOT = Path(__file__).resolve().parents[2]
GOLD=ROOT/'parser_baseline/holdout_v05/PARSER_V05_ABNT_EXTERNAL_GOLD_FROZEN.csv'

def norm(x):
    s=str(x or '').casefold().replace('&',' and ')
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()
def fuzzy(a,b):
    a,b=norm(a),norm(b)
    return difflib.SequenceMatcher(None,a,b).ratio() if a and b else 0.0

def field_ok(p,r,field):
    if field=='author': return norm(p.get('author'))==norm(r['gold_author'])
    if field=='year': return str(p.get('year') or '')==r['gold_year']
    if field=='title_exact': return norm(p.get('title'))==norm(r['gold_title'])
    if field=='title_fuzzy90': return fuzzy(p.get('title'),r['gold_title'])>=.90
    if field=='journal_exact': return norm(p.get('journal'))==norm(r['gold_journal'])
    if field=='journal_fuzzy90': return fuzzy(p.get('journal'),r['gold_journal'])>=.90
    if field=='type': return str(p.get('publication_type') or '')==r['gold_publication_type']
    if field=='publisher': return norm(p.get('publisher'))==norm(r['gold_publisher'])
    if field=='publisher_observed': return norm(p.get('publisher_observed'))==norm(r['gold_publisher_observed'])
    if field=='doi': return norm(p.get('doi'))==norm(r['gold_doi'])
    raise KeyError(field)

def metrics(preds, rows):
    specs=[('author',lambda r:True),('year',lambda r:True),('title_exact',lambda r:True),('title_fuzzy90',lambda r:True),('type',lambda r:True),
           ('journal_exact',lambda r:bool(r['gold_journal'])),('journal_fuzzy90',lambda r:bool(r['gold_journal'])),
           ('publisher',lambda r:bool(r['gold_publisher'])),('publisher_observed',lambda r:bool(r['gold_publisher_observed'])),
           ('doi',lambda r:bool(r['gold_doi']))]
    out={}
    for field,eligible in specs:
        idx=[i for i,r in enumerate(rows) if eligible(r)]
        correct=sum(field_ok(preds[i],rows[i],field) for i in idx)
        out[field]={'n':len(idx),'correct':correct,'pct':round(100*correct/len(idx),2) if idx else None}
    jidx=[i for i,r in enumerate(rows) if r['gold_journal']]
    pidx=[i for i,r in enumerate(rows) if r['gold_publisher']]
    poidx=[i for i,r in enumerate(rows) if r['gold_publisher_observed']]
    out['journal_coverage']={'n':len(jidx),'covered':sum(bool(norm(preds[i].get('journal'))) for i in jidx),'pct':round(100*sum(bool(norm(preds[i].get('journal'))) for i in jidx)/len(jidx),2) if jidx else None}
    out['publisher_coverage']={'n':len(pidx),'covered':sum(bool(norm(preds[i].get('publisher'))) for i in pidx),'pct':round(100*sum(bool(norm(preds[i].get('publisher'))) for i in pidx)/len(pidx),2) if pidx else None}
    out['publisher_observed_coverage']={'n':len(poidx),'covered':sum(bool(norm(preds[i].get('publisher_observed'))) for i in poidx),'pct':round(100*sum(bool(norm(preds[i].get('publisher_observed'))) for i in poidx)/len(poidx),2) if poidx else None}
    out['abnt_route_count']=sum(p.get('parse_style')=='abnt_author_title_year_end' for p in preds)
    return out
rows=list(csv.DictReader(GOLD.open(encoding='utf-8-sig',newline='')))
p04=[parse_v04(r['raw_citation']) for r in rows]
p05=[parse_v05(r['raw_citation']) for r in rows]
fields=['author','year','title_fuzzy90','journal_fuzzy90','type','publisher','publisher_observed','doi']
paired={}
for f in fields:
    eligible=[]
    for i,r in enumerate(rows):
        if f.startswith('journal') and not r['gold_journal']: continue
        if f=='publisher' and not r['gold_publisher']: continue
        if f=='publisher_observed' and not r['gold_publisher_observed']: continue
        if f=='doi' and not r['gold_doi']: continue
        eligible.append(i)
    imp=reg=both=neither=0
    for i in eligible:
        a=field_ok(p04[i],rows[i],f); b=field_ok(p05[i],rows[i],f)
        imp += (not a and b); reg += (a and not b); both += (a and b); neither += (not a and not b)
    paired[f]={'n':len(eligible),'improved':imp,'regressed':reg,'both_right':both,'both_wrong':neither}
by={}
for tid in sorted(set(r['thesis_id'] for r in rows)):
    inds=[i for i,r in enumerate(rows) if r['thesis_id']==tid]
    subrows=[rows[i] for i in inds]
    by[tid]={'v04':metrics([p04[i] for i in inds],subrows),'v05':metrics([p05[i] for i in inds],subrows)}
source_hash=hashlib.sha256((ROOT/'biblioref/parsing/v05.py').read_bytes()).hexdigest()
gold_hash=hashlib.sha256(GOLD.read_bytes()).hexdigest()
out={'evaluation':'parser_v0.5_abnt_external_holdout','n':len(rows),'n_theses':len(by),'parser_v05_sha256':source_hash,'gold_sha256':gold_hash,'v04':metrics(p04,rows),'v05':metrics(p05,rows),'paired':paired,'by_thesis':by,'method_note':'Gold frozen before parser execution. Parser v0.5 source not modified after evaluation.'}
Path('PARSER_V0_5_ABNT_EXTERNAL_HOLDOUT_EVALUATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
# predictions
fieldnames=['thesis_id','raw_citation','gold_author','gold_year','gold_title','gold_publication_type','gold_journal','gold_publisher','gold_publisher_observed','v04_style','v05_style','v04_author','v05_author','v04_year','v05_year','v04_title','v05_title','v04_type','v05_type','v04_journal','v05_journal','v04_publisher','v05_publisher','v04_publisher_observed','v05_publisher_observed','v04_doi','v05_doi']
with open('PARSER_V0_5_ABNT_EXTERNAL_HOLDOUT_PREDICTIONS.csv','w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader()
    for r,a,b in zip(rows,p04,p05):
        w.writerow({**{k:r.get(k,'') for k in fieldnames if k in r},'v04_style':a.get('parse_style'),'v05_style':b.get('parse_style'),'v04_author':a.get('author'),'v05_author':b.get('author'),'v04_year':a.get('year'),'v05_year':b.get('year'),'v04_title':a.get('title'),'v05_title':b.get('title'),'v04_type':a.get('publication_type'),'v05_type':b.get('publication_type'),'v04_journal':a.get('journal'),'v05_journal':b.get('journal'),'v04_publisher':a.get('publisher'),'v05_publisher':b.get('publisher'),'v04_publisher_observed':a.get('publisher_observed'),'v05_publisher_observed':b.get('publisher_observed'),'v04_doi':a.get('doi'),'v05_doi':b.get('doi')})
print(json.dumps(out,ensure_ascii=False,indent=2))
