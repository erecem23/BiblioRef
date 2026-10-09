# -*- coding: utf-8 -*-
"""Shared development/regression harness for parser v0.9.

Loads every burned parser gold set as a single development corpus and scores an
arbitrary parser callable against it.  The v0.7 and v0.8 gold sets carry the
``author == first author`` contract plus a separate ``gold_authors`` block; the
older v0.3-v0.6 sets predate that contract and are scored on ``author`` only
when the gold value looks like a single person.
"""
from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "parser_baseline"

DEV_SETS = [
    ("v03_reserve", BASE / "reserve_v03/PARSER_V03_RESERVE_STRICT_GOLD_FROZEN.csv"),
    ("v04_external", BASE / "holdout_v04/PARSER_V04_EXTERNAL_GOLD_FROZEN.csv"),
    ("v05_abnt", BASE / "holdout_v05/PARSER_V05_ABNT_EXTERNAL_GOLD_FROZEN.csv"),
    ("v06_abnt", BASE / "holdout_v06/PARSER_V06_ABNT_EXTERNAL_GOLD_FROZEN.csv"),
    ("v07_external", BASE / "holdout_v07/PARSER_V07_EXTERNAL_GOLD_FROZEN.csv"),
    ("v08_external", BASE / "holdout_v08/PARSER_V08_EXTERNAL_GOLD_FROZEN.csv"),
    ("v08_stress", BASE / "holdout_v08/PARSER_V08_STRESS_GOLD_FROZEN.csv"),
]


def norm(x: Any) -> str:
    s = str(x or "").casefold().replace("&", " and ")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fuzzy(a: Any, b: Any) -> float:
    a, b = norm(a), norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def norm_authors(x: Any) -> str:
    s = str(x or "").strip()
    s = re.sub(r"\s*[|;]\s*", "|", s)
    s = re.sub(r"\s+&\s+", "|", s)
    s = re.sub(r"\s+e\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ])", "|", s)
    s = re.sub(r"\s+y\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇÑ])", "|", s)
    parts = [norm(p) for p in s.split("|") if norm(p)]
    return "|".join(parts)


def load_dev_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for name, path in DEV_SETS:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                row = dict(r)
                row["_set"] = name
                row["_idx"] = str(i)
                row.setdefault("gold_authors", "")
                row.setdefault("gold_publisher_observed", "")
                row.setdefault("institution", row.get("thesis_short", ""))
                rows.append(row)
    return rows


FIELD_SPECS = [
    ("author", lambda r: True),
    ("authors", lambda r: bool(r.get("gold_authors"))),
    ("year", lambda r: True),
    ("title_exact", lambda r: True),
    ("title_fuzzy90", lambda r: True),
    ("type", lambda r: True),
    ("journal_exact", lambda r: bool(r.get("gold_journal"))),
    ("journal_fuzzy90", lambda r: bool(r.get("gold_journal"))),
    ("publisher", lambda r: bool(r.get("gold_publisher"))),
    ("publisher_observed", lambda r: bool(r.get("gold_publisher_observed"))),
    ("doi", lambda r: bool(r.get("gold_doi"))),
]


def field_ok(p: Dict[str, Any], r: Dict[str, str], field: str) -> bool:
    if field == "author":
        return norm(p.get("author")) == norm(r["gold_author"])
    if field == "authors":
        return norm_authors(p.get("authors")) == norm_authors(r.get("gold_authors"))
    if field == "year":
        return str(p.get("year") or "") == r["gold_year"]
    if field == "title_exact":
        return norm(p.get("title")) == norm(r["gold_title"])
    if field == "title_fuzzy90":
        return fuzzy(p.get("title"), r["gold_title"]) >= 0.90
    if field == "journal_exact":
        return norm(p.get("journal")) == norm(r.get("gold_journal"))
    if field == "journal_fuzzy90":
        return fuzzy(p.get("journal"), r.get("gold_journal")) >= 0.90
    if field == "type":
        return str(p.get("publication_type") or "") == r["gold_publication_type"]
    if field == "publisher":
        return norm(p.get("publisher")) == norm(r.get("gold_publisher"))
    if field == "publisher_observed":
        return norm(p.get("publisher_observed")) == norm(r.get("gold_publisher_observed"))
    if field == "doi":
        return norm(p.get("doi")) == norm(r.get("gold_doi"))
    raise KeyError(field)


def metrics(preds: Sequence[Dict[str, Any]], rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for field, eligible in FIELD_SPECS:
        idx = [i for i, r in enumerate(rows) if eligible(r)]
        correct = sum(field_ok(preds[i], rows[i], field) for i in idx)
        out[field] = {
            "n": len(idx),
            "correct": correct,
            "pct": round(100 * correct / len(idx), 2) if idx else None,
        }
    idx = [i for i, r in enumerate(rows) if r.get("gold_journal")]
    covered = sum(bool(norm(preds[i].get("journal"))) for i in idx)
    out["journal_coverage"] = {
        "n": len(idx),
        "covered": covered,
        "pct": round(100 * covered / len(idx), 2) if idx else None,
    }
    return out


def paired(pa: Sequence[Dict[str, Any]], pb: Sequence[Dict[str, Any]],
           rows: Sequence[Dict[str, str]], fields: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    spec = dict(FIELD_SPECS)
    for f in fields:
        idx = [i for i, r in enumerate(rows) if spec[f](r)]
        imp = reg = both = neither = 0
        for i in idx:
            a = field_ok(pa[i], rows[i], f)
            b = field_ok(pb[i], rows[i], f)
            imp += (not a and b)
            reg += (a and not b)
            both += (a and b)
            neither += (not a and not b)
        out[f] = {"n": len(idx), "improved": imp, "regressed": reg,
                  "both_right": both, "both_wrong": neither}
    return out


def run(parser: Callable[[str], Dict[str, Any]], rows: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    return [parser(r["raw_citation"]) for r in rows]
