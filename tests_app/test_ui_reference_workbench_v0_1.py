from fastapi.testclient import TestClient

import app as app_module


client = TestClient(app_module.app)


def _headers():
    return {"X-BiblioRef-Token": app_module.APP_TOKEN}


def test_capabilities_expose_processing_layers():
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    layers = {item["id"]: item for item in payload["layers"]}
    for key in (
        "extraction",
        "parser",
        "styleprofiler",
        "crossref",
        "openalex",
        "consensus",
        "semantic",
        "rag",
        "llm",
        "decision",
        "human_review",
    ):
        assert key in layers
    assert layers["crossref"]["interactive_execution"] is True
    assert layers["openalex"]["interactive_execution"] is True
    assert layers["consensus"]["interactive_execution"] is True
    assert layers["decision"]["interactive_execution"] is True
    assert layers["semantic"]["available"] is False
    assert layers["rag"]["available"] is False
    assert layers["llm"]["available"] is False
    assert layers["semantic"]["interactive_execution"] is False
    assert layers["rag"]["interactive_execution"] is False
    assert layers["llm"]["interactive_execution"] is False
    assert layers["styleprofiler"]["interactive_execution"] is False
    assert layers["parser"]["interactive_execution"] is True
    assert payload["local_runtime"] == {"enabled": False, "policy": "deferred", "active_components": []}


def test_public_reference_keeps_parser_and_exposes_effective_human_overlay():
    ref = {
        "id": "r1",
        "text": "Smith, J. (2020). Original title. Journal X.",
        "parsed": {
            "parser_version": app_module.PARSER_VERSION,
            "author": "Smith, J.",
            "year": "2020",
            "title": "Original title",
            "journal": "Journal X",
        },
        "parsed_review": {
            "status": "edited",
            "overrides": {"title": "Corrected title"},
        },
    }
    public = app_module._reference_with_parse(ref)
    assert public["parsed"]["title"] == "Original title"
    assert public["effective_parsed"]["title"] == "Corrected title"
    assert public["parsed_review"]["overrides"]["title"] == "Corrected title"
    assert ref["parsed"]["title"] == "Original title"


def test_parsed_review_endpoint_never_mutates_raw_reference_or_parser(monkeypatch):
    doc = {
        "id": "doc_test",
        "title": "Tesis",
        "references": [{
            "id": "r1",
            "order": 1,
            "text": "Smith, J. (2020). Original title. Journal X.",
            "original_text": "Smith, J. (2020). Original title. Journal X.",
            "parsed": {
                "parser_version": app_module.PARSER_VERSION,
                "author": "Smith, J.",
                "year": "2020",
                "title": "Original title",
                "journal": "Journal X",
            },
            "status": "extracted",
            "source": "automatic",
            "edited": False,
            "deleted": False,
        }],
        "corrections": [],
        "sections": [],
        "metadata": {},
        "analysis": {},
        "n_references": 1,
    }
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    response = client.patch(
        "/api/documents/doc_test/references/r1/parsed-review",
        headers=_headers(),
        json={"overrides": {"title": "Corrected title", "year": "2021"}},
    )
    assert response.status_code == 200
    row = response.json()
    assert row["text"] == "Smith, J. (2020). Original title. Journal X."
    assert row["parsed"]["title"] == "Original title"
    assert row["parsed"]["year"] == "2020"
    assert row["effective_parsed"]["title"] == "Corrected title"
    assert row["effective_parsed"]["year"] == "2021"
    assert row["parsed_review"]["status"] == "edited"
    assert doc["references"][0]["edited"] is False
    assert doc["corrections"][-1]["kind"] == "edit_parsed_fields"


def test_parsed_review_can_revert_one_field_without_touching_others(monkeypatch):
    doc = {
        "id": "doc_test",
        "title": "Tesis",
        "references": [{
            "id": "r1",
            "order": 1,
            "text": "Smith, J. (2020). Original title. Journal X.",
            "parsed": {
                "parser_version": app_module.PARSER_VERSION,
                "title": "Original title",
                "year": "2020",
            },
            "parsed_review": {"status": "edited", "overrides": {"title": "Corrected", "year": "2021"}},
            "status": "extracted",
            "source": "automatic",
            "edited": False,
            "deleted": False,
        }],
        "corrections": [],
        "sections": [],
        "metadata": {},
        "analysis": {},
        "n_references": 1,
    }
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    response = client.patch(
        "/api/documents/doc_test/references/r1/parsed-review",
        headers=_headers(),
        json={"unset_fields": ["title"]},
    )
    assert response.status_code == 200
    row = response.json()
    assert row["effective_parsed"]["title"] == "Original title"
    assert row["effective_parsed"]["year"] == "2021"
    assert "title" not in row["parsed_review"]["overrides"]


def test_parsed_review_rejects_unknown_field(monkeypatch):
    doc = {
        "id": "doc_test",
        "references": [{"id": "r1", "text": "x", "parsed": {"parser_version": app_module.PARSER_VERSION}, "deleted": False}],
        "corrections": [],
    }
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    response = client.patch(
        "/api/documents/doc_test/references/r1/parsed-review",
        headers=_headers(),
        json={"overrides": {"made_up_field": "x"}},
    )
    assert response.status_code == 400
