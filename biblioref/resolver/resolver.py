# -*- coding: utf-8 -*-
"""Backend-neutral metadata resolver orchestration.

This first version performs candidate collection only. It does not score,
select, merge or write metadata back to parsed references. Consensus and
semantic ranking are intentionally later layers.
"""
from __future__ import annotations

from typing import Iterable, List, Protocol, Sequence

from .models import Candidate, CandidateBatch, ResolverQuery


class ResolverBackend(Protocol):
    """Minimal contract implemented by Crossref/OpenAlex/etc. connectors."""

    name: str

    def search(self, query: ResolverQuery) -> Sequence[Candidate]:
        ...


class MetadataResolver:
    """Collect external candidates without mutating parser output."""

    def __init__(self, backends: Iterable[ResolverBackend] = ()) -> None:
        self.backends = tuple(backends)

    def resolve(self, query: ResolverQuery) -> CandidateBatch:
        candidates: List[Candidate] = []
        errors: List[str] = []

        for backend in self.backends:
            name = str(getattr(backend, "name", backend.__class__.__name__))
            try:
                returned = backend.search(query)
                for candidate in returned or ():
                    if not isinstance(candidate, Candidate):
                        raise TypeError(f"backend {name} returned non-Candidate value")
                    candidates.append(candidate)
            except Exception as exc:
                # Backends are optional enrichers. A failed API must never make
                # extraction/parsing fail, and errors remain explicit for audit.
                errors.append(f"{name}:{exc.__class__.__name__}:{exc}")

        return CandidateBatch(
            query=query,
            candidates=tuple(self._deduplicate(candidates)),
            backend_errors=tuple(errors),
        )

    @staticmethod
    def _deduplicate(candidates: Sequence[Candidate]) -> List[Candidate]:
        """Remove only conservative duplicates from the same backend.

        Cross-backend agreement must remain visible for the future Consensus
        Engine, so a Crossref and an OpenAlex record with the same DOI are kept
        as two independent evidence sources.
        """
        out: List[Candidate] = []
        seen = set()
        for candidate in candidates:
            identity = candidate.identity_key
            key = (candidate.source.casefold(), identity) if identity else None
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            out.append(candidate)
        return out
