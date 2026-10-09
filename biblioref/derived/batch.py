# -*- coding: utf-8 -*-
"""Corpus-scale resolution over the existing resolver stack.

Two phases, deliberately separate:

``fetch``   asks the external backends one question per distinct ``query_sha``
            and stores the answer in ``resolution_cache``. This is the only
            part that touches the network, and it is the only part that is
            expensive, so it is rate limited, resumable and never repeated for
            a question already answered.

``decide``  replays cached answers through ConsensusEngine and
            ResolutionDecisionEngine to produce one row per reference. It is
            offline, cheap and fully repeatable, so improving the decision
            engine costs nothing to re-apply over the whole corpus.

Nothing here writes to ``project.json`` or to parser output, and no status is
promoted: ``AI_SUPPORTED_MATCH`` and ``POSSIBLE_MATCH`` are stored exactly as
the decision engine reports them, with ``review_required`` preserved.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from biblioref.resolver.consensus import ConsensusEngine
from biblioref.resolver.crossref import CrossrefBackend
from biblioref.resolver.decision import RESOLUTION_STATUSES, ResolutionDecisionEngine
from biblioref.resolver.models import Candidate, CandidateBatch, ResolverQuery
from biblioref.resolver.openalex import OpenAlexBackend
from biblioref.resolver.resolver import MetadataResolver

BATCH_RESOLUTION_VERSION = "batch-resolution-v0.1"

DEFAULT_RATE_PER_SECOND = 2.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_S = 2.0


MAX_BACKOFF_INTERVAL_S = 30.0
RATE_LIMIT_RETRIES = 4


def _is_rate_limited(error: Any) -> bool:
    """Whether a trapped backend error is the service asking us to slow down.

    ``MetadataResolver`` turns backend exceptions into strings, so this reads
    the message rather than the exception. Both public APIs surface throttling
    as HTTP 429.
    """
    text = str(error)
    return "429" in text or "too many requests" in text.lower()


class _BackendPacer:
    """Per-backend pacing that slows down when a service pushes back.

    One shared rate is not enough: Crossref and OpenAlex throttle differently,
    and the anonymous pools are much tighter than the documented limits. A
    backend that answers 429 gets its own interval doubled, and earns it back
    slowly once it starts answering again.
    """

    def __init__(self, per_second: float, sleep: Callable[[float], None] = time.sleep) -> None:
        self.base_interval = 0.0 if per_second <= 0 else 1.0 / float(per_second)
        self._sleep = sleep
        self._intervals: Dict[str, float] = {}
        self._last: Dict[str, float] = {}

    def interval(self, backend: str) -> float:
        return self._intervals.get(backend, self.base_interval)

    def wait(self, backends: Sequence[str]) -> None:
        now = time.monotonic()
        delay = 0.0
        for name in backends:
            delay = max(delay, self._last.get(name, 0.0) + self.interval(name) - now)
        if delay > 0:
            self._sleep(delay)
        stamp = time.monotonic()
        for name in backends:
            self._last[name] = stamp

    def penalize(self, backend: str) -> float:
        current = self.interval(backend) or 0.5
        self._intervals[backend] = min(current * 2.0, MAX_BACKOFF_INTERVAL_S)
        return self._intervals[backend]

    def relax(self, backend: str) -> None:
        current = self._intervals.get(backend)
        if current is None:
            return
        eased = current * 0.8
        if eased <= self.base_interval:
            self._intervals.pop(backend, None)
        else:
            self._intervals[backend] = eased

    def snapshot(self) -> Dict[str, float]:
        return {k: round(v, 2) for k, v in sorted(self._intervals.items())}


@dataclass
class FetchReport:
    pending_at_start: int = 0
    fetched: int = 0
    empty_answers: int = 0
    failed: int = 0
    rate_limited: int = 0
    partial_answers: int = 0
    skipped_exhausted: int = 0
    requests: int = 0
    elapsed_s: float = 0.0
    stopped_early: Optional[str] = None
    final_intervals: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pending_at_start": self.pending_at_start,
            "fetched": self.fetched,
            "empty_answers": self.empty_answers,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "partial_answers": self.partial_answers,
            "skipped_exhausted": self.skipped_exhausted,
            "requests": self.requests,
            "elapsed_s": round(self.elapsed_s, 2),
            "stopped_early": self.stopped_early,
            "final_intervals_s": dict(self.final_intervals),
            "errors": self.errors[:20],
        }


@dataclass
class DecideReport:
    considered: int = 0
    decided: int = 0
    skipped_no_cache: int = 0
    statuses: Dict[str, int] = field(default_factory=dict)
    review_required: int = 0
    elapsed_s: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "considered": self.considered,
            "decided": self.decided,
            "skipped_no_cache": self.skipped_no_cache,
            "statuses": dict(sorted(self.statuses.items(), key=lambda kv: -kv[1])),
            "review_required": self.review_required,
            "elapsed_s": round(self.elapsed_s, 2),
        }


def candidate_from_cached(data: Mapping[str, Any]) -> Candidate:
    """Rebuild a Candidate from its stored projection.

    Raw provider payloads are intentionally not persisted: the provider id
    (DOI / OpenAlex work id) is stored, so the full record stays re-fetchable
    without carrying tens of thousands of copies of it in the sidecar.
    """
    return Candidate.from_mapping(
        str(data.get("source") or "unknown"),
        dict(data),
        source_id=data.get("source_id"),
        retrieval_method=data.get("retrieval_method"),
        provider_score=data.get("provider_score"),
        rank=data.get("rank"),
    )


def batch_from_cache(query: ResolverQuery, row: Mapping[str, Any]) -> CandidateBatch:
    raw = json.loads(row["candidates_json"] or "[]")
    errors = json.loads(row["backend_errors"] or "[]") if row["backend_errors"] else []
    return CandidateBatch(
        query=query,
        candidates=tuple(candidate_from_cached(x) for x in raw),
        backend_errors=tuple(str(e) for e in errors),
    )


def _query_from_row(row: Mapping[str, Any]) -> ResolverQuery:
    """Rebuild the resolver query from the derived reference row."""
    return ResolverQuery.from_parser(
        row["raw_text"] or "",
        {
            "title": row["title"],
            "authors": row["authors"] or row["author"],
            "year": row["year"],
            "journal": row["journal"],
            "publisher": row["publisher"],
            "doi": row["doi"],
            "publication_type": row["publication_type"],
            "parser_version": row["parser_version"],
        },
    )


def pending_queries(conn: sqlite3.Connection, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                    retry_failed: bool = False, limit: Optional[int] = None,
                    doc_ids: Optional[Sequence[str]] = None,
                    only_missing_doi: bool = False) -> List[sqlite3.Row]:
    """One representative reference row per still-unanswered query.

    ``only_missing_doi`` restricts the run to the references the parser could
    not give a DOI. Those are both the expensive case (a bibliographic search
    rather than a DOI lookup) and the only case where resolution can add an
    identifier the corpus does not already have.
    """
    where = ["c.query_sha IS NULL"]
    params: List[Any] = []
    if not retry_failed:
        where.append("(f.attempts IS NULL OR f.attempts < ?)")
        params.append(int(max_attempts))
    if only_missing_doi:
        where.append("r.doi IS NULL")
    if doc_ids:
        where.append("r.doc_id IN (%s)" % ",".join("?" for _ in doc_ids))
        params.extend(doc_ids)

    sql = f"""
        SELECT r.*, MIN(r.ref_id) AS _rep
        FROM reference r
        LEFT JOIN resolution_cache c ON c.query_sha = r.query_sha
        LEFT JOIN resolution_failure f ON f.query_sha = r.query_sha
        WHERE {' AND '.join(where)}
        GROUP BY r.query_sha
        ORDER BY r.doi IS NULL, r.doc_id, r.ord
    """
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return list(conn.execute(sql, params))


def count_exhausted(conn: sqlite3.Connection, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> int:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT f.query_sha) AS n
        FROM resolution_failure f
        LEFT JOIN resolution_cache c ON c.query_sha = f.query_sha
        WHERE c.query_sha IS NULL AND f.attempts >= ?
        """,
        (int(max_attempts),),
    ).fetchone()
    return int(row["n"]) if row else 0


