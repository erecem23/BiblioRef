# -*- coding: utf-8 -*-
"""Independent real-reference holdout for BiblioRef metadata resolution.

Unlike ``benchmark.py``, this module does not generate query variants from the
canonical target record. It harvests reference strings as deposited by
*independent citing works* in Crossref, strips persistent identifiers from the
query, runs the current parser, and evaluates resolution against the DOI that
was attached to the deposited reference.

The intended workflow is one-way:
1. freeze code/thresholds;
2. harvest the holdout;
3. evaluate it once;
4. archive/freeze the exact JSONL rows and evidence.

Holdout failures are evidence. They must not be used to silently mutate parser
or resolver rules in the same validation cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote
from urllib.request import Request, urlopen

from biblioref.parsing import PARSER_VERSION, parse_reference

from .benchmark import AUTO_VERIFIED, summarize
from .consensus import ConsensusEngine
from .crossref import CrossrefBackend
from .decision import ResolutionDecisionEngine
from .models import CandidateBatch, ResolverQuery
from .normalize import clean_text, normalize_doi
from .openalex import OpenAlexBackend
from .resolver import MetadataResolver
from .semantic import SemanticResolver, SentenceTransformerEmbeddingBackend

HOLDOUT_VERSION = "resolution-holdout-v0.1"
DEFAULT_THRESHOLD = 0.82
CHALLENGER_THRESHOLD = 0.74
CROSSREF_BASE = "https://api.crossref.org/v1"

_DOI_TOKEN_RE = re.compile(r"(?i)\b10\.\d{4,9}/[-._;()/:A-Z0-9]+")
_URL_RE = re.compile(r"(?i)https?://\S+")
_DOI_PREFIX_RE = re.compile(r"(?i)\b(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)")


@dataclass(frozen=True)
class HoldoutSource:
    source_id: str
    doi: str
    domain: str
    max_refs: int = 3
    note: str = ""


JsonTransport = Any


def _default_transport(url: str, timeout: float = 20.0) -> Mapping[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BiblioRef-resolution-holdout/0.1",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:  # nosec - fixed Crossref endpoint
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Crossref response is not a JSON object")
    return payload


def load_sources(path: str | Path) -> Tuple[HoldoutSource, ...]:
    out: List[HoldoutSource] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        doi = normalize_doi(row.get("doi"))
        if not doi:
            raise ValueError(f"source line {line_no} has no valid DOI")
        out.append(
            HoldoutSource(
                source_id=str(row["source_id"]),
                doi=doi,
                domain=str(row.get("domain") or "unknown"),
                max_refs=max(1, min(int(row.get("max_refs") or 3), 10)),
                note=str(row.get("note") or ""),
            )
        )
    if not out:
        raise ValueError("holdout source manifest is empty")
    if len({item.source_id for item in out}) != len(out):
        raise ValueError("holdout source_id values must be unique")
    return tuple(out)


def load_excluded_dois(path: str | Path | None) -> set[str]:
    if path is None:
        return set()
    excluded: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        doi = normalize_doi(row.get("doi") or row.get("expected_doi"))
        if doi:
            excluded.add(doi)
    return excluded


def _reference_text(ref: Mapping[str, Any]) -> str:
    """Return the citing work's deposited reference text, never target metadata."""
    raw = clean_text(ref.get("unstructured"))
    if raw:
        return raw
    fields = (
        ref.get("author"),
        ref.get("year"),
        ref.get("article-title"),
        ref.get("volume-title"),
        ref.get("series-title"),
        ref.get("journal-title"),
        ref.get("volume"),
        ref.get("issue"),
        ref.get("first-page"),
    )
    return ". ".join(clean_text(value).strip(" .") for value in fields if clean_text(value)) + "."


def strip_identifiers(text: Any) -> str:
    """Remove DOI/URL leakage before parsing/resolution while preserving wording."""
    value = clean_text(text)
    value = _URL_RE.sub(" ", value)
    value = _DOI_PREFIX_RE.sub(" ", value)
    value = _DOI_TOKEN_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" .;,:")
    return value


