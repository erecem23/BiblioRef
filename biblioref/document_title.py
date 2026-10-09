from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from difflib import SequenceMatcher
import math, re
from typing import Any, Iterable
from biblioref.ingestion.backend_context import pymupdf as fitz

TITLE_READING_REVISION='document-title-v2.1'

INST_TERMS=(
    'universidad','universidade','university','université','universite','università','universita',
    'facultad','faculdade','faculty','faculté','faculte','departamento','department','instituto','institute','institut',
    'escuela','school','escola','secretaría','secretaria','graduate school','college','research group',
)
ROLE_TERMS=(
    'autor:','autora:','author:','presentada por','presentado por','presented by','submitted by','by ',
    'director:','directora:','codirector','co-director','supervisor','advisor','orientador','orientadora','tutor:',
    'tesista:','candidate:','candidato:','candidata:','autora aspirante','autor aspirante',
)
DEGREE_TERMS=(
    'tesis doctoral','tesis de doctorado','doctoral thesis','doctoral dissertation','phd thesis','ph.d. thesis',
    'tese de doutorado','tesi di dottorato','doctor of philosophy','doctorado','doutorado','dottorato',
    'master thesis','master of','maestría','maestria','mestrado','licenciatura','magister','máster','master',
    'para obtener el título','para obtener el titulo','para optar al título','para optar al titulo',
    'para optar por el título','para optar por el titulo','para obtener el grado','para optar al grado',
    'thesis submitted','thesis by publication','submitted in fulfilment','submitted in partial fulfilment',
    'tesis para optar','requirements for the degree','degree of doctor',
)
META_GARBAGE=(
    'microsoft word','microsoft® word','acrobat','pdfmaker','untitled','sin título','sin titulo','document.doc','documento',
    'file://','localhost','scanner','scan_','tesis_final','thesis_final','finalversion.doc','final version.doc',
)
REPOSITORY_COVER_TERMS=(
    'permanent wrap url','repository record','repository home page','please scroll down to view the document',
    'copyright and reuse','wrap team','downloaded from','institutional repository','repository url',
)

PAGE_ROLE_HEADINGS=(
    'agradecimientos','acknowledgements','acknowledgment','acknowledgement','dedication','dedicatoria',
    'declaration','thesis declaration','statement of originality','copyright','abstract','resumen','índice','indice',
    'table of contents','contents','introducción','introduction','overview','impact statement','preface','foreword',
)
TOC_MARKERS=('capítulo','chapter','bibliografía','bibliography','references','appendix','anexo','págs','pages')
GENERIC={'tesis','thesis','doctoral thesis','tesis doctoral','dissertation','tese','tesi','bibliografía','bibliografia','references','referencias'}
WORD_RE=re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)?",re.UNICODE)
YEAR_ONLY_RE=re.compile(r'^\(?\s*(?:18|19|20)\d{2}(?:\s*[-–—/]\s*(?:18|19|20)\d{2})?\s*\)?[.,]?$')
PAGE_NO_RE=re.compile(r'^\s*(?:[ivxlcdm]+|\d+)\s*$',re.I)


def norm(s:str)->str:
    return re.sub(r'\s+',' ',str(s or '').replace('\u00ad','')).strip()

def clean(s:str)->str:
    return norm(s).strip(' -–—:;,.|·•\"“”‘’')

def words(s:str)->list[str]:
    return WORD_RE.findall(norm(s))

def filename_as_title(filename:str)->str:
    s=Path(filename).stem
    s=re.sub(r'[_-]+',' ',s)
    s=re.sub(r'%20',' ',s,flags=re.I)
    return norm(s) or Path(filename).stem

def has_term(text:str, terms:Iterable[str])->int:
    low=norm(text).casefold(); hits=0
    for t in terms:
        tl=norm(t).casefold()
        if not tl: continue
        if tl.endswith(' '):
            if low.startswith(tl): hits+=1
            continue
        if re.search(r'(?<!\w)'+re.escape(tl)+r'(?!\w)',low,re.UNICODE): hits+=1
    return hits

def plausible(text:str, allow_numeric=False)->bool:
    t=clean(text)
    if not t or len(t)>430: return False
    if allow_numeric and YEAR_ONLY_RE.match(t): return True
    ws=words(t)
    if len(t)<8 or len(ws)<2: return False
    if t.casefold() in GENERIC: return False
    visible=sum(not c.isspace() for c in t); alpha=sum(c.isalpha() for c in t)
    if visible and alpha/visible<0.45: return False
    return True