def build_backends(
    *,
    names: Sequence[str] = ("crossref", "openalex"),
    crossref_email: Optional[str] = None,
    openalex_api_key: Optional[str] = None,
    timeout: float = 10.0,
) -> List[Any]:
    backends: List[Any] = []
    for name in names:
        key = str(name).strip().lower()
        if key == "crossref":
            backends.append(CrossrefBackend(email=crossref_email, timeout=timeout))
        elif key == "openalex":
            backends.append(OpenAlexBackend(api_key=openalex_api_key, timeout=timeout))
        else:
            raise ValueError(f"backend desconocido: {name}")
    return backends


def fetch_missing(
    conn: sqlite3.Connection,
    backends: Sequence[Any],
    *,
    limit: Optional[int] = None,
    doc_ids: Optional[Sequence[str]] = None,
    rate_per_second: float = DEFAULT_RATE_PER_SECOND,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_failed: bool = False,
    only_missing_doi: bool = False,
    consecutive_failure_limit: int = 25,
    progress: Optional[Callable[[int, int], None]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchReport:
    """Ask the backends every question that has no cached answer yet.

    Interrupting the process is safe: each answer is committed as it arrives,
    so the next run resumes exactly where this one stopped.
    """
    started = time.time()
    report = FetchReport()
    if not backends:
        raise ValueError("no hay backends configurados")

    rows = pending_queries(
        conn, max_attempts=max_attempts, retry_failed=retry_failed, limit=limit,
        doc_ids=doc_ids, only_missing_doi=only_missing_doi,
    )
    report.pending_at_start = len(rows)
    report.skipped_exhausted = count_exhausted(conn, max_attempts)

    pacer = _BackendPacer(rate_per_second, sleep=sleep)
    resolver = MetadataResolver(backends)
    names = [str(getattr(b, "name", type(b).__name__)) for b in backends]
    backend_names = ",".join(names)
    consecutive_failures = 0

    for index, row in enumerate(rows, start=1):
        query = _query_from_row(row)
        batch = None
        error = None

        for attempt in range(RATE_LIMIT_RETRIES + 1):
            pacer.wait(names)
            report.requests += len(backends)
            try:
                batch = resolver.resolve(query)
            except Exception as exc:  # defensive: MetadataResolver traps per backend
                batch, error = None, f"{exc.__class__.__name__}:{exc}"
                break

            throttled = [e for e in batch.backend_errors if _is_rate_limited(e)]
            for name in names:
                if any(e.startswith(f"{name}:") for e in throttled):
                    report.rate_limited += 1
                    pacer.penalize(name)
                else:
                    pacer.relax(name)

            if not throttled:
                error = None
                break
            if attempt == RATE_LIMIT_RETRIES:
                error = "; ".join(throttled)[:500]
        else:  # pragma: no cover - the loop always breaks or exhausts above
            error = error or "rate_limited"

        # A partial answer is not an answer. The decision tier depends on
        # whether independent sources agree, so caching a batch where one
        # backend was throttled or down would permanently record a lower
        # confidence than the evidence actually supports.
        if batch is not None and error is None and batch.backend_errors:
            error = "respuesta parcial: " + "; ".join(batch.backend_errors)[:400]

        now = int(time.time())
        if error:
            report.failed += 1
            if error.startswith("respuesta parcial"):
                report.partial_answers += 1
            report.errors.append(f"{row['query_sha'][:12]} {error[:160]}")
            conn.execute(
                """
                INSERT INTO resolution_failure(query_sha, attempts, last_error, last_attempt_at)
                VALUES(?, 1, ?, ?)
                ON CONFLICT(query_sha) DO UPDATE SET
                    attempts = attempts + 1,
                    last_error = excluded.last_error,
                    last_attempt_at = excluded.last_attempt_at
                """,
                (row["query_sha"], error[:500], now),
            )
            conn.commit()
            consecutive_failures += 1
            if consecutive_failure_limit and consecutive_failures >= consecutive_failure_limit:
                report.stopped_early = (
                    f"{consecutive_failures} fallos seguidos: el servicio parece caido, "
                    "la corrida se detiene para no gastar intentos"
                )
                break
            sleep(min(DEFAULT_BACKOFF_S * consecutive_failures, 30.0))
            continue

        consecutive_failures = 0
        conn.execute(
            """
            INSERT INTO resolution_cache(query_sha, query_json, candidates_json, backend_errors,
                                         backends, resolver_version, fetched_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(query_sha) DO UPDATE SET
                query_json=excluded.query_json,
                candidates_json=excluded.candidates_json,
                backend_errors=excluded.backend_errors,
                backends=excluded.backends,
                resolver_version=excluded.resolver_version,
                fetched_at=excluded.fetched_at
            """,
            (
                row["query_sha"],
                json.dumps(query.as_dict(), ensure_ascii=False),
                json.dumps([c.as_dict() for c in batch.candidates], ensure_ascii=False),
                json.dumps(list(batch.backend_errors), ensure_ascii=False) if batch.backend_errors else None,
                backend_names,
                BATCH_RESOLUTION_VERSION,
                now,
            ),
        )
        conn.execute("DELETE FROM resolution_failure WHERE query_sha=?", (row["query_sha"],))
        conn.commit()
        report.fetched += 1
        if not batch.candidates:
            report.empty_answers += 1
        if progress:
            progress(index, len(rows))

    report.final_intervals = pacer.snapshot()
    report.elapsed_s = time.time() - started
    return report


def decide_pending(
    conn: sqlite3.Connection,
    *,
    redecide: bool = False,
    doc_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    engine: Optional[ResolutionDecisionEngine] = None,
) -> DecideReport:
    """Turn cached answers into one decision per reference. Offline."""
    started = time.time()
    report = DecideReport()
    engine = engine or ResolutionDecisionEngine()
    consensus_engine = ConsensusEngine()

    where = []
    params: List[Any] = []
    if not redecide:
        # A decision made against a different question does not count as done.
        where.append("(res.ref_id IS NULL OR res.query_sha <> r.query_sha)")
    if doc_ids:
        where.append("r.doc_id IN (%s)" % ",".join("?" for _ in doc_ids))
        params.extend(doc_ids)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT r.*, c.candidates_json, c.backend_errors
        FROM reference r
        JOIN resolution_cache c ON c.query_sha = r.query_sha
        LEFT JOIN resolution res ON res.ref_id = r.ref_id
        {clause}
        ORDER BY r.doc_id, r.ord
    """
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    now = int(time.time())
    pending = list(conn.execute(sql, params))
    report.considered = len(pending)

    writes: List[Tuple[Any, ...]] = []
    for row in pending:
        query = _query_from_row(row)
        batch = batch_from_cache(query, row)
        consensus = consensus_engine.assess(batch)
        decision = engine.decide(batch, consensus)

        if decision.status not in RESOLUTION_STATUSES:
            raise RuntimeError(f"estado de resolución desconocido: {decision.status}")

        selected = None
        if decision.selected_candidate_index is not None:
            try:
                selected = batch.candidates[decision.selected_candidate_index]
            except IndexError:
                selected = None

        writes.append((
            row["ref_id"],
            row["query_sha"],
            decision.status,
            decision.version,
            selected.source if selected else None,
            selected.source_id if selected else None,
            selected.doi if selected else None,
            selected.title if selected else None,
            selected.year if selected else None,
            selected.container_title if selected else None,
            json.dumps(decision.as_dict(), ensure_ascii=False),
            now,
        ))
        report.statuses[decision.status] = report.statuses.get(decision.status, 0) + 1
        if decision.review_required:
            report.review_required += 1

    if writes:
        conn.executemany(
            """
            INSERT INTO resolution(ref_id, query_sha, status, decision_version, selected_source,
                                   selected_source_id, selected_doi, selected_title, selected_year,
                                   selected_container, evidence_json, decided_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ref_id) DO UPDATE SET
                query_sha=excluded.query_sha, status=excluded.status,
                decision_version=excluded.decision_version,
                selected_source=excluded.selected_source,
                selected_source_id=excluded.selected_source_id,
                selected_doi=excluded.selected_doi,
                selected_title=excluded.selected_title,
                selected_year=excluded.selected_year,
                selected_container=excluded.selected_container,
                evidence_json=excluded.evidence_json, decided_at=excluded.decided_at
            """,
            writes,
        )
        conn.commit()
        report.decided = len(writes)

    missing = conn.execute(
        """
        SELECT COUNT(*) AS n FROM reference r
        LEFT JOIN resolution_cache c ON c.query_sha = r.query_sha
        WHERE c.query_sha IS NULL
        """
    ).fetchone()
    report.skipped_no_cache = int(missing["n"]) if missing else 0
    report.elapsed_s = time.time() - started
    return report


def resolution_progress(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Where the corpus stands: answered, decided, and what it bought."""
    total = conn.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"]
    queries = conn.execute("SELECT COUNT(DISTINCT query_sha) AS n FROM reference").fetchone()["n"]
    cached = conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"]
    failed = conn.execute("SELECT COUNT(*) AS n FROM resolution_failure").fetchone()["n"]
    decided = conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"]

    statuses = {
        r["status"]: r["n"]
        for r in conn.execute("SELECT status, COUNT(*) AS n FROM resolution GROUP BY status ORDER BY n DESC")
    }

    parser_doi = conn.execute("SELECT COUNT(*) AS n FROM reference WHERE doi IS NOT NULL").fetchone()["n"]
    gained = conn.execute(
        """
        SELECT COUNT(*) AS n FROM reference r
        JOIN resolution res ON res.ref_id = r.ref_id
        WHERE r.doi IS NULL AND res.selected_doi IS NOT NULL
        """
    ).fetchone()["n"]

    return {
        "references": total,
        "distinct_queries": queries,
        "queries_answered": cached,
        "queries_failed": failed,
        "queries_pending": max(queries - cached, 0),
        "references_decided": decided,
        "statuses": statuses,
        "doi": {
            "from_parser": parser_doi,
            "from_parser_pct": round(100 * parser_doi / total, 1) if total else 0.0,
            "gained_by_resolution": gained,
            "combined_pct": round(100 * (parser_doi + gained) / total, 1) if total else 0.0,
        },
        "version": BATCH_RESOLUTION_VERSION,
    }
