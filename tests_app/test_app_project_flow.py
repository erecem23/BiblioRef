import io
import os
import tempfile
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ['BIBLIOREF_WORKSPACE'] = _tmp.name

from tests_support import pdf_factory as fitz
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)
TOKEN = client.get('/api/health').json()['session_token']
HEADERS = {'X-BiblioRef-Token': TOKEN}


def make_pdf(title: str, refs: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((70, 170), title, fontsize=19)
    page.insert_text((70, 230), 'Tesis doctoral', fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((70, 90), 'Referencias', fontsize=16)
    y = 130
    for ref in refs:
        page2.insert_text((70, y), ref, fontsize=10)
        y += 35
    data = doc.tobytes()
    doc.close()
    return data


def upload(name: str, title: str):
    data = make_pdf(title, ['García, M. (2020). Texto de prueba.'])
    r = client.post('/api/documents', headers=HEADERS, files=[('files', (name, data, 'application/pdf'))])
    assert r.status_code == 200, r.text
    return r.json()['documents'][0]


def test_title_and_project_ids_are_created_and_editable():
    d1 = upload('archivo_uno.pdf', 'Trayectorias científicas y formación doctoral')
    d2 = upload('archivo_dos.pdf', 'Bibliometría de tesis universitarias')
    assert d1['thesis_id'].startswith('T')
    assert d2['thesis_id'] != d1['thesis_id']
    assert 'Trayectorias' in d1['title']
    r = client.patch(f"/api/documents/{d1['id']}/metadata", headers={**HEADERS, 'Content-Type':'application/json'}, json={'title':'Título corregido por usuario'})
    assert r.status_code == 200
    assert r.json()['title'] == 'Título corregido por usuario'
    assert r.json()['title_source'] == 'human'


def test_selected_project_csv_contains_thesis_identity():
    docs = client.get('/api/documents').json()['documents']
    first = docs[0]
    r = client.post(f"/api/documents/{first['id']}/references", headers={**HEADERS, 'Content-Type':'application/json'}, json={'text':'Autor, A. (2024). Referencia manual.', 'start_page':2})
    assert r.status_code == 200
    r = client.get(f"/api/project/export/selection/csv?documents={first['id']}")
    assert r.status_code == 200
    text = r.content.decode('utf-8-sig')
    assert 'thesis_id,thesis_title,filename,document_id,reference_id' in text
    assert 'parsed_publisher' in text
    assert 'biblioref-parser-v0.12.8' in text
    assert first['thesis_id'] in text
    assert 'Título corregido por usuario' in text
    # Selecting one thesis must not include the second thesis identifier.
    if len(docs) > 1:
        assert docs[1]['thesis_id'] not in text


def test_project_xlsx_and_json_export_selected_documents():
    docs = client.get('/api/documents').json()['documents']
    ids = ','.join(d['id'] for d in docs[:2])
    rj = client.get(f'/api/project/export/selection/json?documents={ids}')
    assert rj.status_code == 200
    body = rj.json()
    assert body['project']['n_documents'] == min(2, len(docs))
    assert all(x['document']['thesis_id'] for x in body['documents'])
    rx = client.get(f'/api/project/export/selection/xlsx?documents={ids}')
    assert rx.status_code == 200
    assert rx.content[:2] == b'PK'


def test_v22_section_preview_returns_continuous_crop_geometry():
    docs = client.get('/api/documents').json()['documents']
    first = docs[0]
    r = client.get(f"/api/documents/{first['id']}/section-preview?start_page=2&end_page=2&start_y=80&end_y=300")
    assert r.status_code == 200, r.text
    page = r.json()['pages'][0]
    assert page['page'] == 2
    assert page['crop_top'] == 80
    assert page['crop_bottom'] == 300


def test_v22_click_can_recover_reference_candidate_and_insert_before_known_ref():
    data = make_pdf('Extracción asistida de referencias', [
        'Alonso Mielgo, A. (2002). Primera referencia omitida.',
        'Altieri, M. A. (1985). Segunda referencia ya conocida.',
    ])
    r = client.post('/api/documents', headers=HEADERS, files=[('files', ('click_test.pdf', data, 'application/pdf'))])
    assert r.status_code == 200, r.text
    doc = r.json()['documents'][0]
    # Seed the output with the second reference only, reproducing a missed first item.
    r = client.post(
        f"/api/documents/{doc['id']}/references",
        headers={**HEADERS, 'Content-Type':'application/json'},
        json={'text':'Altieri, M. A. (1985). Segunda referencia ya conocida.', 'start_page':2},
    )
    assert r.status_code == 200, r.text
    known = r.json()['references'][0]
    lines = client.get(f"/api/documents/{doc['id']}/page/2/lines").json()['lines']
    line = next(x for x in lines if 'Alonso Mielgo' in x['text'])
    y = (line['y0'] + line['y1']) / 2
    r = client.post(
        f"/api/documents/{doc['id']}/references/candidate-from-point",
        headers={**HEADERS, 'Content-Type':'application/json'},
        json={'page':2, 'y':y, 'end_page':2, 'section_label':'Referencias'},
    )
    assert r.status_code == 200, r.text
    c = r.json()
    assert 'Alonso Mielgo' in c['text']
    assert c['before_ref_id'] == known['id']
    r = client.post(
        f"/api/documents/{doc['id']}/references",
        headers={**HEADERS, 'Content-Type':'application/json'},
        json={
            'text':c['text'], 'start_page':c['start_page'], 'end_page':c['end_page'],
            'start_y':c['start_y'], 'before_ref_id':c['before_ref_id'], 'source':'human_pdf_click'
        },
    )
    assert r.status_code == 200, r.text
    refs = r.json()['references']
    assert 'Alonso Mielgo' in refs[0]['text']
    assert refs[0]['source'] == 'human_pdf_click'
    assert 'Altieri' in refs[1]['text']
