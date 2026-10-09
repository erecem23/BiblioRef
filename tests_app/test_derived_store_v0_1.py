# -*- coding: utf-8 -*-
"""Derived analysis store v0.1.

The invariants under test are the ones that make the sidecar safe to delete and
safe to re-run: project.json is never written, a second sync is a no-op, and the
network-derived cache survives a full rebuild of everything else.
"""
import json
import time

import pytest

from biblioref.derived import (
    DERIVED_SCHEMA_VERSION,
    corpus_stats,
    open_store,
    query_for_reference,
    query_sha,
    sync_documents,
    sync_from_file,
)


def _ref(ref_id, text, order=1, parsed=None, **extra):
    row = {
        "id": ref_id,
        "order": order,
        "text": text,
        "original_text": text,
        "start_page": 10,
        "end_page": 10,
        "status": "ok",
        "source": "automatic",
        "edited": False,
        "deleted": False,
        "parsed": parsed if parsed is not None else {
            "parser_version": "biblioref-parser-v0.12.5",
            "author": "Smith, John",
            "authors": "Smith, John",
            "year": "2019",
            "title": "Machine learning in psychology",
            "journal": "Journal of X",
            "publisher": None,
            "doi": None,
            "publication_type": "articulo_revista",
        },
    }
    row.update(extra)
    return row


def _store(*docs):
    return {"schema": 2, "documents": {d["id"]: d for d in docs}}


def _doc(doc_id="doc1", refs=None, **meta):
    metadata = {
        "university": "Universidad Nacional de Mar del Plata",
        "faculty": "Psicología",
        "program": "Doctorado en Psicología",
        "director": "Pérez, Ana",
        "degree_level": "doctorado",
        "year": "2020",
    }
    metadata.update(meta)
    return {
        "id": doc_id,
        "thesis_id": "T-001",
        "title": "Una tesis",
        "filename": "tesis.pdf",
        "project_id": "p1",
        "n_references": len(refs or []),
        "content_sha256": "abc",
        "updated_at": 1700000000,
        "metadata": metadata,
        "references": list(refs or []),
    }


def test_sync_populates_documents_and_references(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    report = sync_documents(conn, _store(_doc(refs=[_ref("r1", "Smith, J. 2019..."), _ref("r2", "Otra ref", order=2)])))

    assert report.documents_inserted == 1
    assert report.references_inserted == 2
    assert conn.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"] == 2

    row = conn.execute("SELECT * FROM reference WHERE ref_id='r1'").fetchone()
    assert row["doc_id"] == "doc1"
    assert row["title"] == "Machine learning in psychology"
    assert row["year"] == "2019"
    assert row["query_sha"]

    doc = conn.execute("SELECT * FROM document").fetchone()
    assert doc["university"] == "Universidad Nacional de Mar del Plata"
    assert doc["thesis_year"] == "2020"


def test_second_sync_is_a_no_op(tmp_path):
    store = _store(_doc(refs=[_ref("r1", "Smith, J. 2019...")]))
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, store)
    again = sync_documents(conn, store)

    assert again.documents_inserted == 0
    assert again.documents_updated == 0
    assert again.references_inserted == 0
    assert again.references_updated == 0
    assert again.references_deleted == 0


def test_edit_updates_and_removal_deletes(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "uno"), _ref("r2", "dos", order=2)])))

    edited = _ref("r1", "uno corregido")
    edited["edited"] = True
    report = sync_documents(conn, _store(_doc(refs=[edited])))

    assert report.references_updated == 1
    assert report.references_deleted == 1
    assert conn.execute("SELECT raw_text FROM reference WHERE ref_id='r1'").fetchone()["raw_text"] == "uno corregido"
    assert conn.execute("SELECT COUNT(*) AS n FROM reference WHERE ref_id='r2'").fetchone()["n"] == 0


