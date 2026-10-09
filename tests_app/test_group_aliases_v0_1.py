# -*- coding: utf-8 -*-
"""Group aliases v0.1.

Two labels that look alike are sometimes two different places, so nothing here
merges on its own. What is under test is that the suggestion is good, that the
decision is the user's, that it survives a rebuilt sidecar, and that the
original spelling is never overwritten.
"""
import json

import pytest
from fastapi.testclient import TestClient

from biblioref.derived import open_store, sync_documents
from biblioref.derived.aliases import apply_alias, canonical_form, similarity, suggest_aliases

UNLP = "Universidad Nacional de La Plata"
UNLP_CORTA = "Universidad de La Plata"
UNC = "Universidad Nacional de Córdoba"


def _parsed(**over):
    base = {
        "parser_version": "p", "author": "Smith, John", "authors": "Smith, John",
        "year": "2010", "title": "Machine learning in psychology", "journal": "J",
        "publisher": None, "doi": None, "publication_type": "articulo_revista",
    }
    base.update(over)
    return base


def _doc(doc_id, university, project_id="p1"):
    return {
        "id": doc_id, "thesis_id": doc_id, "title": f"Tesis {doc_id}", "filename": f"{doc_id}.pdf",
        "project_id": project_id, "n_references": 1, "content_sha256": doc_id, "updated_at": 1,
        "metadata": {"university": university, "year": "2020"},
        "references": [{
            "id": f"{doc_id}r", "order": 1, "text": f"ref {doc_id}", "original_text": "",
            "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
            "edited": False, "deleted": False,
            "parsed": _parsed(title=f"Un titulo suficientemente largo {doc_id}"),
        }],
    }


def _store(*docs, aliases=None):
    project = {"id": "p1", "name": "Proyecto"}
    if aliases:
        project["group_aliases"] = aliases
    return {"schema": 2, "projects": {"p1": project}, "documents": {d["id"]: d for d in docs}}


@pytest.fixture
def conn(tmp_path):
    return open_store(tmp_path / "derived.sqlite3")


def test_the_two_spellings_of_one_university_are_recognised():
    assert canonical_form(UNLP) == canonical_form(UNLP_CORTA)
    assert similarity(UNLP, UNLP_CORTA) == 1.0


def test_two_different_universities_are_not():
    assert similarity(UNLP, UNC) < 0.5
    assert similarity("Universidad Nacional del Litoral", "Universidad Nacional del Sur") < 0.5


def test_a_suggestion_is_offered_but_nothing_is_merged(conn):
    sync_documents(conn, _store(_doc("d1", UNLP), _doc("d2", UNLP), _doc("d3", UNLP_CORTA)))

    got = suggest_aliases(conn, "university")

    assert len(got) == 1
    assert got[0]["suggested_canonical"] == UNLP        # el grupo más grande
    assert got[0]["suggested_variant"] == UNLP_CORTA
    assert got[0]["identical_once_normalised"] is True
    # y siguen contándose por separado hasta que alguien decida
    assert conn.execute(
        "SELECT COUNT(DISTINCT university) AS n FROM document").fetchone()["n"] == 2


def test_universities_that_only_share_a_prefix_are_not_suggested(conn):
    sync_documents(conn, _store(_doc("d1", UNLP), _doc("d2", UNC)))
    assert suggest_aliases(conn, "university") == []


def test_a_confirmed_alias_unifies_the_group(conn):
    store = _store(_doc("d1", UNLP), _doc("d2", UNLP), _doc("d3", UNLP_CORTA),
                   aliases={"university": {UNLP_CORTA: UNLP}})
    sync_documents(conn, store)

    rows = {r["university"]: r["n"] for r in conn.execute(
        "SELECT university, COUNT(*) AS n FROM document GROUP BY university")}
    assert rows == {UNLP: 3}


def test_the_original_spelling_is_never_overwritten(conn):
    store = _store(_doc("d3", UNLP_CORTA), aliases={"university": {UNLP_CORTA: UNLP}})
    sync_documents(conn, store)

    assert store["documents"]["d3"]["metadata"]["university"] == UNLP_CORTA


