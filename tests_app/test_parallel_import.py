"""Live import, durable partial results and process isolation regression tests."""
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from copy import deepcopy
import io
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time
import zipfile
from tests_support import pdf_factory as fitz

from test_projects_explorer import client, create, pdf, upload
import app as app_module
from biblioref.metadata.integration import install_cover_metadata
from biblioref import import_stream
from biblioref.pdf_workers import prepare_pdf, worker_count


def streamed(client, project, files):
    return client.post("/api/documents", data={"project_id": project, "stream_progress": "true"},
                       files=[("files", item) for item in files])


def frames(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines()]


def test_stream_keeps_nested_folders_and_continues_after_bad_pdf(client):
    install_cover_metadata(app_module)
    p = create(client, "Paralelo")
    inner, outer = io.BytesIO(), io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("UNC/tesis.pdf", pdf())
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("Lote/interno.zip", inner.getvalue())
        archive.writestr("UNLP/tesis.pdf", pdf())
    events = frames(streamed(client, p, [("Corpus/lote.zip", outer.getvalue()), ("mala.pdf", b"broken")]))
    docs = [e["document"] for e in events if e["type"] == "document"]
    assert len(docs) == 2
    assert len({d["thesis_id"] for d in docs}) == 2
    assert events[-1]["type"] == "done" and events[-1]["imported"] == 2
    assert "mala.pdf" in events[-1]["warnings"][0]
    assert any(e.get("total") == 3 and e.get("active") for e in events)
    tree = client.get(f"/api/projects/{p}/tree").json()["nodes"]
    assert tree[0]["name"] == "Corpus" and tree[0]["count"] == 2
    assert tree[0]["children"][0]["name"] == "Lote"
    state = json.loads(app_module.STATE_FILE.read_text())
    assert len(state["documents"]) == 2
    assert all(Path(d["path"]).exists() for d in state["documents"].values())
    assert not list(app_module.WORKSPACE.glob("biblioref_import_*"))


