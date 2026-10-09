import csv, json, re, unicodedata, difflib, hashlib
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from biblioref.parsing.v05 import parse_reference as parse_v05
from biblioref.parsing.v06 import parse_reference as parse_v06
ROOT = Path(__file__).resolve().parents[2]
GOLD=ROOT/'parser_baseline/holdout_v06/PARSER_V06_ABNT_EXTERNAL_GOLD_FROZEN.csv'

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
    for name,key in [('journal_coverage','gold_journal'),('publisher_coverage','gold_publisher'),('publisher_observed_coverage','gold_publisher_observed')]:
        idx=[i for i,r in enumerate(rows) if r[key]]
        field={'journal_coverage':'journal','publisher_coverage':'publisher','publisher_observed_coverage':'publisher_observed'}[name]
        covered=sum(bool(norm(preds[i].get(field))) for i in idx)
        out[name]={'n':len(idx),'covered':covered,'pct':round(100*covered/len(idx),2) if idx else None}
    out['abnt_route_count']=sum(str(p.get('parse_style') or '').startswith('abnt_') for p in preds)
    return out

rows=list(csv.DictReader(GOLD.open(encoding='utf-8-sig',newline='')))
p05=[parse_v05(r['raw_citation']) for r in rows]
p06=[parse_v06(r['raw_citation']) for r in rows]
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
        a=field_ok(p05[i],rows[i],f); b=field_ok(p06[i],rows[i],f)
        imp += (not a and b); reg += (a and not b); both += (a and b); neither += (not a and not b)
    paired[f]={'n':len(eligible),'improved':imp,'regressed':reg,'both_right':both,'both_wrong':neither}
by={}
for tid in sorted(set(r['thesis_id'] for r in rows)):
    inds=[i for i,r in enumerate(rows) if r['thesis_id']==tid]
    subrows=[rows[i] for i in inds]
    by[tid]={'v05':metrics([p05[i] for i in inds],subrows),'v06':metrics([p06[i] for i in inds],subrows)}
source_hash=hashlib.sha256((ROOT/'biblioref/parsing/v06.py').read_bytes()).hexdigest()
gold_hash=hashlib.sha256(GOLD.read_bytes()).hexdigest()
out={'evaluation':'parser_v0.6_abnt_external_holdout','n':len(rows),'n_theses':len(by),'parser_v06_sha256':source_hash,'gold_sha256':gold_hash,'v05':metrics(p05,rows),'v06':metrics(p06,rows),'paired':paired,'by_thesis':by,'method_note':'Gold frozen and hashed before importing/running parser v0.6 on these 30 references. Parser v0.6 source must remain unchanged after evaluation.'}
(ROOT / "reports" / "parser" / "PARSER_V0_6_ABNT_EXTERNAL_HOLDOUT_EVALUATION.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
fieldnames=['thesis_id','institution','raw_citation','gold_author','gold_year','gold_title','gold_publication_type','gold_journal','gold_publisher','gold_publisher_observed','v05_style','v06_style','v05_author','v06_author','v05_year','v06_year','v05_title','v06_title','v05_type','v06_type','v05_journal','v06_journal','v05_publisher','v06_publisher','v05_publisher_observed','v06_publisher_observed','v05_doi','v06_doi']
with (ROOT/'PARSER_V0_6_ABNT_EXTERNAL_HOLDOUT_PREDICTIONS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader()
    for r,a,b in zip(rows,p05,p06):
        w.writerow({**{k:r.get(k,'') for k in fieldnames if k in r},'v05_style':a.get('parse_style'),'v06_style':b.get('parse_style'),'v05_author':a.get('author'),'v06_author':b.get('author'),'v05_year':a.get('year'),'v06_year':b.get('year'),'v05_title':a.get('title'),'v06_title':b.get('title'),'v05_type':a.get('publication_type'),'v06_type':b.get('publication_type'),'v05_journal':a.get('journal'),'v06_journal':b.get('journal'),'v05_publisher':a.get('publisher'),'v06_publisher':b.get('publisher'),'v05_publisher_observed':a.get('publisher_observed'),'v06_publisher_observed':b.get('publisher_observed'),'v05_doi':a.get('doi'),'v06_doi':b.get('doi')})
print(json.dumps(out,ensure_ascii=False,indent=2))
