# -*- coding: utf-8 -*-
"""Batch resolution v0.1.

Every test here is offline: the backends receive a fake transport, so the suite
never contacts Crossref or OpenAlex. What is under test is the part that a long
corpus run depends on — that it resumes, that it never asks the same question
twice, that a dead service cannot burn the retry budget, and that deciding is
separable from fetching.
"""
import json
import time

import pytest

from biblioref.derived import open_store, sync_documents
from biblioref.derived.batch import (
    build_backends,
    decide_pending,
    fetch_missing,
    pending_queries,
    resolution_progress,
)
from biblioref.resolver.crossref import CrossrefBackend
from biblioref.resolver.openalex import OpenAlexBackend


def _parsed(**over):
    base = {
        "parser_version": "biblioref-parser-v0.12.5",
        "author": "Smith, John",
        "authors": "Smith, John",
        "year": "2019",
        "title": "Machine learning in psychology",
        "journal": "Journal of X",
        "publisher": None,
        "doi": None,
        "publication_type": "articulo_revista",
    }
    base.update(over)
    return base


def _ref(ref_id, text, order=1, parsed=None):
    return {
        "id": ref_id, "order": order, "text": text, "original_text": text,
        "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
        "edited": False, "deleted": False,
        "parsed": parsed if parsed is not None else _parsed(),
    }


def _store(refs):
    return {
        "schema": 2,
        "documents": {
            "doc1": {
                "id": "doc1", "thesis_id": "T-1", "title": "Tesis", "filename": "t.pdf",
                "project_id": "p1", "n_references": len(refs), "content_sha256": "x",
                "updated_at": 1, "metadata": {"university": "UNMdP", "year": "2020"},
                "references": refs,
            }
        },
    }


class FakeTransport:
    """Records every call and replays canned payloads."""

    def __init__(self, payload=None, error=None):
        self.calls = []
        self.payload = payload
        self.error = error

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.payload


CROSSREF_HIT = {
    "message": {
        "items": [{
            "DOI": "10.1234/abc",
            "title": ["Machine learning in psychology"],
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[2019]]},
            "container-title": ["Journal of X"],
            "publisher": "Elsevier",
            "type": "journal-article",
            "score": 90.0,
        }]
    }
}

OPENALEX_HIT = {
    "results": [{
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1234/abc",
        "title": "Machine learning in psychology",
        "authorships": [{"author": {"display_name": "John Smith"}}],
        "publication_year": 2019,
        "primary_location": {"source": {"display_name": "Journal of X"}},
        "type": "article",
        "relevance_score": 80.0,
    }]
}


def _conn(tmp_path, refs):
    conn = open_store(tmp_path / "derived.sqlite3")
    sync_documents(conn, _store(refs))
    return conn


def _backends(crossref_payload=CROSSREF_HIT, openalex_payload=OPENALEX_HIT, error=None):
    ct = FakeTransport(crossref_payload, error)
    ot = FakeTransport(openalex_payload, error)
    return [CrossrefBackend(transport=ct), OpenAlexBackend(transport=ot)], ct, ot


def _no_sleep(_seconds):
    return None


def test_identical_references_ask_only_once(tmp_path):
    """Two references with the same content are one question, not two."""
    conn = _conn(tmp_path, [
        _ref("r1", "Smith, J. 2019. Machine learning..."),
        _ref("r2", "Smith, J. 2019. Machine learning...", order=2),
    ])
    backends, ct, ot = _backends()

    report = fetch_missing(conn, backends, rate_per_second=0, sleep=_no_sleep)

    assert report.pending_at_start == 1
    assert report.fetched == 1
    assert len(ct.calls) == 1 and len(ot.calls) == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 1


def test_a_second_run_asks_nothing(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    backends, ct, _ = _backends()
    fetch_missing(conn, backends, rate_per_second=0, sleep=_no_sleep)

    backends2, ct2, ot2 = _backends()
    again = fetch_missing(conn, backends2, rate_per_second=0, sleep=_no_sleep)

    assert again.pending_at_start == 0
    assert again.fetched == 0
    assert ct2.calls == [] and ot2.calls == []


def test_limit_makes_the_run_resumable(tmp_path):
    refs = [_ref(f"r{i}", f"ref {i}", order=i, parsed=_parsed(title=f"Title {i}")) for i in range(1, 6)]
    conn = _conn(tmp_path, refs)

    first = fetch_missing(conn, _backends()[0], limit=2, rate_per_second=0, sleep=_no_sleep)
    assert first.fetched == 2

    second = fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)
    assert second.fetched == 3
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 5

    assert pending_queries(conn) == []


