from pathlib import Path
import app

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')

def test_visual_reading_toggle_is_non_destructive():
    assert 'id="toggleVisualText"' in HTML
    assert 'Aa · vista limpia' in HTML
    assert 'displayRefText' in JS
    assert 'visualText' in JS
    # Exports still use the stored raw ``text`` field in app.py.
    assert 'fieldnames = ["thesis_id"' in (ROOT/'app.py').read_text(encoding='utf-8')

def test_titles_use_gap_aware_span_joining():
    spans=[
        {'text':'Sevilla','bbox':(10,0,45,10),'size':10},
        {'text':'G','bbox':(48,0,54,10),'size':10},
        {'text':'uzmán','bbox':(54.4,0,82,10),'size':10},
    ]
    out=app._join_spans_for_reading(spans)
    assert out == 'Sevilla Guzmán'

def test_gap_aware_join_preserves_real_word_space():
    spans=[
        {'text':'A','bbox':(10,0,16,10),'size':10},
        {'text':'study','bbox':(20,0,45,10),'size':10},
    ]
    assert app._join_spans_for_reading(spans) == 'A study'

def test_visual_css_has_no_artificial_letter_spacing():
    assert 'letter-spacing:0' in HTML
    assert 'font-kerning:normal' in HTML

def test_new_cache_buster_and_port():
    assert 'app.js?v=283' in HTML
    assert '8775' in (ROOT/'run_biblioref.py').read_text(encoding='utf-8')
