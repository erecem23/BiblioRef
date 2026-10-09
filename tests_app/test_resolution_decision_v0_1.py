from biblioref.resolver.adjudicator import AdjudicationResult
from biblioref.resolver.consensus import CandidateAssessment, ConsensusResult
from biblioref.resolver.decision import (
    AI_SUPPORTED_MATCH,
    POSSIBLE_MATCH,
    UNRESOLVED,
    VERIFIED_EXACT,
    VERIFIED_EXTERNAL_CONSENSUS,
    VERIFIED_SEMANTIC,
    ResolutionDecisionEngine,
)
from biblioref.resolver.models import Candidate, CandidateBatch, ResolverQuery
from biblioref.resolver.semantic import SemanticCandidateScore, SemanticResult


def _candidate(source="crossref", doi=None, title="A study", year="2020", author="Smith"):
    return Candidate(
        source=source,
        source_id=f"{source}:1",
        doi=doi,
        title=title,
        year=year,
        authors=(author,),
        container_title="Journal",
    )


def _batch(candidates, doi=None):
    return CandidateBatch(
        query=ResolverQuery(
            raw_reference="Smith (2020). A study. Journal.",
            title="A study",
            authors=("Smith",),
            year="2020",
            journal="Journal",
            doi=doi,
        ),
        candidates=tuple(candidates),
    )


def _assessment(index, score=0.8, contradictory=()):
    return CandidateAssessment(
        candidate_index=index,
        source="crossref",
        source_id=f"id:{index}",
        identity_key=None,
        evidence_score=score,
        positive=("title_strong",),
        contradictory=tuple(contradictory),
    )


def _consensus(status, leader=0, assessments=(), groups=()):
    return ConsensusResult(
        version="metadata-consensus-v0.1",
        status=status,
        leading_candidate_index=leader,
        assessments=tuple(assessments),
        cross_source_identity_groups=tuple(tuple(x) for x in groups),
        notes=("evidence_score_is_not_probability",),
    )


def _semantic(leader=0, scores=((0, 0.9),), status="ranked"):
    return SemanticResult(
        version="semantic-resolver-v0.1",
        status=status,
        backend="fake-embedding",
        query_text_source="parsed_title",
        leading_candidate_index=leader,
        scores=tuple(SemanticCandidateScore(candidate_index=i, similarity=s) for i, s in scores),
        notes=("semantic_similarity_is_not_match_probability",),
    )


def _ai(status="candidate_selected", selected=0):
    return AdjudicationResult(
        version="local-ai-adjudicator-v0.1",
        status=status,
        shadow_mode=True,
        backend="fake-local",
        model="fake-model",
        consensus_status="ambiguous_conflict",
        candidate_count=2,
        selected_candidate_index=selected,
        selected_identity_key=None,
        reason_codes=("title_match",),
        considered_candidate_indexes=(0, 1),
        semantic_leading_candidate_index=0,
        notes=("shadow",),
    )


def test_exact_doi_becomes_verified_exact():
    batch = _batch([_candidate(doi="10.1000/test")], doi="10.1000/test")
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("exact_identifier", assessments=[_assessment(0, 1.0)])
    )
    assert result.status == VERIFIED_EXACT
    assert result.selected_candidate_index == 0
    assert result.review_required is False


def test_exact_identifier_inconsistent_is_not_promoted():
    batch = _batch([_candidate(doi="10.1000/other")], doi="10.1000/test")
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("exact_identifier", assessments=[_assessment(0, 1.0)])
    )
    assert result.status == UNRESOLVED
    assert "exact_identifier_without_reproducible_doi_match" in result.warnings


def test_cross_source_consensus_has_its_own_verified_tier():
    first = _candidate(source="crossref", doi="10.1000/test")
    second = _candidate(source="openalex", doi="10.1000/test")
    batch = _batch([first, second])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus(
            "external_consensus",
            leader=0,
            assessments=[_assessment(0, 0.95), _assessment(1, 0.94)],
            groups=[(0, 1)],
        ),
    )
    assert result.status == VERIFIED_EXTERNAL_CONSENSUS
    assert result.review_required is False


def test_external_consensus_without_group_is_rejected():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("external_consensus", assessments=[_assessment(0, 0.95)])
    )
    assert result.status == UNRESOLVED


def test_probable_plus_same_strong_semantic_leader_is_verified_semantic():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("probable_candidate", leader=0, assessments=[_assessment(0, 0.9), _assessment(1, 0.4)]),
        _semantic(leader=0, scores=((0, 0.91), (1, 0.3))),
    )
    assert result.status == VERIFIED_SEMANTIC
    assert result.selected_candidate_index == 0
    assert result.review_required is False


