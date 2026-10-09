# -*- coding: utf-8 -*-
"""Build and refresh the derived analysis store from ``project.json``.

The sync is one-directional and read-only on the project store: it never opens
``project.json`` for writing and never calls the network. Running it twice in a
row is a no-op, and deleting the sqlite file loses nothing except the cached
external answers in ``resolution_cache``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from biblioref.resolver.models import ResolverQuery
from biblioref.parsing.inheritance import inherit_repeated_authors
from biblioref.resolver.normalize import clean_text, normalize_match_text

from .aliases import ALIASABLE_FIELDS, aliases_for, apply_alias
from .identity import work_keys

from .schema import (
    DERIVED_SCHEMA_VERSION,
    DERIVED_STORE_VERSION,
    connect,
    create_schema,
    schema_version,
)

DERIVED_FILENAME = "derived.sqlite3"

# Bumped whenever the way a query is BUILT changes — hygiene rules, which
# fields are sent, how they are combined. A cached answer is only valid for the
# question that produced it, and the normalized key alone cannot see a change
# in query construction: without this tag, improving hygiene would leave the
# cache silently serving answers obtained with the old, dirty query.
QUERY_BUILD_VERSION = "query-build-v0.3-openalex-search-sanitation"

_DOC_FIELDS = (
    "doc_id", "project_id", "thesis_id", "title", "filename", "university",
    "faculty", "program", "director", "degree_level", "thesis_year",
    "n_references", "content_sha256", "updated_at", "row_sha",
)

_REF_FIELDS = (
    "ref_id", "doc_id", "ord", "raw_text", "original_text", "start_page",
    "end_page", "status", "source", "edited", "parser_version", "author",
    "authors", "year", "title", "journal", "publisher", "doi",
    "publication_type", "query_sha", "work_key", "work_key_loose", "row_sha",
)


def default_workspace() -> Path:
    return Path(os.environ.get("BIBLIOREF_WORKSPACE", Path.home() / ".biblioref" / "projects" / "default"))


def default_store_path(workspace: Optional[Path] = None) -> Path:
    return (workspace or default_workspace()) / DERIVED_FILENAME


def default_project_file(workspace: Optional[Path] = None) -> Path:
    return (workspace or default_workspace()) / "project.json"


def _sha(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def query_for_reference(reference: Mapping[str, Any]) -> ResolverQuery:
    """Build the resolver query a reference would send, without sending it."""
    return ResolverQuery.from_parser(reference.get("text") or "", reference.get("parsed") or {})


def query_sha(query: ResolverQuery) -> str:
    """Content key for one resolution question.

    A DOI fully determines the answer regardless of how the query was built, so
    it keys alone. Otherwise the key covers the normalized evidence a backend
    searches on — so two identically-worded references anywhere in the corpus
    share one cache entry — plus ``QUERY_BUILD_VERSION``, so that changing how
    queries are built retires the answers built the old way.
    """
    if query.doi:
        return hashlib.sha256(f"doi:{query.doi}".encode("utf-8")).hexdigest()
    parts = {
        "build": QUERY_BUILD_VERSION,
        "title": normalize_match_text(query.title),
        "authors": [normalize_match_text(a) for a in query.authors[:3]],
        "year": query.year or "",
        "journal": normalize_match_text(query.journal),
    }
    if not parts["title"] and not parts["authors"]:
        # Nothing stable to key on: fall back to the raw reference so distinct
        # unparsed references never collapse onto one cache entry.
        parts["raw"] = normalize_match_text(query.raw_reference)
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class SyncReport:
    documents_inserted: int = 0
    documents_updated: int = 0
    documents_deleted: int = 0
    references_inserted: int = 0
    references_updated: int = 0
    references_deleted: int = 0
    references_skipped_deleted: int = 0
    stale_resolutions_dropped: int = 0
    human_resolutions: int = 0
    unique_queries: int = 0
    elapsed_s: float = 0.0
    warnings: list = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "documents": {
                "inserted": self.documents_inserted,
                "updated": self.documents_updated,
                "deleted": self.documents_deleted,
            },
            "references": {
                "inserted": self.references_inserted,
                "updated": self.references_updated,
                "deleted": self.references_deleted,
                "skipped_deleted": self.references_skipped_deleted,
            },
            "stale_resolutions_dropped": self.stale_resolutions_dropped,
            "human_resolutions": self.human_resolutions,
            "unique_queries": self.unique_queries,
            "elapsed_s": round(self.elapsed_s, 2),
            "warnings": list(self.warnings),
        }


def _document_row(doc: Mapping[str, Any], alias_tables: Optional[Mapping[str, Mapping[str, str]]] = None) -> Dict[str, Any]:
    """Derive one document row, resolving the labels the user chose to unify.

    The alias is applied here rather than in every query, so grouping, counting
    and comparison all see the same label. The project store keeps the original
    spelling untouched.
    """
    meta = doc.get("metadata") or {}
    tables = alias_tables or {}

    def field(name: str) -> Optional[str]:
        value = clean_text(meta.get(name)) or None
        if name in ALIASABLE_FIELDS and tables.get(name):
            return apply_alias(value, tables[name])
        return value

    row = {
        "doc_id": str(doc.get("id") or ""),
        "project_id": doc.get("project_id"),
        "thesis_id": doc.get("thesis_id"),
        "title": clean_text(doc.get("title")) or None,
        "filename": doc.get("filename"),
        "university": field("university"),
        "faculty": field("faculty"),
        "program": field("program"),
        "director": field("director"),
        "degree_level": clean_text(meta.get("degree_level")) or None,
        "thesis_year": clean_text(meta.get("year")) or None,
        "n_references": _int_or_none(doc.get("n_references")),
        "content_sha256": doc.get("content_sha256"),
        "updated_at": _int_or_none(doc.get("updated_at")),
    }
    row["row_sha"] = _sha(row)
    return row


def _reference_row(doc_id: str, ref: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = ref.get("parsed") or {}
    query = query_for_reference(ref)
    row = {
        "ref_id": str(ref.get("id") or ""),
        "doc_id": doc_id,
        "ord": _int_or_none(ref.get("order")),
        "raw_text": str(ref.get("text") or ""),
        "original_text": ref.get("original_text"),
        "start_page": _int_or_none(ref.get("start_page")),
        "end_page": _int_or_none(ref.get("end_page")),
        "status": ref.get("status"),
        "source": ref.get("source"),
        "edited": 1 if ref.get("edited") else 0,
        "parser_version": parsed.get("parser_version"),
        "author": clean_text(parsed.get("author")) or None,
        "authors": clean_text(parsed.get("authors")) or None,
        "year": query.year,
        "title": clean_text(parsed.get("title")) or None,
        "journal": clean_text(parsed.get("journal")) or None,
        "publisher": clean_text(parsed.get("publisher")) or None,
        "doi": query.doi,
        "publication_type": parsed.get("publication_type"),
        "query_sha": query_sha(query),
    }
    row["work_key"], row["work_key_loose"] = work_keys(row)
    row["row_sha"] = _sha(row)
    return row


def _upsert(conn: sqlite3.Connection, table: str, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    placeholders = ",".join("?" for _ in fields)
    columns = ",".join(fields)
    updates = ",".join(f"{f}=excluded.{f}" for f in fields[1:])
    sql = (
        f"INSERT INTO {table}({columns}) VALUES({placeholders}) "
        f"ON CONFLICT({fields[0]}) DO UPDATE SET {updates}"
    )
    conn.executemany(sql, [tuple(r[f] for f in fields) for r in rows])


def sync_documents(conn: sqlite3.Connection, store: Mapping[str, Any]) -> SyncReport:
    """Refresh document/reference/human_resolution tables from a store dict."""
    started = time.time()
    report = SyncReport()

    documents = store.get("documents") or {}
    if not isinstance(documents, Mapping):
        raise ValueError("store['documents'] must be a mapping")

    existing_docs = {r["doc_id"]: r["row_sha"] for r in conn.execute("SELECT doc_id, row_sha FROM document")}
    existing_refs = {r["ref_id"]: r["row_sha"] for r in conn.execute("SELECT ref_id, row_sha FROM reference")}

    doc_rows: list = []
    ref_rows: list = []
    human_rows: list = []
    seen_docs = set()
    seen_refs = set()

    alias_cache: Dict[Any, Dict[str, Dict[str, str]]] = {}

    def tables_for(project_id: Any) -> Dict[str, Dict[str, str]]:
        if project_id not in alias_cache:
            alias_cache[project_id] = {
                name: aliases_for(store, project_id, name) for name in ALIASABLE_FIELDS
            }
        return alias_cache[project_id]

    for doc in documents.values():
        if not isinstance(doc, Mapping):
            continue
        row = _document_row(doc, tables_for(doc.get("project_id")))
        doc_id = row["doc_id"]
        if not doc_id:
            report.warnings.append("documento sin id, omitido")
            continue
        seen_docs.add(doc_id)
        previous = existing_docs.get(doc_id)
        if previous is None:
            report.documents_inserted += 1
            doc_rows.append(row)
        elif previous != row["row_sha"]:
            report.documents_updated += 1
            doc_rows.append(row)

        # «------------- (2013)» counts for the author of the entry above it.
        references = inherit_repeated_authors(
            [dict(r) for r in (doc.get("references") or ()) if isinstance(r, Mapping)], parsed_keys=("parsed",)
        )
        for ref in references:
            if ref.get("deleted"):
                report.references_skipped_deleted += 1
                continue
            ref_row = _reference_row(doc_id, ref)
            ref_id = ref_row["ref_id"]
            if not ref_id:
                report.warnings.append(f"referencia sin id en {doc_id}, omitida")
                continue
            seen_refs.add(ref_id)
            prior = existing_refs.get(ref_id)
            if prior is None:
                report.references_inserted += 1
                ref_rows.append(ref_row)
            elif prior != ref_row["row_sha"]:
                report.references_updated += 1
                ref_rows.append(ref_row)

            human = ref.get("human_resolution")
            if isinstance(human, Mapping):
                human_rows.append({
                    "ref_id": ref_id,
                    "decision": str(human.get("decision") or human.get("status") or "confirmed"),
                    "payload_json": json.dumps(human, ensure_ascii=False, sort_keys=True, default=str),
                    "confirmed_at": _int_or_none(human.get("confirmed_at") or human.get("at")),
                })

    # Documents must exist before their references (foreign key).
    if doc_rows:
        _upsert(conn, "document", _DOC_FIELDS, doc_rows)
    if ref_rows:
        _upsert(conn, "reference", _REF_FIELDS, ref_rows)

    gone_refs = set(existing_refs) - seen_refs
    if gone_refs:
        conn.executemany("DELETE FROM reference WHERE ref_id=?", [(r,) for r in gone_refs])
        report.references_deleted = len(gone_refs)

    gone_docs = set(existing_docs) - seen_docs
    if gone_docs:
        conn.executemany("DELETE FROM document WHERE doc_id=?", [(d,) for d in gone_docs])
        report.documents_deleted = len(gone_docs)

    # A decision belongs to the question that produced it. If a reference's
    # query changed — an edit, a reparse, a change in query construction — the
    # stored decision no longer describes it and must not survive into the
    # statistics. The cached answers stay: they are keyed by content, so the
    # new question either finds its own answer or is fetched.
    stale = conn.execute(
        """
        DELETE FROM resolution
        WHERE ref_id IN (
            SELECT res.ref_id FROM resolution res
            JOIN reference r ON r.ref_id = res.ref_id
            WHERE res.query_sha <> r.query_sha
        )
        """
    ).rowcount
    report.stale_resolutions_dropped = max(stale, 0)

    conn.execute("DELETE FROM human_resolution")
    if human_rows:
        _upsert(
            conn,
            "human_resolution",
            ("ref_id", "decision", "payload_json", "confirmed_at"),
            human_rows,
        )
    report.human_resolutions = len(human_rows)

    row = conn.execute("SELECT COUNT(DISTINCT query_sha) AS n FROM reference").fetchone()
    report.unique_queries = int(row["n"]) if row else 0

    conn.execute(
        "INSERT INTO meta(key, value) VALUES('source_fingerprint', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (source_fingerprint(store),),
    )

    conn.execute(
        "INSERT INTO meta(key, value) VALUES('last_sync_at', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(int(time.time())),),
    )
    conn.commit()
    report.elapsed_s = time.time() - started
    return report


def _rescue_cache(conn: sqlite3.Connection) -> list:
    """Read the external answers out of an outdated sidecar, if they are there."""
    try:
        return [tuple(r) for r in conn.execute(
            "SELECT query_sha, query_json, candidates_json, backend_errors, backends, "
            "resolver_version, fetched_at FROM resolution_cache"
        )]
    except sqlite3.Error:
        return []


def open_store(path: Optional[Path] = None, rebuild_on_mismatch: bool = True) -> sqlite3.Connection:
    """Open (creating if needed) the derived database at ``path``.

    A sidecar written by an older version is rebuilt rather than refused: every
    table here is derived from project.json and can be recomputed. The one
    exception is ``resolution_cache``, which cost network time, so it is
    carried across instead of being thrown away.
    """
    target = Path(path) if path else default_store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(target)
    current = schema_version(conn)
    if current == DERIVED_SCHEMA_VERSION:
        return conn
    if current == 0:
        create_schema(conn)
        return conn
    if not rebuild_on_mismatch:
        raise RuntimeError(
            f"derived store schema {current} != {DERIVED_SCHEMA_VERSION}; "
            "borrar el archivo y re-sincronizar (no se pierde nada salvo la cache externa)"
        )

    rescued = _rescue_cache(conn)
    conn.close()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(target) + suffix)
        if candidate.exists():
            candidate.unlink()

    conn = connect(target)
    create_schema(conn)
    if rescued:
        conn.executemany(
            "INSERT OR REPLACE INTO resolution_cache(query_sha, query_json, candidates_json, "
            "backend_errors, backends, resolver_version, fetched_at) VALUES(?,?,?,?,?,?,?)",
            rescued,
        )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('rebuilt_from_schema', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(current),),
    )
    conn.commit()
    return conn


def sync_from_file(
    project_file: Optional[Path] = None,
    store_path: Optional[Path] = None,
) -> Tuple[sqlite3.Connection, SyncReport]:
    source = Path(project_file) if project_file else default_project_file()
    if not source.exists():
        raise FileNotFoundError(f"no existe {source}")
    data = json.loads(source.read_text(encoding="utf-8"))
    conn = open_store(store_path)
    return conn, sync_documents(conn, data)


# Only what an analysis can actually see. Hashing the derived rows instead
# would mean rebuilding every ResolverQuery just to compare, which is the
# expensive half of a sync and made opening the screen take seconds.
_FINGERPRINT_PARSED_FIELDS = (
    "author", "authors", "year", "title", "journal", "publisher", "doi", "publication_type",
)
_FINGERPRINT_META_FIELDS = (
    "university", "faculty", "program", "director", "degree_level", "year",
)
FINGERPRINT_VERSION = "source-fingerprint-v0.1"

_UNIT = ""
_RECORD = ""


def source_fingerprint(store: Mapping[str, Any], project_id: Optional[str] = None) -> str:
    """Hash of everything in the project store that the analysis depends on.

    Cheaper proxies (a reference count, a timestamp) miss the change that
    matters most: a correction that leaves the count untouched. This reads the
    raw fields directly, so it stays fast enough to run when a screen opens.

    ``project_id`` restricts it to one project, so editing one project does not
    mark another project's report stale.
    """
    digest = hashlib.sha256()
    digest.update(FINGERPRINT_VERSION.encode("utf-8"))
    digest.update(str(project_id or "").encode("utf-8"))

    documents = store.get("documents") or {}
    if not isinstance(documents, Mapping):
        return digest.hexdigest()

    for doc_id in sorted(documents):
        doc = documents[doc_id]
        if not isinstance(doc, Mapping):
            continue
        if project_id and doc.get("project_id") != project_id:
            continue
        meta = doc.get("metadata") or {}
        tables = {name: aliases_for(store, doc.get("project_id"), name) for name in ALIASABLE_FIELDS}
        parts = [str(doc_id), str(doc.get("title") or "")]
        parts.extend(
            str((apply_alias(meta.get(f), tables[f]) if f in ALIASABLE_FIELDS else meta.get(f)) or "")
            for f in _FINGERPRINT_META_FIELDS
        )
        digest.update(_UNIT.join(parts).encode("utf-8"))
        digest.update(_RECORD.encode("utf-8"))

        refs = doc.get("references") or ()
        for ref in sorted(refs, key=lambda r: str(r.get("id") or "") if isinstance(r, Mapping) else ""):
            if not isinstance(ref, Mapping) or ref.get("deleted"):
                continue
            parsed = ref.get("parsed") or {}
            row = [str(ref.get("id") or ""), str(ref.get("text") or "")]
            row.extend(str(parsed.get(f) or "") for f in _FINGERPRINT_PARSED_FIELDS)
            digest.update(_UNIT.join(row).encode("utf-8"))
            digest.update(_RECORD.encode("utf-8"))

    return digest.hexdigest()


def documents_of(store: Mapping[str, Any], project_id: Optional[str] = None) -> List[str]:
    """Ids of the documents an analysis should cover, in the project's scope."""
    documents = store.get("documents") or {}
    if not isinstance(documents, Mapping):
        return []
    out = []
    for doc_id, doc in documents.items():
        if not isinstance(doc, Mapping):
            continue
        if project_id and doc.get("project_id") != project_id:
            continue
        out.append(str(doc_id))
    return sorted(out)


