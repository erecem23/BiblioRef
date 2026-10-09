"""Project persistence, import provenance and isolation across real API calls."""
from copy import deepcopy
import io
import json
from pathlib import Path
import zipfile

from tests_support import pdf_factory as fitz
import pytest
from fastapi.testclient import TestClient
import app as app_module
from biblioref.projects import project_tree


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(app_module, "STATE_FILE", tmp_path / "project.json")
    for attr, folder in [("UPLOAD_DIR", "pdfs"), ("RESULT_DIR", "results")]:
        path = tmp_path / folder
        path.mkdir()
        monkeypatch.setattr(app_module, attr, path)
    monkeypatch.setattr(app_module, "STORE", app_module.Store())
    with TestClient(app_module.app) as client:
        client.headers["X-BiblioRef-Token"] = app_module.APP_TOKEN
        yield client


_PDF_SERIAL = iter(range(1, 1_000_000))


def pdf():
    # The neutral PDF writer is byte-deterministic; a distinct metadata serial
    # keeps repeated fixtures from being rejected as duplicate files.
    with fitz.open() as document:
        document.set_metadata({"subject": f"fixture-{next(_PDF_SERIAL)}"})
        page = document.new_page()
        page.insert_text((50, 80), "Universidad Nacional de La Plata", fontsize=18)
        page.insert_text((50, 150), "Un corpus para probar proyectos", fontsize=20)
        return document.tobytes()