def looks_path(text:str)->bool:
    low=norm(text).casefold()
    if any(x in low for x in META_GARBAGE): return True
    return bool(re.search(r'\.(?:pdf|docx?|rtf|odt|tex|ps)(?:\b|$)',low) or re.search(r'(?:file:|https?:|[A-Za-z]:[/\\]|(?:^|\s)[./\\][^\s]+)',low))

def _fold_token(s:str)->str:
    import unicodedata
    s=unicodedata.normalize('NFKD',s.casefold())
    return ''.join(ch for ch in s if not unicodedata.combining(ch))

def _token_coverage(target:str,evidence:str)->float:
    tw={_fold_token(w) for w in words(target) if len(w)>1}
    ew={_fold_token(w) for w in words(evidence) if len(w)>1}
    if not tw: return 0.0
    return len(tw & ew)/len(tw)

def metadata_score(text:str,fallback:str)->float:
    t=clean(text)
    if not plausible(t): return -math.inf
    low=t.casefold()
    if low==fallback.casefold() or looks_path(t): return -math.inf
    score=28+min(len(t),180)/45
    inst=has_term(t,INST_TERMS); role=has_term(t,ROLE_TERMS); deg=has_term(t,DEGREE_TERMS)
    score-=15*inst+22*role
    if deg and len(words(t))<=12: score-=18*deg
    if (inst+deg)>=2 and len(words(t))<18: score-=20
    return score

@dataclass(frozen=True)
class Line:
    text:str; size:float; x0:float; x1:float; y0:float; y1:float; page:int; width:float; height:float; med:float
    @property
    def yr(self): return ((self.y0+self.y1)/2)/max(1,self.height)
    @property
    def center(self): return ((self.x0+self.x1)/2)/max(1,self.width)

@dataclass(frozen=True)
class Candidate:
    text:str; score:float; source:str; page:int; start:int=0; end:int=0

def join_spans(spans:list[dict[str,Any]])->str:
    ps=[s for s in spans if str(s.get('text') or '').strip()]
    if not ps: return ''
    ps.sort(key=lambda s:float((s.get('bbox') or (0,0,0,0))[0]))
    out=str(ps[0].get('text') or '').strip(); prev=ps[0]
    for cur in ps[1:]:
        rawp=str(prev.get('text') or ''); rawc=str(cur.get('text') or '')
        pb=prev.get('bbox') or (0,0,0,0); cb=cur.get('bbox') or (0,0,0,0)
        gap=float(cb[0])-float(pb[2]); sz=max(1,(float(prev.get('size') or 0)+float(cur.get('size') or 0))/2)
        sep=' ' if rawp.endswith((' ','\t')) or rawc.startswith((' ','\t')) or gap>max(1.1,sz*0.18) else ''
        out=out.rstrip()+sep+rawc.lstrip(); prev=cur
    return norm(out)

def extract_lines(page:Any,pno:int)->list[Line]:
    W=float(page.rect.width or 1); H=float(page.rect.height or 1)
    raw=[]; sizes=[]
    for b in page.get_text('dict').get('blocks',[]):
        if b.get('type')!=0: continue
        for ln in b.get('lines',[]):
            spans=ln.get('spans',[]); txt=join_spans(spans)
            if not txt: continue
            bbox=ln.get('bbox') or (0,0,0,0)
            ss=[float(s.get('size') or 0) for s in spans if str(s.get('text') or '').strip()]
            sz=median(ss) if ss else 0
            if sz<=0: continue
            raw.append((txt,sz,*map(float,bbox))); sizes.append(sz)
    body=[sz for txt,sz,*_ in raw if not PAGE_NO_RE.match(clean(txt))]
    med=median(body) if body else (median(sizes) if sizes else 10.0)
    return [
        Line(txt,sz,x0,x1,y0,y1,pno,W,H,med)
        for txt,sz,x0,y0,x1,y1 in sorted(raw,key=lambda z:(z[3],z[2]))
    ]

def is_page_number(t:str)->bool: return bool(PAGE_NO_RE.match(clean(t)))
def is_year_line(t:str)->bool: return bool(YEAR_ONLY_RE.match(clean(t)))
def is_role_line(t:str)->bool:
    low=clean(t).casefold()
    if has_term(t,ROLE_TERMS): return True
    if re.match(r'^(?:dr\.?|dra\.?|lic\.?|prof\.?|mr\.?|ms\.?|mrs\.?|miss)\s+',low): return True
    return False