def test_first_pdf_is_durable_and_api_responds_before_last_finishes(client, monkeypatch):
    p = create(client, "Respuesta durante lectura")
    source = app_module.WORKSPACE / "fixture.pdf"
    source.write_bytes(pdf())
    prepared = prepare_pdf(str(source), "tesis.pdf")
    entered, release = threading.Event(), threading.Event()

    def slow(path, name):
        if name == "lenta.pdf":
            entered.set()
            assert release.wait(10)
        return deepcopy(prepared)

    # Threads are only a controllable test double; no PDF is opened in them.
    with ThreadPoolExecutor(2) as fake, ThreadPoolExecutor(1) as requests:
        monkeypatch.setattr(import_stream, "get_pool", lambda: fake)
        monkeypatch.setattr(import_stream, "prepare_pdf", slow)
        future = requests.submit(streamed, client, p, [("primera.pdf", pdf()), ("lenta.pdf", pdf())])
        try:
            assert entered.wait(5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                stored = json.loads(app_module.STATE_FILE.read_text()).get("documents", {})
                if stored:
                    break
                time.sleep(.02)
            assert len(stored) == 1
            assert next(iter(stored.values()))["filename"] == "primera.pdf"
            assert not future.done()
            start = time.monotonic()
            assert client.get("/api/health").status_code == 200
            assert time.monotonic() - start < 2
            assert client.get(f"/api/projects/{p}/tree").json()["nodes"]
        finally:
            release.set()
        assert frames(future.result(timeout=10))[-1]["imported"] == 2


def _isolated_probe(path, filename, markers):
    marker = Path(markers) / str(os.getpid())
    marker.touch()
    deadline = time.monotonic() + 15
    while len(list(Path(markers).iterdir())) < 2 and time.monotonic() < deadline:
        time.sleep(.02)
    return os.getpid(), prepare_pdf(path, filename)


def test_two_real_processes_preserve_exact_preflight_title_and_metadata(tmp_path):
    path = tmp_path / "tesis.pdf"
    path.write_bytes(pdf())
    expected = prepare_pdf(str(path), path.name)
    markers = tmp_path / "processes"
    markers.mkdir()
    with ProcessPoolExecutor(2, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(_isolated_probe, str(path), path.name, str(markers)) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert len({pid for pid, _ in results}) == 2
    assert all(result == expected for _, result in results)


def test_worker_limits_and_invalid_setting(monkeypatch):
    monkeypatch.setenv("BIBLIOREF_WORKERS", "invalid")
    assert 1 <= worker_count() <= 4
    monkeypatch.setenv("BIBLIOREF_WORKERS", "1000")
    assert 1 <= worker_count() <= 8
    monkeypatch.setenv("BIBLIOREF_WORKERS", "0")
    assert worker_count() == 1


def test_failed_checkpoint_does_not_announce_unsaved_pdf(client, monkeypatch):
    p = create(client, "Guardado parcial")
    real_save = app_module.STORE.save

    def failed_save():
        if len(app_module.STORE.docs()) > 1:
            raise OSError("No se pudo escribir el proyecto")
        real_save()

    monkeypatch.setattr(app_module.STORE, "save", failed_save)
    events = frames(streamed(client, p, [("a.pdf", pdf()), ("b.pdf", pdf())]))
    assert events[-1]["type"] == "error" and events[-1]["imported"] == 1
    assert len([e for e in events if e["type"] == "document"]) == 1
    assert len(app_module.STORE.docs()) == 1
    assert len(json.loads(app_module.STATE_FILE.read_text())["documents"]) == 1


def test_real_http_delivers_document_before_batch_finishes(client, monkeypatch):
    import socket
    import urllib.request
    import uvicorn

    p = create(client, "Streaming HTTP")
    source = app_module.WORKSPACE / "fixture.pdf"
    source.write_bytes(pdf())
    prepared = prepare_pdf(str(source), "tesis.pdf")
    release = threading.Event()

    def slow(path, name):
        if name == "lenta.pdf":
            assert release.wait(10)
        return deepcopy(prepared)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app_module.app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    with ThreadPoolExecutor(2) as fake:
        monkeypatch.setattr(import_stream, "get_pool", lambda: fake)
        monkeypatch.setattr(import_stream, "prepare_pdf", slow)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(.02)
            assert server.started
            boundary = "biblioref-test-boundary"
            parts = []
            for name, value in [("project_id", p), ("stream_progress", "true")]:
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            for name in ("rapida.pdf", "lenta.pdf"):
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: application/pdf\r\n\r\n'.encode() + pdf() + b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode())
            request = urllib.request.Request(f"http://127.0.0.1:{port}/api/documents", data=b"".join(parts),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-BiblioRef-Token": app_module.APP_TOKEN})
            with urllib.request.urlopen(request, timeout=5) as response:
                while True:
                    event = json.loads(response.readline())
                    if event["type"] == "document":
                        assert event["document"]["filename"] == "rapida.pdf"
                        assert not release.is_set()
                        assert len(json.loads(app_module.STATE_FILE.read_text())["documents"]) == 1
                        break
                    assert event["type"] not in {"error", "done"}
                release.set()
                tail = [json.loads(line) for line in response]
                assert tail[-1]["type"] == "done" and tail[-1]["imported"] == 2
        finally:
            release.set()
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()


def test_worker_analysis_uses_existing_pipeline_and_preserves_import_metadata(client):
    p = create(client, "Referencias en proceso")
    with fitz.open() as source:
        cover = source.new_page()
        cover.insert_text((50, 80), "Universidad Nacional de La Plata", fontsize=18)
        cover.insert_text((50, 150), "Un corpus para probar proyectos", fontsize=20)
        page = source.new_page()
        page.insert_text((60, 80), "BIBLIOGRAFIA", fontsize=18)
        for i, line in enumerate([
            "Alonso, J. (2019). Estudios sobre educacion. Buenos Aires: Editorial Sur.",
            "Bourdieu, P. (1998). La distincion. Madrid: Taurus.",
            "Freire, P. (1970). Pedagogia del oprimido. Buenos Aires: Siglo XXI.",
            "Vygotsky, L. (1986). Pensamiento y lenguaje. Barcelona: Paidos.",
        ]):
            page.insert_text((60, 130 + i * 45), line, fontsize=11)
        content = source.tobytes()
    d = upload(client, p, data=content).json()["documents"][0]
    stored = app_module.STORE.docs()[d["id"]]
    original = deepcopy(stored)
    # Compare the complete persisted reference output and APP guard with the
    # ordinary route, using the same PDF and profile.
    app_module._analyze_document(stored)
    expected = deepcopy(stored)
    app_module.STORE.docs()[d["id"]] = original
    response = client.post(f"/api/documents/{d['id']}/analyze", json={"worker": True})
    assert response.status_code == 200, response.text
    actual = app_module.STORE.docs()[d["id"]]
    assert expected["n_references"] > 0
    for item in (actual, expected):
        for row in item["sections"] + item["references"]:
            row.pop("id", None)  # Fresh review rows legitimately get fresh UUIDs.
    for key in ("metadata", "title", "ingestion", "sections", "references", "n_references", "status"):
        assert actual[key] == expected[key], key
