from pathlib import Path
import app
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
PY=(ROOT/'app.py').read_text(encoding='utf-8')

def test_dashboard_and_navigation_present():
    assert 'APP v2.7.0' in HTML
    assert 'data-screen="project"' in HTML
    assert 'id="projectStats"' in HTML
    assert 'id="dashboardTable"' in HTML
    assert 'mínimo por tesis' in JS and 'máximo por tesis' in JS

def test_home_lists_projects_and_collection_owns_import_controls():
    home = HTML.split('<section id="screen-new"')[1].split('</section>')[0]
    collection = HTML.split('<section id="screen-collection"')[1].split('<input id="fileInput"')[0]
    assert 'id="newProject"' in home and 'id="recentProjects"' in home
    assert 'id="uploadCards"' not in home and 'id="chooseFiles"' not in home
    assert 'id="chooseFiles"' in collection and 'id="chooseFolder"' in collection
    assert 'id="projectTree"' in collection
    assert 'id="analyzeAll"' in collection
    assert 'id="folderInput"' in HTML
    assert 'webkitdirectory' in HTML
    assert "$('#chooseFolder')" in JS

def test_processing_routes_to_project_dashboard():
    assert "show('project');renderDashboard()" in JS

def test_export_from_dashboard_and_current_thesis():
    assert 'id="dashboardExport"' in HTML
    assert 'id="exportCurrent"' in HTML
    assert 'openExportModal' in JS

def test_bulk_generic_metadata_ui_and_api():
    assert 'id="bulkMetadata"' in HTML
    assert 'id="bulkMetadataReview"' in HTML
    assert '/api/documents/bulk-metadata' in JS
    assert '@app.patch("/api/documents/bulk-metadata")' in PY
    assert 'bulk_edit_thesis_metadata' in PY

def test_cache_is_disabled_everywhere():
    assert 'no-store, no-cache, must-revalidate, max-age=0' in PY
    assert 'http-equiv="Cache-Control"' in HTML
    assert "opt.cache='no-store'" in JS
    assert 'app.js?v=283' in HTML

def test_click_margin_is_larger_and_revision_bumped():
    assert app.PDF_CLICK_MARGIN_PT == 42.0
    assert app.EXTRACTION_REVISION == 'v096-core-first-reference-1'
    assert 'margin_pt:42' in JS

def test_port_is_unique():
    assert '8775' in (ROOT/'run_biblioref.py').read_text(encoding='utf-8')


def test_trusted_click_uses_existing_later_reference_as_boundary():
    from biblioref_v0_3 import LayoutLine
    def L(y, text):
        return LayoutLine(page=24, page_height=842.0, text=text, x0=72.0, y0=float(y), x1=500.0, y1=float(y)+10, median_font_size=10.0)
    lines = [
        L(98, 'Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,'),
        L(109, 'G. (2002): Propuestas alternativas a la agricultura industrializada: el caso de la'),
        L(120, 'agricultura ecológica en España.'),
        L(142, 'Altieri, M A (1985): Agroecología. Bases Científicas de la Agricultura Alternativa'),
    ]
    first = {'reference_text': 'G. (2002): Propuestas alternativas a la agricultura industrializada', 'reference_start_page': 24}
    known = [{'text': 'Altieri, M A (1985): Agroecología. Bases Científicas de la Agricultura Alternativa'}]
    text, used = app._trusted_click_prefix(lines, 24, 98, first, known)
    assert text.startswith('Alonso Mielgo')
    assert '(2002)' in text
    assert 'Altieri' not in text
    assert len(used) == 3
