import json
from types import SimpleNamespace

from biblioref.resolver.benchmark import calibrate_semantic_threshold, load_gold, prepare_cases, summarize
from biblioref.resolver.models import Candidate, CandidateBatch, ResolverQuery


def test_load_gold_normalizes_doi_and_preserves_labels(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(
        json.dumps({"work_id": "x", "doi": "https://doi.org/10.1038/NPHYS1170", "domain": "physics"}) + "\n",
        encoding="utf-8",
    )
    works = load_gold(path)
    assert len(works) == 1
    assert works[0].doi == "10.1038/nphys1170"
    assert works[0].domain == "physics"


def test_prepare_cases_never_leaks_gold_doi_into_query():
    candidate = Candidate(
        source="crossref",
        source_id="10.1038/nature14539",
        doi="10.1038/nature14539",
        title="Deep learning",
        authors=("Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"),
        year="2015",
        container_title="Nature",
    )
    work = load_gold_from_text("ml", "10.1038/nature14539")
    cases = prepare_cases(work, candidate)
    assert [case.variant for case in cases] == ["clean", "title_year", "short_title"]
    assert all(case.query.doi is None for case in cases)
    assert all("10.1038/nature14539" not in case.query.raw_reference for case in cases)


def load_gold_from_text(work_id, doi):
    from biblioref.resolver.benchmark import GoldWork
    return GoldWork(work_id=work_id, doi=doi, domain="test")


def test_summarize_reports_false_verified_and_review_rate():
    rows = [
        {
            "expected_in_candidates": True,
            "selected_doi": "10.good/a",
            "selected_correct": True,
            "decision_status": "VERIFIED_SEMANTIC",
            "false_verified": False,
            "review_required": False,
        },
        {
            "expected_in_candidates": True,
            "selected_doi": "10.bad/b",
            "selected_correct": False,
            "decision_status": "VERIFIED_SEMANTIC",
            "false_verified": True,
            "review_required": False,
        },
        {
            "expected_in_candidates": False,
            "selected_doi": None,
            "selected_correct": False,
            "decision_status": "UNRESOLVED",
            "false_verified": False,
            "review_required": True,
        },
    ]
    metrics = summarize(rows)
    assert metrics["candidate_recall_at_returned"] == 0.6667
    assert metrics["auto_verified_precision"] == 0.5
    assert metrics["false_verified_count"] == 1
    assert metrics["review_required_rate"] == 0.3333


def test_calibration_ignores_exact_or_external_consensus_cases():
    work = load_gold_from_text("x", "10.1/x")
    case = SimpleNamespace(work=work)
    batch = CandidateBatch(query=ResolverQuery(raw_reference="x"), candidates=())
    semantic = SimpleNamespace()
    prepared = [
        (case, batch, SimpleNamespace(status="exact_identifier"), semantic),
        (case, batch, SimpleNamespace(status="external_consensus"), semantic),
    ]
    result = calibrate_semantic_threshold(prepared)
    assert result["n_calibration_cases"] == 0
    assert result["recommended_verified_semantic_threshold"] is None
