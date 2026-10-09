from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

import app as app_module


client = TestClient(app_module.app)


def _headers():
    return {"X-BiblioRef-Token": app_module.APP_TOKEN}


def test_raw_reference_edit_resets_stale_parsed_overrides(monkeypatch):
    doc = {
        "id": "doc_test",
        "references": [{
            "id": "r1",
            "order": 1,
            "text": "Smith, J. (2020). Old title.",
            "original_text": "Smith, J. (2020). Old title.",
            "parsed": {"parser_version": app_module.PARSER_VERSION, "title": "Old title"},
            "parsed_review": {"status": "edited", "overrides": {"title": "Human old title"}},
            "status": "extracted",
            "source": "automatic",
            "edited": False,
            "deleted": False,
        }],
        "corrections": [],
    }
    monkeypatch.setattr(app_module.STORE, "get", lambda doc_id: doc)
    monkeypatch.setattr(app_module.STORE, "save", lambda: None)

    response = client.patch(
        "/api/documents/doc_test/references/r1",
        headers=_headers(),
        json={"text": "Smith, J. (2021). New title.", "status": "reviewed"},
    )
    assert response.status_code == 200
    row = response.json()
    assert row["text"] == "Smith, J. (2021). New title."
    assert row["parsed_review"]["overrides"] == {}
    assert row["effective_parsed"] == row["parsed"]
    assert doc["corrections"][-1]["parsed_review_reset"] is True


def test_frontend_declares_pipeline_and_editable_spreadsheet_contract():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="layerOptions"' in html
    assert 'Planilla editable' in html
    assert 'parsed_review.overrides' in js
    assert 'effective_parsed' in js
    assert '/parsed-review' in js
    assert 'Referencia cruda' in js
    assert '<th>Resolución</th>' in js
    assert '<th>RAG</th>' not in js
    assert '<th>LLM</th>' not in js
    assert "x.mode!=='deferred_local'" in js
    assert 'runtime local está desactivado' in js


def test_frontend_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "--check", str(root / "static" / "app.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