def test_a_chain_of_aliases_lands_on_the_canonical_label():
    aliases = {"UNLP": "Universidad de La Plata", "Universidad de La Plata": UNLP}
    assert apply_alias("UNLP", aliases) == UNLP


def test_a_cycle_stops_instead_of_hanging():
    assert apply_alias("A", {"A": "B", "B": "A"}) in {"A", "B"}


def test_an_alias_is_not_suggested_again_once_decided(conn):
    store = _store(_doc("d1", UNLP), _doc("d2", UNLP), _doc("d3", UNLP_CORTA),
                   aliases={"university": {UNLP_CORTA: UNLP}})
    sync_documents(conn, store)
    assert suggest_aliases(conn, "university", known={UNLP_CORTA: UNLP}) == []


# --- API ---------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(app_module, "STATE_FILE", tmp_path / "project.json")
    saved = app_module.STORE.data
    app_module.STORE.data = _store(_doc("d1", UNLP), _doc("d2", UNLP), _doc("d3", UNLP_CORTA))
    api = TestClient(app_module.app)
    api.headers["X-BiblioRef-Token"] = app_module.APP_TOKEN
    try:
        yield api, app_module
    finally:
        app_module.STORE.data = saved


def test_the_api_offers_the_suggestion_after_a_run(client):
    api, _ = client
    api.post("/api/analysis/run", json={"project_id": "p1"})

    got = api.get("/api/analysis/alias-suggestions", params={"project_id": "p1"}).json()

    assert got["aliasable"] is True
    assert len(got["suggestions"]) == 1
    assert got["suggestions"][0]["suggested_canonical"] == UNLP


def test_confirming_the_alias_merges_the_group_on_the_next_run(client):
    api, app_module = client
    api.post("/api/analysis/run", json={"project_id": "p1"})
    before = api.get("/api/analysis", params={"project_id": "p1"}).json()
    assert len(before["report"]["groups"]["groups"]) == 2

    api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP_CORTA, "canonical": UNLP})

    assert api.get("/api/analysis", params={"project_id": "p1"}).json()["status"] == "stale"
    after = api.post("/api/analysis/run", json={"project_id": "p1"}).json()
    groups = after["report"]["groups"]["groups"]
    assert len(groups) == 1
    assert groups[0]["group"] == UNLP
    assert groups[0]["theses"] == 3


def test_the_decision_is_stored_in_the_project_not_in_the_sidecar(client):
    api, app_module = client
    api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP_CORTA, "canonical": UNLP})

    stored = app_module.STORE.data["projects"]["p1"]["group_aliases"]["university"]
    assert stored == {UNLP_CORTA: UNLP}


def test_an_alias_can_be_undone(client):
    api, app_module = client
    api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP_CORTA, "canonical": UNLP})
    api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP_CORTA, "canonical": ""})

    assert "university" not in app_module.STORE.data["projects"]["p1"].get("group_aliases", {})
    after = api.post("/api/analysis/run", json={"project_id": "p1"}).json()
    assert len(after["report"]["groups"]["groups"]) == 2


def test_an_alias_that_would_invert_an_existing_one_is_refused(client):
    api, _ = client
    api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP_CORTA, "canonical": UNLP})

    got = api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "university", "variant": UNLP, "canonical": UNLP_CORTA})
    assert got.status_code == 400


def test_a_field_that_cannot_be_unified_is_refused(client):
    api, _ = client
    got = api.post("/api/analysis/aliases", json={
        "project_id": "p1", "field": "thesis_year", "variant": "2020", "canonical": "2021"})
    assert got.status_code == 400


def test_suggestions_for_a_non_aliasable_grouping_are_empty_not_an_error(client):
    api, _ = client
    got = api.get("/api/analysis/alias-suggestions", params={"project_id": "p1", "group_by": "thesis_year"}).json()
    assert got["aliasable"] is False
    assert got["suggestions"] == []
