# -*- coding: utf-8 -*-
"""External-holdout harness for parser v0.9.

Usage::

    python3 evaluate_parser_v09_external_holdout.py <gold.csv> [label]

The gold CSV must be frozen and hashed BEFORE this script is executed, and the
parser source must not be modified afterwards.  Required columns:

    raw_citation, gold_author, gold_year, gold_title, gold_publication_type,
    gold_journal, gold_publisher, gold_doi

Optional columns: ``gold_authors`` (complete author block; when absent the
``authors`` field is not scored), ``gold_publisher_observed``, ``thesis_id``,
``institution``, ``source_url``, ``notes``.

The script reports v0.8 and v0.9 side by side plus the paired improvement /
regression counts, writes an evaluation JSON and a per-reference prediction CSV,
and records the SHA-256 of both parser sources and of the gold file, so the
result can be audited against the frozen release.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

from parser_dev_v09_harness import FIELD_SPECS, field_ok, metrics, paired  # noqa: E402
from biblioref.parsing.v08 import parse_reference as parse_v08  # noqa: E402
from biblioref.parsing.v09 import parse_reference as parse_v09  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["author", "authors", "year", "title_fuzzy90", "journal_fuzzy90", "type",
          "publisher", "publisher_observed", "doi"]
REQUIRED = ["raw_citation", "gold_author", "gold_year", "gold_title",
            "gold_publication_type", "gold_journal", "gold_publisher", "gold_doi"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    gold = Path(argv[1]).resolve()
    label = argv[2] if len(argv) > 2 else gold.stem
    rows = list(csv.DictReader(gold.open(encoding="utf-8-sig", newline="")))
    if not rows:
        print(f"empty gold file: {gold}")
        return 1
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        print(f"gold file is missing required columns: {missing}")
        return 1
    for r in rows:
        r.setdefault("gold_authors", "")
        r.setdefault("gold_publisher_observed", "")

    p08 = [parse_v08(r["raw_citation"]) for r in rows]
    p09 = [parse_v09(r["raw_citation"]) for r in rows]

    by_thesis = {}
    if "thesis_id" in rows[0]:
        for tid in sorted({r["thesis_id"] for r in rows}):
            idx = [i for i, r in enumerate(rows) if r["thesis_id"] == tid]
            sub = [rows[i] for i in idx]
            by_thesis[tid] = {"n": len(idx),
                              "v08": metrics([p08[i] for i in idx], sub),
                              "v09": metrics([p09[i] for i in idx], sub)}

    out = {
        "evaluation": f"parser_v0.9_external_holdout::{label}",
        "n": len(rows),
        "gold_file": gold.name,
        "gold_sha256": hashlib.sha256(gold.read_bytes()).hexdigest(),
        "parser_v08_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v08.py").read_bytes()).hexdigest(),
        "parser_v09_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v09.py").read_bytes()).hexdigest(),
        "v08": metrics(p08, rows),
        "v09": metrics(p09, rows),
        "paired": paired(p08, p09, rows, FIELDS),
        "by_thesis": by_thesis,
        "v09_route_count": sum(str(p.get("parse_style") or "").startswith("abnt_v09")
                               or "v09_journal_rescue" in str(p.get("parse_style") or "")
                               for p in p09),
        "method_note": (
            "Valid as external validation only if this gold set was frozen and hashed "
            "before the run and no parser source was modified afterwards. Scores parser "
            "fields from bibliography strings, not PDF section detection or segmentation."
        ),
    }
    stem = f"PARSER_V0_9_EXTERNAL_HOLDOUT_{label.upper()}"
    (ROOT / f"{stem}_EVALUATION.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    base = [c for c in rows[0] if not c.startswith("_")]
    fieldnames = base + ["v08_style", "v09_style", "v08_author", "v09_author",
                         "v08_authors", "v09_authors", "v08_year", "v09_year",
                         "v08_title", "v09_title", "v08_type", "v09_type",
                         "v08_journal", "v09_journal", "v08_publisher", "v09_publisher",
                         "v08_publisher_observed", "v09_publisher_observed",
                         "v08_doi", "v09_doi", "fields_wrong_v09"]
    with (ROOT / f"{stem}_PREDICTIONS.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        specs = dict(FIELD_SPECS)
        for r, a, b in zip(rows, p08, p09):
            wrong = [f for f in FIELDS if specs[f](r) and not field_ok(b, r, f)]
            w.writerow({
                **{k: r.get(k, "") for k in base},
                "v08_style": a.get("parse_style"), "v09_style": b.get("parse_style"),
                "v08_author": a.get("author"), "v09_author": b.get("author"),
                "v08_authors": a.get("authors"), "v09_authors": b.get("authors"),
                "v08_year": a.get("year"), "v09_year": b.get("year"),
                "v08_title": a.get("title"), "v09_title": b.get("title"),
                "v08_type": a.get("publication_type"), "v09_type": b.get("publication_type"),
                "v08_journal": a.get("journal"), "v09_journal": b.get("journal"),
                "v08_publisher": a.get("publisher"), "v09_publisher": b.get("publisher"),
                "v08_publisher_observed": a.get("publisher_observed"),
                "v09_publisher_observed": b.get("publisher_observed"),
                "v08_doi": a.get("doi"), "v09_doi": b.get("doi"),
                "fields_wrong_v09": "|".join(wrong),
            })
    print(json.dumps({
        "n": out["n"],
        "gold_sha256": out["gold_sha256"],
        "parser_v09_sha256": out["parser_v09_sha256"],
        "v08": {k: v["pct"] for k, v in out["v08"].items()},
        "v09": {k: v["pct"] for k, v in out["v09"].items()},
        "paired": {k: (v["improved"], v["regressed"]) for k, v in out["paired"].items()},
    }, ensure_ascii=False, indent=2))
    print(f"\nwrote {stem}_EVALUATION.json and {stem}_PREDICTIONS.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
