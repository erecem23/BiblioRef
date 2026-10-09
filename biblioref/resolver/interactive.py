# -*- coding: utf-8 -*-
"""Interactive orchestration for BiblioRef's downstream resolution layers.

This module exposes the existing resolver stack to the local application
without granting any downstream layer writeback authority over parser fields.
It returns sidecar evidence suitable for UI inspection and human confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .consensus import ConsensusEngine, ConsensusResult
from .crossref import CrossrefBackend
from .decision import ResolutionDecisionEngine
from .models import CandidateBatch, ResolverQuery
from .openalex import OpenAlexBackend
from .resolver import MetadataResolver

INTERACTIVE_RESOLUTION_VERSION = "interactive-resolution-v0.1"
INTERACTIVE_LAYERS = frozenset(
    {"crossref", "openalex", "consensus", "decision"}
)


@dataclass(frozen=True)
class InteractiveResolutionResult:
    version: str
    requested_layers: Tuple[str, ...]
    executed_layers: Tuple[str, ...]
    query: Dict[str, Any]
    batch: Dict[str, Any]
    candidates: Tuple[Dict[str, Any], ...]
    consensus: Optional[Dict[str, Any]]
    semantic: Optional[Dict[str, Any]]
    rag: Optional[Dict[str, Any]]
    adjudication: Optional[Dict[str, Any]]
    decision: Optional[Dict[str, Any]]
    layer_errors: Dict[str, str]
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "requested_layers": list(self.requested_layers),
            "executed_layers": list(self.executed_layers),
            "query": dict(self.query),
            "batch": dict(self.batch),
            "candidates": [dict(x) for x in self.candidates],
            "consensus": self.consensus,
            "semantic": self.semantic,
            "rag": self.rag,
            "adjudication": self.adjudication,
            "decision": self.decision,
            "layer_errors": dict(self.layer_errors),
            "notes": list(self.notes),
        }


class InteractiveResolutionRunner:
    """Run user-selected resolver layers with explicit prerequisite expansion."""

    def __init__(
        self,
        *,
        crossref_email: Optional[str] = None,
        openalex_api_key: Optional[str] = None,
    ) -> None:
        self.crossref_email = crossref_email or os.environ.get("BIBLIOREF_CROSSREF_EMAIL")
        self.openalex_api_key = openalex_api_key or os.environ.get("BIBLIOREF_OPENALEX_API_KEY")

    @staticmethod
    def _normalize_layers(layers: Iterable[str]) -> Tuple[str, ...]:
        requested = []
        for raw in layers or ():
            layer = str(raw).strip().lower()
            if layer not in INTERACTIVE_LAYERS:
                raise ValueError(f"unknown interactive layer: {layer}")
            if layer not in requested:
                requested.append(layer)
        return tuple(requested)

    @staticmethod
    def _expand_layers(requested: Sequence[str]) -> Tuple[str, ...]:
        expanded = list(requested)
        if "decision" in expanded and "consensus" not in expanded:
            expanded.append("consensus")
        order = ["crossref", "openalex", "consensus", "decision"]
        return tuple(layer for layer in order if layer in expanded)

    def run(
        self,
        *,
        raw_reference: str,
        parsed: Mapping[str, Any] | None,
        layers: Iterable[str],
    ) -> InteractiveResolutionResult:
        requested = self._normalize_layers(layers)
        executed = self._expand_layers(requested)
        query = ResolverQuery.from_parser(raw_reference, parsed)
        errors: Dict[str, str] = {}

        backends = []
        if "crossref" in executed:
            backends.append(CrossrefBackend(email=self.crossref_email))
        if "openalex" in executed:
            backends.append(OpenAlexBackend(api_key=self.openalex_api_key))
        batch = MetadataResolver(backends).resolve(query) if backends else CandidateBatch(query=query)

        consensus: Optional[ConsensusResult] = None
        if "consensus" in executed:
            consensus = ConsensusEngine().assess(batch)

        semantic = None
        rag = None
        adjudication = None

        decision = None
        if "decision" in executed:
            if consensus is None:
                errors["decision"] = "consensus_not_available"
            else:
                try:
                    decision = ResolutionDecisionEngine().decide(
                        batch, consensus, semantic, adjudication
                    )
                except Exception as exc:
                    errors["decision"] = f"{exc.__class__.__name__}:{exc}"

        candidates = []
        for index, candidate in enumerate(batch.candidates):
            item = candidate.as_dict()
            item["candidate_index"] = index
            item["identity_key"] = candidate.identity_key
            candidates.append(item)

        return InteractiveResolutionResult(
            version=INTERACTIVE_RESOLUTION_VERSION,
            requested_layers=requested,
            executed_layers=executed,
            query=query.as_dict(),
            batch={
                "status": batch.status,
                "backend_errors": list(batch.backend_errors),
                "candidate_count": len(batch.candidates),
            },
            candidates=tuple(candidates),
            consensus=consensus.as_dict() if consensus is not None else None,
            semantic=semantic.as_dict() if semantic is not None else None,
            rag=rag.as_dict() if rag is not None else None,
            adjudication=adjudication.as_dict() if adjudication is not None else None,
            decision=decision.as_dict() if decision is not None else None,
            layer_errors=errors,
            notes=(
                "interactive_layers_are_sidecar_evidence_only",
                "local_model_runtime_is_disabled",
            ),
        )
