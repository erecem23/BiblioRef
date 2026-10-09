from copy import deepcopy
import inspect
import json
from pathlib import Path

import app
from biblioref import pipeline
from tests_support import pdf_factory as fitz
from biblioref_v0_3 import LayoutLine

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')


def L(y,text,x0=72,x1=500,page=24):
    return LayoutLine(page=page,page_height=842.0,text=text,x0=x0,y0=float(y),x1=x1,y1=float(y)+10.0,median_font_size=10.0)


def test_ui_252_identity_and_cache_buster():
    assert 'APP v2.7.0' in HTML
    assert 'app.js?v=283' in HTML
    assert '8775' in (ROOT/'run_biblioref.py').read_text(encoding='utf-8')


def test_claude_visual_audit_changes_are_integrated():
    # v2.7.0 UI migration: Console design supersedes the earlier reading-room tokens,
    # while retaining the audited interaction/accessibility behaviors.
    assert '--sidebar:#101a30' in HTML
    assert '--accent:#2f6feb' in HTML
    assert '--warn:#b45309' in HTML
    assert ':focus-visible{outline:2px solid var(--accent)' in HTML
    assert '.pill.neutral' in HTML
    assert 'font-size:13.5px' in HTML
    assert '.refitem:hover .refquick' in HTML
    assert '@media(hover:none){.refitem .refquick{opacity:1}}' in HTML
    assert 'grid-template-columns:minmax(0,1fr) minmax(0,1fr)' in HTML
    assert '<details class="thesisdetails"><summary>Datos de la tesis</summary>' in HTML
    assert '<button class="btn xs" id="visibleStart">Inicio</button>' in HTML
    assert '<button class="btn xs" id="visibleEnd">Final</button>' in HTML
    assert 'id="dashViewToggle"' in HTML and 'data-view="grouped"' in HTML
    assert 'id="refViewToggle"' in HTML and 'data-refview="table"' in HTML
    assert 'function pillClass(d)' in JS
    assert 'function updateHeroEmphasis()' in JS
    assert 'boundaryCropMarkup' in JS and '/lines`)' in JS
    assert '⚠ revisar' in JS and '✓ resuelto' in JS


def test_metadata_edits_do_not_freeze_old_extraction():
    doc={
        'status':'ready',
        'sections':[{'source':'automatic','confirmed':False}],
        'references':[{'source':'automatic','status':'extracted','edited':False,'deleted':False}],
        'corrections':[{'kind':'edit_thesis_metadata','changes':{'title':['a','b']}}],
        'audit_decisions':{'x':{'decision':'ignore'}},
    }
    assert app._has_manual_work(doc) is False
    doc['references'][0]['edited']=True
    assert app._has_manual_work(doc) is True


def test_click_snap_prefers_deferred_year_author_over_heading():
    lines=[
        L(68,'B ib liografía.'),
        L(98,'Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,'),
        L(109,'G. (2002): Propuestas alternativas a la agricultura industrializada: el caso de la'),
        L(120,'agricultura ecológica en España.'),
        L(142,'Altieri, M A (1985): Agroecología. Bases Científicas de la Agricultura Alternativa'),
    ]
    idx,line,dist=app._select_click_start_line(lines,24,82,100,42)
    assert line is not None
    assert line.text.startswith('Alonso Mielgo')
    assert idx==1
    assert dist>0


def test_click_snap_uses_x_as_soft_column_cue():
    lines=[
        L(100,'Other column, X. (2000). Different reference.',x0=320,x1=550),
        L(102,'Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F.',x0=70,x1=285),
        L(113,'G. (2002): Propuestas alternativas.',x0=70,x1=285),
    ]
    idx,line,_=app._select_click_start_line(lines,24,101,120,42)
    assert line.text.startswith('Alonso Mielgo')


def test_pdf_click_margin_is_wider_and_revision_forces_refresh():
    assert app.PDF_CLICK_MARGIN_PT == 42.0
    assert app.EXTRACTION_REVISION == 'v096-core-first-reference-1'
    assert 'margin_pt:42' in JS
    assert 'x,end_page' in JS


