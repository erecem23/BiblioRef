from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app, APP_TOKEN, STORE
from biblioref_v0_2 import diagnose_style
from biblioref_v0_3 import LayoutLine, diagnose_layout
from biblioref_v0_4 import AdaptiveLayoutZone, segment_adaptive_layout_zone
from biblioref_page_boundary import evaluate_page_boundary
from biblioref_page_decorations import filter_repeated_page_decorations
from biblioref_paragraph_flow import profile_paragraph_flow
from biblioref.audit.coverage import build_coverage_report


def L(page, text, y0, x0=72.0, h=842.0):
    return LayoutLine(page=page,page_height=h,text=text,x0=x0,y0=y0,x1=520.0,y1=y0+10.0,median_font_size=10.0,fragment_count=1)


def zone(lines, style=None):
    style = style or diagnose_style([x.text for x in lines])
    layout = diagnose_layout(lines)
    return AdaptiveLayoutZone(
        heading=L(lines[0].page,'Bibliografía',50), lines=lines,
        start_page=min(x.page for x in lines), end_page=max(x.page for x in lines),
        style=style, layout=layout, termination_reason='end_of_document',
        confidence_score=1, confidence_label='high', confidence_reasons=[],
        start_confidence_score=1,start_confidence_label='high',start_confidence_reasons=[],
        end_confidence_score=1,end_confidence_label='high',end_confidence_reasons=[],
        zone_completeness='complete',adaptive_soft_limit_pages=25,
        zone_span_pages=max(x.page for x in lines)-min(x.page for x in lines)+1,
        adaptive_limit_exceeded=False)


def test_page_decoration_filter_removes_repeated_outer_header_only():
    lines=[L(1,'Eduardo Sevilla Guzmán',30),L(1,'Altieri, M. (1985). Título.',100),L(2,'Eduardo Sevilla Guzmán',31),L(2,'Beck, U. (1992). Título.',110)]
    kept,removed=filter_repeated_page_decorations(lines)
    assert len(removed)==2
    assert [x.text for x in kept]==['Altieri, M. (1985). Título.','Beck, U. (1992). Título.']


def test_decoration_filter_does_not_remove_first_reference_near_but_not_in_edge_band():
    lines=[L(1,'Autor A. (2001). Uno.',100),L(2,'Autor B. (2002). Dos.',100)]
    kept,removed=filter_repeated_page_decorations(lines)
    assert len(kept)==2 and not removed


def test_paragraph_flow_detects_two_gap_populations():
    lines=[]; y=100
    for i in range(10):
        lines.append(L(1,f'Autor {i}, A. (20{i:02d}). Título.',y)); y+=20
        lines.append(L(1,'continuación editorial.',y)); y+=30
    p=profile_paragraph_flow(lines)
    assert p.separated and p.threshold is not None


def test_deferred_year_at_page_start_becomes_new_reference():
    lines=[
        L(1,'Habermas, J. (1989). El discurso filosófico de la modernidad. Taurus.',700),
        L(2,'Hann and Jan Douwe van der Ploeg (eds.)',80),
        L(2,'Endogenous Rural Development in Europe: Theory method and practice (Brussels: European Commission, 1994).',100),
        L(2,'Hernández, E. (1985). Xolocotzia.',140),
    ]
    seg=segment_adaptive_layout_zone(zone(lines))
    texts=[x['reference_text'] for x in seg]
    assert any(t.startswith('Hann and Jan') and '1994' in t for t in texts)


def test_mixed_bare_year_with_paragraph_gap_splits_locally():
    lines=[
        L(1,'Ottmann; G.; E. Sevilla Guzmán y el CEPAR (2003) Una estrategia de sustentabilidad.',100),
        L(1,'Madrid: IEPALA; pp. 199-240.',120),
        L(1,'Ottmann, 2004, Agroecología y Sociología Histórica desde Latinoamérica.',160),
        L(1,'México/Madrid/Córdoba: PNUMA/Mundi-Prensa.',180),
        L(1,'Reijntjes, G. (1992). Farming for the Future.',220),
        L(1,'London: McMillan.',240),
        L(1,'Rissler, J. (1996). Ecological Risks.',280),
        L(1,'MIT Press.',300),
        L(1,'Shanin, T. (1990). Defining Peasants.',340),
        L(1,'Oxford: Basil Blackwell.',360),
    ]
    seg=segment_adaptive_layout_zone(zone(lines))
    assert any(t.startswith('Ottmann, 2004') for t in [x['reference_text'] for x in seg])


def test_page_boundary_split_helper():
    r=evaluate_page_boundary(['Habermas, J. (1989). El discurso filosófico. Taurus.'],['Hann and Jan Douwe van der Ploeg (eds.)','Endogenous Rural Development (Brussels, 1994).'])
    assert r['verdict']=='split'


def test_page_boundary_continue_helper():
    r=evaluate_page_boundary(['Cornwall, A. Acknowledging process: challenges for agricultural'],['research and extension methodology. London: ITDG.'])
    assert r['verdict']=='continue'


def test_page_boundary_review_helper():
    r=evaluate_page_boundary(['Texto ambiguo'],['Otro texto ambiguo'])
    assert r['verdict']=='review'


def test_coverage_report_surfaces_missing_candidate(monkeypatch):
    lines=[L(1,'Altieri, M. (1985). Agroecología.',100),L(1,'Beck, U. (1992). Risk Society.',150)]
    monkeypatch.setattr('biblioref.audit.coverage.extract_layout_lines_range',lambda *a,**k: lines)
    monkeypatch.setattr('biblioref.audit.coverage.page_dimensions',lambda *a,**k:(595.0,842.0))
    result={'zones':[{'zone_id':1,'start_page':1,'start_y':80,'end_page':1,'end_y':200}], 'records':[{'zone_id':1,'reference_text':'Altieri, M. (1985). Agroecología.','reference_start_page':1}]}
    cov=build_coverage_report('dummy.pdf',result)
    assert cov['summary']['n_possible_missing']>=1
    assert any('Beck' in x['text'] for x in cov['possible_missing'])


def test_app_v24_static_controls_present():
    html=Path('static/index.html').read_text(encoding='utf-8')
    js=Path('static/app.js').read_text(encoding='utf-8')
    assert 'APP v2.7.0' in html
    assert 'Control de extracción' in html
    assert 'reviewBoundary' in js and 'addMissing' in js


def test_audit_decision_endpoint_persists(monkeypatch):
    # In-memory synthetic document: endpoint does not touch PDF.
    old=STORE.data
    try:
        STORE.data={'schema':1,'documents':{'d1':{'id':'d1','filename':'x.pdf','audit_decisions':{},'corrections':[]}}}
        client=TestClient(app)
        r=client.post('/api/documents/d1/audit-checks/boundary_z1_1_2/decision',headers={'X-BiblioRef-Token':APP_TOKEN},json={'decision':'continue'})
        assert r.status_code==200
        assert STORE.get('d1')['audit_decisions']['boundary_z1_1_2']['decision']=='continue'
    finally:
        STORE.data=old