def likely_person_name(t:str)->bool:
    s=clean(t); ws=words(s)
    if not (2<=len(ws)<=7): return False
    if has_term(s,INST_TERMS) or has_term(s,DEGREE_TERMS) or has_term(s,PAGE_ROLE_HEADINGS): return False
    if any(ch in s for ch in ':;?!.') and not re.match(r'^(?:Dr|Dra|Lic|Prof)\.?\s',s,re.I): return False
    alpha=[w for w in ws if w]
    titleish=sum(w[:1].isupper() or w.isupper() for w in alpha)
    return titleish>=max(2,len(alpha)-1) and len(s)<80

def page_role(lines:list[Line])->str|None:
    joined=' '.join(x.text for x in lines[:30]).casefold()
    repo_hits=sum(term in joined for term in REPOSITORY_COVER_TERMS)
    url_hits=sum(('http://' in x.text.casefold() or 'https://' in x.text.casefold() or '@' in x.text) for x in lines[:30])
    if repo_hits >= 2 or (repo_hits >= 1 and url_hits >= 2):
        return 'repository-coversheet'
    for ln in lines[:10]:
        if ln.yr>0.30: break
        low=clean(ln.text).casefold()
        if low in PAGE_ROLE_HEADINGS or any(low.startswith(h+':') or low.startswith(h+' ') for h in PAGE_ROLE_HEADINGS if len(h)>=5):
            return low
    if len(lines)>=18:
        joined=' '.join(x.text for x in lines[:35]).casefold()
        dots=sum('....' in x.text for x in lines[:35])
        if dots>=3 or sum(m in joined for m in TOC_MARKERS)>=4:
            return 'contents-like'
    return None

def title_page_signal(lines:list[Line])->float:
    joined=' '.join(x.text for x in lines)
    s=0.0
    if has_term(joined,DEGREE_TERMS): s+=5
    if has_term(joined,INST_TERMS): s+=2
    if has_term(joined,ROLE_TERMS): s+=2
    if len(lines)<=18: s+=2
    role=page_role(lines)
    if role=='repository-coversheet': s-=14
    elif role: s-=4
    return s

def barrier(ln:Line, prev:Line|None=None, nxt:Line|None=None)->bool:
    t=clean(ln.text)
    if not t or is_page_number(t): return True
    if is_role_line(t): return True
    if t.casefold() in GENERIC: return True
    if has_term(t,INST_TERMS) and len(words(t))<=10: return True
    if has_term(t,DEGREE_TERMS) and len(words(t))<=15: return True
    if clean(t).casefold() in PAGE_ROLE_HEADINGS: return True
    if likely_person_name(t):
        if nxt and (has_term(nxt.text,DEGREE_TERMS) or has_term(nxt.text,INST_TERMS) or is_role_line(nxt.text)):
            return True
        if prev and prev.size>=ln.size*1.15 and prev.yr<0.65:
            return True
    return False

def can_join(prev:Line,cur:Line)->bool:
    if is_year_line(cur.text):
        gap=cur.y0-prev.y1
        return -2<=gap<=max(34,2.5*max(prev.size,cur.size)) and abs(cur.center-prev.center)<=0.18
    if barrier(cur,prev,None) or barrier(prev,None,cur): return False
    gap=cur.y0-prev.y1; mx=max(prev.size,cur.size,1)
    if gap < -max(5.0, 0.45*mx) or gap>max(32,2.35*mx): return False
    ratio=min(prev.size,cur.size)/max(prev.size,cur.size)
    if ratio<0.56:
        tight = gap <= 1.15*min(prev.size,cur.size)
        aligned = abs(prev.center-cur.center) <= 0.09 or abs(prev.x0-cur.x0) <= 0.06*prev.width
        if ratio < 0.42 or not (tight and aligned): return False
    if abs(prev.center-cur.center)>0.30 and abs(prev.x0-cur.x0)>0.20*prev.width: return False
    return True

def candidate_score(group:list[Line],role:str|None,title_signal:float)->float:
    text=clean(' '.join(x.text for x in group))
    if not plausible(text): return -math.inf
    ws=words(text); sz=median([x.size for x in group]); med=max(1,median([x.med for x in group])); prom=sz/med
    page=group[0].page; yr=sum(x.yr for x in group)/len(group)
    score=13 + max(-4,min(24,(prom-1)*20)) + min(len(text),220)/32
    if 4<=len(ws)<=35: score+=5
    if 2<=len(group)<=4: score+=4
    if len(group)>=2:
        cont=0
        for ln in group[1:]:
            t=clean(ln.text)
            if is_year_line(t) or (t and t[0].islower()): cont+=1
        score += min(6.0, 4.0*cont)
    if 0.14<=yr<=0.68: score+=6
    elif 0.06<=yr<=0.80: score+=2
    else: score-=5
    centers=[x.center for x in group]; lefts=[x.x0/x.width for x in group]
    if max(centers)-min(centers)<=0.11 or max(lefts)-min(lefts)<=0.07: score+=3
    if abs(sum(centers)/len(centers)-0.5)<=0.14: score+=2
    score+=title_signal
    inst=has_term(text,INST_TERMS); ro=has_term(text,ROLE_TERMS); deg=has_term(text,DEGREE_TERMS)
    score-=16*inst+20*ro
    if deg and len(ws)<=16: score-=12*deg
    if looks_path(text): score-=25
    if role=='repository-coversheet':
        score -= 55
    elif role:
        top=max(x.yr for x in group)<=0.10
        score += 4 if top else -18
    score-=page*1.8
    return score

