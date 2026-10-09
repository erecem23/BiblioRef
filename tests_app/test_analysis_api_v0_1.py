# -*- coding: utf-8 -*-
"""Analysis API v0.1.

The behaviour under test is the one the user asked for: the analysis is a
result you request, not something the app computes when a screen opens.
"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point the app at a scratch workspace without reloading the module.

    Reloading regenerates ``APP_TOKEN``, and other suites capture it at import
    time, so a reload here makes their requests fail. The endpoints read
    ``WORKSPACE`` when called, so patching the attribute is enough.
    """
    import app as app_module

    monkeypatch.setattr(app_module, "WORKSPACE", tmp_path)
    saved = app_module.STORE.data
    app_module.STORE.data = {"schema": 2, "documents": {}}
    api = TestClient(app_module.app)
    api.headers["X-BiblioRef-Token"] = app_module.APP_TOKEN
    try:
        yield api, app_module
    finally:
        app_module.STORE.data = saved


def _parsed(**over):
    base = {
        "parser_version": "p", "author": "Smith, John", "authors": "Smith, John",
        "year": "2010", "title": "Machine learning in psychology", "journal": "Journal of X",
        "publisher": None, "doi": None, "publication_type": "articulo_revista",
    }
    base.update(over)
    return base


def _seed(app_module, refs=None):
    refs = refs if refs is not None else [{
        "id": "r1", "order": 1, "text": "una referencia", "original_text": "una referencia",
        "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
        "edited": False, "deleted": False, "parsed": _parsed(),
    }]
    app_module.STORE.data = {
        "schema": 2,
        "documents": {
            "d1": {
                "id": "d1", "thesis_id": "T-1", "title": "Tesis", "filename": "t.pdf",
                "project_id": "p1", "n_references": len(refs), "content_sha256": "x",
                "updated_at": 1, "metadata": {"university": "UNMdP", "year": "2020"},
                "references": refs,
            }
        },
    }


def test_the_analysis_is_not_computed_until_it_is_requested(client):
    api, app_module = client
    _seed(app_module)

    got = api.get("/api/analysis").json()

    assert got["status"] == "never_run"
    assert got["report"] is None


def test_running_it_returns_the_report_and_stores_it(client):
    api, app_module = client
    _seed(app_module)

    ran = api.post("/api/analysis/run", json={"group_by": "university"}).json()
    assert ran["status"] == "current"
    assert ran["report"]["coverage"]["references"] == 1
    assert ran["sync"]["references"]["inserted"] == 1

    again = api.get("/api/analysis").json()
    assert again["status"] == "current"
    assert again["generated_at"] == ran["generated_at"]


def test_a_changed_corpus_is_reported_as_stale_not_recomputed(client):
    api, app_module = client
    _seed(app_module)
    api.post("/api/analysis/run", json={"group_by": "university"})

    _seed(app_module, refs=[{
        "id": "r1", "order": 1, "text": "corregida", "original_text": "una referencia",
        "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
        "edited": True, "deleted": False,
        "parsed": _parsed(title="Un titulo corregido a mano por el usuario"),
    }])

    got = api.get("/api/analysis").json()
    assert got["status"] == "stale"
    assert got["report"]["coverage"]["references"] == 1     # sigue siendo el viejo


def test_an_unsupported_grouping_is_refused(client):
    api, _ = client
    assert api.get("/api/analysis", params={"group_by": "doi"}).status_code == 400
    assert api.post("/api/analysis/run", json={"group_by": "doi"}).status_code == 400


def test_export_before_any_run_is_a_404_not_an_empty_file(client):
    api, app_module = client
    _seed(app_module)
    assert api.get("/api/analysis/export.json").status_code == 404


def test_export_returns_the_stored_report_as_a_download(client):
    api, app_module = client
    _seed(app_module)
    api.post("/api/analysis/run", json={"group_by": "university"})

    got = api.get("/api/analysis/export.json")
    assert got.status_code == 200
    assert "attachment" in got.headers["content-disposition"]
    assert json.loads(got.text)["report"]["coverage"]["references"] == 1


def test_running_the_analysis_does_not_write_to_the_project_store(client):
    api, app_module = client
    _seed(app_module)
    before = json.dumps(app_module.STORE.data, sort_keys=True, default=str)

    api.post("/api/analysis/run", json={"group_by": "university"})

    assert json.dumps(app_module.STORE.data, sort_keys=True, default=str) == before


def test_each_grouping_is_requested_separately(client):
    api, app_module = client
    _seed(app_module)
    api.post("/api/analysis/run", json={"group_by": "university"})

    assert api.get("/api/analysis", params={"group_by": "program"}).json()["status"] == "never_run"
    assert api.get("/api/analysis", params={"group_by": "university"}).json()["status"] == "current"


def _seed_two_projects(app_module):
    def doc(doc_id, project_id, title):
        return {
            "id": doc_id, "thesis_id": doc_id, "title": title, "filename": f"{doc_id}.pdf",
            "project_id": project_id, "n_references": 1, "content_sha256": doc_id, "updated_at": 1,
            "metadata": {"university": "UNMdP", "year": "2020"},
            "references": [{
                "id": f"{doc_id}r", "order": 1, "text": f"ref {doc_id}", "original_text": "",
                "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
                "edited": False, "deleted": False,
                "parsed": _parsed(title=f"Un titulo suficientemente largo {doc_id}"),
            }],
        }
    app_module.STORE.data = {
        "schema": 2,
        "documents": {
            "a1": doc("a1", "pA", "Tesis A"),
            "b1": doc("b1", "pB", "Tesis B"),
            "b2": doc("b2", "pB", "Tesis B2"),
        },
    }


def test_a_report_covers_only_its_own_project(client):
    api, app_module = client
    _seed_two_projects(app_module)

    a = api.post("/api/analysis/run", json={"project_id": "pA"}).json()
    b = api.post("/api/analysis/run", json={"project_id": "pB"}).json()

    assert a["report"]["coverage"]["documents"] == 1
    assert b["report"]["coverage"]["documents"] == 2
    assert a["report"]["coverage"]["references"] == 1
    assert b["report"]["coverage"]["references"] == 2


def test_editing_one_project_does_not_age_anothers_report(client):
    api, app_module = client
    _seed_two_projects(app_module)
    api.post("/api/analysis/run", json={"project_id": "pA"})
    api.post("/api/analysis/run", json={"project_id": "pB"})

    app_module.STORE.data["documents"]["b1"]["references"][0]["parsed"]["title"] = "Otro titulo corregido aca"

    assert api.get("/api/analysis", params={"project_id": "pA"}).json()["status"] == "current"
    assert api.get("/api/analysis", params={"project_id": "pB"}).json()["status"] == "stale"


def test_an_empty_project_is_refused_rather_than_analysed(client):
    api, app_module = client
    _seed_two_projects(app_module)
    assert api.post("/api/analysis/run", json={"project_id": "pZ"}).status_code == 404