def test_probable_without_semantic_remains_possible_and_reviewable():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("probable_candidate", assessments=[_assessment(0, 0.9)])
    )
    assert result.status == POSSIBLE_MATCH
    assert result.review_required is True


def test_probable_with_semantic_disagreement_is_not_verified():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("probable_candidate", leader=0, assessments=[_assessment(0, 0.9), _assessment(1, 0.7)]),
        _semantic(leader=1, scores=((1, 0.95), (0, 0.7))),
    )
    assert result.status == POSSIBLE_MATCH
    assert "semantic_leader_disagrees_with_consensus_leader" in result.warnings


def test_ai_selected_with_independent_metadata_support_is_ai_supported():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("ambiguous_conflict", leader=0, assessments=[_assessment(0, 0.72), _assessment(1, 0.7)]),
        _semantic(leader=0, scores=((0, 0.84), (1, 0.81))),
        _ai(selected=0),
    )
    assert result.status == AI_SUPPORTED_MATCH
    assert result.selected_candidate_index == 0
    assert result.review_required is True


def test_ai_can_never_be_only_support_for_a_match():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("ambiguous_conflict", leader=0, assessments=[_assessment(0, 0.2), _assessment(1, 0.2)]),
        _semantic(leader=0, scores=((0, 0.4), (1, 0.3))),
        _ai(selected=0),
    )
    assert result.status == UNRESOLVED
    assert "ai_selection_requires_non_ai_support" in result.warnings


def test_strong_semantic_disagreement_blocks_ai_selection():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("ambiguous_conflict", leader=0, assessments=[_assessment(0, 0.7), _assessment(1, 0.7)]),
        _semantic(leader=1, scores=((1, 0.93), (0, 0.8))),
        _ai(selected=0),
    )
    assert result.status == UNRESOLVED
    assert "ai_and_semantic_leaders_disagree" in result.warnings


def test_ai_abstention_stays_unresolved():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("ambiguous_conflict", leader=0, assessments=[_assessment(0, 0.6), _assessment(1, 0.6)]),
        adjudication=_ai(status="abstained", selected=None),
    )
    assert result.status == UNRESOLVED
    assert "ai_abstained" in result.warnings


def test_semantic_only_strong_candidate_can_be_possible_not_verified():
    batch = _batch([_candidate(), _candidate(source="openalex", title="Other")])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("unresolved", leader=0, assessments=[_assessment(0, 0.62), _assessment(1, 0.3)]),
        _semantic(leader=0, scores=((0, 0.94), (1, 0.2))),
    )
    assert result.status == POSSIBLE_MATCH
    assert result.review_required is True


def test_semantic_candidate_with_contradiction_stays_unresolved():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("unresolved", leader=0, assessments=[_assessment(0, 0.7, ("year_conflict",))]),
        _semantic(leader=0, scores=((0, 0.95),)),
    )
    assert result.status == UNRESOLVED


def test_no_candidates_is_unresolved():
    batch = _batch([])
    result = ResolutionDecisionEngine().decide(batch, _consensus("unresolved", leader=None))
    assert result.status == UNRESOLVED
    assert result.selected_candidate_index is None


def test_ai_out_of_range_index_is_rejected_even_if_object_was_forged():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch,
        _consensus("ambiguous_conflict", leader=0, assessments=[_assessment(0, 0.8)]),
        adjudication=_ai(selected=9),
    )
    assert result.status == UNRESOLVED
    assert "ai_selected_candidate_out_of_range" in result.warnings


def test_unknown_consensus_status_fails_closed():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("future_status", leader=0, assessments=[_assessment(0, 0.9)])
    )
    assert result.status == UNRESOLVED
    assert "unknown_consensus_status" in result.warnings


def test_thresholds_must_be_bounded():
    try:
        ResolutionDecisionEngine(verified_semantic_threshold=1.2)
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_as_dict_contains_audit_chain_but_not_candidate_metadata():
    batch = _batch([_candidate()])
    result = ResolutionDecisionEngine().decide(
        batch, _consensus("probable_candidate", assessments=[_assessment(0, 0.9)])
    )
    payload = result.as_dict()
    assert payload["status"] == POSSIBLE_MATCH
    assert payload["consensus_version"] == "metadata-consensus-v0.1"
    assert "raw_metadata" not in payload
    assert "title" not in payload
    assert "doi" not in payload
