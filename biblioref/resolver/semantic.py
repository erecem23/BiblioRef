# -*- coding: utf-8 -*-
"""Optional local semantic ranking for metadata candidates.

The semantic layer is deliberately narrower than the deterministic consensus:
it compares title/citation meaning and returns a similarity signal. It does not
select metadata as truth and it never mutates parsed references.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from .models import Candidate, CandidateBatch, ResolverQuery
from .normalize import clean_text

SEMANTIC_RESOLVER_VERSION = "semantic-resolver-v0.1"
DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingBackend(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...


class SentenceTransformerEmbeddingBackend:
    """Lazy optional adapter; importing BiblioRef does not require torch/models."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL, *, device: Optional[str] = None) -> None:
        self.model_name = model_name
        self.device = device
        self.name = f"sentence-transformers:{model_name}"
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "Semantic resolution requires the optional 'sentence-transformers' package"
                ) from exc
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        model = self._load()
        return model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = sqrt(sum(float(x) * float(x) for x in a))
    nb = sqrt(sum(float(y) * float(y) for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    value = dot / (na * nb)
    return max(-1.0, min(1.0, value))


@dataclass(frozen=True)
class SemanticCandidateScore:
    candidate_index: int
    similarity: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "candidate_index": self.candidate_index,
            "similarity": self.similarity,
        }


@dataclass(frozen=True)
class SemanticResult:
    version: str
    status: str
    backend: str
    query_text_source: str
    leading_candidate_index: Optional[int]
    scores: Tuple[SemanticCandidateScore, ...]
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "backend": self.backend,
            "query_text_source": self.query_text_source,
            "leading_candidate_index": self.leading_candidate_index,
            "scores": [x.as_dict() for x in self.scores],
            "notes": list(self.notes),
        }


class SemanticResolver:
    """Rank candidates semantically using an injected local embedding backend."""

    def __init__(self, backend: EmbeddingBackend) -> None:
        self.backend = backend

    def rank(self, batch: CandidateBatch) -> SemanticResult:
        query_text, source = self._query_text(batch.query)
        usable = [
            (index, clean_text(candidate.title))
            for index, candidate in enumerate(batch.candidates)
            if clean_text(candidate.title)
        ]
        if not query_text or not usable:
            return SemanticResult(
                version=SEMANTIC_RESOLVER_VERSION,
                status="insufficient_evidence",
                backend=self.backend.name,
                query_text_source=source,
                leading_candidate_index=None,
                scores=(),
                notes=("semantic_similarity_is_not_match_probability",),
            )

        texts = [query_text] + [text for _, text in usable]
        vectors = list(self.backend.encode(texts))
        if len(vectors) != len(texts):
            raise ValueError("embedding backend returned an unexpected vector count")

        query_vector = vectors[0]
        scores: List[SemanticCandidateScore] = []
        for (candidate_index, _), vector in zip(usable, vectors[1:]):
            scores.append(
                SemanticCandidateScore(
                    candidate_index=candidate_index,
                    similarity=round(_cosine(query_vector, vector), 6),
                )
            )
        scores.sort(key=lambda x: x.similarity, reverse=True)
        leader = scores[0].candidate_index if scores else None
        return SemanticResult(
            version=SEMANTIC_RESOLVER_VERSION,
            status="ranked" if scores else "insufficient_evidence",
            backend=self.backend.name,
            query_text_source=source,
            leading_candidate_index=leader,
            scores=tuple(scores),
            notes=("semantic_similarity_is_not_match_probability",),
        )

    @staticmethod
    def _query_text(query: ResolverQuery) -> Tuple[str, str]:
        title = clean_text(query.title)
        if title:
            return title, "parsed_title"
        raw = clean_text(query.raw_reference)
        if raw:
            return raw, "raw_reference"
        return "", "none"
