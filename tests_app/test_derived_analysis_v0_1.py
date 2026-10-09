# -*- coding: utf-8 -*-
"""Corpus analysis v0.1.

The invariant under test is the one that makes these figures publishable: every
metric states the base it was computed over, and nothing that could not be
identified is quietly dropped from a percentage.
"""
import pytest

from biblioref.derived import open_store, sync_documents
from biblioref.derived.analysis import (
    bibliographic_coupling,
    co_citation,
    coverage,
    document_types,
    full_report,
    group_comparison,
    identity_sensitivity,
    obsolescence,
    temporal_distribution,
    top_sources,
    top_works,
)
from biblioref.derived.identity import work_keys


def _parsed(**over):
    base = {
        "parser_version": "p", "author": "Smith, John", "authors": "Smith, John",
        "year": "2010", "title": "Machine learning in psychology", "journal": "Journal of X",
        "publisher": None, "doi": None, "publication_type": "articulo_revista",
    }
    base.update(over)
    return base


def _ref(ref_id, order=1, **parsed):
    return {
        "id": ref_id, "order": order, "text": f"texto {ref_id}", "original_text": "",
        "start_page": 1, "end_page": 1, "status": "ok", "source": "automatic",
        "edited": False, "deleted": False, "parsed": _parsed(**parsed),
    }


def _doc(doc_id, refs, university="UNMdP", year="2020", program="Doctorado"):
    return {
        "id": doc_id, "thesis_id": doc_id, "title": f"Tesis {doc_id}", "filename": f"{doc_id}.pdf",
        "project_id": "p1", "n_references": len(refs), "content_sha256": doc_id, "updated_at": 1,
        "metadata": {"university": university, "year": year, "program": program},
        "references": refs,
    }


def _store(conn, *docs):
    sync_documents(conn, {"schema": 2, "documents": {d["id"]: d for d in docs}})
    return conn


@pytest.fixture
def conn(tmp_path):
    return open_store(tmp_path / "derived.sqlite3")


def test_coverage_reports_what_it_could_not_identify(conn):
    _store(conn, _doc("d1", [
        _ref("r1", title="Un titulo suficientemente largo"),
        _ref("r2", 2, title=None, authors=None, author=None),
    ]))
    got = coverage(conn)

    assert got["references"] == 2
    assert got["identifiable"]["n"] == 1
    assert got["identifiable"]["excluded"] == 1
    assert got["identifiable"]["excluded_pct"] == 50.0


def test_obsolescence_states_its_base_and_exclusions(conn):
    _store(conn, _doc("d1", [
        _ref("r1", year="2010"),                 # 10 años
        _ref("r2", 2, year="2000", title="Otro titulo bastante largo aca"),   # 20 años
        _ref("r3", 3, year=None, title="Un tercer titulo largo tambien"),     # sin año
    ], year="2020"))
    got = obsolescence(conn)

    assert got["base"] == 2
    assert got["excluded"] == 1
    assert got["base_pct"] == 66.7
    assert got["median"] in (10, 20)
    assert got["price_index_pct"] == 0.0


def test_obsolescence_without_usable_years_reports_an_empty_base(conn):
    _store(conn, _doc("d1", [_ref("r1", year=None)], year=None))
    got = obsolescence(conn)

    assert got["base"] == 0
    assert "median" not in got


def test_document_types_percentages_sum_over_their_own_base(conn):
    _store(conn, _doc("d1", [
        _ref("r1", publication_type="libro"),
        _ref("r2", 2, publication_type="libro", title="Otro titulo bastante largo"),
        _ref("r3", 3, publication_type="articulo_revista", title="Tercer titulo largo aca"),
    ]))
    got = document_types(conn)

    assert got["base"] == 3
    assert got["types"][0] == {"type": "libro", "n": 2, "pct": 66.7}


def test_top_works_ranks_by_theses_not_by_repetition(conn):
    citada_mucho_en_una = [_ref(f"a{i}", i, title="Obra repetida dentro de una tesis") for i in range(1, 6)]
    _store(
        conn,
        _doc("d1", citada_mucho_en_una),
        _doc("d2", [_ref("b1", title="Obra citada por varias tesis")]),
        _doc("d3", [_ref("c1", title="Obra citada por varias tesis")]),
    )
    works = top_works(conn)["works"]

    assert works[0]["theses"] == 2
    assert works[0]["references"] == 2
    assert works[1]["theses"] == 1
    assert works[1]["references"] == 5


def test_identity_sensitivity_exposes_the_re_edition_question(conn):
    _store(conn, _doc("d1", [
        _ref("r1", year="1971", title="Realidad y juego", authors="Winnicott, D."),
        _ref("r2", 2, year="1993", title="Realidad y juego", authors="Winnicott, D."),
    ]))
    got = identity_sensitivity(conn)

    assert got["works_with_year"] == 2
    assert got["works_ignoring_year"] == 1
    assert got["works_merged_by_ignoring_year"] == 1


