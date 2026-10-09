# -*- coding: utf-8 -*-
"""Auditable bibliographic retrieval-augmented evidence for BiblioRef.

The RAG layer retrieves only from an explicitly supplied local evidence store.
It is downstream from parsing and does not mutate parser output, resolver
candidates, consensus, or decisions. Only strongly verified or human-confirmed
records are accepted into the store to reduce self-reinforcing errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from .models import ResolverQuery
from .normalize import clean_text, normalize_authors, normalize_doi, normalize_match_text, normalize_year

BIBLIOGRAPHIC_RAG_VERSION = "bibliographic-rag-v0.1"
TRUSTED_EVIDENCE_STATUSES = frozenset(
    {
        "verified_exact",
        "verified_external_consensus",
        "human_confirmed",
    }
)
_TRUST_PRIORITY = {
    "human_confirmed": 3,
    "verified_exact": 2,
    "verified_external_consensus": 1,
}


class RAGEmbeddingBackend(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = sqrt(sum(float(x) * float(x) for x in a))
    nb = sqrt(sum(float(y) * float(y) for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    value = dot / (na * nb)
    return max(-1.0, min(1.0, value))


def _tokens(value: Any) -> frozenset[str]:
    return frozenset(x for x in normalize_match_text(value).split() if len(x) > 1)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(frozen=True)
class EvidenceRecord:
    """One trusted bibliographic record eligible for local retrieval."""

    evidence_id: str
    verification_status: str
    provenance: str
    title: str = ""
    authors: Tuple[str, ...] = ()
    year: Optional[str] = None
    container_title: str = ""
    publisher: str = ""
    doi: Optional[str] = None
    raw_reference: str = ""
    source_document_id: str = ""

    def __post_init__(self) -> None:
        evidence_id = clean_text(self.evidence_id)
        provenance = clean_text(self.provenance)
        status = clean_text(self.verification_status).casefold()
        if not evidence_id:
            raise ValueError("evidence_id is required")
        if not provenance:
            raise ValueError("provenance is required")
        if status not in TRUSTED_EVIDENCE_STATUSES:
            raise ValueError(
                "RAG evidence must be verified_exact, verified_external_consensus, or human_confirmed"
            )
        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "verification_status", status)
        object.__setattr__(self, "title", clean_text(self.title))
        object.__setattr__(self, "authors", normalize_authors(self.authors))
        object.__setattr__(self, "year", normalize_year(self.year))
        object.__setattr__(self, "container_title", clean_text(self.container_title))
        object.__setattr__(self, "publisher", clean_text(self.publisher))
        object.__setattr__(self, "doi", normalize_doi(self.doi))
        object.__setattr__(self, "raw_reference", clean_text(self.raw_reference))
        object.__setattr__(self, "source_document_id", clean_text(self.source_document_id))
        if not self.title and not self.raw_reference:
            raise ValueError("RAG evidence requires title or raw_reference")

    @property
    def identity_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi}"
        title = normalize_match_text(self.title)
        first_author = normalize_match_text(self.authors[0]) if self.authors else ""
        if title and self.year and first_author:
            return f"tya:{title}|{self.year}|{first_author}"
        return f"evidence:{self.evidence_id}"

    @property
    def retrieval_text(self) -> str:
        fields = [
            self.title,
            "; ".join(self.authors),
            self.year or "",
            self.container_title,
            self.publisher,
            self.raw_reference,
        ]
        return clean_text(" | ".join(x for x in fields if clean_text(x)))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "identity_key": self.identity_key,
            "verification_status": self.verification_status,
            "provenance": self.provenance,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "container_title": self.container_title,
            "publisher": self.publisher,
            "doi": self.doi,
            "raw_reference": self.raw_reference,
            "source_document_id": self.source_document_id,
        }


class EvidenceStore:
    """Small local store with conservative identity deduplication."""

    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        self._records: List[EvidenceRecord] = []
        self._by_identity: Dict[str, int] = {}
        self._by_id: Dict[str, int] = {}
        for record in records:
            self.add(record)

    def add(self, record: EvidenceRecord) -> None:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("EvidenceStore accepts EvidenceRecord objects only")
        if record.evidence_id in self._by_id:
            existing = self._records[self._by_id[record.evidence_id]]
            if existing != record:
                raise ValueError(f"duplicate evidence_id with conflicting content: {record.evidence_id}")
            return
        identity = record.identity_key
        if identity in self._by_identity:
            idx = self._by_identity[identity]
            current = self._records[idx]
            if _TRUST_PRIORITY[record.verification_status] > _TRUST_PRIORITY[current.verification_status]:
                del self._by_id[current.evidence_id]
                self._records[idx] = record
                self._by_id[record.evidence_id] = idx
            return
        idx = len(self._records)
        self._records.append(record)
        self._by_identity[identity] = idx
        self._by_id[record.evidence_id] = idx

    @property
    def records(self) -> Tuple[EvidenceRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence_index: int
    evidence_id: str
    identity_key: str
    lexical_score: float
    semantic_score: Optional[float]
    retrieval_score: float
    record: EvidenceRecord

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evidence_index": self.evidence_index,
            "evidence_id": self.evidence_id,
            "identity_key": self.identity_key,
            "lexical_score": self.lexical_score,
            "semantic_score": self.semantic_score,
            "retrieval_score": self.retrieval_score,
            "record": self.record.as_dict(),
        }


@dataclass(frozen=True)
class RAGResult:
    version: str
    status: str
    backend: str
    query_text_source: str
    query_text: str
    evidence_count: int
    retrieved: Tuple[RetrievedEvidence, ...]
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "backend": self.backend,
            "query_text_source": self.query_text_source,
            "query_text": self.query_text,
            "evidence_count": self.evidence_count,
            "retrieved": [x.as_dict() for x in self.retrieved],
            "notes": list(self.notes),
        }


class BibliographicRAG:
    """Hybrid local retrieval over trusted previously resolved references.

    Lexical retrieval is always available and deterministic. An optional local
    embedding backend can add semantic similarity. Retrieved evidence is
    advisory only and cannot select or mutate a resolver candidate.
    """

    def __init__(
        self,
        store: EvidenceStore,
        *,
        embedding_backend: Optional[RAGEmbeddingBackend] = None,
        lexical_weight: float = 0.65,
        semantic_weight: float = 0.35,
        min_score: float = 0.10,
        top_k: int = 5,
    ) -> None:
        if not isinstance(store, EvidenceStore):
            raise TypeError("store must be an EvidenceStore")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if lexical_weight < 0 or semantic_weight < 0:
            raise ValueError("retrieval weights must be non-negative")
        if lexical_weight + semantic_weight <= 0:
            raise ValueError("at least one retrieval weight must be positive")
        if embedding_backend is None and semantic_weight > 0:
            semantic_weight = 0.0
        total = lexical_weight + semantic_weight
        self.store = store
        self.embedding_backend = embedding_backend
        self.lexical_weight = float(lexical_weight) / total
        self.semantic_weight = float(semantic_weight) / total
        self.min_score = float(min_score)
        self.top_k = int(top_k)

    def retrieve(self, query: ResolverQuery) -> RAGResult:
        query_text, source = self._query_text(query)
        records = self.store.records
        backend_name = (
            str(self.embedding_backend.name)
            if self.embedding_backend is not None
            else "deterministic-lexical"
        )
        if not query_text or not records:
            return RAGResult(
                version=BIBLIOGRAPHIC_RAG_VERSION,
                status="insufficient_evidence",
                backend=backend_name,
                query_text_source=source,
                query_text=query_text,
                evidence_count=len(records),
                retrieved=(),
                notes=("retrieved_evidence_is_not_a_resolution_decision",),
            )

        query_tokens = _tokens(query_text)
        lexical = [_jaccard(query_tokens, _tokens(record.retrieval_text)) for record in records]
        semantic: List[Optional[float]] = [None] * len(records)
        if self.embedding_backend is not None:
            texts = [query_text] + [record.retrieval_text for record in records]
            vectors = list(self.embedding_backend.encode(texts))
            if len(vectors) != len(texts):
                raise ValueError("embedding backend returned an unexpected vector count")
            q = vectors[0]
            semantic = [round(_cosine(q, vector), 6) for vector in vectors[1:]]

        scored: List[RetrievedEvidence] = []
        for index, record in enumerate(records):
            sem = semantic[index]
            sem_component = max(0.0, sem) if sem is not None else 0.0
            score = self.lexical_weight * lexical[index] + self.semantic_weight * sem_component
            if score < self.min_score:
                continue
            scored.append(
                RetrievedEvidence(
                    evidence_index=index,
                    evidence_id=record.evidence_id,
                    identity_key=record.identity_key,
                    lexical_score=round(lexical[index], 6),
                    semantic_score=sem,
                    retrieval_score=round(score, 6),
                    record=record,
                )
            )
        scored.sort(
            key=lambda item: (
                -item.retrieval_score,
                -_TRUST_PRIORITY[item.record.verification_status],
                item.evidence_id,
            )
        )
        retrieved = tuple(scored[: self.top_k])
        return RAGResult(
            version=BIBLIOGRAPHIC_RAG_VERSION,
            status="retrieved" if retrieved else "no_match",
            backend=backend_name,
            query_text_source=source,
            query_text=query_text,
            evidence_count=len(records),
            retrieved=retrieved,
            notes=(
                "retrieved_evidence_is_not_a_resolution_decision",
                "evidence_store_accepts_only_strongly_verified_or_human_confirmed_records",
            ),
        )

    @staticmethod
    def _query_text(query: ResolverQuery) -> Tuple[str, str]:
        parts = []
        if clean_text(query.title):
            parts.append(clean_text(query.title))
        if query.authors:
            parts.append("; ".join(clean_text(x) for x in query.authors if clean_text(x)))
        if clean_text(query.year):
            parts.append(clean_text(query.year))
        if clean_text(query.journal):
            parts.append(clean_text(query.journal))
        if clean_text(query.publisher):
            parts.append(clean_text(query.publisher))
        if parts:
            return clean_text(" | ".join(parts)), "parsed_fields"
        raw = clean_text(query.raw_reference)
        if raw:
            return raw, "raw_reference"
        return "", "none"
