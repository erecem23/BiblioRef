import pytest

from biblioref.resolver.models import ResolverQuery
from biblioref.resolver.rag import (
    BIBLIOGRAPHIC_RAG_VERSION,
    BibliographicRAG,
    EvidenceRecord,
    EvidenceStore,
)


class FakeEmbeddingBackend:
    name = "fake-local-embeddings"

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        return self.vectors


def record(
    evidence_id,
    title,
    *,
    status="verified_exact",
    authors=("García, A.",),
    year="2020",
    doi=None,
    provenance="fixture",
    raw_reference="",
):
    return EvidenceRecord(
        evidence_id=evidence_id,
        verification_status=status,
        provenance=provenance,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        raw_reference=raw_reference,
    )


def test_untrusted_or_ai_only_records_cannot_enter_rag_store():
    for status in ("possible_match", "ai_supported_match", "unresolved", "verified_semantic"):
        with pytest.raises(ValueError, match="RAG evidence"):
            record("x", "Título", status=status)


def test_human_confirmed_record_is_explicitly_allowed():
    item = record("h1", "Redes complejas en psicología", status="human_confirmed")
    store = EvidenceStore([item])
    assert len(store) == 1
    assert store.records[0].verification_status == "human_confirmed"


def test_store_deduplicates_same_identity_and_prefers_human_confirmation():
    weak = record(
        "e1",
        "Redes complejas en psicología",
        status="verified_external_consensus",
        doi="10.1000/example",
    )
    human = record(
        "e2",
        "Redes complejas en psicología",
        status="human_confirmed",
        doi="https://doi.org/10.1000/example",
        provenance="author-choice",
    )
    store = EvidenceStore([weak, human])
    assert len(store) == 1
    assert store.records[0].evidence_id == "e2"
    assert store.records[0].provenance == "author-choice"


def test_duplicate_evidence_id_with_conflicting_content_is_rejected():
    store = EvidenceStore([record("e1", "Título A")])
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        store.add(record("e1", "Título B"))


def test_deterministic_lexical_rag_retrieves_relevant_verified_reference():
    store = EvidenceStore(
        [
            record("e1", "Redes complejas en psicología", doi="10.1000/a"),
            record("e2", "Biología molecular de plantas", authors=("Smith, J.",), doi="10.1000/b"),
        ]
    )
    query = ResolverQuery(
        raw_reference="García, A. (2020). Redes complejas en psicología.",
        title="Redes complejas en psicología",
        authors=("García, A.",),
        year="2020",
    )
    result = BibliographicRAG(store, semantic_weight=0.0).retrieve(query)
    assert result.version == BIBLIOGRAPHIC_RAG_VERSION
    assert result.status == "retrieved"
    assert result.query_text_source == "parsed_fields"
    assert result.retrieved[0].evidence_id == "e1"
    assert result.retrieved[0].record.doi == "10.1000/a"
    assert "resolution_decision" in result.notes[0]


def test_accents_are_normalized_for_lexical_retrieval():
    store = EvidenceStore([record("e1", "Psicología y educación")])
    query = ResolverQuery(raw_reference="", title="Psicologia y educacion", year="2020")
    result = BibliographicRAG(store, semantic_weight=0.0).retrieve(query)
    assert result.retrieved[0].evidence_id == "e1"
    assert result.retrieved[0].lexical_score > 0.0


def test_raw_reference_is_used_only_when_parsed_fields_are_absent():
    store = EvidenceStore(
        [
            record(
                "e1",
                "",
                raw_reference="García A 2020 Redes complejas en psicología Journal X",
                doi="10.1000/a",
            )
        ]
    )
    query = ResolverQuery(raw_reference="Garcia A 2020 Redes complejas en psicologia Journal X")
    result = BibliographicRAG(store, semantic_weight=0.0).retrieve(query)
    assert result.query_text_source == "raw_reference"
    assert result.retrieved[0].evidence_id == "e1"


def test_hybrid_retrieval_can_add_optional_local_semantic_signal():
    store = EvidenceStore(
        [
            record("e1", "Título con poco solapamiento literal", doi="10.1000/a"),
            record("e2", "Otro documento", doi="10.1000/b"),
        ]
    )
    # query + e1 + e2; e1 is semantically identical in the fake embedding space
    backend = FakeEmbeddingBackend([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    query = ResolverQuery(raw_reference="Referencia ambigua sin coincidencia lexical clara")
    result = BibliographicRAG(
        store,
        embedding_backend=backend,
        lexical_weight=0.2,
        semantic_weight=0.8,
        min_score=0.01,
    ).retrieve(query)
    assert result.backend == "fake-local-embeddings"
    assert result.retrieved[0].evidence_id == "e1"
    assert result.retrieved[0].semantic_score == 1.0
    assert len(backend.calls) == 1


def test_embedding_backend_vector_count_is_validated():
    store = EvidenceStore([record("e1", "Título", doi="10.1000/a")])
    backend = FakeEmbeddingBackend([[1.0, 0.0]])
    with pytest.raises(ValueError, match="unexpected vector count"):
        BibliographicRAG(store, embedding_backend=backend).retrieve(
            ResolverQuery(raw_reference="Título")
        )


def test_empty_store_abstains_without_error():
    result = BibliographicRAG(EvidenceStore(), semantic_weight=0.0).retrieve(
        ResolverQuery(raw_reference="Referencia")
    )
    assert result.status == "insufficient_evidence"
    assert result.retrieved == ()


def test_retrieval_does_not_mutate_query_or_evidence():
    item = record("e1", "Redes complejas en psicología", doi="10.1000/a")
    store = EvidenceStore([item])
    query = ResolverQuery(raw_reference="Garcia 2020 Redes complejas", year="2020")
    before_query = query.as_dict()
    before_record = store.records[0].as_dict()
    BibliographicRAG(store, semantic_weight=0.0).retrieve(query)
    assert query.as_dict() == before_query
    assert store.records[0].as_dict() == before_record


def test_rag_output_keeps_provenance_and_does_not_claim_probability():
    store = EvidenceStore(
        [
            record(
                "e1",
                "Redes complejas en psicología",
                status="human_confirmed",
                provenance="author-confirmed:thesis-001",
                doi="10.1000/a",
            )
        ]
    )
    result = BibliographicRAG(store, semantic_weight=0.0).retrieve(
        ResolverQuery(raw_reference="", title="Redes complejas en psicología", year="2020")
    )
    payload = result.as_dict()
    assert payload["retrieved"][0]["record"]["provenance"] == "author-confirmed:thesis-001"
    assert "confidence" not in payload
    assert "probability" not in payload
