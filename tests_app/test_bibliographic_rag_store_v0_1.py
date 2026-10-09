from biblioref.resolver.models import Candidate
from biblioref.resolver.rag import EvidenceRecord, EvidenceStore
from biblioref.resolver.rag_store import (
    evidence_from_candidate,
    load_evidence_jsonl,
    save_evidence_jsonl,
)


def test_human_choice_adapter_copies_existing_candidate_without_invention():
    candidate = Candidate(
        source="openalex",
        source_id="W123",
        title="Redes complejas en psicología",
        authors=("García, A.",),
        year="2020",
        container_title="Journal X",
        publisher="Editorial X",
        doi="10.1000/example",
    )
    evidence = evidence_from_candidate(
        candidate,
        evidence_id="human-001",
        provenance="author-confirmed:thesis-001",
        raw_reference="García A. (2020). Redes complejas en psicología.",
        source_document_id="thesis-001",
    )
    assert evidence.verification_status == "human_confirmed"
    assert evidence.doi == candidate.doi
    assert evidence.title == candidate.title
    assert evidence.authors == candidate.authors
    assert evidence.provenance == "author-confirmed:thesis-001"


def test_human_choice_adapter_still_passes_through_rag_trust_gate():
    candidate = Candidate(source="crossref", title="Título", year="2020")
    try:
        evidence_from_candidate(
            candidate,
            evidence_id="x",
            provenance="fixture",
            verification_status="ai_supported_match",
        )
    except ValueError as exc:
        assert "RAG evidence" in str(exc)
    else:
        raise AssertionError("untrusted AI evidence entered the RAG store")


def test_jsonl_roundtrip_preserves_trusted_evidence(tmp_path):
    store = EvidenceStore(
        [
            EvidenceRecord(
                evidence_id="e2",
                verification_status="verified_exact",
                provenance="doi-control",
                title="Segundo",
                year="2021",
                doi="10.1000/b",
            ),
            EvidenceRecord(
                evidence_id="e1",
                verification_status="human_confirmed",
                provenance="author-confirmed:doc-1",
                title="Primero",
                authors=("Pérez, M.",),
                year="2020",
                doi="10.1000/a",
                source_document_id="doc-1",
            ),
        ]
    )
    path = tmp_path / "evidence.jsonl"
    save_evidence_jsonl(path, store)
    loaded = load_evidence_jsonl(path)
    assert [x.evidence_id for x in loaded.records] == ["e1", "e2"]
    assert loaded.records[0].verification_status == "human_confirmed"
    assert loaded.records[0].source_document_id == "doc-1"


def test_jsonl_loader_rejects_untrusted_persisted_status(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '{"evidence_id":"x","verification_status":"possible_match","provenance":"bad","title":"X"}\n',
        encoding="utf-8",
    )
    try:
        load_evidence_jsonl(path)
    except ValueError as exc:
        assert "RAG evidence" in str(exc)
    else:
        raise AssertionError("persisted untrusted evidence bypassed the trust gate")
