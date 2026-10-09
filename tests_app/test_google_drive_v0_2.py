from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
from biblioref.integrations import google_drive as gd


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Files:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return _Req(self.pages.pop(0))


class _Svc:
    def __init__(self, pages):
        self._files = _Files(pages)

    def files(self):
        return self._files


def test_drive_v02_contract_is_read_only_and_searchable(monkeypatch, tmp_path):
    monkeypatch.setattr(gd, "GOOGLE_DRIVE_LIBS_AVAILABLE", False)
    monkeypatch.setattr(gd, "default_client_secret_path", lambda: tmp_path / "missing.json")
    st = gd.status()
    assert gd.GOOGLE_DRIVE_INTEGRATION_VERSION == "google-drive-readonly-0.2"
    assert st["read_only"] is True
    assert st["auth_mode"] == "user_oauth_desktop"
    assert st["capabilities"]["search"] is True
    assert st["capabilities"]["write_drive"] is False
    assert st["scope"] == "drive.readonly"


def test_drive_search_filters_supported_items_and_caps_results(monkeypatch):
    svc = _Svc([{"files": [
        {"id": "p1", "name": "tesis psicologia.pdf", "mimeType": gd.PDF_MIME, "size": "100"},
        {"id": "x1", "name": "tesis video.mp4", "mimeType": "video/mp4"},
        {"id": "d1", "name": "Tesis 2024", "mimeType": gd.FOLDER_MIME},
        {"id": "z1", "name": "tesis lote.zip", "mimeType": "application/zip"},
    ]}])
    monkeypatch.setattr(gd, "service", lambda: svc)
    out = gd.search_items("tesis", max_results=2)
    assert [x["id"] for x in out["items"]] == ["p1", "d1"]
    assert out["limit"] == 2
    assert len(out["items"]) == 2
    call = svc._files.calls[0]
    assert "name contains 'tesis'" in call["q"]
    assert call["spaces"] == "drive"
    assert call["supportsAllDrives"] is True
    assert call["includeItemsFromAllDrives"] is True


def test_drive_search_escapes_query_literal(monkeypatch):
    svc = _Svc([{"files": []}])
    monkeypatch.setattr(gd, "service", lambda: svc)
    out = gd.search_items("O'Brien \\ tesis")
    assert out["query"] == "O'Brien \\ tesis"
    q = svc._files.calls[0]["q"]
    assert "O\\'Brien" in q
    assert "\\\\ tesis" in q


def test_drive_search_rejects_tiny_or_excessive_terms():
    with pytest.raises(gd.GoogleDriveError, match="2 caracteres"):
        gd.search_items("x")
    with pytest.raises(gd.GoogleDriveError, match="demasiado larga"):
        gd.search_items("x" * 201)


def test_drive_search_api_is_mockable_and_does_not_write(monkeypatch):
    seen = {}

    def fake_search(q, *, max_results=100):
        seen.update(q=q, max_results=max_results)
        return {
            "query": q,
            "items": [{"id": "p1", "name": "tesis.pdf", "is_folder": False}],
            "limit": max_results,
            "truncated": False,
            "integration_version": gd.GOOGLE_DRIVE_INTEGRATION_VERSION,
        }

    monkeypatch.setattr(app_module.gdrive, "search_items", fake_search)
    client = TestClient(app_module.app)
    response = client.get("/api/integrations/google-drive/search?q=tesis&limit=25")
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "tesis.pdf"
    assert seen == {"q": "tesis", "max_results": 25}


def test_drive_frontend_exposes_search_account_and_guided_setup():
    root = Path(__file__).resolve().parents[1]
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    assert "/api/integrations/google-drive/search" in js
    assert "driveSearchInput" in js
    assert "Buscar en todo Drive" in js
    assert "Cuenta conectada" in js
    assert "Google Drive API" in js
    assert "Aplicación de escritorio" in js
    assert "drive.readonly" in js
    assert "solo lectura" in js.lower()