def test_process_all_includes_safe_stale_documents():
    assert 'function processableDocs()' in JS
    assert 'const pending=processableDocs().map(x=>x.id);' in JS



def _app_core_report(records):
    return {
        "scope": "all_reference_sections",
        "scope_definition": "all reference sections",
        "records": records,
        "zones": [{
            "zone_id": 1,
            "heading": "Bibliografía",
            "start_page": 1,
            "end_page": 1,
            "zone_role": "primary_references",
            "start_confidence_score": 1.0,
            "start_confidence_label": "high",
            "end_confidence_score": 1.0,
            "end_confidence_label": "high",
            "zone_completeness": "complete",
            "termination_reason": "fixture",
            "adaptive_limit_exceeded": False,
        }],
        "duplicate_groups": [],
        "n_occurrences_all_zones": len(records),
        "n_unique_references": len(records),
        "n_duplicate_groups": 0,
        "n_occurrences_in_duplicate_groups": 0,
        "n_repeated_occurrences_beyond_first": 0,
        "n_records_selected": len(records),
        "detection_decision": {
            "method": "fixture",
            "requires_confirmation": False,
        },
    }


def _app_core_record(text, ref_in_zone=1):
    return {
        "zone_id": 1,
        "ref_in_zone": ref_in_zone,
        "reference_text": text,
        "reference_start_page": 1,
        "reference_end_page": 1,
        "reference_start_x": 70.0,
        "zone_start_page": 1,
        "boundary_evidence": "fixture",
        "audit_flags": "",
    }


def _write_app_core_fixture(tmp_path, name):
    pdf = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((70, 70), "Bibliografía", fontsize=14)
    page.insert_text(
        (70, 105),
        "Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 116),
        "G. (2002): Propuestas alternativas a la agricultura industrializada.",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 138),
        "Altieri, M. A. (1985). Segunda referencia.",
        fontsize=9.5,
    )
    doc.save(pdf)
    doc.close()
    return pdf


def _assert_app_core_parity(tmp_path, monkeypatch, records, name):
    pdf = _write_app_core_fixture(tmp_path, name)
    report = _app_core_report(records)
    monkeypatch.setattr(
        pipeline,
        "_ORIGINAL_EFFECTIVE",
        lambda *args, **kwargs: deepcopy(report),
    )
    core_result = pipeline.process_pdf(pdf, rescue_audit=False)
    monkeypatch.setattr(app, "RESULT_DIR", tmp_path)
    document = {
        "id": Path(name).stem,
        "path": str(pdf),
        "references": [],
        "sections": [],
    }

    app._analyze_document(document, prepared_result=deepcopy(core_result))

    core_texts = [
        record["reference_text"]
        for record in core_result["records"]
    ]
    app_texts = [record["text"] for record in document["references"]]
    persisted = json.loads(Path(document["result_file"]).read_text(encoding="utf-8"))
    assert app_texts == core_texts
    assert document["n_references"] == len(core_texts)
    assert persisted["first_reference_repairs"] == core_result["first_reference_repairs"]
    assert "app_repairs" not in persisted
    assert "_first_reference_guard" not in inspect.getsource(app._analyze_document)
    assert not hasattr(app, "_first_reference_guard")


def test_app_core_first_reference_parity_for_omitted_entry(tmp_path, monkeypatch):
    _assert_app_core_parity(
        tmp_path,
        monkeypatch,
        [_app_core_record("Altieri, M. A. (1985). Segunda referencia.")],
        "parity-omitted.pdf",
    )


def test_app_core_first_reference_parity_for_deferred_author(tmp_path, monkeypatch):
    _assert_app_core_parity(
        tmp_path,
        monkeypatch,
        [
            _app_core_record(
                "G. (2002): Propuestas alternativas a la agricultura industrializada."
            ),
            _app_core_record(
                "Altieri, M. A. (1985). Segunda referencia.",
                2,
            ),
        ],
        "parity-deferred.pdf",
    )
