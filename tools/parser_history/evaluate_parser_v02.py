import csv, difflib, json, math, re, sys, time, unicodedata
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd

from biblioref.parsing import parse_reference as parse_v02
from biblioref.parsing.legacy import parse_reference as parse_v01

ROOT = Path(__file__).resolve().parents[2]
SOURCE=Path('/mnt/data/handoff_full/02_datos_fuente/dataset_referencias_corpus_analitico_29470_editoriales_v2.csv')
SEED=ROOT/'parser_baseline/gold_seed_120_parser_legacy_v0_1.csv'

def norm(x):
    if x is None or (isinstance(x,float) and math.isnan(x)): return ''
    s=str(x).casefold().replace('&',' and ')
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def fuzzy(a,b):
    a,b=norm(a),norm(b)
    return difflib.SequenceMatcher(None,a,b).ratio() if a and b else 0.0

def high_type(x):
    return {
        'articulo_revista':'articulo','articulo_revista_probable':'articulo',
        'libro':'monografia','capitulo_libro':'monografia','capitulo':'monografia',
        'material_web':'web','recurso_web':'web','tesis':'tesis',
        'conference_paper':'conferencia','conferencia':'conferencia',
        'documento_guia_manual':'otro','informe_documento':'otro','no_referencia_fragmento':'otro',
        'documento_legal':'otro','documento_institucional':'otro','sin_clasificar':'otro','otro':'otro'
    }.get(str(x or ''),'otro')

def eval_full():
    df=pd.read_csv(SOURCE,low_memory=False)
    old=[]; new=[]
    t=time.time()
    for raw in df.raw_citation.fillna(''):
        old.append(parse_v01(raw)); new.append(parse_v02(raw))
    elapsed=time.time()-t
    n=len(df)
    inv={k:sum((old[i].get(k) or '')==(new[i].get(k) or '') for i in range(n)) for k in ['year','title','doi']}
    # author
    a1=sum(norm(p['author'])==norm(g) and bool(norm(g)) for p,g in zip(old,df.first_author_canonical))
    a2=sum(norm(p['author'])==norm(g) and bool(norm(g)) for p,g in zip(new,df.first_author_canonical))
    # journal gold rows
    jm=df.journal_canonical.notna(); jdf=df[jm]; io=list(jdf.index)
    def jmetrics(preds):
        vals=[preds[i].get('journal') for i in io]
        coverage=sum(bool(norm(x)) for x in vals)/len(vals)
        exact=sum(norm(p)==norm(g) and bool(norm(g)) for p,g in zip(vals,jdf.journal_canonical))/len(vals)
        fuzz=sum(fuzzy(p,g)>=.9 for p,g in zip(vals,jdf.journal_canonical))/len(vals)
        return {'n_gold':len(vals),'coverage_pct':round(100*coverage,2),'exact_pct':round(100*exact,2),'fuzzy90_pct':round(100*fuzz,2)}
    # type
    t1=sum(high_type(p['publication_type'])==high_type(g) for p,g in zip(old,df.document_type_v2))/n
    t2=sum(high_type(p['publication_type'])==high_type(g) for p,g in zip(new,df.document_type_v2))/n
    d2=sum(p['publication_type']==g for p,g in zip(new,df.document_type_v2))/n
    # publisher target = accepted v2 publisher rows. v0.1 source can contain publisher; v0.2 isolates.
    pm=df.publisher_name_v2.notna(); pdf=df[pm]; ip=list(pdf.index)
    old_cont=sum(norm(g) in norm(old[i].get('source_publisher')) for i,g in zip(ip,pdf.publisher_name_v2))/len(ip)
    new_exact=sum(norm(new[i].get('publisher'))==norm(g) for i,g in zip(ip,pdf.publisher_name_v2))/len(ip)
    new_cov=sum(bool(norm(new[i].get('publisher'))) for i in ip)/len(ip)
    # publisher overall on v2 monographic rows
    mon=df.document_type_v2.isin(['libro','capitulo_libro']); im=list(df[mon].index)
    new_pub_all=sum(bool(norm(new[i].get('publisher'))) for i in im)/len(im)
    return {
        'dataset':'development_29470_v2','n':n,'runtime_seconds':round(elapsed,3),
        'invariants_v01_to_v02':{k:{'identical':v,'n':n,'pct':round(100*v/n,3)} for k,v in inv.items()},
        'author_strict_norm_pct':{'v0.1':round(100*a1/n,2),'v0.2':round(100*a2/n,2),'note':'development corpus canonical author is known to contain normalization noise'},
        'journal':{'v0.1':jmetrics(old),'v0.2':jmetrics(new)},
        'type_high_accuracy_pct':{'v0.1':round(100*t1,2),'v0.2':round(100*t2,2)},
        'type_detailed_v02_accuracy_pct':round(100*d2,2),
        'publisher':{
            'accepted_v2_target_n':len(pdf),
            'v0.1_gold_name_contained_in_source_pct':round(100*old_cont,2),
            'v0.2_isolated_exact_pct':round(100*new_exact,2),
            'v0.2_coverage_on_target_pct':round(100*new_cov,2),
            'v0.2_coverage_all_v2_monographic_pct':round(100*new_pub_all,2),
            'warning':'target is development pipeline v2, not external gold'
        }
    }, old, new, df