def create(client, name):
    r = client.post("/api/projects", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def upload(client, project, path="tesis.pdf", data=None):
    return client.post("/api/documents", data={"project_id": project},
                       files=[("files", (path, data or pdf(), "application/pdf"))])


def test_projects_persist_and_scope_same_named_documents(client):
    assert client.get("/api/projects").json()["projects"] == []
    a, b = create(client, "Corpus A"), create(client, "Corpus B")
    first = upload(client, a).json()["documents"][0]
    second = upload(client, b).json()["documents"][0]
    assert first["id"] != second["id"]
    assert first["project_id"] == a and second["project_id"] == b
    r = client.patch(f"/api/projects/{a}", json={"name": "Corpus editado"})
    assert r.status_code == 200
    app_module.STORE.data = {}
    app_module.STORE.load()
    assert client.get(f"/api/documents?project_id={a}").json()["documents"][0]["id"] == first["id"]
    assert client.get(f"/api/documents?project_id={b}").json()["documents"][0]["id"] == second["id"]
    client.post(f"/api/projects/{a}/open")
    projects = client.get("/api/projects").json()["projects"]
    assert projects[0]["name"] == "Corpus editado"
    assert all(p["n_documents"] == 1 for p in projects)
    assert all("documents" not in p for p in projects)


def test_legacy_migration_preserves_pdf_references_and_corrections(client):
    d = client.post("/api/documents", files=[("files", ("anterior.pdf", pdf()))]).json()["documents"][0]
    stored = app_module.STORE.docs()[d["id"]]
    stored.pop("project_id")
    stored["references"] = [{"text": "Texto crudo", "parsed": {"author": "Autor"}, "edited": True}]
    stored["corrections"] = [{"kind": "human_edit", "text": "Corrección"}]
    app_module.STORE.data.pop("projects")
    before = deepcopy(stored)
    original_pdf = Path(stored["path"]).read_bytes()
    projects = client.get("/api/projects").json()["projects"]
    assert len(projects) == 1 and projects[0]["name"] == "Proyecto anterior"
    assert {k: v for k, v in stored.items() if k != "project_id"} == before
    assert Path(stored["path"]).read_bytes() == original_pdf


def test_directory_and_nested_zip_keep_distinct_hierarchy(client):
    p = create(client, "Estructura")
    r = upload(client, p, "Corpus/UNLP/Psicología/tesis.pdf")
    assert r.status_code == 200, r.text
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("UNC/Historia/tesis.pdf", pdf())
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("Lote/interno.zip", inner.getvalue())
        archive.writestr("UNMdP/tesis.pdf", pdf())
    assert upload(client, p, "paquete.zip", outer.getvalue()).status_code == 200
    tree = client.get(f"/api/projects/{p}/tree").json()["nodes"]
    corpus = next(n for n in tree if n["name"] == "Corpus")
    assert corpus["children"][0]["name"] == "UNLP"
    assert corpus["children"][0]["children"][0]["name"] == "Psicología"
    assert next(n for n in tree if n["name"] == "Lote")["children"][0]["name"] == "interno.zip"
    assert next(n for n in tree if n["name"] == "UNMdP")["count"] == 1


def test_university_groups_only_loose_files_and_does_not_edit_metadata(client):
    p = create(client, "Organización")
    a = upload(client, p, "Carpeta elegida/tesis.pdf").json()["documents"][0]
    b = upload(client, p, "suelta.pdf").json()["documents"][0]
    for d in (a, b):
        original = app_module.STORE.docs()[d["id"]]
        original["metadata"] = {"university": "Universidad sugerida"}
        original["metadata_detection"] = {"suggestions": {"university": "Universidad sugerida"}}
    before = deepcopy(app_module.STORE.docs())
    client.patch(f"/api/projects/{p}", json={"group_loose_by_university": True})
    tree = client.get(f"/api/projects/{p}/tree").json()["nodes"]
    assert [n["name"] for n in tree] == ["Carpeta elegida", "Universidad sugerida"]
    assert tree[1]["children"][0]["university_suggested"] is True
    assert app_module.STORE.docs() == before
    client.patch(f"/api/projects/{p}", json={"group_loose_by_university": False})
    assert any(n["kind"] == "document" for n in client.get(f"/api/projects/{p}/tree").json()["nodes"])


def test_failed_import_does_not_lose_successful_files_and_rejects_traversal(client):
    p = create(client, "Carga parcial")
    r = client.post("/api/documents", data={"project_id": p}, files=[
        ("files", ("UNLP/buena.pdf", pdf())),
        ("files", ("mala.pdf", b"broken")),
        ("files", ("../escape.pdf", pdf())),
    ])
    assert r.status_code == 200, r.text
    assert len(r.json()["documents"]) == 1
    assert len(r.json()["warnings"]) == 2
    app_module.STORE.load()
    assert len(app_module.STORE.docs()) == 1
    assert upload(client, "project_does_not_exist").status_code == 404
    assert client.post("/api/projects", json={"name": "   "}).status_code == 422


def test_export_selection_remains_scoped_after_opening_another_project(client):
    a, b = create(client, "A"), create(client, "B")
    da = upload(client, a).json()["documents"][0]
    db = upload(client, b).json()["documents"][0]
    client.post(f"/api/documents/{da['id']}/references", json={"text": "Autor, A. (2024). Obra A.", "start_page": 1})
    client.post(f"/api/documents/{db['id']}/references", json={"text": "Otro, B. (2023). Obra B.", "start_page": 1})
    client.post(f"/api/projects/{b}/open")
    text = client.get(f"/api/project/export/selection/csv?documents={da['id']}").content.decode("utf-8-sig")
    assert "Obra A" in text and "Obra B" not in text


def test_home_markup_contains_only_projects(client):
    html = client.get("/").text
    home = html.split('<section id="screen-new"')[1].split('</section>')[0]
    assert 'id="recentProjects"' in home
    assert 'id="uploadCards"' not in home and 'id="fileInput"' not in home


def test_import_reads_title_once_and_preserves_cover_result(client, monkeypatch):
    from biblioref.metadata import integration
    integration.install_cover_metadata(app_module)
    original = integration.detect_thesis_title
    calls = []

    def counted(path, filename, **kwargs):
        calls.append(filename)
        return original(path, filename, **kwargs)

    monkeypatch.setattr(integration, "detect_thesis_title", counted)
    p = create(client, "Lectura eficiente")
    doc = upload(client, p).json()["documents"][0]
    assert calls == ["tesis.pdf"]
    stored = app_module.STORE.docs()[doc["id"]]
    expected = integration._combined_detection(Path(stored["path"]), "tesis.pdf")
    assert stored["title"] == expected["title"]
    assert stored["metadata_detection"] == integration._detection_public(expected)


def test_current_documents_do_not_reread_titles_or_covers_on_get(client, monkeypatch):
    from biblioref.metadata import integration
    integration.install_cover_metadata(app_module)
    p = create(client, "Sin relecturas")
    doc = upload(client, p).json()["documents"][0]
    before = deepcopy(app_module.STORE.docs()[doc["id"]])

    def unexpected(*args, **kwargs):
        raise AssertionError("Una tesis actualizada no debe volver a leer su PDF")

    monkeypatch.setattr(app_module, "_detect_thesis_title", unexpected)
    monkeypatch.setattr(integration, "_combined_detection", unexpected)
    for _ in range(2):
        assert client.get(f"/api/documents?project_id={p}").status_code == 200
        assert client.get(f"/api/documents/{doc['id']}").status_code == 200
    assert app_module.STORE.docs()[doc["id"]] == before
