# -*- coding: utf-8 -*-
"""SQLite schema for the derived analysis store.

The derived store is a sidecar, never a second source of truth. ``project.json``
remains authoritative for extraction, parsing, manual editing and human
resolution decisions; every table here can be dropped and rebuilt from it.

One table is deliberately exempt from that rule in practice: ``resolution_cache``
holds external backend answers, which cost network time and are the only data
here that cannot be recomputed offline. It is therefore keyed by the *content*
of the resolution query rather than by reference id, so it survives rebuilds,
reference splits/merges and re-analysis, and is shared by every reference in the
corpus that asks the same question.
"""
from __future__ import annotations

import sqlite3
from typing import Final

DERIVED_SCHEMA_VERSION: Final = 5
DERIVED_STORE_VERSION: Final = "derived-store-v0.5"

SCHEMA_SQL: Final = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document (
    doc_id         TEXT PRIMARY KEY,
    project_id     TEXT,
    thesis_id      TEXT,
    title          TEXT,
    filename       TEXT,
    university     TEXT,
    faculty        TEXT,
    program        TEXT,
    director       TEXT,
    degree_level   TEXT,
    thesis_year    TEXT,
    n_references   INTEGER,
    content_sha256 TEXT,
    updated_at     INTEGER,
    row_sha        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reference (
    ref_id           TEXT PRIMARY KEY,
    doc_id           TEXT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
    ord              INTEGER,
    raw_text         TEXT NOT NULL,
    original_text    TEXT,
    start_page       INTEGER,
    end_page         INTEGER,
    status           TEXT,
    source           TEXT,
    edited           INTEGER NOT NULL DEFAULT 0,
    parser_version   TEXT,
    author           TEXT,
    authors          TEXT,
    year             TEXT,
    title            TEXT,
    journal          TEXT,
    publisher        TEXT,
    doi              TEXT,
    publication_type TEXT,
    query_sha        TEXT NOT NULL,
    work_key         TEXT,
    work_key_loose   TEXT,
    row_sha          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS reference_doc_idx   ON reference(doc_id);
CREATE INDEX IF NOT EXISTS reference_query_idx ON reference(query_sha);
CREATE INDEX IF NOT EXISTS reference_doi_idx   ON reference(doi);
CREATE INDEX IF NOT EXISTS reference_year_idx  ON reference(year);
CREATE INDEX IF NOT EXISTS reference_type_idx  ON reference(publication_type);
CREATE INDEX IF NOT EXISTS reference_work_idx  ON reference(work_key);
CREATE INDEX IF NOT EXISTS reference_loose_idx ON reference(work_key_loose);

-- Expensive, network-derived, content-keyed. Not rebuilt from project.json.
CREATE TABLE IF NOT EXISTS resolution_cache (
    query_sha        TEXT PRIMARY KEY,
    query_json       TEXT NOT NULL,
    candidates_json  TEXT NOT NULL,
    backend_errors   TEXT,
    backends         TEXT,
    resolver_version TEXT,
    fetched_at       INTEGER NOT NULL
);

-- Cheap, recomputable offline from resolution_cache. Machine decision only.
CREATE TABLE IF NOT EXISTS resolution (
    ref_id             TEXT PRIMARY KEY REFERENCES reference(ref_id) ON DELETE CASCADE,
    query_sha          TEXT NOT NULL,
    status             TEXT NOT NULL,
    decision_version   TEXT,
    selected_source    TEXT,
    selected_source_id TEXT,
    selected_doi       TEXT,
    selected_title     TEXT,
    selected_year      TEXT,
    selected_container TEXT,
    evidence_json      TEXT,
    decided_at         INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS resolution_status_idx ON resolution(status);
CREATE INDEX IF NOT EXISTS resolution_query_idx  ON resolution(query_sha);

-- Transport failures only. A backend that legitimately returns nothing is a
-- valid cached answer; a timeout is not, and must be retried on the next run
-- without retrying forever.
CREATE TABLE IF NOT EXISTS resolution_failure (
    query_sha       TEXT PRIMARY KEY,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    last_attempt_at INTEGER NOT NULL
);

-- Analysis is never computed on open: it is a result the user asks for, so it
-- is stored with the fingerprint of the corpus it was computed over. Reopening
-- the screen shows that stored result and whether the corpus moved since.
CREATE TABLE IF NOT EXISTS analysis_report (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT NOT NULL DEFAULT '',
    group_by     TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,
    report_json  TEXT NOT NULL,
    generated_at INTEGER NOT NULL,
    elapsed_s    REAL
);

CREATE INDEX IF NOT EXISTS analysis_report_idx ON analysis_report(project_id, group_by, generated_at DESC);

-- Mirror of ref["human_resolution"]; project.json stays authoritative.
CREATE TABLE IF NOT EXISTS human_resolution (
    ref_id       TEXT PRIMARY KEY REFERENCES reference(ref_id) ON DELETE CASCADE,
    decision     TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    confirmed_at INTEGER
);
"""


def connect(path) -> sqlite3.Connection:
    """Open the derived database with the pragmas this store relies on."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(DERIVED_SCHEMA_VERSION),),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('store_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (DERIVED_STORE_VERSION,),
    )
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["value"]) if row else 0
