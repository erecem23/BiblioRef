# -*- coding: utf-8 -*-
"""Structural non-regression sweep of parser v0.9 over the historical corpus.

The 29,027-row analytic corpus is development material, not a holdout.  Its
``gold_author`` column follows a different author convention and is not used to
score; ``target_journal``, ``target_publisher_v2`` and ``target_type_v2`` are
used only to say whether the rows that v0.9 changes move towards or away from
the curated labels.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

from parser_dev_v09_harness import norm  # noqa: E402
from biblioref.parsing.v09 import parse_reference as parse_v08  # noqa: E402
from biblioref.parsing.v10 import parse_reference as parse_v09  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "PARSER_V0_2_DIFFERENTIAL_29470.csv"
FIELDS = ["author", "authors", "year", "title", "journal", "publication_type",
          "publisher", "publisher_observed", "doi"]

rows = list(csv.DictReader(CORPUS.open(encoding="utf-8-sig", newline="")))
changed = Counter()
route = Counter()
journal_added = journal_removed = journal_modified = 0
label_journal = {"better": 0, "worse": 0, "neutral": 0}
label_type = {"better": 0, "worse": 0, "neutral": 0}
changed_rows = []

for r in rows:
    text = r["raw_citation"]
    a = parse_v08(text)
    b = parse_v09(text)
    route[str(b.get("parse_style"))] += 1
    diff = [f for f in FIELDS if norm(a.get(f)) != norm(b.get(f))]
    if not diff:
        continue
    for f in diff:
        changed[f] += 1
    if "journal" in diff:
        if not a.get("journal") and b.get("journal"):
            journal_added += 1
        elif a.get("journal") and not b.get("journal"):
            journal_removed += 1
        else:
            journal_modified += 1
        tgt = norm(r.get("target_journal"))
        if tgt:
            oa, ob = norm(a.get("journal")) == tgt, norm(b.get("journal")) == tgt
            label_journal["better" if (ob and not oa) else "worse" if (oa and not ob) else "neutral"] += 1
    if "publication_type" in diff:
        tgt = r.get("target_type_v2") or ""
        if tgt:
            oa = str(a.get("publication_type") or "") == tgt
            ob = str(b.get("publication_type") or "") == tgt
            label_type["better" if (ob and not oa) else "worse" if (oa and not ob) else "neutral"] += 1
    changed_rows.append({
        "ref_uid": r["ref_uid"], "changed": "|".join(diff),
        "raw_citation": text,
        "v08_style": a.get("parse_style"), "v09_style": b.get("parse_style"),
        **{f"v08_{f}": a.get(f) for f in FIELDS},
        **{f"v09_{f}": b.get(f) for f in FIELDS},
        "target_journal": r.get("target_journal", ""),
        "target_type_v2": r.get("target_type_v2", ""),
        "target_publisher_v2": r.get("target_publisher_v2", ""),
    })

out = {
    "sweep": "parser_v0.10_vs_v0.9_historical_structural",
    "corpus": CORPUS.name,
    "n_rows": len(rows),
    "n_rows_changed": len(changed_rows),
    "pct_rows_changed": round(100 * len(changed_rows) / len(rows), 3),
    "changed_by_field": dict(changed),
    "journal_delta": {"added": journal_added, "removed": journal_removed,
                      "modified": journal_modified},
    "labelled_journal_moves": label_journal,
    "labelled_type_moves": label_type,
    "v09_route_counts": {k: v for k, v in route.most_common(12)},
    "parser_v10_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v10.py").read_bytes()).hexdigest(),
    "parser_v09_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v09.py").read_bytes()).hexdigest(),
    "note": "Development corpus. Labels are used only to orient the changed rows, never as a holdout estimate.",
}
(ROOT / "reports" / "parser" / "PARSER_V0_10_HISTORICAL_SWEEP.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
if changed_rows:
    with (ROOT / "PARSER_V0_10_HISTORICAL_CHANGED_ROWS.csv").open(
            "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(changed_rows[0].keys()))
        w.writeheader()
        w.writerows(changed_rows)
print(json.dumps(out, ensure_ascii=False, indent=2))
