"""Audit/export projection for resolver sidecars.

This module flattens a ResolutionDecision plus its selected Candidate into
human-readable columns. It is a view only: candidate metadata remains owned by
the resolver sidecar and parser output is never rewritten.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from biblioref.resolver.decision import ResolutionDecision
from biblioref.resolver.models import CandidateBatch


def resolution_audit_columns(batch: CandidateBatch, decision: ResolutionDecision) -> Dict[str, Any]:
    selected = None
    index = decision.selected_candidate_index
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(batch.candidates):
        selected = batch.candidates[index]
    return {
        "resolution_status": decision.status,
        "resolution_method": decision.decision_method,
        "resolution_review_required": decision.review_required,
        "resolution_selected_index": decision.selected_candidate_index,
        "resolution_selected_identity": decision.selected_identity_key,
        "resolution_selected_source": selected.source if selected is not None else None,
        "resolution_selected_source_id": selected.source_id if selected is not None else None,
        "resolution_selected_doi": selected.doi if selected is not None else None,
        "resolution_selected_title": selected.title if selected is not None else None,
        "resolution_selected_year": selected.year if selected is not None else None,
        "resolution_evidence": " | ".join(decision.evidence_basis),
        "resolution_warnings": " | ".join(decision.warnings),
        "resolution_version": decision.version,
        "resolution_consensus_status": decision.consensus_status,
        "resolution_semantic_status": decision.semantic_status,
        "resolution_ai_status": decision.ai_status,
    }


def attach_resolution_columns(
    records: Iterable[dict],
    sidecars: Sequence[Tuple[CandidateBatch, ResolutionDecision]],
) -> List[dict]:
    rows = [dict(record) for record in records]
    if len(rows) != len(sidecars):
        raise ValueError("records and resolution sidecars must have identical length")
    for row, (batch, decision) in zip(rows, sidecars):
        row.update(resolution_audit_columns(batch, decision))
    return rows
