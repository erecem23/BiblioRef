# -*- coding: utf-8 -*-
"""Development/regression evaluation of parser v0.9.

The 190 references are every gold set already consumed by parser holdouts up to
v0.8.  They are development and regression material for v0.9 and carry no claim
of external validity.  External validation requires a gold set frozen before
v0.9 is executed; use ``evaluate_parser_v09_external_holdout.py`` for that.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

from parser_dev_v09_harness import DEV_SETS, load_dev_rows, metrics, paired, run  # noqa: E402
from biblioref.parsing.v09 import parse_reference as parse_v08  # noqa: E402
from biblioref.parsing.v10 import parse_reference as parse_v09  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["author", "authors", "year", "title_fuzzy90", "journal_fuzzy90", "type",
          "publisher", "publisher_observed", "doi"]

rows = load_dev_rows()
p08 = run(parse_v08, rows)
p09 = run(parse_v09, rows)

by_set = {}
for name, _ in DEV_SETS:
    idx = [i for i, r in enumerate(rows) if r["_set"] == name]
    sub = [rows[i] for i in idx]
    by_set[name] = {
        "n": len(idx),
        "v09": metrics([p08[i] for i in idx], sub),
        "v10": metrics([p09[i] for i in idx], sub),
    }

out = {
    "evaluation": "parser_v0.10_development_regression",
    "n": len(rows),
    "sets": {name: str(path.relative_to(ROOT)) for name, path in DEV_SETS},
    "parser_v09_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v09.py").read_bytes()).hexdigest(),
    "parser_v10_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v10.py").read_bytes()).hexdigest(),
    "v09": metrics(p08, rows),
    "v10": metrics(p09, rows),
    "paired": paired(p08, p09, rows, FIELDS),
    "by_set": by_set,
    "method_note": (
        "Development/regression only. Every gold set here was opened before v0.9 was "
        "written, so these numbers describe the corpus v0.9 was developed against and "
        "must not be reported as external validation."
    ),
}
(ROOT / "reports" / "parser" / "PARSER_V0_10_DEVELOPMENT_EVALUATION.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

fieldnames = ["_set", "_idx", "raw_citation", "gold_author", "gold_authors", "gold_year",
              "gold_title", "gold_publication_type", "gold_journal", "gold_publisher",
              "gold_publisher_observed", "gold_doi", "v10_style", "v10_style",
              "v09_author", "v09_author", "v09_authors", "v09_authors",
              "v09_title", "v09_title", "v09_journal", "v09_journal",
              "v09_type", "v09_type", "v09_publisher", "v09_publisher"]
with (ROOT / "PARSER_V0_10_DEVELOPMENT_PREDICTIONS.csv").open(
        "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fieldnames)
    w.writeheader()
    for r, a, b in zip(rows, p08, p09):
        w.writerow({
            **{k: r.get(k, "") for k in fieldnames if k in r},
            "v10_style": a.get("parse_style"), "v10_style": b.get("parse_style"),
            "v09_author": a.get("author"), "v09_author": b.get("author"),
            "v09_authors": a.get("authors"), "v09_authors": b.get("authors"),
            "v09_title": a.get("title"), "v09_title": b.get("title"),
            "v09_journal": a.get("journal"), "v09_journal": b.get("journal"),
            "v09_type": a.get("publication_type"), "v09_type": b.get("publication_type"),
            "v09_publisher": a.get("publisher"), "v09_publisher": b.get("publisher"),
        })
print(json.dumps({"n": out["n"], "v09": {k: v["pct"] for k, v in out["v09"].items()},
                  "v10": {k: v["pct"] for k, v in out["v10"].items()},
                  "paired": {k: (v["improved"], v["regressed"]) for k, v in out["paired"].items()}},
                 ensure_ascii=False, indent=2))