def eval_seed():
    df=pd.read_csv(SEED)
    old=[parse_v01(x) for x in df.raw_citation.fillna('')]
    new=[parse_v02(x) for x in df.raw_citation.fillna('')]
    n=len(df)
    out={'dataset':'seed_120_unconfirmed','n':n,'warning':'confirmado_humano is not validated; development only'}
    out['invariants']={k:sum((a.get(k) or '')==(b.get(k) or '') for a,b in zip(old,new)) for k in ['year','title','doi']}
    out['author_strict_norm_pct']={
        'v0.1':round(100*sum(norm(p['author'])==norm(g) and bool(norm(g)) for p,g in zip(old,df.gold_author))/n,2),
        'v0.2':round(100*sum(norm(p['author'])==norm(g) and bool(norm(g)) for p,g in zip(new,df.gold_author))/n,2),
    }
    jm=df.gold_journal.notna(); idx=list(df[jm].index); g=df.loc[jm,'gold_journal']
    def jmtr(pred):
        v=[pred[i]['journal'] for i in idx]
        return {'coverage_pct':round(100*sum(bool(norm(x)) for x in v)/len(v),2),'fuzzy90_pct':round(100*sum(fuzzy(p,q)>=.9 for p,q in zip(v,g))/len(v),2)} if len(v) else {}
    out['journal']={'v0.1':jmtr(old),'v0.2':jmtr(new),'n_gold':len(idx)}
    out['type_high_accuracy_pct']={
        'v0.1':round(100*sum(high_type(p['publication_type'])==str(g) for p,g in zip(old,df.gold_type_high))/n,2),
        'v0.2':round(100*sum(high_type(p['publication_type'])==str(g) for p,g in zip(new,df.gold_type_high))/n,2),
    }
    pm=df.gold_publisher.notna(); idx=list(df[pm].index); gg=df.loc[pm,'gold_publisher']
    if len(idx):
        out['publisher']={
            'n_gold':len(idx),
            'v0.1_gold_contained_pct':round(100*sum(norm(g) in norm(old[i].get('source_publisher')) for i,g in zip(idx,gg))/len(idx),2),
            'v0.2_isolated_exact_pct':round(100*sum(norm(new[i].get('publisher'))==norm(g) for i,g in zip(idx,gg))/len(idx),2),
            'v0.2_coverage_pct':round(100*sum(bool(norm(new[i].get('publisher'))) for i in idx)/len(idx),2),
        }
    return out

if __name__=='__main__':
    full, old, new, df=eval_full(); seed=eval_seed()
    report={'parser_version':'biblioref-parser-v0.2','status':'development_candidate','full_development':full,'seed_development':seed}
    out=ROOT / "reports" / "parser" / "PARSER_V0_2_EVALUATION.json"; out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # differential rows focused on changed fields
    rows=[]
    for i,(o,n) in enumerate(zip(old,new)):
        changed=[k for k in ['author','authors','publication_type','journal','publisher'] if (o.get(k) or '')!=(n.get(k) or '')]
        if changed:
            rows.append({'ref_uid':df.iloc[i].ref_uid,'raw_citation':df.iloc[i].raw_citation,'changed_fields':'|'.join(changed),
                         'v01_author':o.get('author'),'v02_author':n.get('author'),'gold_author':df.iloc[i].first_author_canonical,
                         'v01_type':o.get('publication_type'),'v02_type':n.get('publication_type'),'target_type_v2':df.iloc[i].document_type_v2,
                         'v01_journal':o.get('journal'),'v02_journal':n.get('journal'),'target_journal':df.iloc[i].journal_canonical,
                         'v01_source_publisher':o.get('source_publisher'),'v02_publisher':n.get('publisher'),'target_publisher_v2':df.iloc[i].publisher_name_v2})
    pd.DataFrame(rows).to_csv(ROOT/'PARSER_V0_2_DIFFERENTIAL_29470.csv',index=False)
    print(json.dumps(report,ensure_ascii=False,indent=2))
