from biblioref.resolver.consensus import ConsensusEngine
from biblioref.resolver.models import Candidate, CandidateBatch, ResolverQuery


def _batch(query, *candidates):
    return CandidateBatch(query=query, candidates=tuple(candidates))


def test_exact_query_doi_has_highest_status_even_with_single_source():
    query = ResolverQuery(raw_reference="x", doi="10.1234/one")
    candidate = Candidate.from_mapping("crossref", {"doi": "10.1234/one"})
    result = ConsensusEngine().assess(_batch(query, candidate))
    assert result.status == "exact_identifier"
    assert result.leading_candidate_index == 0


def test_same_external_doi_from_two_sources_is_external_consensus_without_parser_doi():
    query = ResolverQuery(
        raw_reference="Pérez, A. (2020). Un estudio.",
        title="Un estudio",
        authors=("Pérez, A.",),
        year="2020",
    )
    crossref = Candidate.from_mapping(
        "crossref",
        {"doi": "10.1234/one", "title": "Un estudio", "author": "Pérez, A.", "year": 2020},
    )
    openalex = Candidate.from_mapping(
        "openalex",
        {"doi": "10.1234/one", "title": "Un estudio", "author": "Pérez, A.", "year": 2020},
    )
    result = ConsensusEngine().assess(_batch(query, crossref, openalex))
    assert result.status == "external_consensus"
    assert result.cross_source_identity_groups == ((0, 1),)


def test_two_competing_cross_source_doi_groups_are_not_auto_verified_when_close():
    query = ResolverQuery(
        raw_reference="UMAP. (2018). Uniform Manifold Approximation and Projection.",
        title="UMAP Uniform Manifold Approximation and Projection",
        year="2018",
    )
    wrong_crossref = Candidate.from_mapping(
        "crossref",
        {"doi": "10.1111/package", "title": "UMAP Uniform Manifold Approximation and Projection", "year": 2018},
    )
    wrong_openalex = Candidate.from_mapping(
        "openalex",
        {"doi": "10.1111/package", "title": "UMAP Uniform Manifold Approximation and Projection", "year": 2018},
    )
    correct_crossref = Candidate.from_mapping(
        "crossref",
        {"doi": "10.2222/article", "title": "UMAP: Uniform Manifold Approximation and Projection", "year": 2018},
    )
    correct_openalex = Candidate.from_mapping(
        "openalex",
        {"doi": "10.2222/article", "title": "UMAP: Uniform Manifold Approximation and Projection", "year": 2018},
    )
    result = ConsensusEngine().assess(
        _batch(query, wrong_crossref, wrong_openalex, correct_crossref, correct_openalex)
    )
    assert len(result.cross_source_identity_groups) == 2
    assert result.status == "ambiguous_conflict"
    assert "competing_cross_source_identities_prevent_auto_consensus" in result.notes


def test_strongly_separated_cross_source_group_can_still_be_external_consensus():
    query = ResolverQuery(
        raw_reference="A precise title. 2020",
        title="A precise title",
        authors=("Smith, J.",),
        year="2020",
    )
    good_a = Candidate.from_mapping(
        "crossref",
        {"doi": "10.1111/good", "title": "A precise title", "author": "Smith, J.", "year": 2020},
    )
    good_b = Candidate.from_mapping(
        "openalex",
        {"doi": "10.1111/good", "title": "A precise title", "author": "Smith, J.", "year": 2020},
    )
    rival_a = Candidate.from_mapping(
        "crossref",
        {"doi": "10.1111/rival", "title": "A related but different title", "author": "Jones, P.", "year": 2019},
    )
    rival_b = Candidate.from_mapping(
        "openalex",
        {"doi": "10.1111/rival", "title": "A related but different title", "author": "Jones, P.", "year": 2019},
    )
    result = ConsensusEngine().assess(_batch(query, good_a, good_b, rival_a, rival_b))
    assert result.status == "external_consensus"


def test_close_distinct_candidates_are_left_ambiguous():
    query = ResolverQuery(
        raw_reference="x",
        title="Social anxiety in university students",
        authors=("Smith, J.",),
        year="2020",
    )
    a = Candidate.from_mapping(
        "crossref",
        {"title": "Social anxiety in university students", "author": "Smith, J.", "year": 2020},
    )
    b = Candidate.from_mapping(
        "openalex",
        {"title": "Social anxiety in university student", "author": "Smith, J.", "year": 2020},
    )
    result = ConsensusEngine().assess(_batch(query, a, b))
    assert result.status == "ambiguous_conflict"


def test_year_conflict_is_exposed_not_silently_corrected():
    query = ResolverQuery(
        raw_reference="x",
        title="A title",
        authors=("García, M.",),
        year="2017",
    )
    candidate = Candidate.from_mapping(
        "crossref",
        {"title": "A title", "author": "García, M.", "year": 2019},
    )
    result = ConsensusEngine().assess(_batch(query, candidate))
    assessment = result.assessments[0]
    assert "year_conflict" in assessment.contradictory
    assert result.status in {"ambiguous_conflict", "unresolved"}


def test_score_is_documented_as_evidence_not_probability():
    query = ResolverQuery(raw_reference="x", title="A title")
    candidate = Candidate.from_mapping("crossref", {"title": "A title"})
    result = ConsensusEngine().assess(_batch(query, candidate))
    assert "evidence_score_is_not_probability" in result.notes