def test_coupling_reports_jaccard_beside_the_raw_count(conn):
    compartida = dict(title="Una obra compartida entre tesis")
    _store(
        conn,
        _doc("d1", [_ref("r1", **compartida), _ref("r2", 2, title="Propia de la primera tesis")]),
        _doc("d2", [_ref("r3", **compartida)]),
    )
    got = bibliographic_coupling(conn, min_shared=1)

    assert len(got["pairs"]) == 1
    par = got["pairs"][0]
    assert par["shared_works"] == 1
    assert par["jaccard"] == 0.5          # 1 compartida sobre 2 distintas
    assert par["a_university"] == "UNMdP"


def test_coupling_respects_its_threshold(conn):
    _store(
        conn,
        _doc("d1", [_ref("r1", title="Una obra compartida entre tesis")]),
        _doc("d2", [_ref("r2", title="Una obra compartida entre tesis")]),
    )
    assert bibliographic_coupling(conn, min_shared=2)["pairs"] == []


def test_co_citation_counts_theses_not_pairs(conn):
    a = dict(title="Primera obra del par co citado")
    b = dict(title="Segunda obra del par co citado")
    _store(
        conn,
        _doc("d1", [_ref("r1", **a), _ref("r2", 2, **b)]),
        _doc("d2", [_ref("r3", **a), _ref("r4", 2, **b)]),
    )
    got = co_citation(conn, min_theses=2)

    assert len(got["pairs"]) == 1
    assert got["pairs"][0]["theses"] == 2


def test_group_comparison_names_what_it_could_not_group(conn):
    _store(
        conn,
        _doc("d1", [_ref("r1")], university="UNMdP"),
        _doc("d2", [_ref("r2", title="Otro titulo bastante largo")], university=None),
    )
    got = group_comparison(conn, by="university")

    assert got["documents"] == 2
    assert got["ungrouped_documents"] == 1
    assert got["ungrouped_pct"] == 50.0
    assert [g["group"] for g in got["groups"]] == ["UNMdP"]


def test_group_comparison_rejects_an_unsupported_field(conn):
    with pytest.raises(ValueError, match="agrupación"):
        group_comparison(conn, by="doi")


def test_temporal_distribution_buckets_by_decade(conn):
    _store(conn, _doc("d1", [
        _ref("r1", year="1995"),
        _ref("r2", 2, year="1999", title="Otro titulo bastante largo aca"),
        _ref("r3", 3, year="2004", title="Tercer titulo largo por aca"),
    ]))
    got = temporal_distribution(conn)

    assert {d["decade"]: d["n"] for d in got["decades"]} == {1990: 2, 2000: 1}
    assert got["base"] == 3


def test_top_sources_reports_its_base(conn):
    _store(conn, _doc("d1", [
        _ref("r1", journal="Psicothema"),
        _ref("r2", 2, journal=None, title="Otro titulo bastante largo aca"),
    ]))
    got = top_sources(conn)

    assert got["base"] == 1
    assert got["sources"][0]["journal"] == "Psicothema"


def test_an_empty_corpus_does_not_pretend_to_have_figures(conn):
    got = coverage(conn)
    assert got["references"] == 0
    assert "fields" not in got


def test_full_report_carries_every_section(conn):
    _store(conn, _doc("d1", [_ref("r1")]), _doc("d2", [_ref("r2", title="Otro titulo bastante largo")]))
    got = full_report(conn)

    for section in ("coverage", "document_types", "obsolescence", "temporal",
                    "identity_sensitivity", "top_works", "top_sources",
                    "coupling", "co_citation", "groups"):
        assert section in got, section
    assert got["coverage"]["references"] == 2


def test_a_title_that_only_repeats_the_author_is_not_a_work():
    """A known parser failure must not fuse into a fake work."""
    strict, loose = work_keys({"authors": "Yedaide, María Marta", "author": "Yedaide, María Marta",
                               "year": "2015", "title": "Yedaide, María Marta", "doi": None})
    assert strict is None and loose is None


def test_coverage_counts_theses_with_no_references_at_all(conn):
    """An extraction failure is a finding, not a document to leave out."""
    _store(conn, _doc("d1", [_ref("r1")]), _doc("d2", []))
    got = coverage(conn)

    assert got["documents"] == 2
    assert got["documents_with_references"] == 1
    assert got["documents_without_references"] == 1


