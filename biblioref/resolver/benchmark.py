# -*- coding: utf-8 -*-
"""Reproducible live benchmark for bibliographic metadata resolution.

The committed gold set contains identifiers for real scholarly works. Query
variants are generated deterministically from canonical Crossref metadata, so
no thesis/private bibliography text is committed. Live API/model work is never
part of the offline unit-test gate.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .consensus import ConsensusEngine
from .crossref import CrossrefBackend
from .decision import (
    POSSIBLE_MATCH,
    UNRESOLVED,
    VERIFIED_EXACT,
    VERIFIED_EXTERNAL_CONSENSUS,
    VERIFIED_SEMANTIC,
    ResolutionDecisionEngine,
)
from .models import Candidate, CandidateBatch, ResolverQuery
from .normalize import normalize_doi
from .openalex import OpenAlexBackend
from .resolver import MetadataResolver
from .semantic import SemanticResolver, SentenceTransformerEmbeddingBackend

BENCHMARK_VERSION = "resolution-benchmark-v0.1"
AUTO_VERIFIED = frozenset({VERIFIED_EXACT, VERIFIED_EXTERNAL_CONSENSUS, VERIFIED_SEMANTIC})


@dataclass(frozen=True)
class GoldWork:
    work_id: str
    doi: str
    domain: str
    note: str = ""


@dataclass(frozen=True)
class PreparedCase:
    case_id: str
    work: GoldWork
    variant: str
    query: ResolverQuery


def load_gold(path: str | Path) -> Tuple[GoldWork, ...]:
    works: List[GoldWork] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        doi = normalize_doi(row.get("doi"))
        if not doi:
            raise ValueError(f"gold line {line_no} has no valid DOI")
        works.append(
            GoldWork(
                work_id=str(row["work_id"]),
                doi=doi,
                domain=str(row.get("domain") or "unknown"),
                note=str(row.get("note") or ""),
            )
        )
    if not works:
        raise ValueError("gold set is empty")
    if len({work.work_id for work in works}) != len(works):
        raise ValueError("gold work_id values must be unique")
    return tuple(works)


def _citation(canonical: Candidate, *, title: Optional[str] = None, include_container: bool = True) -> str:
    pieces = []
    if canonical.authors:
        pieces.append(canonical.authors[0])
    if canonical.year:
        pieces.append(f"({canonical.year})")
    if title or canonical.title:
        pieces.append(title or canonical.title or "")
    if include_container and canonical.container_title:
        pieces.append(canonical.container_title)
    return ". ".join(piece.strip(" .") for piece in pieces if piece) + "."


def _short_title(title: Optional[str]) -> Optional[str]:
    words = re.findall(r"[\wÀ-ÿ'-]+", title or "", flags=re.UNICODE)
    if len(words) <= 5:
        return " ".join(words) or None
    keep = max(5, int(round(len(words) * 0.62)))
    return " ".join(words[:keep])


def prepare_cases(work: GoldWork, canonical: Candidate) -> Tuple[PreparedCase, ...]:
    clean = ResolverQuery(
        raw_reference=_citation(canonical),
        title=canonical.title,
        authors=canonical.authors,
        year=canonical.year,
        journal=canonical.container_title,
    )
    title_year = ResolverQuery(
        raw_reference=". ".join(str(part) for part in (canonical.title, canonical.year) if part),
        title=canonical.title,
        year=canonical.year,
    )
    short = _short_title(canonical.title)
    noisy = ResolverQuery(
        raw_reference=_citation(canonical, title=short, include_container=False),
        title=short,
        authors=canonical.authors[:1],
        year=canonical.year,
    )
    return (
        PreparedCase(f"{work.work_id}:clean", work, "clean", clean),
        PreparedCase(f"{work.work_id}:title_year", work, "title_year", title_year),
        PreparedCase(f"{work.work_id}:short_title", work, "short_title", noisy),
    )


def _selected_doi(batch: CandidateBatch, index: Optional[int]) -> Optional[str]:
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if index < 0 or index >= len(batch.candidates):
        return None
    return batch.candidates[index].doi


def _expected_present(batch: CandidateBatch, expected_doi: str) -> bool:
    return any(candidate.doi == expected_doi for candidate in batch.candidates)


def _decision_row(
    case: PreparedCase,
    batch: CandidateBatch,
    consensus: Any,
    semantic: Any,
    *,
    decision_engine: Optional[ResolutionDecisionEngine] = None,
) -> Dict[str, Any]:
    engine = decision_engine or ResolutionDecisionEngine()
    decision = engine.decide(batch, consensus, semantic)
    selected_doi = _selected_doi(batch, decision.selected_candidate_index)
    expected = case.work.doi
    return {
        "case_id": case.case_id,
        "work_id": case.work.work_id,
        "domain": case.work.domain,
        "variant": case.variant,
        "expected_doi": expected,
        "candidate_count": len(batch.candidates),
        "backend_errors": list(batch.backend_errors),
        "expected_in_candidates": _expected_present(batch, expected),
        "consensus_status": consensus.status,
        "decision_status": decision.status,
        "decision_method": decision.decision_method,
        "review_required": decision.review_required,
        "selected_doi": selected_doi,
        "selected_correct": bool(selected_doi and selected_doi == expected),
        "false_verified": bool(decision.status in AUTO_VERIFIED and selected_doi != expected),
        "semantic_leader": semantic.leading_candidate_index if semantic is not None else None,
        "semantic_scores": [score.as_dict() for score in semantic.scores] if semantic is not None else [],
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    selected = [row for row in rows if row.get("selected_doi")]
    verified = [row for row in rows if row.get("decision_status") in AUTO_VERIFIED]
    correct_verified = [row for row in verified if row.get("selected_correct")]
    return {
        "n_cases": n,
        "candidate_recall_at_returned": round(sum(bool(r.get("expected_in_candidates")) for r in rows) / n, 4) if n else 0.0,
        "selection_accuracy": round(sum(bool(r.get("selected_correct")) for r in rows) / n, 4) if n else 0.0,
        "selection_precision": round(sum(bool(r.get("selected_correct")) for r in selected) / len(selected), 4) if selected else None,
        "auto_verified_coverage": round(len(correct_verified) / n, 4) if n else 0.0,
        "auto_verified_precision": round(len(correct_verified) / len(verified), 4) if verified else None,
        "false_verified_count": sum(bool(r.get("false_verified")) for r in rows),
        "review_required_rate": round(sum(bool(r.get("review_required")) for r in rows) / n, 4) if n else 0.0,
        "unresolved_rate": round(sum(r.get("decision_status") == UNRESOLVED for r in rows) / n, 4) if n else 0.0,
        "possible_rate": round(sum(r.get("decision_status") == POSSIBLE_MATCH for r in rows) / n, 4) if n else 0.0,
    }


def calibrate_semantic_threshold(
    prepared: Sequence[Tuple[PreparedCase, CandidateBatch, Any, Any]],
    *,
    candidates: Sequence[float] = (0.70, 0.74, 0.78, 0.82, 0.86, 0.90, 0.94),
) -> Dict[str, Any]:
    # verified_semantic_threshold only governs the probable_candidate ->
    # VERIFIED_SEMANTIC promotion. Exact DOI and external consensus would be
    # unchanged at every threshold and must not inflate calibration coverage.
    sensitive = [
        item for item in prepared
        if item[2].status == "probable_candidate" and item[3] is not None
    ]
    trials = []
    for threshold in candidates:
        rows = []
        engine = ResolutionDecisionEngine(verified_semantic_threshold=threshold)
        for case, batch, consensus, semantic in sensitive:
            row = _decision_row(case, batch, consensus, semantic, decision_engine=engine)
            row["false_verified"] = bool(
                row["decision_status"] == VERIFIED_SEMANTIC and not row["selected_correct"]
            )
            rows.append(row)
        metrics = summarize(rows)
        trials.append({"threshold": threshold, **metrics})
    if not sensitive:
        return {
            "criterion": "verified_semantic_threshold applies only to probable_candidate cases; no threshold-sensitive cases were observed",
            "n_calibration_cases": 0,
            "recommended_verified_semantic_threshold": None,
            "trials": trials,
        }
    zero_false = [trial for trial in trials if trial["false_verified_count"] == 0]
    pool = zero_false or trials
    best = max(
        pool,
        key=lambda trial: (
            trial["auto_verified_coverage"],
            trial["auto_verified_precision"] if trial["auto_verified_precision"] is not None else -1.0,
            trial["threshold"],
        ),
    )
    return {
        "criterion": "on probable_candidate cases only: maximize VERIFIED_SEMANTIC coverage subject to zero false VERIFIED_SEMANTIC matches; preliminary, not probability calibration",
        "n_calibration_cases": len(sensitive),
        "recommended_verified_semantic_threshold": best["threshold"],
        "trials": trials,
    }


def run_live(
    gold_path: str | Path,
    *,
    semantic: bool = False,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    works = load_gold(gold_path)
    canonical_backend = CrossrefBackend(rows=1, timeout=20)
    layer_specs = {
        "crossref_only": (CrossrefBackend(rows=5, timeout=20),),
        "openalex_only": (OpenAlexBackend(rows=5, timeout=20),),
        "crossref_openalex": (CrossrefBackend(rows=5, timeout=20), OpenAlexBackend(rows=5, timeout=20)),
    }
    semantic_resolver = None
    if semantic:
        semantic_resolver = SemanticResolver(
            SentenceTransformerEmbeddingBackend(model_name=model_name) if model_name else SentenceTransformerEmbeddingBackend()
        )

    cases: List[PreparedCase] = []
    canonical_failures = []
    for work in works:
        try:
            returned = canonical_backend.search(ResolverQuery(raw_reference=work.doi, doi=work.doi))
            canonical = next((candidate for candidate in returned if candidate.doi == work.doi), None)
            if canonical is None:
                raise LookupError("canonical Crossref DOI did not resolve")
            cases.extend(prepare_cases(work, canonical))
        except Exception as exc:
            canonical_failures.append({"work_id": work.work_id, "doi": work.doi, "error": f"{exc.__class__.__name__}:{exc}"})

    result: Dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "gold_work_count": len(works),
        "prepared_case_count": len(cases),
        "canonical_failures": canonical_failures,
        "layers": {},
    }
    calibration_input = []
    consensus_engine = ConsensusEngine()
    for layer_name, backends in layer_specs.items():
        resolver = MetadataResolver(backends)
        deterministic_rows = []
        semantic_rows = []
        for case in cases:
            # Resolve exactly once. Deterministic vs semantic comparisons below
            # therefore differ only by the semantic sidecar/decision path.
            batch = resolver.resolve(case.query)
            consensus = consensus_engine.assess(batch)
            deterministic_rows.append(_decision_row(case, batch, consensus, None))
            if semantic_resolver is not None:
                semantic_result = semantic_resolver.rank(batch)
                semantic_rows.append(_decision_row(case, batch, consensus, semantic_result))
                calibration_input.append((case, batch, consensus, semantic_result))

        layer_payload: Dict[str, Any] = {
            "deterministic": {
                "summary": summarize(deterministic_rows),
                "cases": deterministic_rows,
            }
        }
        if semantic_resolver is not None:
            layer_payload["with_semantic"] = {
                "summary": summarize(semantic_rows),
                "cases": semantic_rows,
            }
        result["layers"][layer_name] = layer_payload

    if semantic_resolver is not None:
        result["semantic_calibration"] = calibrate_semantic_threshold(calibration_input)
    return result


def _summary_view(result: Mapping[str, Any]) -> Dict[str, Any]:
    layer_summary: Dict[str, Any] = {}
    for name, payload in result["layers"].items():
        layer_summary[name] = {
            mode: content["summary"]
            for mode, content in payload.items()
            if isinstance(content, Mapping) and "summary" in content
        }
    return layer_summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run BiblioRef resolution benchmark on a real-work DOI gold set")
    parser.add_argument("gold", help="JSONL gold file")
    parser.add_argument("--semantic", action="store_true", help="run local SentenceTransformer semantic ranking")
    parser.add_argument("--model", default=None, help="optional SentenceTransformer model name")
    parser.add_argument("--output", default="resolution_benchmark_results.json")
    args = parser.parse_args(argv)
    result = run_live(args.gold, semantic=args.semantic, model_name=args.model)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "benchmark_version": result["benchmark_version"],
        "gold_work_count": result["gold_work_count"],
        "prepared_case_count": result["prepared_case_count"],
        "canonical_failures": len(result["canonical_failures"]),
        "layers": _summary_view(result),
        "semantic_calibration": result.get("semantic_calibration"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
