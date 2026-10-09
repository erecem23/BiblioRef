from biblioref.duplicates import DuplicateDocument, content_hash, find_duplicates, find_existing_copy


def _pdf(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_same_bytes_are_repeated_same_title_alone_is_not(tmp_path):
    a = _pdf(tmp_path, "a.pdf", b"%PDF tesis uno")
    b = _pdf(tmp_path, "b.pdf", b"%PDF tesis uno")
    c = _pdf(tmp_path, "c.pdf", b"%PDF otra tesis con el mismo titulo")
    project = {"id": "p"}
    docs = [
        {"id": "d1", "thesis_id": "T0008", "title": "Contacto", "path": a, "status": "review",
         "ingestion": {"relative_path": "master_tesis/Tesis.zip", "archive_chain": ["Tesis.zip"], "archive_member": "x.pdf"}},
        {"id": "d2", "thesis_id": "T0228", "title": "Contacto", "path": b, "status": "review",
         "ingestion": {"relative_path": "master_tesis/UNC/x.pdf"}},
        {"id": "d3", "thesis_id": "T0300", "title": "Contacto", "path": c, "status": "review", "ingestion": {}},
    ]
    groups = find_duplicates(project, docs)
    assert len(groups) == 1
    g = groups[0]
    assert g["keep"]["thesis_id"] == "T0008" and [r["thesis_id"] for r in g["remove"]] == ["T0228"]
    # The kept copy came from a ZIP: it takes the folder of the loose copy.
    assert g["target_folder"] == ["master_tesis", "UNC"] and g["moves_folder"] is True
    assert content_hash(docs[0]) == docs[0]["content_sha256"]
    assert find_existing_copy(docs, content_hash(docs[1]))["id"] == "d1"
    assert "ya estaba en el proyecto como T0008" in str(DuplicateDocument(docs[0], "x.pdf"))


def test_the_copy_with_work_is_kept(tmp_path):
    a = _pdf(tmp_path, "a.pdf", b"%PDF igual")
    b = _pdf(tmp_path, "b.pdf", b"%PDF igual")
    docs = [
        {"id": "d1", "thesis_id": "T0001", "path": a, "ingestion": {}},
        {"id": "d2", "thesis_id": "T0122", "path": b, "ingestion": {}, "corrections": [{"kind": "edit"}],
         "audit_decisions": {"m1": {"decision": "ignore"}}},
    ]
    g = find_duplicates({"id": "p"}, docs)[0]
    assert g["keep"]["thesis_id"] == "T0122" and "más trabajo" in g["reason"]


def test_ui_reviews_and_removes_repeated_copies_and_import_reports_them():
    from pathlib import Path
    js = Path("static/project-organize.js").read_text(encoding="utf-8")
    assert "Revisar y quitar copias…" in js and "/duplicates/resolve`" in js and "no se puede deshacer" in js
    assert "Repetidas (mismo archivo)" in js
    base = Path("static/projects-base.js").read_text(encoding="utf-8")
    assert "skipped_duplicates" in base and "archivos repetidos no se agregaron" in base
    stream = Path("biblioref/import_stream.py").read_text(encoding="utf-8")
    assert "en esta misma carga" in stream and "skipped_duplicates=skipped" in stream
