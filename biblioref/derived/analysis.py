# -*- coding: utf-8 -*-
"""Corpus-level bibliometrics over the derived store.

Everything here is offline SQL over the sidecar. No network, no writes.

One rule governs the whole module: **every figure carries its own
denominator**. A median reference age computed over 93,8 % of the corpus is a
different claim from one computed over all of it, and a reader who is not told
which cannot check either. Functions therefore return the base they used and
what they excluded, and callers are expected to show both.

The second rule is that work-level figures are only as good as ``work_key``.
Without external identifiers that key is a documented approximation (see
``identity``), so anything counted in works also reports how many references
could not be identified at all.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .identity import IDENTITY_VERSION

ANALYSIS_VERSION = "corpus-analysis-v0.1"

PRICE_INDEX_MAX_AGE = 5
OLD_REFERENCE_MIN_AGE = 20
MIN_PLAUSIBLE_YEAR = 1800


def _scope(doc_ids: Optional[Sequence[str]], alias: str = "r") -> Tuple[str, List[Any]]:
    if not doc_ids:
        return "", []
    marks = ",".join("?" for _ in doc_ids)
    return f" AND {alias}.doc_id IN ({marks})", list(doc_ids)


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def coverage(conn: sqlite3.Connection, doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """What the corpus contains and how much of it each field actually covers.

    Documents with no references at all are reported separately: they are
    extraction failures, and counting per-thesis averages over the documents
    that happen to have references would hide them.
    """
    where, params = _scope(doc_ids)
    total = conn.execute(f"SELECT COUNT(*) AS n FROM reference r WHERE 1=1{where}", params).fetchone()["n"]
    with_refs = conn.execute(
        f"SELECT COUNT(DISTINCT r.doc_id) AS n FROM reference r WHERE 1=1{where}", params
    ).fetchone()["n"]
    if doc_ids:
        docs = len(set(doc_ids))
    else:
        docs = conn.execute("SELECT COUNT(*) AS n FROM document").fetchone()["n"]
    empty = max(docs - with_refs, 0)
    if not total:
        return {
            "documents": docs,
            "documents_with_references": with_refs,
            "documents_without_references": empty,
            "references": 0,
            "version": ANALYSIS_VERSION,
        }

    # One pass over the scope rather than one query per field: this function is
    # also called once per group by the comparison, where the cost multiplies.
    counts = conn.execute(
        f"""SELECT
              SUM(CASE WHEN r.author IS NOT NULL THEN 1 ELSE 0 END) AS author,
              SUM(CASE WHEN r.year IS NOT NULL AND r.year <> '' THEN 1 ELSE 0 END) AS year,
              SUM(CASE WHEN r.title IS NOT NULL THEN 1 ELSE 0 END) AS title,
              SUM(CASE WHEN r.doi IS NOT NULL THEN 1 ELSE 0 END) AS doi,
              SUM(CASE WHEN r.journal IS NOT NULL THEN 1 ELSE 0 END) AS journal,
              SUM(CASE WHEN r.work_key IS NOT NULL THEN 1 ELSE 0 END) AS identified
            FROM reference r WHERE 1=1{where}""",
        params,
    ).fetchone()

    identified = counts["identified"] or 0
    return {
        "documents": docs,
        "documents_with_references": with_refs,
        "documents_without_references": empty,
        "references": total,
        "fields": {
            name: {"n": counts[name] or 0, "pct": _pct(counts[name] or 0, total)}
            for name in ("author", "year", "title", "doi", "journal")
        },
        "identifiable": {
            "n": identified,
            "pct": _pct(identified, total),
            "excluded": total - identified,
            "excluded_pct": _pct(total - identified, total),
        },
        "identity_version": IDENTITY_VERSION,
        "version": ANALYSIS_VERSION,
    }


def document_types(conn: sqlite3.Connection, doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    where, params = _scope(doc_ids)
    rows = list(conn.execute(
        f"""SELECT COALESCE(r.publication_type, 'sin_tipo') AS tipo, COUNT(*) AS n
            FROM reference r WHERE 1=1{where}
            GROUP BY tipo ORDER BY n DESC""",
        params,
    ))
    total = sum(r["n"] for r in rows)
    return {
        "base": total,
        "types": [{"type": r["tipo"], "n": r["n"], "pct": _pct(r["n"], total)} for r in rows],
        "version": ANALYSIS_VERSION,
    }


def obsolescence(conn: sqlite3.Connection, doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Age of the cited literature, relative to each thesis's own year.

    Only references whose year and whose thesis year are both known can enter,
    which is why the base is reported: it is materially smaller than the corpus.
    """
    where, params = _scope(doc_ids)
    total = conn.execute(f"SELECT COUNT(*) AS n FROM reference r WHERE 1=1{where}", params).fetchone()["n"]
    ages = [
        int(row["age"])
        for row in conn.execute(
            f"""SELECT CAST(d.thesis_year AS INTEGER) - CAST(r.year AS INTEGER) AS age
                FROM reference r JOIN document d ON d.doc_id = r.doc_id
                WHERE r.year GLOB '[0-9][0-9][0-9][0-9]'
                  AND d.thesis_year GLOB '[0-9][0-9][0-9][0-9]'{where}""",
            params,
        )
        if row["age"] is not None and 0 <= int(row["age"]) <= 150
    ]
    ages.sort()
    result: Dict[str, Any] = {
        "base": len(ages),
        "base_pct": _pct(len(ages), total),
        "excluded": total - len(ages),
        "version": ANALYSIS_VERSION,
    }
    if ages:
        result.update({
            "median": ages[len(ages) // 2],
            "mean": round(sum(ages) / len(ages), 1),
            "p25": ages[len(ages) // 4],
            "p75": ages[(3 * len(ages)) // 4],
            "price_index_pct": _pct(sum(1 for a in ages if a <= PRICE_INDEX_MAX_AGE), len(ages)),
            "over_20_pct": _pct(sum(1 for a in ages if a > OLD_REFERENCE_MIN_AGE), len(ages)),
        })
    return result


def temporal_distribution(conn: sqlite3.Connection, doc_ids: Optional[Sequence[str]] = None,
                          min_year: int = MIN_PLAUSIBLE_YEAR,
                          max_year: Optional[int] = None) -> Dict[str, Any]:
    """Distribution of publication years by decade.

    Years outside the plausible range are counted and set aside rather than
    charted: they come from page ranges read as a year ("10, 2031-2048") and a
    phantom 2040s decade in a figure is worse than a reported anomaly.
    """
    max_year = int(max_year or date.today().year)
    where, params = _scope(doc_ids)
    rows = list(conn.execute(
        f"""SELECT (CAST(r.year AS INTEGER) / 10) * 10 AS decada, COUNT(*) AS n
            FROM reference r
            WHERE r.year GLOB '[0-9][0-9][0-9][0-9]'
              AND CAST(r.year AS INTEGER) BETWEEN ? AND ?{where}
            GROUP BY decada ORDER BY decada""",
        [int(min_year), max_year] + params,
    ))
    out_of_range = conn.execute(
        f"""SELECT COUNT(*) AS n FROM reference r
            WHERE r.year GLOB '[0-9][0-9][0-9][0-9]'
              AND CAST(r.year AS INTEGER) NOT BETWEEN ? AND ?{where}""",
        [int(min_year), max_year] + params,
    ).fetchone()["n"]
    total = sum(r["n"] for r in rows)
    return {
        "base": total,
        "range": [int(min_year), max_year],
        "out_of_range": out_of_range,
        "decades": [{"decade": int(r["decada"]), "n": r["n"], "pct": _pct(r["n"], total)} for r in rows],
        "version": ANALYSIS_VERSION,
    }


def top_works(conn: sqlite3.Connection, limit: int = 20,
              doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Most cited works, ranked by how many theses cite them, not by raw count.

    Raw counts reward a single thesis citing one work repeatedly; the number of
    distinct theses is the figure that means something across a corpus.
    """
    where, params = _scope(doc_ids)
    rows = list(conn.execute(
        f"""SELECT r.work_key AS k, COUNT(DISTINCT r.doc_id) AS theses, COUNT(*) AS refs,
                   MAX(r.title) AS title, MAX(r.authors) AS authors, MAX(r.year) AS year
            FROM reference r WHERE r.work_key IS NOT NULL{where}
            GROUP BY r.work_key ORDER BY theses DESC, refs DESC LIMIT ?""",
        params + [int(limit)],
    ))
    return {
        "works": [
            {"work_key": r["k"], "theses": r["theses"], "references": r["refs"],
             "title": r["title"], "authors": r["authors"], "year": r["year"]}
            for r in rows
        ],
        "version": ANALYSIS_VERSION,
    }


def top_sources(conn: sqlite3.Connection, limit: int = 20,
                doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    where, params = _scope(doc_ids)
    rows = list(conn.execute(
        f"""SELECT r.journal AS j, COUNT(DISTINCT r.doc_id) AS theses, COUNT(*) AS refs
            FROM reference r WHERE r.journal IS NOT NULL AND r.journal <> ''{where}
            GROUP BY LOWER(r.journal) ORDER BY refs DESC LIMIT ?""",
        params + [int(limit)],
    ))
    base = conn.execute(
        f"SELECT COUNT(*) AS n FROM reference r WHERE r.journal IS NOT NULL AND r.journal <> ''{where}",
        params,
    ).fetchone()["n"]
    return {
        "base": base,
        "sources": [{"journal": r["j"], "theses": r["theses"], "references": r["refs"]} for r in rows],
        "version": ANALYSIS_VERSION,
    }


def identity_sensitivity(conn: sqlite3.Connection,
                         doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """How much the work count depends on treating editions as separate works.

    The gap between the two keys is the size of the re-edition question. It is
    reported rather than resolved, because resolving it needs external
    identifiers the corpus does not yet have.
    """
    where, params = _scope(doc_ids)
    strict = conn.execute(
        f"SELECT COUNT(DISTINCT r.work_key) AS n FROM reference r WHERE r.work_key IS NOT NULL{where}",
        params,
    ).fetchone()["n"]
    loose = conn.execute(
        f"SELECT COUNT(DISTINCT r.work_key_loose) AS n FROM reference r "
        f"WHERE r.work_key_loose IS NOT NULL{where}",
        params,
    ).fetchone()["n"]
    identified = conn.execute(
        f"SELECT COUNT(*) AS n FROM reference r WHERE r.work_key IS NOT NULL{where}", params
    ).fetchone()["n"]
    return {
        "identified_references": identified,
        "works_with_year": strict,
        "works_ignoring_year": loose,
        "works_merged_by_ignoring_year": max(strict - loose, 0),
        "collapse_pct": _pct(identified - strict, identified),
        "version": ANALYSIS_VERSION,
    }


def bibliographic_coupling(conn: sqlite3.Connection, min_shared: int = 5,
                           limit: int = 50,
                           doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Thesis pairs that cite the same works.

    Jaccard is reported alongside the raw count because a long bibliography
    shares more works with everything simply by being long.
    """
    where, params = _scope(doc_ids, "a")
    where_b, params_b = _scope(doc_ids, "b")
    rows = list(conn.execute(
        f"""SELECT a.doc_id AS a, b.doc_id AS b, COUNT(DISTINCT a.work_key) AS shared
            FROM reference a JOIN reference b
              ON a.work_key = b.work_key AND a.doc_id < b.doc_id
            WHERE a.work_key IS NOT NULL{where}{where_b}
            GROUP BY a.doc_id, b.doc_id
            HAVING shared >= ? ORDER BY shared DESC LIMIT ?""",
        params + params_b + [int(min_shared), int(limit)],
    ))
    sizes = {
        r["doc_id"]: r["n"]
        for r in conn.execute(
            "SELECT doc_id, COUNT(DISTINCT work_key) AS n FROM reference "
            "WHERE work_key IS NOT NULL GROUP BY doc_id"
        )
    }
    titles = {
        r["doc_id"]: (r["title"], r["university"])
        for r in conn.execute("SELECT doc_id, title, university FROM document")
    }
    pairs = []
    for r in rows:
        union = sizes.get(r["a"], 0) + sizes.get(r["b"], 0) - r["shared"]
        pairs.append({
            "a": r["a"], "b": r["b"],
            "a_title": titles.get(r["a"], (None, None))[0],
            "b_title": titles.get(r["b"], (None, None))[0],
            "a_university": titles.get(r["a"], (None, None))[1],
            "b_university": titles.get(r["b"], (None, None))[1],
            "shared_works": r["shared"],
            "jaccard": round(r["shared"] / union, 4) if union else 0.0,
        })
    return {"min_shared": min_shared, "pairs": pairs, "version": ANALYSIS_VERSION}


def co_citation(conn: sqlite3.Connection, min_theses: int = 4, limit: int = 50,
                doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Work pairs cited together by the same theses.

    A pair can only reach ``min_theses`` if each of its two works reaches it
    alone, so the self-join is restricted to those works first. Over this
    corpus that is a few hundred works instead of twenty-nine thousand, which
    is the difference between twenty seconds and a fraction of one.
    """
    where, params = _scope(doc_ids, "a")
    where_m, params_m = _scope(doc_ids, "m")
    rows = list(conn.execute(
        f"""WITH shared AS (
              SELECT m.work_key AS k FROM reference m
              WHERE m.work_key IS NOT NULL{where_m}
              GROUP BY m.work_key HAVING COUNT(DISTINCT m.doc_id) >= ?
            )
            SELECT a.work_key AS wa, b.work_key AS wb, COUNT(DISTINCT a.doc_id) AS theses
            FROM reference a JOIN reference b
              ON a.doc_id = b.doc_id AND a.work_key < b.work_key
            WHERE a.work_key IN (SELECT k FROM shared)
              AND b.work_key IN (SELECT k FROM shared){where}
            GROUP BY a.work_key, b.work_key
            HAVING theses >= ? ORDER BY theses DESC LIMIT ?""",
        params_m + [int(min_theses)] + params + [int(min_theses), int(limit)],
    ))
    labels = {}
    if rows:
        keys = {r["wa"] for r in rows} | {r["wb"] for r in rows}
        marks = ",".join("?" for _ in keys)
        labels = {
            r["work_key"]: r["title"]
            for r in conn.execute(
                f"SELECT work_key, MAX(title) AS title FROM reference "
                f"WHERE work_key IN ({marks}) GROUP BY work_key",
                list(keys),
            )
        }
    return {
        "min_theses": min_theses,
        "pairs": [
            {"a": r["wa"], "b": r["wb"], "theses": r["theses"],
             "a_title": labels.get(r["wa"]), "b_title": labels.get(r["wb"])}
            for r in rows
        ],
        "version": ANALYSIS_VERSION,
    }


def group_comparison(conn: sqlite3.Connection, by: str = "university",
                     doc_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Compare groups of theses, reporting how many fall outside the grouping.

    Documents whose grouping field is missing are counted and named, never
    folded into an 'other' bucket that would quietly distort every percentage.
    """
    if by not in {"university", "program", "faculty", "thesis_year", "director", "degree_level"}:
        raise ValueError(f"agrupación no soportada: {by}")

    scope, scope_params = ("", [])
    if doc_ids:
        scope = " AND doc_id IN (%s)" % ",".join("?" for _ in doc_ids)
        scope_params = list(doc_ids)

    ungrouped = conn.execute(
        f"SELECT COUNT(*) AS n FROM document WHERE ({by} IS NULL OR {by} = ''){scope}",
        scope_params,
    ).fetchone()["n"]
    total_docs = conn.execute(
        f"SELECT COUNT(*) AS n FROM document WHERE 1=1{scope}", scope_params
    ).fetchone()["n"]

    groups = []
    dscope = scope.replace("doc_id IN", "d.doc_id IN")
    for row in conn.execute(
        f"""SELECT d.{by} AS g, COUNT(DISTINCT d.doc_id) AS theses, COUNT(r.ref_id) AS refs,
                   COUNT(DISTINCT r.work_key) AS works
            FROM document d LEFT JOIN reference r ON r.doc_id = d.doc_id
            WHERE d.{by} IS NOT NULL AND d.{by} <> ''{dscope}
            GROUP BY d.{by} ORDER BY theses DESC""",
        scope_params,
    ):
        group_docs = [
            x["doc_id"] for x in conn.execute(
                f"SELECT doc_id FROM document WHERE {by} = ?{scope}", [row["g"]] + scope_params
            )
        ]
        doc_ids_for_group = group_docs
        groups.append({
            "group": row["g"],
            "theses": row["theses"],
            "references": row["refs"],
            "works": row["works"],
            "refs_per_thesis": round(row["refs"] / row["theses"], 1) if row["theses"] else 0.0,
            "obsolescence": obsolescence(conn, doc_ids_for_group),
            "doi_pct": (coverage(conn, doc_ids_for_group).get("fields") or {}).get("doi", {}).get("pct", 0.0),
        })

    # Every group's work set in one pass, then intersected in memory: querying
    # per pair costs one round trip per comparison and grows quadratically.
    by_group: Dict[Any, set] = {}
    for row in conn.execute(
        f"""SELECT d.{by} AS g, r.work_key AS k
            FROM reference r JOIN document d ON d.doc_id = r.doc_id
            WHERE r.work_key IS NOT NULL AND d.{by} IS NOT NULL AND d.{by} <> ''{dscope}""",
        scope_params,
    ):
        by_group.setdefault(row["g"], set()).add(row["k"])

    overlaps = []
    names = [g["group"] for g in groups]
    for i, first in enumerate(names):
        a = by_group.get(first, set())
        for second in names[i + 1:]:
            b = by_group.get(second, set())
            union = len(a | b)
            if union:
                shared = len(a & b)
                overlaps.append({
                    "a": first, "b": second,
                    "shared_works": shared,
                    "jaccard": round(shared / union, 4),
                })
    overlaps.sort(key=lambda x: -x["shared_works"])

    return {
        "by": by,
        "documents": total_docs,
        "ungrouped_documents": ungrouped,
        "ungrouped_pct": _pct(ungrouped, total_docs),
        "groups": groups,
        "overlaps": overlaps,
        "version": ANALYSIS_VERSION,
    }


def full_report(conn: sqlite3.Connection, doc_ids: Optional[Sequence[str]] = None,
                group_by: str = "university") -> Dict[str, Any]:
    """Everything above, in one structure suitable for export or rendering."""
    return {
        "coverage": coverage(conn, doc_ids),
        "document_types": document_types(conn, doc_ids),
        "obsolescence": obsolescence(conn, doc_ids),
        "temporal": temporal_distribution(conn, doc_ids),
        "identity_sensitivity": identity_sensitivity(conn, doc_ids),
        "top_works": top_works(conn, 20, doc_ids),
        "top_sources": top_sources(conn, 20, doc_ids),
        "coupling": bibliographic_coupling(conn, 5, 25, doc_ids),
        "co_citation": co_citation(conn, 4, 25, doc_ids),
        "groups": group_comparison(conn, group_by, doc_ids),
        "version": ANALYSIS_VERSION,
    }


def corpus_fingerprint(conn: sqlite3.Connection) -> str:
    """The source fingerprint the last sync recorded.

    The sidecar does not recompute it: the value describes the project state
    the sidecar was built from, and is written by the sync that built it.
    """
    row = conn.execute("SELECT value FROM meta WHERE key='source_fingerprint'").fetchone()
    return row["value"] if row else ""


def run_and_store(conn: sqlite3.Connection, group_by: str = "university",
                  project_id: str = "", doc_ids: Optional[Sequence[str]] = None,
                  fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """Compute the report the user asked for and keep it with its fingerprint.

    ``project_id`` and ``doc_ids`` scope it: this app keeps several projects in
    one store, and a report that mixed them would answer a question nobody
    asked.
    """
    started = time.perf_counter()
    report = full_report(conn, doc_ids=doc_ids, group_by=group_by)
    elapsed = time.perf_counter() - started
    fingerprint = fingerprint or corpus_fingerprint(conn)
    generated_at = int(time.time())

    conn.execute(
        "INSERT INTO analysis_report(project_id, group_by, fingerprint, report_json, generated_at, elapsed_s) "
        "VALUES(?,?,?,?,?,?)",
        (project_id or "", group_by, fingerprint,
         json.dumps(report, ensure_ascii=False), generated_at, round(elapsed, 3)),
    )
    # Only the last few runs per project and grouping are worth keeping; the
    # report is derived and can always be recomputed.
    conn.execute(
        """DELETE FROM analysis_report WHERE project_id = ? AND group_by = ? AND id NOT IN (
               SELECT id FROM analysis_report WHERE project_id = ? AND group_by = ?
               ORDER BY generated_at DESC LIMIT 5)""",
        (project_id or "", group_by, project_id or "", group_by),
    )
    conn.commit()
    return {
        "report": report,
        "group_by": group_by,
        "project_id": project_id or "",
        "generated_at": generated_at,
        "elapsed_s": round(elapsed, 3),
        "stale": False,
    }


def stored_report(conn: sqlite3.Connection, group_by: str = "university",
                  fingerprint: Optional[str] = None,
                  project_id: str = "") -> Optional[Dict[str, Any]]:
    """The last report for this grouping, and whether the corpus moved since.

    Returns ``None`` when nothing has been run yet: an empty screen with a
    button is the honest state, not a report computed behind the user's back.

    ``fingerprint`` is the state to compare against. Callers that can see the
    project store pass its fingerprint, so an edit made since the last run
    shows as stale without the sidecar having been refreshed.
    """
    row = conn.execute(
        "SELECT * FROM analysis_report WHERE project_id = ? AND group_by = ? "
        "ORDER BY generated_at DESC LIMIT 1",
        (project_id or "", group_by),
    ).fetchone()
    if row is None:
        return None
    return {
        "report": json.loads(row["report_json"]),
        "group_by": row["group_by"],
        "project_id": row["project_id"],
        "generated_at": row["generated_at"],
        "elapsed_s": row["elapsed_s"],
        "stale": row["fingerprint"] != (fingerprint or corpus_fingerprint(conn)),
    }
