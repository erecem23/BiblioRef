# -*- coding: utf-8 -*-
"""Explainable deterministic consensus over external metadata candidates.

Scores in this module are evidence scores, not probabilities. The engine ranks
and flags candidates but has no authority to overwrite parser output.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .models import Candidate, CandidateBatch, ResolverQuery
from .normalize import normalize_match_text

CONSENSUS_VERSION = "metadata-consensus-v0.2"
EXTERNAL_CONSENSUS_MIN_EVIDENCE = 0.78
EXTERNAL_CONSENSUS_MIN_GROUP_MARGIN = 0.10


def _sim(a: Any, b: Any) -> Optional[float]:
    left = normalize_match_text(a)
    right = normalize_match_text(b)
    if not left or not right:
        return None
    return SequenceMatcher(None, left, right).ratio()


def _first_author(query: ResolverQuery | Candidate) -> Optional[str]:
    return query.authors[0] if query.authors else None


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_index: int
    source: str
    source_id: Optional[str]
    identity_key: Optional[str]
    evidence_score: float
    positive: Tuple[str, ...]
    contradictory: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "candidate_index": self.candidate_index,
            "source": self.source,
            "source_id": self.source_id,
            "identity_key": self.identity_key,
            "evidence_score": self.evidence_score,
            "positive": list(self.positive),
            "contradictory": list(self.contradictory),
        }


@dataclass(frozen=True)
class ConsensusResult:
    version: str
    status: str
    leading_candidate_index: Optional[int]
    assessments: Tuple[CandidateAssessment, ...]
    cross_source_identity_groups: Tuple[Tuple[int, ...], ...]
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "leading_candidate_index": self.leading_candidate_index,
            "assessments": [x.as_dict() for x in self.assessments],
            "cross_source_identity_groups": [list(x) for x in self.cross_source_identity_groups],
            "notes": list(self.notes),
        }


class ConsensusEngine:
    """Rank candidates using transparent field agreement and source consensus."""

    def assess(self, batch: CandidateBatch) -> ConsensusResult:
        query = batch.query
        if not batch.candidates:
            return ConsensusResult(
                version=CONSENSUS_VERSION,
                status="unresolved",
                leading_candidate_index=None,
                assessments=(),
                cross_source_identity_groups=(),
                notes=("no_external_candidates",),
            )

        assessments = tuple(
            self._assess_candidate(query, candidate, index)
            for index, candidate in enumerate(batch.candidates)
        )
        groups = self._cross_source_groups(batch.candidates)
        ordered = sorted(assessments, key=lambda x: x.evidence_score, reverse=True)
        leader = ordered[0]
        runner = ordered[1] if len(ordered) > 1 else None

        exact_doi = any(
            query.doi
            and candidate.doi
            and query.doi == candidate.doi
            for candidate in batch.candidates
        )
        leader_group_margin = self._leader_group_margin(
            leader.candidate_index,
            groups,
            assessments,
        )
        leader_has_group = self._leader_has_cross_source_consensus(
            leader.candidate_index,
            groups,
        )
        competing_cross_source_identity = (
            leader_has_group
            and leader_group_margin is not None
            and leader_group_margin < EXTERNAL_CONSENSUS_MIN_GROUP_MARGIN
        )
        external_consensus_supported = (
            leader_has_group
            and not leader.contradictory
            and leader.evidence_score >= EXTERNAL_CONSENSUS_MIN_EVIDENCE
            and not competing_cross_source_identity
        )

        if exact_doi:
            status = "exact_identifier"
        elif external_consensus_supported:
            status = "external_consensus"
        elif competing_cross_source_identity:
            status = "ambiguous_conflict"
        elif (
            runner is not None
            and leader.identity_key != runner.identity_key
            and abs(leader.evidence_score - runner.evidence_score) < 0.05
        ):
            status = "ambiguous_conflict"
        elif leader.contradictory and leader.evidence_score < 0.75:
            status = "ambiguous_conflict"
        elif leader.evidence_score >= 0.78 and (
            runner is None or leader.evidence_score - runner.evidence_score >= 0.10
        ):
            status = "probable_candidate"
        else:
            status = "unresolved"

        notes = ["evidence_score_is_not_probability"]
        if competing_cross_source_identity:
            notes.append("competing_cross_source_identities_prevent_auto_consensus")
        return ConsensusResult(
            version=CONSENSUS_VERSION,
            status=status,
            leading_candidate_index=leader.candidate_index,
            assessments=assessments,
            cross_source_identity_groups=groups,
            notes=tuple(notes),
        )

    @staticmethod
    def _leader_has_cross_source_consensus(index: int, groups: Sequence[Tuple[int, ...]]) -> bool:
        return any(index in group for group in groups)

    @staticmethod
    def _leader_group_margin(
        index: int,
        groups: Sequence[Tuple[int, ...]],
        assessments: Sequence[CandidateAssessment],
    ) -> Optional[float]:
        """Evidence separation from the strongest rival cross-source identity.

        ``None`` means the leader has no rival cross-source identity group. The
        value is an evidence-score margin, not a calibrated probability.
        """
        leader_group = next((group for group in groups if index in group), None)
        if leader_group is None:
            return None
        score_by_index = {item.candidate_index: item.evidence_score for item in assessments}
        leader_score = max(score_by_index.get(i, 0.0) for i in leader_group)
        rival_scores = [
            max(score_by_index.get(i, 0.0) for i in group)
            for group in groups
            if group != leader_group
        ]
        if not rival_scores:
            return None
        return round(leader_score - max(rival_scores), 4)

    @staticmethod
    def _cross_source_groups(candidates: Sequence[Candidate]) -> Tuple[Tuple[int, ...], ...]:
        by_identity: Dict[str, List[int]] = {}
        for index, candidate in enumerate(candidates):
            if candidate.identity_key:
                by_identity.setdefault(candidate.identity_key, []).append(index)
        groups = []
        for indexes in by_identity.values():
            sources = {candidates[i].source.casefold() for i in indexes}
            if len(sources) >= 2:
                groups.append(tuple(indexes))
        return tuple(groups)

    @staticmethod
    def _assess_candidate(query: ResolverQuery, candidate: Candidate, index: int) -> CandidateAssessment:
        positive: List[str] = []
        contradictory: List[str] = []
        weighted = 0.0
        observed = 0.0

        if query.doi and candidate.doi:
            observed += 1.00
            if query.doi == candidate.doi:
                weighted += 1.00
                positive.append("doi_exact")
            else:
                contradictory.append("doi_conflict")

        title_sim = _sim(query.title, candidate.title)
        if title_sim is not None:
            observed += 0.45
            weighted += 0.45 * title_sim
            if title_sim >= 0.92:
                positive.append("title_strong")
            elif title_sim < 0.45:
                contradictory.append("title_conflict")

        if query.year and candidate.year:
            observed += 0.20
            if query.year == candidate.year:
                weighted += 0.20
                positive.append("year_exact")
            else:
                contradictory.append("year_conflict")

        author_sim = _sim(_first_author(query), _first_author(candidate))
        if author_sim is not None:
            observed += 0.20
            weighted += 0.20 * author_sim
            if author_sim >= 0.80:
                positive.append("first_author_strong")
            elif author_sim < 0.35:
                contradictory.append("first_author_conflict")

        journal_sim = _sim(query.journal, candidate.container_title)
        if journal_sim is not None:
            observed += 0.15
            weighted += 0.15 * journal_sim
            if journal_sim >= 0.85:
                positive.append("container_strong")
            elif journal_sim < 0.35:
                contradictory.append("container_conflict")

        score = weighted / observed if observed else 0.0
        return CandidateAssessment(
            candidate_index=index,
            source=candidate.source,
            source_id=candidate.source_id,
            identity_key=candidate.identity_key,
            evidence_score=round(score, 4),
            positive=tuple(positive),
            contradictory=tuple(contradictory),
        )
