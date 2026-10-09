# -*- coding: utf-8 -*-
"""Persistence and human-confirmation adapters for bibliographic RAG."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import Candidate
from .rag import EvidenceRecord, EvidenceStore


def evidence_from_candidate(
    candidate: Candidate,
    *,
    evidence_id: str,
    provenance: str,
    verification_status: str = "human_confirmed",
    raw_reference: str = "",
    source_document_id: str = "",
) -> EvidenceRecord:
    """Convert one already-retrieved candidate into explicitly sourced RAG evidence.

    The intended interactive use is a human choosing one candidate in audit UI.
    The adapter copies candidate fields; it does not infer or repair metadata.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError("candidate must be a Candidate")
    return EvidenceRecord(
        evidence_id=evidence_id,
        verification_status=verification_status,
        provenance=provenance,
        title=candidate.title or "",
        authors=candidate.authors,
        year=candidate.year,
        container_title=candidate.container_title or "",
        publisher=candidate.publisher or "",
        doi=candidate.doi,
        raw_reference=raw_reference,
        source_document_id=source_document_id,
    )


def _record_from_mapping(data: Mapping[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=data.get("evidence_id", ""),
        verification_status=data.get("verification_status", ""),
        provenance=data.get("provenance", ""),
        title=data.get("title", ""),
        authors=tuple(data.get("authors") or ()),
        year=data.get("year"),
        container_title=data.get("container_title", ""),
        publisher=data.get("publisher", ""),
        doi=data.get("doi"),
        raw_reference=data.get("raw_reference", ""),
        source_document_id=data.get("source_document_id", ""),
    )


def load_evidence_jsonl(path: str | Path) -> EvidenceStore:
    """Load a local JSONL evidence store through the same trust gate as runtime."""
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid evidence JSONL at line {line_number}") from exc
            if not isinstance(payload, Mapping):
                raise ValueError(f"evidence JSONL line {line_number} must be an object")
            records.append(_record_from_mapping(payload))
    return EvidenceStore(records)


def save_evidence_jsonl(path: str | Path, store: EvidenceStore) -> None:
    """Persist canonical trusted evidence in deterministic JSONL order."""
    if not isinstance(store, EvidenceStore):
        raise TypeError("store must be an EvidenceStore")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for record in sorted(store.records, key=lambda x: x.evidence_id):
            payload = record.as_dict()
            payload.pop("identity_key", None)
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
