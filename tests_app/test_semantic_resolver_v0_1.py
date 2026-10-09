from biblioref.resolver.models import Candidate, CandidateBatch, ResolverQuery
from biblioref.resolver.semantic import SemanticResolver


class _FakeEmbeddings:
    name = "fake-embeddings"

    def __init__(self, mapping):
        self.mapping = mapping

    def encode(self, texts):
        return [self.mapping[text] for text in texts]


def test_semantic_resolver_prefers_parsed_title_and_ranks_candidates():
    query = ResolverQuery(
        raw_reference="Long raw citation",
        title="social anxiety in university students",
    )
    candidates = (
        Candidate.from_mapping("crossref", {"title": "social anxiety among college students"}),
        Candidate.from_mapping("openalex", {"title": "marine ecology in coastal waters"}),
    )
    mapping = {
        "social anxiety in university students": (1.0, 0.0),
        "social anxiety among college students": (0.9, 0.1),
        "marine ecology in coastal waters": (0.0, 1.0),
    }
    result = SemanticResolver(_FakeEmbeddings(mapping)).rank(
        CandidateBatch(query=query, candidates=candidates)
    )

    assert result.status == "ranked"
    assert result.query_text_source == "parsed_title"
    assert result.leading_candidate_index == 0
    assert result.scores[0].similarity > result.scores[1].similarity
    assert "semantic_similarity_is_not_match_probability" in result.notes


def test_semantic_resolver_uses_raw_reference_only_when_title_missing():
    query = ResolverQuery(raw_reference="raw citation text")
    candidate = Candidate.from_mapping("crossref", {"title": "candidate title"})
    mapping = {
        "raw citation text": (1.0, 0.0),
        "candidate title": (1.0, 0.0),
    }
    result = SemanticResolver(_FakeEmbeddings(mapping)).rank(
        CandidateBatch(query=query, candidates=(candidate,))
    )
    assert result.query_text_source == "raw_reference"
    assert result.leading_candidate_index == 0


def test_semantic_resolver_abstains_when_candidates_have_no_titles():
    query = ResolverQuery(raw_reference="citation")
    candidate = Candidate(source="crossref", doi="10.1/example")
    result = SemanticResolver(_FakeEmbeddings({})).rank(
        CandidateBatch(query=query, candidates=(candidate,))
    )
    assert result.status == "insufficient_evidence"
    assert result.leading_candidate_index is None


def test_semantic_resolver_rejects_wrong_embedding_count():
    class _Broken:
        name = "broken"

        def encode(self, texts):
            return [(1.0, 0.0)]

    query = ResolverQuery(raw_reference="citation", title="query title")
    candidate = Candidate.from_mapping("crossref", {"title": "candidate title"})
    try:
        SemanticResolver(_Broken()).rank(CandidateBatch(query=query, candidates=(candidate,)))
    except ValueError as exc:
        assert "unexpected vector count" in str(exc)
    else:
        raise AssertionError("expected ValueError")
