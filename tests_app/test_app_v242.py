from pathlib import Path
import app

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
HTML = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')


def test_manual_work_false_for_untouched_automatic_result():
    doc = {
        'references': [{'source': 'automatic', 'status': 'extracted', 'edited': False, 'deleted': False}],
        'sections': [{'source': 'automatic', 'confirmed': False}],
        'corrections': [],
        'audit_decisions': {},
    }
    assert app._has_manual_work(doc) is False


def test_manual_work_detects_manual_section_or_correction():
    assert app._has_manual_work({'sections': [{'source': 'manual', 'confirmed': True}], 'references': []}) is True
    assert app._has_manual_work({'sections': [], 'references': [], 'corrections': [{'kind': 'edit'}]}) is True


def test_stale_untouched_document_is_auto_updated_on_open():
    assert 'S.doc.analysis_stale&&!S.doc.has_manual_work' in JS
    assert "await api(`/api/documents/${id}/analyze`" in JS


def test_add_from_pdf_help_is_nonblocking_and_transient():
    assert 'viewerToast' in HTML
    assert 'pointer-events:none' in HTML
    assert "showViewerToast('Clic en la primera línea de la referencia que falta · Esc cancela',2200)" in JS
    assert '<div class="clickhint"><b>Agregar desde PDF:' not in JS


def test_add_from_pdf_is_one_shot_and_escape_cancels():
    assert 'S.addFromPdfMode=false;updateViewerMode();hideViewerToast();candidateFromPoint' in JS
    assert "e.key==='Escape'" in JS and 'S.addFromPdfMode||S.markMode' in JS


def test_app_identity_v242():
    assert 'APP v2.7.0' in HTML
    assert '8775' in (ROOT / 'run_biblioref.py').read_text(encoding='utf-8')