def test_deleted_references_are_not_synced(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    gone = _ref("r2", "borrada", order=2)
    gone["deleted"] = True
    report = sync_documents(conn, _store(_doc(refs=[_ref("r1", "viva"), gone])))

    assert report.references_inserted == 1
    assert report.references_skipped_deleted == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"] == 1


def test_removing_a_document_cascades_to_its_references(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(_doc("doc1", [_ref("r1", "uno")]), _doc("doc2", [_ref("r9", "nueve")])))
    report = sync_documents(conn, _store(_doc("doc1", [_ref("r1", "uno")])))

    assert report.documents_deleted == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM reference WHERE ref_id='r9'").fetchone()["n"] == 0


def test_resolution_cache_survives_a_full_rebuild(tmp_path):
    """The only data here that costs network time must not be lost on rebuild."""
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "Smith, J. 2019...")])))
    sha = conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"]

    conn.execute(
        "INSERT INTO resolution_cache(query_sha, query_json, candidates_json, backends, fetched_at) "
        "VALUES(?,?,?,?,?)",
        (sha, "{}", json.dumps([{"doi": "10.1/x"}]), "crossref", int(time.time())),
    )
    conn.commit()

    # Everything the project store owns disappears...
    empty = sync_documents(conn, _store())
    assert empty.documents_deleted == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"] == 0

    # ...and the expensive answer is still there, still reachable by content key.
    cached = conn.execute("SELECT * FROM resolution_cache WHERE query_sha=?", (sha,)).fetchone()
    assert cached is not None
    assert json.loads(cached["candidates_json"])[0]["doi"] == "10.1/x"

    # Re-syncing the same reference finds its own cache entry again.
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "Smith, J. 2019...")])))
    assert conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"] == sha


def test_reference_rows_disappear_with_their_resolution(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "uno")])))
    sha = conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"]
    conn.execute(
        "INSERT INTO resolution(ref_id, query_sha, status, decided_at) VALUES(?,?,?,?)",
        ("r1", sha, "VERIFIED_EXACT", int(time.time())),
    )
    conn.commit()

    sync_documents(conn, _store(_doc(refs=[])))
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"] == 0


def test_human_resolution_is_mirrored_not_owned(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    ref = _ref("r1", "uno")
    ref["human_resolution"] = {"decision": "confirmed", "candidate_index": 0, "confirmed_at": 1700000001}
    report = sync_documents(conn, _store(_doc(refs=[ref])))

    assert report.human_resolutions == 1
    row = conn.execute("SELECT * FROM human_resolution WHERE ref_id='r1'").fetchone()
    assert row["decision"] == "confirmed"

    # Withdrawn upstream -> gone here on the next sync.
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "uno")])))
    assert conn.execute("SELECT COUNT(*) AS n FROM human_resolution").fetchone()["n"] == 0


def test_query_sha_keys_on_content_not_on_reference_id():
    a = query_for_reference(_ref("r1", "Smith, J. 2019. Machine learning..."))
    b = query_for_reference(_ref("r2", "Smith, J. 2019. Machine learning...", order=7))
    assert query_sha(a) == query_sha(b)


def test_query_sha_collapses_equivalent_doi_forms():
    parsed = dict(_ref("x", "t")["parsed"])
    first = dict(parsed, doi="https://doi.org/10.1234/ABC")
    second = dict(parsed, doi="doi: 10.1234/abc", title="otro titulo", journal="otra revista")
    a = query_for_reference(_ref("r1", "una", parsed=first))
    b = query_for_reference(_ref("r2", "otra", parsed=second))
    assert query_sha(a) == query_sha(b)


def test_query_sha_separates_different_works():
    parsed = dict(_ref("x", "t")["parsed"])
    a = query_for_reference(_ref("r1", "una", parsed=dict(parsed, title="Machine learning in psychology")))
    b = query_for_reference(_ref("r2", "otra", parsed=dict(parsed, title="Deep learning in sociology")))
    assert query_sha(a) != query_sha(b)


def test_unparsed_references_do_not_collapse_onto_one_key():
    blank = {"parser_version": "v", "author": None, "authors": None, "year": None,
             "title": None, "journal": None, "publisher": None, "doi": None,
             "publication_type": "sin_clasificar"}
    a = query_for_reference(_ref("r1", "fragmento ilegible uno", parsed=dict(blank)))
    b = query_for_reference(_ref("r2", "fragmento ilegible dos", parsed=dict(blank)))
    assert query_sha(a) != query_sha(b)


def test_sync_from_file_does_not_touch_project_json(tmp_path):
    project = tmp_path / "project.json"
    payload = _store(_doc(refs=[_ref("r1", "uno")]))
    project.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    before = project.read_bytes()
    before_mtime = project.stat().st_mtime_ns

    conn, report = sync_from_file(project, tmp_path / "derived.sqlite3")

    assert report.references_inserted == 1
    assert project.read_bytes() == before
    assert project.stat().st_mtime_ns == before_mtime
    conn.close()