def corpus_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Descriptives with their denominators, straight from SQL."""
    total = conn.execute("SELECT COUNT(*) AS n FROM reference").fetchone()["n"]
    docs = conn.execute("SELECT COUNT(*) AS n FROM document").fetchone()["n"]
    if not total:
        return {"documents": docs, "references": 0}

    with_doi = conn.execute("SELECT COUNT(*) AS n FROM reference WHERE doi IS NOT NULL").fetchone()["n"]
    with_year = conn.execute("SELECT COUNT(*) AS n FROM reference WHERE year IS NOT NULL AND year<>''").fetchone()["n"]
    unique_q = conn.execute("SELECT COUNT(DISTINCT query_sha) AS n FROM reference").fetchone()["n"]
    resolved = conn.execute("SELECT COUNT(*) AS n FROM resolution").fetchone()["n"]
    cached = conn.execute("SELECT COUNT(*) AS n FROM resolution_cache").fetchone()["n"]

    types = {
        r["publication_type"] or "sin_tipo": r["n"]
        for r in conn.execute(
            "SELECT publication_type, COUNT(*) AS n FROM reference GROUP BY publication_type ORDER BY n DESC"
        )
    }

    ages = [
        int(r["age"])
        for r in conn.execute(
            """
            SELECT CAST(d.thesis_year AS INTEGER) - CAST(r.year AS INTEGER) AS age
            FROM reference r JOIN document d ON d.doc_id = r.doc_id
            WHERE r.year GLOB '[0-9][0-9][0-9][0-9]'
              AND d.thesis_year GLOB '[0-9][0-9][0-9][0-9]'
            """
        )
        if r["age"] is not None and 0 <= int(r["age"]) <= 150
    ]
    ages.sort()

    age_block: Dict[str, Any] = {"base": len(ages), "base_pct": round(100 * len(ages) / total, 1)}
    if ages:
        age_block.update({
            "median": ages[len(ages) // 2],
            "mean": round(sum(ages) / len(ages), 1),
            "price_index_pct": round(100 * sum(1 for a in ages if a <= 5) / len(ages), 1),
            "over_20_pct": round(100 * sum(1 for a in ages if a > 20) / len(ages), 1),
        })

    return {
        "documents": docs,
        "references": total,
        "doi": {"n": with_doi, "pct": round(100 * with_doi / total, 1)},
        "year": {"n": with_year, "pct": round(100 * with_year / total, 1)},
        "unique_queries": unique_q,
        "query_reuse_pct": round(100 * (1 - unique_q / total), 1),
        "resolution": {"decided": resolved, "cached_queries": cached},
        "publication_types": types,
        "age": age_block,
        "store_version": DERIVED_STORE_VERSION,
    }