def _reference_is_usable(query_reference: str) -> bool:
    if len(query_reference) < 28:
        return False
    words = re.findall(r"[A-Za-zÀ-ÿ]{2,}", query_reference)
    return len(words) >= 4


def _fetch_source_message(
    source: HoldoutSource,
    *,
    transport: JsonTransport = _default_transport,
    timeout: float = 20.0,
) -> Mapping[str, Any]:
    url = f"{CROSSREF_BASE}/works/{quote(source.doi, safe='')}"
    payload = transport(url, timeout)
    message = payload.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Crossref source record has no message object")
    return message


def harvest_from_message(
    source: HoldoutSource,
    message: Mapping[str, Any],
    *,
    excluded_dois: Iterable[str] = (),
    globally_seen: Optional[set[str]] = None,
) -> Tuple[Dict[str, Any], ...]:
    references = message.get("reference")
    if not isinstance(references, list):
        return ()
    excluded = {normalize_doi(x) for x in excluded_dois if normalize_doi(x)}
    excluded.add(source.doi)
    seen = globally_seen if globally_seen is not None else set()
    rows: List[Dict[str, Any]] = []
    for index, ref in enumerate(references, start=1):
        if not isinstance(ref, Mapping):
            continue
        expected = normalize_doi(ref.get("DOI") or ref.get("doi"))
        if not expected or expected in excluded or expected in seen:
            continue
        observed = _reference_text(ref)
        query = strip_identifiers(observed)
        if not observed or not _reference_is_usable(query):
            continue
        if expected in query.lower():
            raise AssertionError("expected DOI leaked into holdout query")
        digest = hashlib.sha256(observed.encode("utf-8")).hexdigest()
        rows.append(
            {
                "case_id": f"{source.source_id}:r{index}",
                "source_id": source.source_id,
                "source_work_doi": source.doi,
                "source_reference_index": index,
                "source_reference_key": clean_text(ref.get("key")) or None,
                "domain": source.domain,
                "expected_doi": expected,
                "observed_reference": observed,
                "query_reference": query,
                "observed_sha256": digest,
            }
        )
        seen.add(expected)
        if len(rows) >= source.max_refs:
            break
    return tuple(rows)


def harvest_holdout(
    sources: Sequence[HoldoutSource],
    *,
    excluded_dois: Iterable[str] = (),
    transport: JsonTransport = _default_transport,
    timeout: float = 20.0,
) -> Tuple[Tuple[Dict[str, Any], ...], Tuple[Dict[str, Any], ...]]:
    seen: set[str] = set()
    rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    for source in sources:
        try:
            message = _fetch_source_message(source, transport=transport, timeout=timeout)
            source_rows = harvest_from_message(
                source,
                message,
                excluded_dois=excluded_dois,
                globally_seen=seen,
            )
            rows.extend(source_rows)
            if not source_rows:
                failures.append(
                    {
                        "source_id": source.source_id,
                        "doi": source.doi,
                        "error": "no_eligible_doi_reference_with_query_text",
                    }
                )
        except Exception as exc:
            failures.append(
                {
                    "source_id": source.source_id,
                    "doi": source.doi,
                    "error": f"{exc.__class__.__name__}:{exc}",
                }
            )
    return tuple(rows), tuple(failures)


