"""External bibliographic metadata resolution for BiblioRef.

This package is deliberately downstream from extraction and parsing. Resolver
components may inspect parsed fields and external metadata, but they must never
mutate the parser output in place.
"""

from .adjudicator import AdjudicationResult, LocalAIAdjudicator, OllamaJSONBackend
from .chat import ChatResult, LocalBibliographicChat, OllamaChatBackend
from .consensus import ConsensusEngine, ConsensusResult
from .crossref import CrossrefBackend
from .decision import (
    AI_SUPPORTED_MATCH,
    POSSIBLE_MATCH,
    UNRESOLVED,
    VERIFIED_EXACT,
    VERIFIED_EXTERNAL_CONSENSUS,
    VERIFIED_SEMANTIC,
    ResolutionDecision,
    ResolutionDecisionEngine,
)
from .interactive import InteractiveResolutionResult, InteractiveResolutionRunner
from .models import Candidate, CandidateBatch, ResolverQuery
from .openalex import OpenAlexBackend
from .rag import (
    BIBLIOGRAPHIC_RAG_VERSION,
    BibliographicRAG,
    EvidenceRecord,
    EvidenceStore,
    RAGResult,
    RetrievedEvidence,
)
from .rag_adjudicator import (
    RAG_AI_ADJUDICATOR_VERSION,
    RAGAdjudicationResult,
    RAGLocalAIAdjudicator,
)
from .rag_store import evidence_from_candidate, load_evidence_jsonl, save_evidence_jsonl
from .resolver import MetadataResolver, ResolverBackend
from .semantic import SemanticResolver, SentenceTransformerEmbeddingBackend

__all__ = [
    "Candidate",
    "CandidateBatch",
    "ResolverQuery",
    "MetadataResolver",
    "ResolverBackend",
    "CrossrefBackend",
    "OpenAlexBackend",
    "ConsensusEngine",
    "ConsensusResult",
    "SemanticResolver",
    "SentenceTransformerEmbeddingBackend",
    "BIBLIOGRAPHIC_RAG_VERSION",
    "EvidenceRecord",
    "EvidenceStore",
    "RetrievedEvidence",
    "RAGResult",
    "BibliographicRAG",
    "evidence_from_candidate",
    "load_evidence_jsonl",
    "save_evidence_jsonl",
    "LocalAIAdjudicator",
    "OllamaJSONBackend",
    "AdjudicationResult",
    "RAG_AI_ADJUDICATOR_VERSION",
    "RAGLocalAIAdjudicator",
    "RAGAdjudicationResult",
    "ResolutionDecision",
    "ResolutionDecisionEngine",
    "VERIFIED_EXACT",
    "VERIFIED_EXTERNAL_CONSENSUS",
    "VERIFIED_SEMANTIC",
    "AI_SUPPORTED_MATCH",
    "POSSIBLE_MATCH",
    "UNRESOLVED",
    "InteractiveResolutionResult",
    "InteractiveResolutionRunner",
    "ChatResult",
    "LocalBibliographicChat",
    "OllamaChatBackend",
]
