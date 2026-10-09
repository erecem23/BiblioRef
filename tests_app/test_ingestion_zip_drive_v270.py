from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from biblioref.ingestion.archives import ZipIngestionError, extract_pdfs_from_zip
from biblioref.integrations import google_drive as gd


def fake_pdf(label: str = "x") -> bytes:
    # ZIP ingestion only validates the PDF signature; the normal app preflight
    # is responsible for validating a real PDF before registration.
    return b"%PDF-1.4\n% " + label.encode() + b"\n%%EOF\n"


def make_zip(path: Path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)


def test_zip_recursively_finds_pdfs_and_ignores_other_files(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("nested/second.PDF", fake_pdf("second"))
        z.writestr("nested/readme.txt", b"ignore")
    archive = tmp_path / "batch.zip"
    make_zip(archive, {
        "tesis/first.pdf": fake_pdf("first"),
        "notes.txt": b"ignore",
        "sub/bundle.zip": inner.getvalue(),
    })
    out = tmp_path / "out"
    pdfs, warnings = extract_pdfs_from_zip(archive, out)
    assert [p.display_name for p in pdfs] == ["first.pdf", "second.PDF"]
    assert all(p.path.exists() for p in pdfs)
    assert pdfs[0].archive_member == "tesis/first.pdf"
    assert pdfs[1].archive_member == "nested/second.PDF"
    assert len(pdfs[0].sha256) == 64
    assert warnings == []


def test_zip_rejects_path_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    make_zip(archive, {"../escape.pdf": fake_pdf()})
    with pytest.raises(ZipIngestionError, match="Ruta insegura"):
        extract_pdfs_from_zip(archive, tmp_path / "out")


def test_zip_rejects_fake_pdf_content(tmp_path):
    archive = tmp_path / "fake.zip"
    make_zip(archive, {"not_really.pdf": b"plain text"})
    pdfs, warnings = extract_pdfs_from_zip(archive, tmp_path / "out")
    assert pdfs == []
    assert warnings and "contenido no reconocido" in warnings[0]


def test_google_client_secret_validation_and_local_save(tmp_path):
    payload = {
        "installed": {
            "client_id": "id.apps.googleusercontent.com",
            "client_secret": "secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    target = tmp_path / "client.json"
    gd.save_client_secret_bytes(json.dumps(payload).encode(), target)
    assert target.exists()
    assert gd.validate_client_secret_data(json.loads(target.read_text())) == payload


def test_google_client_secret_rejects_unrelated_json():
    with pytest.raises(gd.GoogleDriveError, match="OAuth"):
        gd.validate_client_secret_data({"hello": "world"})


def test_drive_supported_item_is_conservative():
    assert gd.supported_item({"name": "tesis.pdf", "mimeType": "application/pdf"})
    assert gd.supported_item({"name": "lote.zip", "mimeType": "application/octet-stream"})
    assert gd.supported_item({"name": "carpeta", "mimeType": gd.FOLDER_MIME})
    assert not gd.supported_item({"name": "video.bin", "mimeType": "application/octet-stream"})


def test_drive_shortcut_uses_target_identity_and_mime():
    item = {
        "id": "shortcut",
        "name": "tesis.pdf",
        "mimeType": gd.SHORTCUT_MIME,
        "shortcutDetails": {"targetId": "real", "targetMimeType": "application/pdf"},
    }
    assert gd.effective_id(item) == "real"
    assert gd.effective_mime(item) == "application/pdf"
    assert gd.supported_item(item)


def test_drive_list_folder_filters_to_supported_items(monkeypatch):
    class Req:
        def __init__(self, payload): self.payload = payload
        def execute(self): return self.payload
    class Files:
        def list(self, **kwargs):
            return Req({"files": [
                {"id":"f1","name":"tesis.pdf","mimeType":"application/pdf","size":"100"},
                {"id":"z1","name":"lote.zip","mimeType":"application/octet-stream","size":"200"},
                {"id":"d1","name":"carpeta","mimeType":gd.FOLDER_MIME},
                {"id":"x1","name":"video.mp4","mimeType":"video/mp4"},
            ]})
        def get(self, **kwargs): return Req({"id":kwargs["fileId"],"name":"Mi unidad"})
    class Svc:
        def files(self): return Files()
    monkeypatch.setattr(gd, "service", lambda: Svc())
    data = gd.list_folder("root")
    assert [x["name"] for x in data["items"]] == ["tesis.pdf", "lote.zip", "carpeta"]
    assert data["items"][2]["is_folder"] is True