def load_frozen_holdout(path: str | Path) -> Tuple[Dict[str, Any], ...]:
    rows: List[Dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        expected = normalize_doi(row.get("expected_doi"))
        query = strip_identifiers(row.get("query_reference"))
        if not expected or not query:
            raise ValueError(f"holdout line {line_no} is incomplete")
        if expected in query.lower() or _DOI_TOKEN_RE.search(query) or _URL_RE.search(query):
            raise ValueError(f"identifier leakage in holdout line {line_no}")
        rows.append(dict(row, expected_doi=expected, query_reference=query))
    if not rows:
        raise ValueError("frozen holdout is empty")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("holdout case_id values must be unique")
    return tuple(rows)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    Path(path).write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _selected_doi(batch: CandidateBatch, index: Optional[int]) -> Optional[str]:
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if index < 0 or index >= len(batch.candidates):
        return None
    return batch.candidates[index].doi


def _evaluate_one(
    case: Mapping[str, Any],
    batch: CandidateBatch,
    consensus: Any,
    semantic: Any,
    *,
    threshold: float,
    parsed: Mapping[str, Any],
) -> Dict[str, Any]:
    decision = ResolutionDecisionEngine(verified_semantic_threshold=threshold).decide(batch, consensus, semantic)
    selected_doi = _selected_doi(batch, decision.selected_candidate_index)
    expected = normalize_doi(case.get("expected_doi"))
    return {
        "case_id": case.get("case_id"),
        "source_id": case.get("source_id"),
        "domain": case.get("domain"),
        "expected_doi": expected,
        "parser_version": parsed.get("parser_version"),
        "parsed_title": parsed.get("title"),
        "parsed_year": parsed.get("year"),
        "parsed_authors": parsed.get("authors") or parsed.get("author"),
        "parsed_doi": parsed.get("doi"),
        "candidate_count": len(batch.candidates),
        "backend_errors": list(batch.backend_errors),
        "expected_in_candidates": any(candidate.doi == expected for candidate in batch.candidates),
        "consensus_status": consensus.status,
        "semantic_leader": semantic.leading_candidate_index if semantic is not None else None,
        "decision_status": decision.status,
        "decision_method": decision.decision_method,
        "review_required": decision.review_required,
        "selected_doi": selected_doi,
        "selected_correct": bool(selected_doi and selected_doi == expected),
        "false_verified": bool(decision.status in AUTO_VERIFIED and selected_doi != expected),
        "warnings": list(decision.warnings),
    }


def evaluate_holdout(
    rows: Sequence[Mapping[str, Any]],
    *,
    semantic_backend: Optional[Any] = None,
    thresholds: Sequence[float] = (DEFAULT_THRESHOLD, CHALLENGER_THRESHOLD),
) -> Dict[str, Any]:
    resolver = MetadataResolver((CrossrefBackend(rows=5, timeout=20), OpenAlexBackend(rows=5, timeout=20)))
    consensus_engine = ConsensusEngine()
    semantic_resolver = SemanticResolver(semantic_backend) if semantic_backend is not None else None
    by_threshold: Dict[str, List[Dict[str, Any]]] = {f"{float(t):.2f}": [] for t in thresholds}
    deterministic_rows: List[Dict[str, Any]] = []

    for case in rows:
        query_reference = strip_identifiers(case.get("query_reference"))
        parsed = parse_reference(query_reference)
        query = ResolverQuery.from_parser(query_reference, parsed)
        if query.doi:
            raise AssertionError(f"parser recovered DOI from sanitized holdout query: {case.get('case_id')}")
        batch = resolver.resolve(query)
        consensus = consensus_engine.assess(batch)
        semantic = semantic_resolver.rank(batch) if semantic_resolver is not None else None

        deterministic = ResolutionDecisionEngine().decide(batch, consensus, None)
        deterministic_selected = _selected_doi(batch, deterministic.selected_candidate_index)
        expected = normalize_doi(case.get("expected_doi"))
        deterministic_rows.append(
            {
                "case_id": case.get("case_id"),
                "source_id": case.get("source_id"),
                "domain": case.get("domain"),
                "expected_doi": expected,
                "candidate_count": len(batch.candidates),
                "backend_errors": list(batch.backend_errors),
                "expected_in_candidates": any(candidate.doi == expected for candidate in batch.candidates),
                "decision_status": deterministic.status,
                "review_required": deterministic.review_required,
                "selected_doi": deterministic_selected,
                "selected_correct": bool(deterministic_selected and deterministic_selected == expected),
                "false_verified": bool(deterministic.status in AUTO_VERIFIED and deterministic_selected != expected),
            }
        )
        for threshold in thresholds:
            by_threshold[f"{float(threshold):.2f}"].append(
                _evaluate_one(case, batch, consensus, semantic, threshold=float(threshold), parsed=parsed)
            )

    default_key = f"{DEFAULT_THRESHOLD:.2f}"
    challenger_key = f"{CHALLENGER_THRESHOLD:.2f}"
    default_rows = by_threshold.get(default_key, [])
    challenger_rows = by_threshold.get(challenger_key, [])
    changes = []
    if default_rows and challenger_rows:
        for base, challenger in zip(default_rows, challenger_rows):
            if (
                base["decision_status"] != challenger["decision_status"]
                or base["selected_doi"] != challenger["selected_doi"]
            ):
                changes.append(
                    {
                        "case_id": base["case_id"],
                        "expected_doi": base["expected_doi"],
                        "default_status": base["decision_status"],
                        "default_selected_doi": base["selected_doi"],
                        "challenger_status": challenger["decision_status"],
                        "challenger_selected_doi": challenger["selected_doi"],
                        "challenger_false_verified": challenger["false_verified"],
                    }
                )

    return {
        "holdout_version": HOLDOUT_VERSION,
        "parser_version": PARSER_VERSION,
        "n_cases": len(rows),
        "deterministic": {"summary": summarize(deterministic_rows), "cases": deterministic_rows},
        "thresholds": {
            key: {"summary": summarize(items), "cases": items}
            for key, items in by_threshold.items()
        },
        "threshold_comparison": {
            "default": DEFAULT_THRESHOLD,
            "challenger": CHALLENGER_THRESHOLD,
            "changed_case_count": len(changes),
            "challenger_new_false_verified_count": sum(bool(item["challenger_false_verified"]) for item in changes),
            "changes": changes,
        },
    }


def _summary_view(result: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "holdout_version": result.get("holdout_version"),
        "parser_version": result.get("parser_version"),
        "n_cases": result.get("n_cases"),
        "deterministic": (result.get("deterministic") or {}).get("summary"),
        "thresholds": {
            key: payload.get("summary")
            for key, payload in (result.get("thresholds") or {}).items()
        },
        "threshold_comparison": result.get("threshold_comparison"),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Harvest and evaluate an independent real-reference holdout")
    parser.add_argument("--sources", required=True, help="JSONL manifest of independent citing works")
    parser.add_argument("--exclude-gold", default=None, help="existing DOI gold JSONL to exclude from holdout")
    parser.add_argument("--frozen", default=None, help="evaluate an already frozen holdout JSONL instead of harvesting")
    parser.add_argument("--holdout-output", default="resolution_holdout_frozen.jsonl")
    parser.add_argument("--result-output", default="resolution_holdout_results.json")
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--min-cases", type=int, default=24)
    args = parser.parse_args(argv)

    failures: Sequence[Mapping[str, Any]] = ()
    if args.frozen:
        rows = load_frozen_holdout(args.frozen)
    else:
        sources = load_sources(args.sources)
        excluded = load_excluded_dois(args.exclude_gold)
        rows, failures = harvest_holdout(sources, excluded_dois=excluded)
        write_jsonl(args.holdout_output, rows)

    semantic_backend = None
    if args.semantic:
        semantic_backend = SentenceTransformerEmbeddingBackend(model_name=args.model) if args.model else SentenceTransformerEmbeddingBackend()
    result = evaluate_holdout(rows, semantic_backend=semantic_backend)
    result["harvest_failures"] = list(failures)
    result["source_count"] = len({row.get("source_id") for row in rows})
    result["frozen_holdout_sha256"] = hashlib.sha256(
        Path(args.holdout_output if not args.frozen else args.frozen).read_bytes()
    ).hexdigest()
    Path(args.result_output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_summary_view(result), ensure_ascii=False, indent=2))

    if len(rows) < args.min_cases:
        print(f"HOLDOUT_GATE_FAIL: only {len(rows)} cases; minimum is {args.min_cases}")
        return 2
    default = result["thresholds"][f"{DEFAULT_THRESHOLD:.2f}"]["summary"]
    challenger = result["thresholds"][f"{CHALLENGER_THRESHOLD:.2f}"]["summary"]
    if default["false_verified_count"]:
        print("HOLDOUT_GATE_FAIL: default 0.82 produced false VERIFIED decisions")
        return 3
    if challenger["false_verified_count"] > default["false_verified_count"]:
        print("HOLDOUT_GATE_FAIL: challenger 0.74 increases false VERIFIED decisions")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
