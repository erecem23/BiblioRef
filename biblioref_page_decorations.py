from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Sequence, Any


def _norm(text:str)->str:
    text=unicodedata.normalize('NFKD',str(text or ''))
    text=''.join(c for c in text if not unicodedata.combining(c))
    text=re.sub(r'\b\d{1,4}\b',' ',text)
    text=re.sub(r'[^A-Za-z]+',' ',text).lower()
    return re.sub(r'\s+',' ',text).strip()


def _similar(a:str,b:str)->bool:
    aa,bb=_norm(a),_norm(b)
    if len(aa)<5 or len(bb)<5:return False
    if aa==bb:return True
    return SequenceMatcher(None,aa,bb).ratio()>=0.80


def detect_repeated_page_decorations(lines:Sequence[Any])->list[Any]:
    by=defaultdict(list)
    for l in lines: by[int(l.page)].append(l)
    extremes=[]
    for page,ls in by.items():
        ls=sorted(ls,key=lambda x:(x.y0,x.x0))
        if not ls:continue
        # A decoration candidate must truly live in an outer page band.
        # Being merely the first/last bibliography line is not enough.
        # A running header may take two or three lines («…de Regulación» / «Emocional»):
        # every line of the band is a candidate, and repetition on other pages confirms it.
        for top in ls[:3]:
            h=float(getattr(top,'page_height',0) or 0)
            if not (h and float(top.y0) <= 0.08*h):break
            extremes.append(top)
        if len(ls)>1:
            for bottom in reversed(ls[-3:]):
                if bottom in extremes:break
                h2=float(getattr(bottom,'page_height',0) or 0)
                if not (h2 and float(bottom.y1) >= 0.92*h2):break
                extremes.append(bottom)
    confirmed=[]
    for i,l in enumerate(extremes):
        support={int(o.page) for j,o in enumerate(extremes) if j!=i and int(o.page)!=int(l.page) and _similar(l.text,o.text)}
        if support: confirmed.append(l)
    return confirmed


#: 0.6.15: a running header lower than the 8 % band ("REFERENCIAS
#: BIBLIOGRÁFICAS" at 12 %) is still a header when the same text sits at the
#: same height at the top of three or more pages.
RUNNING_HEADER_BAND=0.16
RUNNING_HEADER_MIN_PAGES=3
#: Dictionary guide words ("A/B", "P/S") fused to the first line of a page.
GUIDE_WORDS_RX=re.compile(r'^([A-ZÁÉÍÓÚÑ]{1,3})\s?/\s?([A-ZÁÉÍÓÚÑ]{1,3})\s+(?=\S)')


def _page_tops(lines:Sequence[Any])->dict[int,list[Any]]:
    by=defaultdict(list)
    for l in lines: by[int(l.page)].append(l)
    return {page:sorted(ls,key=lambda x:(x.y0,x.x0))[:3] for page,ls in by.items()}


def detect_running_headers(lines:Sequence[Any])->list[Any]:
    groups=defaultdict(list)
    for tops in _page_tops(lines).values():
        # 0.6.18: a header may take two lines (title, then a signature below it);
        # each candidate needs content under it on the same page.
        for top in tops[:max(0,min(2,len(tops)-1))]:
            h=float(getattr(top,'page_height',0) or 0)
            text=re.sub(r'\s+',' ',str(top.text)).strip().casefold()
            if (h and float(top.y0)<=RUNNING_HEADER_BAND*h and len(_norm(text))>=5
                    and not re.search(r'\b(?:1[5-9]|20)\d{2}\b',text)):
                groups[(text,round(float(top.y0)))].append(top)
    return [l for ls in groups.values() if len({int(x.page) for x in ls})>=RUNNING_HEADER_MIN_PAGES for l in ls]


def strip_guide_words(lines:list[Any])->tuple[list[Any],list[Any]]:
    firsts=[tops[0] for tops in _page_tops(lines).values() if tops]
    marked=[l for l in firsts if GUIDE_WORDS_RX.match(str(l.text))]
    if len({int(l.page) for l in marked})<RUNNING_HEADER_MIN_PAGES:
        return lines,[]
    ids={id(l) for l in marked}
    out=[]
    for l in lines:
        if id(l) in ids and dataclasses.is_dataclass(l):
            l=dataclasses.replace(l,text=GUIDE_WORDS_RX.sub('',str(l.text),count=1))
        out.append(l)
    return out,marked


def filter_repeated_page_decorations(lines:Sequence[Any])->tuple[list[Any],list[dict]]:
    confirmed=detect_repeated_page_decorations(lines)
    ids={id(x) for x in confirmed}
    confirmed+=[x for x in detect_running_headers(lines) if id(x) not in ids]
    ids={id(x) for x in confirmed}
    removed=[{'page':int(x.page),'text':str(x.text),'y0':round(float(x.y0),2),'y1':round(float(x.y1),2)} for x in confirmed]
    kept,guided=strip_guide_words([x for x in lines if id(x) not in ids])
    removed+=[{'page':int(x.page),'text':GUIDE_WORDS_RX.match(str(x.text)).group(0).strip(),'y0':round(float(x.y0),2),'y1':round(float(x.y1),2)} for x in guided]
    return kept, removed
