from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Any

@dataclass(frozen=True)
class ParagraphFlowProfile:
    threshold: float | None
    small_mean: float | None
    large_mean: float | None
    n_gaps: int
    separated: bool


def profile_paragraph_flow(lines: Sequence[Any]) -> ParagraphFlowProfile:
    gaps=[]
    prev=None
    for line in lines:
        if prev is not None and getattr(prev,'page',None)==getattr(line,'page',None):
            g=float(line.y0)-float(prev.y1)
            if -1.0 <= g <= 80.0:
                gaps.append(max(0.0,g))
        prev=line
    if len(gaps)<8:
        return ParagraphFlowProfile(None,None,None,len(gaps),False)
    vals=sorted(gaps)
    best=None
    # Otsu-like split: maximize between-class variance, require useful material each side.
    for i in range(4,len(vals)-3):
        a,b=vals[:i],vals[i:]
        ma=sum(a)/len(a); mb=sum(b)/len(b)
        score=len(a)*len(b)*(mb-ma)**2
        if best is None or score>best[0]: best=(score,i,ma,mb)
    if not best:
        return ParagraphFlowProfile(None,None,None,len(gaps),False)
    _,i,ma,mb=best
    separated=(mb-ma)>=2.5 and vals[i]-vals[i-1]>=0.6
    threshold=(vals[i-1]+vals[i])/2 if separated else None
    return ParagraphFlowProfile(round(threshold,3) if threshold is not None else None,round(ma,3),round(mb,3),len(gaps),separated)


def is_paragraph_start(index:int, lines:Sequence[Any], profile:ParagraphFlowProfile) -> bool:
    if index<=0 or not profile.separated or profile.threshold is None:
        return False
    cur=lines[index]; prev=lines[index-1]
    if getattr(cur,'page',None)!=getattr(prev,'page',None):
        return False
    return float(cur.y0)-float(prev.y1) >= profile.threshold