def test_an_impossible_year_is_reported_not_charted(conn):
    """A page range read as a year would otherwise invent a decade."""
    _store(conn, _doc("d1", [
        _ref("r1", year="2010"),
        _ref("r2", 2, year="2044", title="Otro titulo bastante largo aca"),
    ]))
    got = temporal_distribution(conn, max_year=2026)

    assert got["out_of_range"] == 1
    assert got["base"] == 1
    assert [d["decade"] for d in got["decades"]] == [2010]


def test_co_citation_pruning_does_not_lose_pairs(conn):
    """The optimisation prunes works below the threshold; it must not prune pairs."""
    from biblioref.derived.analysis import co_citation as cc

    a = dict(title="Primera obra del par co citado")
    b = dict(title="Segunda obra del par co citado")
    solitaria = dict(title="Obra citada por una sola tesis")
    _store(
        conn,
        _doc("d1", [_ref("r1", **a), _ref("r2", 2, **b), _ref("r3", 3, **solitaria)]),
        _doc("d2", [_ref("r4", **a), _ref("r5", 2, **b)]),
        _doc("d3", [_ref("r6", **a), _ref("r7", 2, **b)]),
    )

    assert len(cc(conn, min_theses=3)["pairs"]) == 1
    assert cc(conn, min_theses=3)["pairs"][0]["theses"] == 3
    assert len(cc(conn, min_theses=4)["pairs"]) == 0


def test_nothing_is_analysed_until_it_is_asked_for(conn):
    from biblioref.derived.analysis import stored_report

    _store(conn, _doc("d1", [_ref("r1")]))
    assert stored_report(conn) is None


def test_a_stored_report_comes_back_with_its_date(conn):
    from biblioref.derived.analysis import run_and_store, stored_report

    _store(conn, _doc("d1", [_ref("r1")]))
    ran = run_and_store(conn)
    got = stored_report(conn)

    assert got is not None
    assert got["stale"] is False
    assert got["generated_at"] == ran["generated_at"]
    assert got["report"]["coverage"]["references"] == 1


def test_editing_the_corpus_marks_the_stored_report_stale(conn):
    from biblioref.derived.analysis import run_and_store, stored_report

    _store(conn, _doc("d1", [_ref("r1")]))
    run_and_store(conn)
    assert stored_report(conn)["stale"] is False

    _store(conn, _doc("d1", [_ref("r1"), _ref("r2", 2, title="Otro titulo bastante largo")]))
    assert stored_report(conn)["stale"] is True


def test_a_correction_that_keeps_the_count_still_marks_it_stale(conn):
    """A cheaper fingerprint would miss exactly the change that matters most."""
    from biblioref.derived.analysis import run_and_store, stored_report

    _store(conn, _doc("d1", [_ref("r1", title="Titulo con un error de parseo")]))
    run_and_store(conn)

    _store(conn, _doc("d1", [_ref("r1", title="Titulo corregido a mano por el usuario")]))
    assert stored_report(conn)["stale"] is True


def test_each_grouping_keeps_its_own_report(conn):
    from biblioref.derived.analysis import run_and_store, stored_report

    _store(conn, _doc("d1", [_ref("r1")]))
    run_and_store(conn, group_by="university")
    assert stored_report(conn, group_by="program") is None
    assert stored_report(conn, group_by="university") is not None


def test_only_the_last_runs_are_kept(conn):
    _store(conn, _doc("d1", [_ref("r1")]))
    from biblioref.derived.analysis import run_and_store

    for _ in range(7):
        run_and_store(conn)

    kept = conn.execute("SELECT COUNT(*) AS n FROM analysis_report").fetchone()["n"]
    assert kept == 5


def test_both_fingerprints_agree_on_the_same_corpus(conn):
    """The whole staleness mechanism rests on these two never drifting apart."""
    from biblioref.derived.analysis import corpus_fingerprint
    from biblioref.derived.sync import source_fingerprint

    docs = [
        _doc("d2", [_ref("r3"), _ref("r4", 2, title="Otro titulo bastante largo aca")]),
        _doc("d1", [_ref("r1"), _ref("r2", 2, title="Un tercer titulo largo por aca")]),
    ]
    store = {"schema": 2, "documents": {d["id"]: d for d in docs}}
    sync_documents(conn, store)

    assert source_fingerprint(store) == corpus_fingerprint(conn)


def test_a_deleted_reference_is_excluded_from_both_fingerprints(conn):
    from biblioref.derived.analysis import corpus_fingerprint
    from biblioref.derived.sync import source_fingerprint

    borrada = _ref("r2", 2, title="Una referencia borrada por el usuario")
    borrada["deleted"] = True
    store = {"schema": 2, "documents": {"d1": _doc("d1", [_ref("r1"), borrada])}}
    sync_documents(conn, store)

    assert source_fingerprint(store) == corpus_fingerprint(conn)
