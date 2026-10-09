from pathlib import Path
import app
from biblioref_v0_3 import LayoutLine

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
JS = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')


def L(y, text, page=24):
    return LayoutLine(page=page, page_height=842.0, text=text, x0=72.0, y0=float(y), x1=500.0, y1=float(y)+10.0, median_font_size=10.0)


def test_trusted_click_recovers_prefix_skipped_by_segmenter():
    lines = [
        L(98, 'Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,'),
        L(109, 'G. (2002): Propuestas alternativas a la agricultura industrializada: el caso de la'),
        L(120, 'agricultura ecológica en España.'),
        L(142, 'Altieri, M A (1985): Agroecología. Bases Científicas de la Agricultura Alternativa'),
        L(153, '(Valparaíso: CETAL, 1985).'),
    ]
    first = {'reference_text': 'Altieri, M A (1985): Agroecología. Bases Científicas de la Agricultura Alternativa (Valparaíso: CETAL, 1985).', 'reference_start_page': 24}
    text, used = app._trusted_click_prefix(lines, 24, 98, first)
    assert text.startswith('Alonso Mielgo')
    assert '(2002)' in text
    assert 'Altieri' not in text
    assert len(used) == 3


def test_trusted_click_does_not_override_when_segmenter_starts_at_click():
    lines = [L(98, 'Alonso Mielgo, A. (2002): Propuestas alternativas.'), L(120, 'Altieri, M. (1985): Agroecología.')]
    first = {'reference_text': 'Alonso Mielgo, A. (2002): Propuestas alternativas.', 'reference_start_page': 24}
    text, used = app._trusted_click_prefix(lines, 24, 98, first)
    assert text is None
    assert used == []


def test_extraction_revision_forces_old_project_refresh():
    doc = {'status':'ready','references':[{'source':'automatic','status':'extracted'}], 'analysis':{
        'software_version': app.SOFTWARE_VERSION,
        'algorithm_version': app.ALGORITHM_VERSION,
        'stable_engine_version': app.STABLE_ENGINE_VERSION,
    }}
    assert app._analysis_stale(doc) is True
    doc['analysis']['extraction_revision'] = app.EXTRACTION_REVISION
    assert app._analysis_stale(doc) is False


def test_pdf_click_margin_and_compact_reextract_control_present():
    assert 'margin_pt: float = Field(default=PDF_CLICK_MARGIN_PT' in (ROOT/'app.py').read_text(encoding='utf-8')
    assert "margin_pt:42" in JS
    assert 'trusted_click_override' in (ROOT/'app.py').read_text(encoding='utf-8')
    assert 'id="reextract"' in HTML
    assert 'APP v2.7.0' in HTML
    assert '8775' in (ROOT/'run_biblioref.py').read_text(encoding='utf-8')
