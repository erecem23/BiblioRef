# -*- coding: utf-8 -*-
"""Unified, auditable decision layer for bibliographic resolution.

The decision engine combines already-computed deterministic consensus,
optional semantic similarity and optional local-AI adjudication. It never
mutates parser output or candidate metadata. Statuses are evidence tiers, not
probabilities or assertions of ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from .adjudicator import AdjudicationResult
from .consensus import CandidateAssessment, ConsensusResult
from .models import CandidateBatch
from .semantic import SemanticResult

RESOLUTION_DECISION_VERSION = "resolution-decision-v0.1"

VERIFIED_EXACT = "VERIFIED_EXACT"
VERIFIED_EXTERNAL_CONSENSUS = "VERIFIED_EXTERNAL_CONSENSUS"
VERIFIED_SEMANTIC = "VERIFIED_SEMANTIC"
AI_SUPPORTED_MATCH = "AI_SUPPORTED_MATCH"
POSSIBLE_MATCH = "POSSIBLE_MATCH"
UNRESOLVED = "UNRESOLVED"

RESOLUTION_STATUSES = frozenset(
    {
        VERIFIED_EXACT,
        VERIFIED_EXTERNAL_CONSENSUS,
        VERIFIED_SEMANTIC,
        AI_SUPPORTED_MATCH,
        POSSIBLE_MATCH,
        UNRESOLVED,
    }
)


@dataclass(frozen=True)
class ResolutionDecision:
    """Final sidecar decision over one candidate batch.

    ``selected_candidate_index`` points back into ``CandidateBatch.candidates``;
    metadata remains source-specific and is intentionally not copied into this
    object. ``review_required`` signals whether a human should inspect the
    selection before downstream use.
    """

    version: str
    status: str
    selected_candidate_index: Optional[int]
    selected_identity_key: Optional[str]
    decision_method: str
    review_required: bool
    evidence_basis: Tuple[str, ...]
    warnings: Tuple[str, ...]
    consensus_version: str
    consensus_status: str
    semantic_version: Optional[str] = None
    semantic_status: Optional[str] = None
    ai_version: Optional[str] = None
    ai_status: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "selected_candidate_index": self.selected_candidate_index,
            "selected_identity_key": self.selected_identity_key,
            "decision_method": self.decision_method,
            "review_required": self.review_required,
            "evidence_basis": list(self.evidence_basis),
            "warnings": list(self.warnings),
            "consensus_version": self.consensus_version,
            "consensus_status": self.consensus_status,
            "semantic_version": self.semantic_version,
            "semantic_status": self.semantic_status,
            "ai_version": self.ai_version,
            "ai_status": self.ai_status,
        }


class ResolutionDecisionEngine:
    """Combine deterministic, semantic and AI signals conservatively."""

    def __init__(
        self,
        *,
        verified_semantic_threshold: float = 0.82,
        possible_semantic_threshold: float = 0.88,
        ai_independent_evidence_threshold: float = 0.65,
        semantic_independent_evidence_threshold: float = 0.55,
    ) -> None:
        for name, value in (
            ("verified_semantic_threshold", verified_semantic_threshold),
            ("possible_semantic_threshold", possible_semantic_threshold),
            ("ai_independent_evidence_threshold", ai_independent_evidence_threshold),
            ("semantic_independent_evidence_threshold", semantic_independent_evidence_threshold),
        ):
            value = float(value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        self.verified_semantic_threshold = float(verified_semantic_threshold)
        self.possible_semantic_threshold = float(possible_semantic_threshold)
        self.ai_independent_evidence_threshold = float(ai_independent_evidence_threshold)
        self.semantic_independent_evidence_threshold = float(semantic_independent_evidence_threshold)

    def decide(
        self,
        batch: CandidateBatch,
        consensus: ConsensusResult,
        semantic: Optional[SemanticResult] = None,
        adjudication: Optional[AdjudicationResult] = None,
    ) -> ResolutionDecision:
        if not batch.candidates:
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="no_candidates",
                review_required=True,
                basis=("no_external_candidates",),
            )

        leader = self._valid_index(consensus.leading_candidate_index, batch)

        if consensus.status == "exact_identifier" and leader is not None:
            candidate = batch.candidates[leader]
            if batch.query.doi and candidate.doi and batch.query.doi == candidate.doi:
                return self._result(
                    batch,
                    consensus,
                    semantic,
                    adjudication,
                    status=VERIFIED_EXACT,
                    selected=leader,
                    method="doi_exact",
                    review_required=False,
                    basis=("query_candidate_doi_exact",),
                )
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="exact_identifier_inconsistent",
                review_required=True,
                basis=("consensus_exact_identifier",),
                warnings=("exact_identifier_without_reproducible_doi_match",),
            )

        if consensus.status == "external_consensus" and leader is not None:
            if self._in_cross_source_group(leader, consensus):
                return self._result(
                    batch,
                    consensus,
                    semantic,
                    adjudication,
                    status=VERIFIED_EXTERNAL_CONSENSUS,
                    selected=leader,
                    method="cross_source_consensus",
                    review_required=False,
                    basis=("same_identity_across_independent_sources",),
                )
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="external_consensus_inconsistent",
                review_required=True,
                basis=("consensus_external_consensus",),
                warnings=("leader_not_present_in_cross_source_identity_group",),
            )

        if consensus.status == "probable_candidate" and leader is not None:
            similarity = self._semantic_similarity(semantic, leader)
            semantic_leader = self._valid_index(
                semantic.leading_candidate_index if semantic is not None else None,
                batch,
            )
            if (
                similarity is not None
                and similarity >= self.verified_semantic_threshold
                and semantic_leader == leader
            ):
                return self._result(
                    batch,
                    consensus,
                    semantic,
                    adjudication,
                    status=VERIFIED_SEMANTIC,
                    selected=leader,
                    method="deterministic_plus_semantic",
                    review_required=False,
                    basis=("probable_deterministic_candidate", "semantic_leader_agreement"),
                )
            warnings = ()
            if semantic_leader is not None and semantic_leader != leader:
                warnings = ("semantic_leader_disagrees_with_consensus_leader",)
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=POSSIBLE_MATCH,
                selected=leader,
                method="deterministic_probable",
                review_required=True,
                basis=("probable_deterministic_candidate",),
                warnings=warnings,
            )

        if consensus.status in {"ambiguous_conflict", "unresolved"}:
            ai_decision = self._from_ai(batch, consensus, semantic, adjudication)
            if ai_decision is not None:
                return ai_decision

            semantic_candidate = self._strong_semantic_possible(batch, consensus, semantic)
            if semantic_candidate is not None:
                return self._result(
                    batch,
                    consensus,
                    semantic,
                    adjudication,
                    status=POSSIBLE_MATCH,
                    selected=semantic_candidate,
                    method="semantic_possible",
                    review_required=True,
                    basis=("strong_semantic_similarity", "independent_metadata_support"),
                    warnings=("consensus_not_resolved",),
                )

            basis = [f"consensus_{consensus.status}"]
            warnings = []
            if adjudication is not None:
                basis.append(f"ai_{adjudication.status}")
                if adjudication.status in {"backend_error", "invalid_response"}:
                    warnings.append("ai_adjudication_not_usable")
                elif adjudication.status == "abstained":
                    warnings.append("ai_abstained")
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="insufficient_or_conflicting_evidence",
                review_required=True,
                basis=tuple(basis),
                warnings=tuple(warnings),
            )

        return self._result(
            batch,
            consensus,
            semantic,
            adjudication,
            status=UNRESOLVED,
            method="unsupported_consensus_status",
            review_required=True,
            basis=(f"consensus_{consensus.status}",),
            warnings=("unknown_consensus_status",),
        )

    def _from_ai(
        self,
        batch: CandidateBatch,
        consensus: ConsensusResult,
        semantic: Optional[SemanticResult],
        adjudication: Optional[AdjudicationResult],
    ) -> Optional[ResolutionDecision]:
        if adjudication is None or adjudication.status != "candidate_selected":
            return None
        selected = self._valid_index(adjudication.selected_candidate_index, batch)
        if selected is None:
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="ai_invalid_candidate",
                review_required=True,
                basis=("ai_candidate_selected",),
                warnings=("ai_selected_candidate_out_of_range",),
            )

        semantic_leader = self._valid_index(
            semantic.leading_candidate_index if semantic is not None else None,
            batch,
        )
        selected_semantic = self._semantic_similarity(semantic, selected)
        semantic_leader_score = self._semantic_similarity(semantic, semantic_leader)
        if (
            semantic_leader is not None
            and semantic_leader != selected
            and semantic_leader_score is not None
            and semantic_leader_score >= self.verified_semantic_threshold
        ):
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="ai_semantic_conflict",
                review_required=True,
                basis=("ai_candidate_selected", "strong_semantic_disagreement"),
                warnings=("ai_and_semantic_leaders_disagree",),
            )

        assessment = self._assessment(consensus, selected)
        deterministic_score = assessment.evidence_score if assessment is not None else 0.0
        cross_source = self._in_cross_source_group(selected, consensus)
        independent_support = (
            cross_source
            or deterministic_score >= self.ai_independent_evidence_threshold
            or (
                selected_semantic is not None
                and selected_semantic >= self.verified_semantic_threshold
            )
        )
        if not independent_support:
            return self._result(
                batch,
                consensus,
                semantic,
                adjudication,
                status=UNRESOLVED,
                method="ai_without_independent_support",
                review_required=True,
                basis=("ai_candidate_selected",),
                warnings=("ai_selection_requires_non_ai_support",),
            )

        basis = ["ai_candidate_selected", "independent_non_ai_support"]
        if cross_source:
            basis.append("cross_source_identity_support")
        if selected_semantic is not None and selected_semantic >= self.verified_semantic_threshold:
            basis.append("semantic_support")
        if deterministic_score >= self.ai_independent_evidence_threshold:
            basis.append("deterministic_metadata_support")
        return self._result(
            batch,
            consensus,
            semantic,
            adjudication,
            status=AI_SUPPORTED_MATCH,
            selected=selected,
            method="local_ai_supported",
            review_required=True,
            basis=tuple(basis),
            warnings=("ai_supported_matches_require_review",),
        )

    def _strong_semantic_possible(
        self,
        batch: CandidateBatch,
        consensus: ConsensusResult,
        semantic: Optional[SemanticResult],
    ) -> Optional[int]:
        if semantic is None or semantic.status != "ranked":
            return None
        leader = self._valid_index(semantic.leading_candidate_index, batch)
        if leader is None:
            return None
        similarity = self._semantic_similarity(semantic, leader)
        assessment = self._assessment(consensus, leader)
        if similarity is None or similarity < self.possible_semantic_threshold:
            return None
        if assessment is None or assessment.evidence_score < self.semantic_independent_evidence_threshold:
            return None
        if assessment.contradictory:
            return None
        return leader

    @staticmethod
    def _valid_index(index: Optional[int], batch: CandidateBatch) -> Optional[int]:
        if isinstance(index, bool) or not isinstance(index, int):
            return None
        if index < 0 or index >= len(batch.candidates):
            return None
        return index

    @staticmethod
    def _assessment(consensus: ConsensusResult, index: Optional[int]) -> Optional[CandidateAssessment]:
        if index is None:
            return None
        return next((item for item in consensus.assessments if item.candidate_index == index), None)

    @staticmethod
    def _semantic_similarity(semantic: Optional[SemanticResult], index: Optional[int]) -> Optional[float]:
        if semantic is None or index is None:
            return None
        item = next((score for score in semantic.scores if score.candidate_index == index), None)
        return item.similarity if item is not None else None

    @staticmethod
    def _in_cross_source_group(index: int, consensus: ConsensusResult) -> bool:
        return any(index in group for group in consensus.cross_source_identity_groups)

    @staticmethod
    def _result(
        batch: CandidateBatch,
        consensus: ConsensusResult,
        semantic: Optional[SemanticResult],
        adjudication: Optional[AdjudicationResult],
        *,
        status: str,
        method: str,
        review_required: bool,
        basis: Sequence[str],
        selected: Optional[int] = None,
        warnings: Sequence[str] = (),
    ) -> ResolutionDecision:
        if status not in RESOLUTION_STATUSES:
            raise ValueError(f"unsupported resolution status: {status}")
        identity = None
        if selected is not None and 0 <= selected < len(batch.candidates):
            identity = batch.candidates[selected].identity_key
        return ResolutionDecision(
            version=RESOLUTION_DECISION_VERSION,
            status=status,
            selected_candidate_index=selected,
            selected_identity_key=identity,
            decision_method=method,
            review_required=bool(review_required),
            evidence_basis=tuple(basis),
            warnings=tuple(warnings),
            consensus_version=consensus.version,
            consensus_status=consensus.status,
            semantic_version=semantic.version if semantic is not None else None,
            semantic_status=semantic.status if semantic is not None else None,
            ai_version=adjudication.version if adjudication is not None else None,
            ai_status=adjudication.status if adjudication is not None else None,
        )
