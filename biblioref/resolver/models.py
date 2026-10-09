# -*- coding: utf-8 -*-
"""Data contracts for external bibliographic metadata resolution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .normalize import (
    clean_query_text,
    clean_text,
    normalize_authors,
    normalize_doi,
    normalize_match_text,
    normalize_year,
    strip_reference_noise,
)


@dataclass(frozen=True)
class ResolverQuery:
    """Immutable snapshot of the evidence the parser exposes to a resolver.

    The resolver receives a copy. Nothing here has authority to rewrite the
    original parsed record.
    """

    raw_reference: str
    title: Optional[str] = None
    authors: Tuple[str, ...] = ()
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    publication_type: Optional[str] = None
    parser_version: Optional[str] = None
    parser_confidence: Optional[float] = None

    @classmethod
    def from_parser(cls, raw_reference: Any, parsed: Mapping[str, Any] | None) -> "ResolverQuery":
        """Snapshot the parsed evidence, repaired for searching.

        The text fields pass through query hygiene: what a backend receives is
        free of the extraction artefacts (soft hyphens, split words, curly
        quotes, access trails) that a search engine cannot see through. The
        parsed record itself is untouched.
        """
        parsed = dict(parsed or {})
        confidence = parsed.get("parser_confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        return cls(
            raw_reference=strip_reference_noise(raw_reference),
            title=clean_query_text(parsed.get("title")) or None,
            authors=normalize_authors(parsed.get("authors") or parsed.get("author")),
            year=normalize_year(parsed.get("year")),
            journal=clean_query_text(parsed.get("journal") or parsed.get("container_title")) or None,
            publisher=clean_query_text(parsed.get("publisher")) or None,
            doi=normalize_doi(parsed.get("doi")),
            publication_type=clean_text(parsed.get("publication_type")) or None,
            parser_version=clean_text(parsed.get("parser_version")) or None,
            parser_confidence=confidence,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "raw_reference": self.raw_reference,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "journal": self.journal,
            "publisher": self.publisher,
            "doi": self.doi,
            "publication_type": self.publication_type,
            "parser_version": self.parser_version,
            "parser_confidence": self.parser_confidence,
        }


@dataclass(frozen=True)
class Candidate:
    """One bibliographic work candidate returned by an external backend."""

    source: str
    source_id: Optional[str] = None
    title: Optional[str] = None
    authors: Tuple[str, ...] = ()
    year: Optional[str] = None
    container_title: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    work_type: Optional[str] = None
    url: Optional[str] = None
    retrieval_method: Optional[str] = None
    provider_score: Optional[float] = None
    rank: Optional[int] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False, repr=False)

    @classmethod
    def from_mapping(
        cls,
        source: str,
        data: Mapping[str, Any],
        *,
        source_id: Any = None,
        retrieval_method: Any = None,
        provider_score: Any = None,
        rank: Any = None,
    ) -> "Candidate":
        container = data.get("container_title") or data.get("journal") or data.get("source")
        if isinstance(container, (list, tuple)):
            container = next((x for x in container if clean_text(x)), None)
        try:
            score = float(provider_score if provider_score is not None else data.get("score"))
        except (TypeError, ValueError):
            score = None
        try:
            rank_value = int(rank) if rank is not None else None
        except (TypeError, ValueError):
            rank_value = None
        return cls(
            source=clean_text(source),
            source_id=clean_text(source_id or data.get("id") or data.get("source_id")) or None,
            title=clean_text(data.get("title")) or None,
            authors=normalize_authors(data.get("authors") or data.get("author")),
            year=normalize_year(data.get("year") or data.get("published") or data.get("publication_year")),
            container_title=clean_text(container) or None,
            publisher=clean_text(data.get("publisher")) or None,
            doi=normalize_doi(data.get("doi") or data.get("DOI")),
            work_type=clean_text(data.get("type") or data.get("work_type")) or None,
            url=clean_text(data.get("url") or data.get("URL")) or None,
            retrieval_method=clean_text(retrieval_method or data.get("retrieval_method")) or None,
            provider_score=score,
            rank=rank_value,
            raw_metadata=dict(data),
        )

    @property
    def identity_key(self) -> Optional[str]:
        """Conservative cross-backend identity key used before consensus logic.

        DOI wins. Without DOI we only deduplicate candidates when title, year and
        first author all exist; weak candidates remain separate rather than being
        accidentally fused.
        """
        if self.doi:
            return f"doi:{self.doi}"
        title = normalize_match_text(self.title)
        year = self.year or ""
        first_author = normalize_match_text(self.authors[0] if self.authors else "")
        if title and year and first_author:
            return f"tya:{title}|{year}|{first_author}"
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "container_title": self.container_title,
            "publisher": self.publisher,
            "doi": self.doi,
            "work_type": self.work_type,
            "url": self.url,
            "retrieval_method": self.retrieval_method,
            "provider_score": self.provider_score,
            "rank": self.rank,
        }


@dataclass(frozen=True)
class CandidateBatch:
    """Read-only result of querying one or more metadata backends."""

    query: ResolverQuery
    candidates: Tuple[Candidate, ...] = ()
    backend_errors: Tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.candidates:
            return "candidates_found"
        if self.backend_errors:
            return "backend_error"
        return "no_candidates"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query.as_dict(),
            "candidates": [x.as_dict() for x in self.candidates],
            "backend_errors": list(self.backend_errors),
        }
