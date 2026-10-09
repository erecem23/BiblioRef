from pathlib import Path
import json, tempfile, os, importlib
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'static/index.html').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')

def test_v243_ui_research_metadata():
    assert 'APP v2.7.0' in HTML
    assert 'Secciones de referencias' not in HTML
    assert 'Datos de la tesis' in JS
    for label in ['Universidad','Facultad / unidad académica','Repositorio','Área / disciplina']:
        assert label in JS
    assert '>Ubicación</button>' in JS
    assert '>Origen</button>' not in JS
    assert 'thesisLabel(d)' in JS
    assert 'refs ·' not in JS[JS.index('function renderDocs(){'):JS.index("$('#thesisSelect').onchange")]

def test_v243_compact_section_controls():
    for ident in ['sectionSelect','editSection','addSection','applySectionLimits']:
        assert f'id="{ident}"' in HTML
    assert 'sectionPanel' not in HTML

def test_v243_backend_metadata_fields():
    text=(ROOT/'app.py').read_text(encoding='utf-8')
    for field in ['author','year','university','faculty','program','repository','repository_url','area','country']:
        assert f'{field}: str | None' in text
    assert 'edit_thesis_metadata' in text
    assert '"metadata"' in text

def test_v243_port():
    assert '8775' in (ROOT/'run_biblioref.py').read_text(encoding='utf-8')
