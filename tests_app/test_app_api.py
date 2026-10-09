import os
import tempfile
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ['BIBLIOREF_WORKSPACE'] = _tmp.name

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['software_version'] == '0.9.10-rc2'

def test_capabilities():
    r = client.get('/api/capabilities')
    assert r.status_code == 200
    body = r.json()
    assert body['imports']['pdf'] is True
    assert body['calibration']['manual_sections'] is True
    assert body['exports']['ris'] is False

def test_root():
    r = client.get('/')
    assert r.status_code == 200
    assert 'Referencias por tesis' in r.text