def test_corpus_stats_reports_its_denominators(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    parsed = dict(_ref("x", "t")["parsed"])
    refs = [
        _ref("r1", "uno", parsed=dict(parsed, year="2019", doi="10.1234/abc")),
        _ref("r2", "dos", order=2, parsed=dict(parsed, year="1990", doi=None, title="Otro")),
        _ref("r3", "tres", order=3, parsed=dict(parsed, year=None, doi=None, title="Sin anio")),
    ]
    sync_documents(conn, _store(_doc(refs=refs, year="2020")))
    stats = corpus_stats(conn)

    assert stats["references"] == 3
    assert stats["doi"] == {"n": 1, "pct": 33.3}
    assert stats["age"]["base"] == 2          # la referencia sin anio no entra
    assert stats["age"]["median"] in (1, 30)
    assert stats["resolution"] == {"decided": 0, "cached_queries": 0}


def test_a_newer_sidecar_is_also_rebuilt(tmp_path):
    path = tmp_path / "derived.sqlite3"
    conn = open_store(path)
    conn.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(DERIVED_SCHEMA_VERSION + 1),))
    conn.commit()
    conn.close()

    reopened = open_store(path)
    assert reopened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()["value"]         == str(DERIVED_SCHEMA_VERSION)


def test_a_change_in_query_construction_retires_cached_answers(monkeypatch):
    """A cached answer is only valid for the question that produced it."""
    from biblioref.derived import sync as sync_module

    query = query_for_reference(_ref("r1", "Smith, J. 2019. Machine learning..."))
    before = query_sha(query)

    monkeypatch.setattr(sync_module, "QUERY_BUILD_VERSION", "query-build-v99-otra-higiene")
    assert query_sha(query) != before


def test_a_doi_key_does_not_depend_on_query_construction(monkeypatch):
    from biblioref.derived import sync as sync_module

    parsed = dict(_ref("x", "t")["parsed"], doi="10.1234/abc")
    query = query_for_reference(_ref("r1", "una", parsed=parsed))
    before = query_sha(query)

    monkeypatch.setattr(sync_module, "QUERY_BUILD_VERSION", "query-build-v99-otra-higiene")
    assert query_sha(query) == before


def test_a_changed_query_drops_the_decision_it_no_longer_describes(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "uno")])))
    sha = conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"]
    conn.execute(
        "INSERT INTO resolution(ref_id, query_sha, status, decided_at) VALUES(?,?,?,?)",
        ("r1", sha, "VERIFIED_EXACT", int(time.time())),
    )
    conn.commit()

    # El parse cambia -> la pregunta cambia -> la decision vieja ya no aplica.
    reparsed = _ref("r1", "uno", parsed=dict(
        _ref("x", "t")["parsed"], title="Un titulo completamente distinto"))
    report = sync_documents(conn, _store(_doc(refs=[reparsed])))

    assert report.stale_resolutions_dropped == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"] == 0


def test_an_unchanged_query_keeps_its_decision(tmp_path):
    conn = open_store(tmp_path / "derived.sqlite3")
    store = _store(_doc(refs=[_ref("r1", "uno")]))
    sync_documents(conn, store)
    sha = conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"]
    conn.execute(
        "INSERT INTO resolution(ref_id, query_sha, status, decided_at) VALUES(?,?,?,?)",
        ("r1", sha, "VERIFIED_EXACT", int(time.time())),
    )
    conn.commit()

    report = sync_documents(conn, store)
    assert report.stale_resolutions_dropped == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"] == 1


def test_an_outdated_sidecar_is_rebuilt_instead_of_refused(tmp_path):
    """The sidecar is derived; an old one must never break the app."""
    import sqlite3

    path = tmp_path / "derived.sqlite3"
    conn = open_store(path)
    sync_documents(conn, _store(_doc(refs=[_ref("r1", "una")])))
    sha = conn.execute("SELECT query_sha FROM reference WHERE ref_id='r1'").fetchone()["query_sha"]
    conn.execute(
        "INSERT INTO resolution_cache(query_sha, query_json, candidates_json, backends, fetched_at) "
        "VALUES(?,?,?,?,?)",
        (sha, "{}", json.dumps([{"doi": "10.1234/abc"}]), "crossref", int(time.time())),
    )
    conn.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
    conn.commit()
    conn.close()

    reopened = open_store(path)

    assert reopened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()["value"] \
        == str(DERIVED_SCHEMA_VERSION)
    assert reopened.execute("SELECT value FROM meta WHERE key='rebuilt_from_schema'").fetchone()["value"] == "1"
    # lo unico caro sobrevive; el resto se recomputa desde project.json
    cached = reopened.execute("SELECT candidates_json FROM resolution_cache WHERE query_sha=?", (sha,)).fetchone()
    assert json.loads(cached["candidates_json"])[0]["doi"] == "10.1234/abc"
    assert reopened.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"] == 0


def test_a_strict_caller_can_still_refuse_an_outdated_sidecar(tmp_path):
    path = tmp_path / "derived.sqlite3"
    conn = open_store(path)
    conn.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="schema"):
        open_store(path, rebuild_on_mismatch=False)