def test_an_empty_answer_is_a_real_answer(tmp_path):
    """No candidates is knowledge; it must be cached, not retried forever."""
    conn = _conn(tmp_path, [_ref("r1", "referencia rarisima")])
    backends, _, _ = _backends({"message": {"items": []}}, {"results": []})

    report = fetch_missing(conn, backends, rate_per_second=0, sleep=_no_sleep)

    assert report.fetched == 1
    assert report.empty_answers == 1
    assert pending_queries(conn) == []
    row = conn.execute("SELECT candidates_json FROM resolution_cache").fetchone()
    assert json.loads(row["candidates_json"]) == []


def test_transport_failures_are_not_cached_and_are_retried(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    backends, _, _ = _backends(error=TimeoutError("timed out"))

    report = fetch_missing(conn, backends, rate_per_second=0, consecutive_failure_limit=0, sleep=_no_sleep)

    assert report.fetched == 0
    assert report.failed == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 0
    row = conn.execute("SELECT * FROM resolution_failure").fetchone()
    assert row["attempts"] == 1
    assert "timed out" in row["last_error"]
    assert len(pending_queries(conn)) == 1     # vuelve a intentarse


def test_a_query_stops_being_retried_after_max_attempts(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    for _ in range(3):
        fetch_missing(conn, _backends(error=TimeoutError("nope"))[0],
                      rate_per_second=0, consecutive_failure_limit=0, sleep=_no_sleep)

    assert conn.execute("SELECT attempts FROM resolution_failure").fetchone()["attempts"] == 3
    assert pending_queries(conn, max_attempts=3) == []
    assert len(pending_queries(conn, max_attempts=3, retry_failed=True)) == 1


def test_a_dead_service_stops_the_run_instead_of_burning_the_budget(tmp_path):
    refs = [_ref(f"r{i}", f"ref {i}", order=i, parsed=_parsed(title=f"T{i}")) for i in range(1, 21)]
    conn = _conn(tmp_path, refs)
    backends, _, _ = _backends(error=ConnectionError("connection refused"))

    report = fetch_missing(conn, backends, rate_per_second=0, consecutive_failure_limit=5, sleep=_no_sleep)

    assert report.failed == 5
    assert report.stopped_early and "fallos seguidos" in report.stopped_early
    # las 15 restantes quedan intactas, sin intentos gastados
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_failure").fetchone()["n"] == 5


def test_a_recovered_query_clears_its_failure_record(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    fetch_missing(conn, _backends(error=TimeoutError("x"))[0],
                  rate_per_second=0, consecutive_failure_limit=0, sleep=_no_sleep)
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_failure").fetchone()["n"] == 1

    fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_failure").fetchone()["n"] == 0


def test_rate_limiter_paces_requests(tmp_path):
    refs = [_ref(f"r{i}", f"ref {i}", order=i, parsed=_parsed(title=f"T{i}")) for i in range(1, 4)]
    conn = _conn(tmp_path, refs)
    slept = []

    fetch_missing(conn, _backends()[0], rate_per_second=2.0, sleep=lambda s: slept.append(s))

    assert len(slept) >= 2
    assert all(s <= 0.5 + 1e-6 for s in slept)


def test_deciding_is_offline_and_separable(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una"), _ref("r2", "otra", order=2, parsed=_parsed(title="Otro"))])
    fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)

    report = decide_pending(conn)

    assert report.decided == 2
    assert sum(report.statuses.values()) == 2
    row = conn.execute("SELECT * FROM resolution WHERE ref_id='r1'").fetchone()
    assert row["selected_doi"] == "10.1234/abc"
    assert json.loads(row["evidence_json"])["consensus_status"]


def test_redecide_needs_no_network(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)
    decide_pending(conn)

    backends, ct, ot = _backends()
    again = decide_pending(conn, redecide=True)

    assert again.decided == 1
    assert ct.calls == [] and ot.calls == []
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"] == 1


def test_decide_skips_references_without_a_cached_answer(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una"), _ref("r2", "otra", order=2, parsed=_parsed(title="Otro"))])
    fetch_missing(conn, _backends()[0], limit=1, rate_per_second=0, sleep=_no_sleep)

    report = decide_pending(conn)

    assert report.decided == 1
    assert report.skipped_no_cache == 1


def test_resolution_survives_a_reference_edit_without_refetching(tmp_path):
    """The point of keying the cache by content: editing text elsewhere is free."""
    conn = _conn(tmp_path, [_ref("r1", "una"), _ref("r2", "otra", order=2, parsed=_parsed(title="Otro"))])
    fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)
    decide_pending(conn)

    # r2 se edita (cambia su texto crudo pero no el parse que define la consulta)
    edited = _ref("r2", "otra corregida", order=2, parsed=_parsed(title="Otro"))
    sync_documents(conn, _store([_ref("r1", "una"), edited]))

    backends, ct, ot = _backends()
    report = fetch_missing(conn, backends, rate_per_second=0, sleep=_no_sleep)

    assert report.pending_at_start == 0
    assert ct.calls == [] and ot.calls == []


def test_progress_reports_the_doi_the_resolution_bought(tmp_path):
    conn = _conn(tmp_path, [
        _ref("r1", "sin doi en el parser"),
        _ref("r2", "con doi", order=2, parsed=_parsed(title="Otro", doi="10.5555/yyy")),
    ])
    fetch_missing(conn, _backends()[0], rate_per_second=0, sleep=_no_sleep)
    decide_pending(conn)

    progress = resolution_progress(conn)

    assert progress["references"] == 2
    assert progress["doi"]["from_parser"] == 1
    assert progress["doi"]["gained_by_resolution"] == 1
    assert progress["doi"]["combined_pct"] == 100.0
    assert progress["queries_pending"] == 0


def test_build_backends_rejects_unknown_names():
    with pytest.raises(ValueError, match="desconocido"):
        build_backends(names=("scopus",))


class FlakyTransport:
    """Answers 429 for the first `fail_times` calls, then succeeds."""

    def __init__(self, payload, fail_times):
        self.payload = payload
        self.remaining = fail_times
        self.calls = 0

    def __call__(self, url, headers, timeout):
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return self.payload


def test_a_partial_answer_is_not_cached(tmp_path):
    """One backend down means the evidence is incomplete, not that it is known.

    The decision tier depends on independent sources agreeing, so caching this
    would permanently record less confidence than the evidence supports.
    """
    conn = _conn(tmp_path, [_ref("r1", "una")])
    crossref = CrossrefBackend(transport=FakeTransport(CROSSREF_HIT))
    openalex = OpenAlexBackend(transport=FakeTransport(error=TimeoutError("down")))

    report = fetch_missing(conn, [crossref, openalex], rate_per_second=0,
                           consecutive_failure_limit=0, sleep=_no_sleep)

    assert report.fetched == 0
    assert report.partial_answers == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 0
    assert len(pending_queries(conn)) == 1


def test_a_throttled_backend_is_retried_after_backing_off(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    ct = FakeTransport(CROSSREF_HIT)
    ot = FlakyTransport(OPENALEX_HIT, fail_times=2)
    slept = []

    report = fetch_missing(conn, [CrossrefBackend(transport=ct), OpenAlexBackend(transport=ot)],
                           rate_per_second=2.0, sleep=lambda s: slept.append(s))

    assert report.fetched == 1
    assert report.rate_limited == 2
    assert ot.calls == 3
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 1
    # cada 429 duplica el intervalo de ESE backend
    assert report.final_intervals.get("openalex", 0) > 0.5


def test_a_persistently_throttled_backend_fails_instead_of_caching(tmp_path):
    conn = _conn(tmp_path, [_ref("r1", "una")])
    ct = FakeTransport(CROSSREF_HIT)
    ot = FlakyTransport(OPENALEX_HIT, fail_times=99)

    report = fetch_missing(conn, [CrossrefBackend(transport=ct), OpenAlexBackend(transport=ot)],
                           rate_per_second=0, consecutive_failure_limit=0, sleep=_no_sleep)

    assert report.fetched == 0
    assert report.failed == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"] == 0
    assert "429" in conn.execute("SELECT last_error FROM resolution_failure").fetchone()["last_error"]


def test_throttling_one_backend_does_not_slow_the_other(tmp_path):
    from biblioref.derived.batch import _BackendPacer

    pacer = _BackendPacer(2.0, sleep=_no_sleep)
    assert pacer.interval("crossref") == 0.5
    pacer.penalize("openalex")
    assert pacer.interval("openalex") == 1.0
    assert pacer.interval("crossref") == 0.5


def test_a_recovering_backend_earns_its_speed_back():
    from biblioref.derived.batch import _BackendPacer

    pacer = _BackendPacer(2.0, sleep=_no_sleep)
    pacer.penalize("openalex")
    pacer.penalize("openalex")
    assert pacer.interval("openalex") == 2.0
    for _ in range(20):
        pacer.relax("openalex")
    assert pacer.interval("openalex") == 0.5
    assert pacer.snapshot() == {}
