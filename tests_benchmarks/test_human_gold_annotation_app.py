"""Contract tests for the visual-only human-gold annotation application."""

import builtins
import hashlib
import importlib
import json
import os
import subprocess
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from tests_support import pdf_factory

# Starlette emits this during TestClient import on the pinned dependency set.
warnings.filterwarnings(
    "ignore",
    message="The anyio.abc.BlockingPortal alias is deprecated",
    category=DeprecationWarning,
    module="starlette.testclient",
)
from fastapi.testclient import TestClient


pytestmark = pytest.mark.filterwarnings(
    "ignore:The anyio.abc.BlockingPortal alias is deprecated:DeprecationWarning:starlette.testclient"
)


def _write_pdf(path: Path) -> bytes:
    pdf_factory.write_pdf(
        path,
        [[
            ("References", 24, 48, 11),
            ("1. Example reference", 24, 68, 11),
        ]],
        width=216,
        height=288,
    )
    return path.read_bytes()


def _write_manifest(path: Path, document_id: str, pdf_bytes: bytes) -> str:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    row = {
        "document_id": document_id,
        "partition": "pilot",
        "sha256": digest,
        "selected_before_biblioref_run": True,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return digest


def _annotation(document_id: str, digest: str, annotator: str = "ann-1", **overrides):
    value = {
        "document_id": document_id,
        "document_sha256": digest,
        "annotator_id": annotator,
        "annotation_complete": False,
        "document_has_target_bibliography": True,
        "zones": [
            {
                "gold_zone_id": "z001",
                "role": "references",
                "start_page": 1,
                "end_page": 1,
                "start_y_ratio": 0.1,
                "end_y_ratio": 0.9,
                "heading_present": True,
                "heading_text": "References",
                "references": [
                    {
                        "gold_ref_id": "z001-r0001",
                        "ordinal": 1,
                        "start_page": 1,
                        "start_y_ratio": 0.2,
                        "start_anchor": "1. Example reference",
                        "flags": [],
                    }
                ],
            }
        ],
        "full_text_sample_ids": [],
        "notes": "",
    }
    value.update(overrides)
    if value["annotation_complete"] and value["document_has_target_bibliography"]:
        value["full_text_sample_ids"] = ["z001-r0001"]
        value["zones"][0]["references"][0]["visible_text_gold"] = "1. Example reference"
    return value


def _build_app(tmp_path: Path, document_id: str = "doc-1"):
    from tools.human_gold.annotation_app import create_app

    cache = tmp_path / "cache"
    cache.mkdir()
    pdf_path = cache / f"{document_id}.pdf"
    pdf_bytes = _write_pdf(pdf_path)
    manifest = tmp_path / "manifest.jsonl"
    digest = _write_manifest(manifest, document_id, pdf_bytes)
    output = tmp_path / "work"
    app = create_app(manifest, cache, output, annotator_id="ann-1")
    return app, output, digest, cache, manifest


def test_annotation_ui_never_imports_or_executes_biblioref(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "biblioref" or name.startswith("biblioref."):
            raise AssertionError(f"annotation UI imported production extractor: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("tools.human_gold.annotation_app", None)
    module = importlib.import_module("tools.human_gold.annotation_app")
    assert "biblioref" not in module.__dict__


def test_rendered_page_endpoint_returns_image_without_pdf_text(monkeypatch, tmp_path):
    import tools.human_gold.annotation_app as annotation_app

    app, _, _, _, _ = _build_app(tmp_path)
    real_document = annotation_app.pdfium.PdfDocument

    class GuardedPage:
        def __init__(self, page):
            self._page = page

        def render(self, *args, **kwargs):
            return self._page.render(*args, **kwargs)

        def get_textpage(self, *args, **kwargs):
            raise AssertionError("annotation UI must not call PDF text extraction")

    class GuardedDocument:
        def __init__(self, *args, **kwargs):
            self._document = real_document(*args, **kwargs)

        def __len__(self):
            return len(self._document)

        def __getitem__(self, index):
            return GuardedPage(self._document[index])

        def close(self):
            self._document.close()

    monkeypatch.setattr(annotation_app.pdfium, "PdfDocument", GuardedDocument)
    with TestClient(app) as client:
        response = client.get("/api/document/doc-1/page/1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def test_annotation_round_trip_returns_only_human_draft(tmp_path):
    app, output, digest, _, _ = _build_app(tmp_path)
    annotation = _annotation("doc-1", digest)
    with TestClient(app) as client:
        response = client.post("/api/document/doc-1/annotation", json=annotation)
        assert response.status_code == 200
        fetched = client.get("/api/document/doc-1/annotation")
    assert fetched.status_code == 200
    assert fetched.json() == annotation
    serialized = json.dumps(fetched.json()).casefold()
    for forbidden in ("prediction", "predicted", "biblioref", "styleprofiler", "audit_flag", "parser_output"):
        assert forbidden not in serialized
    assert json.loads((output / "doc-1.json").read_text(encoding="utf-8")) == annotation


def test_annotation_round_trip_and_schema_valid_complete_output(tmp_path):
    from tools.human_gold.schema import load_jsonl, validate_gold, validate_manifest

    app, output, digest, _, manifest = _build_app(tmp_path)
    annotation = _annotation("doc-1", digest, annotation_complete=True)
    with TestClient(app) as client:
        response = client.post("/api/document/doc-1/annotation", json=annotation)
        assert response.status_code == 200
    annotation_path = output / "doc-1.json"
    manifest_rows = load_jsonl(manifest)
    validate_manifest(manifest_rows)
    validate_gold(manifest_rows, [json.loads(annotation_path.read_text(encoding="utf-8"))])


def test_annotation_save_rejects_wrong_document_sha(tmp_path):
    app, _, _, _, _ = _build_app(tmp_path)
    bad = _annotation("doc-1", "0" * 64)
    with TestClient(app) as client:
        response = client.post("/api/document/doc-1/annotation", json=bad)
    assert response.status_code == 422
    assert "sha" in response.json()["detail"].casefold()


def test_annotation_save_is_atomic_under_concurrency(tmp_path):
    app, output, digest, _, _ = _build_app(tmp_path)
    values = [_annotation("doc-1", digest, notes=f"worker-{index}") for index in range(8)]

    def write(value):
        with TestClient(app) as client:
            return client.post("/api/document/doc-1/annotation", json=value).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(write, values))
    assert statuses == [200] * len(values)
    saved = json.loads((output / "doc-1.json").read_text(encoding="utf-8"))
    assert saved["notes"] in {value["notes"] for value in values}
    history = [json.loads(line) for line in (output / ".history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(history) == len(values)


def test_annotation_app_cli_help_is_available_without_biblioref_import():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-m", "tools.human_gold.annotation_app", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--manifest" in result.stdout
    assert "--pdf-cache" in result.stdout
    assert "--output" in result.stdout
    assert "--annotator" in result.stdout


def test_annotation_app_rejects_outside_pdf_cache_paths(tmp_path):
    from tools.human_gold.annotation_app import create_app

    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "outside.pdf"
    pdf_bytes = _write_pdf(outside)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "document_id": "doc-1",
        "partition": "pilot",
        "sha256": digest,
        "selected_before_biblioref_run": True,
        "pdf_filename": "../outside.pdf",
    }) + "\n", encoding="utf-8")
    app = create_app(manifest, cache, tmp_path / "work", annotator_id="ann-1")
    with TestClient(app) as client:
        response = client.get("/api/document/doc-1/page/1")
    assert response.status_code == 404
    assert "cached pdf not found" in response.json()["detail"].casefold()


def test_annotation_app_rejects_manifest_pdf_hash_mismatch(tmp_path):
    from tools.human_gold.annotation_app import create_app

    cache = tmp_path / "cache"
    cache.mkdir()
    pdf = cache / "doc-1.pdf"
    _write_pdf(pdf)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "document_id": "doc-1",
        "partition": "pilot",
        "sha256": "0" * 64,
        "selected_before_biblioref_run": True,
    }) + "\n", encoding="utf-8")
    app = create_app(manifest, cache, tmp_path / "work", annotator_id="ann-1")
    with TestClient(app) as client:
        response = client.get("/api/document/doc-1/page/1")
    assert response.status_code == 409
    assert "sha-256" in response.json()["detail"].casefold()