def canonical_for_repeat(t:str)->str:
    s=clean(t)
    s=re.sub(r'\s+(?:[ivxlcdm]+|\d+)\s*$','',s,flags=re.I)
    return norm(s)

def similarity(a:str,b:str)->float:
    aa=canonical_for_repeat(a).casefold(); bb=canonical_for_repeat(b).casefold()
    if not aa or not bb: return 0
    wa={w.casefold() for w in words(aa) if len(w)>2}; wb={w.casefold() for w in words(bb) if len(w)>2}
    jac=len(wa&wb)/len(wa|wb) if wa and wb else 0
    seq=SequenceMatcher(None,aa,bb).ratio()
    return max(jac,seq)

def layout_candidates(pdf:Any,max_pages:int=6)->list[Candidate]:
    all_lines=[]; page_lines=[]; roles=[]; signals=[]
    for pno in range(min(max_pages,len(pdf))):
        ls=extract_lines(pdf[pno],pno); page_lines.append(ls); all_lines.extend(ls); roles.append(page_role(ls)); signals.append(title_page_signal(ls))
    out=[]
    for pno,ls in enumerate(page_lines):
        if roles[pno]=='repository-coversheet':
            continue
        n=len(ls)
        for i,ln in enumerate(ls):
            prev=ls[i-1] if i else None; nxt=ls[i+1] if i+1<n else None
            if barrier(ln,prev,nxt) or is_year_line(ln.text): continue
            group=[ln]
            sc=candidate_score(group,roles[pno],signals[pno])
            if math.isfinite(sc): out.append(Candidate(clean(ln.text),sc,'cover_layout',pno,i,i))
            for j in range(i+1,min(n,i+6)):
                if not can_join(group[-1],ls[j]): break
                group.append(ls[j])
                sc=candidate_score(group,roles[pno],signals[pno])
                if math.isfinite(sc): out.append(Candidate(clean(' '.join(x.text for x in group)),sc,'cover_layout',pno,i,j))
    repeat_pool=[]
    for c in out:
        if c.page < 0 or len(c.text) > 220:
            continue
        ls=page_lines[c.page]
        if c.start < len(ls) and ls[c.start].yr <= 0.115:
            repeat_pool.append(c)
    boosted=[]
    for c in out:
        b=0.0
        if c in repeat_pool:
            reps={o.page for o in repeat_pool if o.page!=c.page and similarity(c.text,o.text)>=0.86}
            if reps:
                b=min(18.0,6.0*len(reps))+8.0
        boosted.append(Candidate(c.text,c.score+b,c.source,c.page,c.start,c.end))
    return boosted

def detect_thesis_title(path:Path,filename:str)->tuple[str,str]:
    fallback=filename_as_title(filename)
    if fitz is None: return fallback,'filename'
    try:
        with fitz.open(path) as pdf:
            ranked=layout_candidates(pdf)
            meta=clean((pdf.metadata or {}).get('title') or '')
            ms=metadata_score(meta,fallback)
            if math.isfinite(ms):
                overlap=max((similarity(meta,c.text) for c in ranked),default=0)
                if overlap>=0.72: ms+=20
                page_cover=0.0
                for pno in range(min(3,len(pdf))):
                    ls=extract_lines(pdf[pno],pno)
                    if page_role(ls)=='repository-coversheet':
                        continue
                    evidence=' '.join(x.text for x in ls if x.yr <= 0.68)
                    page_cover=max(page_cover,_token_coverage(meta,evidence))
                if page_cover>=0.90: ms+=34
                elif page_cover>=0.75: ms+=22
                ranked.append(Candidate(meta,ms,'pdf_metadata',-1))
            if ranked:
                ranked.sort(key=lambda c:(c.score,len(c.text)),reverse=True)
                best=ranked[0]
                if best.score>=24 and plausible(best.text): return best.text,best.source
    except Exception:
        pass
    return fallback,'filename'
