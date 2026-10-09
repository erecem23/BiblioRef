from pathlib import Path

from fastapi.testclient import TestClient

import app as app_module


client = TestClient(app_module.app)


def _headers():
    return {"X-BiblioRef-Token": app_module.APP_TOKEN}


def _doc():
    return {
        "id": "doc_test",
        "references": [{
            "id": "r1",
            "order": 1,
            "text": "Smith, J. (2020). Example article.",
            "original_text": "Smith, J. (2020). Example article.",
            "parsed": {
                "parser_version": app_module.PARSER_VERSION,
                "author": "Smith, J.",
                "authors": ["Smith, J."],
                "year": "2020",
                "title": "Example article",
                "publication_type": "articulo_revista",
            },
            "status": "extracted",
            "source": "automatic",
            "edited": False,
            "deleted": False,
        }],
        "corrections": [],
        "updated_at": 0,
    }


def test_resolution_endpoint_persists_only_external_deterministic_sidecars(monkeypatch):
    doc = _doc()
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    class Result:
        def as_dict(self):
            return {
                "version": "interactive-resolution-v0.1",
                "requested_layers": ["crossref", "consensus", "decision"],
                "executed_layers": ["crossref", "consensus", "decision"],
                "query": {"raw_reference": doc["references"][0]["text"]},
                "batch": {"status": "candidates_found", "candidate_count": 1, "backend_errors": []},
                "candidates": [{
                    "candidate_index": 0,
                    "source": "crossref",
                    "source_id": "10.1000/example",
                    "title": "Example article",
                    "authors": ["Smith, J."],
                    "year": "2020",
                    "container_title": "Journal",
                    "publisher": "Publisher",
                    "doi": "10.1000/example",
                    "work_type": "journal-article",
                    "url": "https://doi.org/10.1000/example",
                    "retrieval_method": "doi_exact",
                    "provider_score": None,
                    "rank": 1,
                    "identity_key": "doi:10.1000/example",
                }],
                "consensus": {"status": "probable_candidate", "assessments": [], "leading_candidate_index": 0},
                "semantic": None,
                "rag": None,
                "adjudication": None,
                "decision": {"status": "POSSIBLE_MATCH", "selected_candidate_index": 0},
                "layer_errors": {},
                "notes": ["local_model_runtime_is_disabled"],
            }

    class Runner:
        def __init__(self, **kwargs):
            assert kwargs == {}

        def run(self, **kwargs):
            assert kwargs["parsed"]["title"] == "Example article"
            assert kwargs["layers"] == ["crossref", "consensus", "decision"]
            return Result()

    monkeypatch.setattr(app_module, "InteractiveResolutionRunner", Runner)
    before_parsed = dict(doc["references"][0]["parsed"])
    response = client.post(
        "/api/documents/doc_test/references/r1/resolve",
        headers=_headers(),
        json={"layers": ["crossref", "consensus", "decision"]},
    )
    assert response.status_code == 200
    row = response.json()
    assert row["parsed"] == before_parsed
    assert row["resolution_decision"]["status"] == "POSSIBLE_MATCH"
    assert row["resolver_candidates"][0]["doi"] == "10.1000/example"
    assert "rag_result" not in row
    assert "adjudication" not in row
    assert "rag_adjudication" not in row


def test_human_confirmation_is_audit_sidecar_only(monkeypatch):
    doc = _doc()
    ref = doc["references"][0]
    ref["resolver_candidates"] = [{
        "candidate_index": 0,
        "source": "crossref",
        "source_id": "10.1000/example",
        "title": "Example article",
        "authors": ["Smith, J."],
        "year": "2020",
        "doi": "10.1000/example",
        "identity_key": "doi:10.1000/example",
    }]
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    response = client.post(
        "/api/documents/doc_test/references/r1/human-resolution",
        headers=_headers(),
        json={"decision": "candidate", "candidate_index": 0},
    )
    assert response.status_code == 200
    row = response.json()
    assert row["human_resolution"]["status"] == "human_confirmed"
    assert row["human_resolution"]["identity_key"] == "doi:10.1000/example"
    assert "evidence_id" not in row["human_resolution"]
    assert doc["corrections"][-1]["kind"] == "human_resolution_confirmation"


def test_local_chat_http_surface_is_absent(monkeypatch):
    doc = _doc()
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    response = client.post(
        "/api/documents/doc_test/references/r1/local-chat",
        headers=_headers(),
        json={"question": "¿Por qué coincide?"},
    )
    assert response.status_code == 404


def test_raw_edit_invalidates_old_resolution_and_local_sidecars(monkeypatch):
    doc = _doc()
    ref = doc["references"][0]
    ref["resolution_decision"] = {"status": "POSSIBLE_MATCH"}
    ref["resolver_candidates"] = [{"candidate_index": 0}]
    ref["llm_chat"] = {"messages": [{"role": "user", "content": "legacy"}]}
    ref["rag_result"] = {"status": "legacy"}
    ref["human_resolution"] = {"status": "human_confirmed", "candidate_index": 0}
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    response = client.patch(
        "/api/documents/doc_test/references/r1",
        headers=_headers(),
        json={"text": "Smith, J. (2021). Changed article."},
    )
    assert response.status_code == 200
    row = response.json()
    assert "resolution_decision" not in row
    assert "resolver_candidates" not in row
    assert "llm_chat" not in row
    assert "rag_result" not in row
    assert "human_resolution" not in row


def test_frontend_excludes_local_runtime_controls():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="localChatPanel"' not in html
    assert 'id="localChatInput"' not in html
    assert "/local-chat" not in js
    assert "Abrir chat local" not in js
    assert "LLM adjudicador y chat" not in js
    assert "/human-resolution" in js
    assert "/resolve" in js
    assert "Confirmar esta" in js
    assert "Ninguna coincide" in js
