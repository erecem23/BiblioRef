# -*- coding: utf-8 -*-
"""Target-corpus measurement for parser v0.10.

The corpus is the 310-reference export of a Spanish-language education thesis
that was inspected to diagnose the two families v0.10 implements.  It is
development material, not validation: the numbers describe the corpus the
version was written against.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from biblioref.parsing.v09 import parse_reference as p09  # noqa: E402
from biblioref.parsing.v10 import parse_reference as p10  # noqa: E402

src = Path(sys.argv[1])
rows = list(csv.DictReader(src.open(encoding="utf-8-sig", newline="")))
c = Counter()
changed = []
for r in rows:
    t = r.get("text") or ""
    a, b = p09(t), p10(t)
    c["n"] += 1
    c["journal_v09"] += bool(a.get("journal"))
    c["journal_v10"] += bool(b.get("journal"))
    c["publisher_v09"] += bool(a.get("publisher"))
    c["publisher_v10"] += bool(b.get("publisher"))
    c["sin_clasificar_v09"] += a.get("publication_type") == "sin_clasificar"
    c["sin_clasificar_v10"] += b.get("publication_type") == "sin_clasificar"
    if a.get("journal") and b.get("journal") != a.get("journal"):
        c["journal_rewritten"] += 1
    if a.get("publisher") and b.get("publisher") != a.get("publisher"):
        c["publisher_rewritten"] += 1
        changed.append({"order": r.get("order"), "v09_publisher": a.get("publisher"),
                        "v10_publisher": b.get("publisher"), "v10_journal": b.get("journal"),
                        "text": t[:220]})

out = {
    "evaluation": "parser_v0.10_target_corpus",
    "corpus": src.name,
    "n": c["n"],
    "parser_v09_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v09.py").read_bytes()).hexdigest(),
    "parser_v10_sha256": hashlib.sha256((ROOT / "biblioref/parsing/v10.py").read_bytes()).hexdigest(),
    "journal": {"v09": c["journal_v09"], "v10": c["journal_v10"],
                "added": c["journal_v10"] - c["journal_v09"], "rewritten": c["journal_rewritten"]},
    "publisher": {"v09": c["publisher_v09"], "v10": c["publisher_v10"],
                  "rewritten": c["publisher_rewritten"]},
    "sin_clasificar": {"v09": c["sin_clasificar_v09"], "v10": c["sin_clasificar_v10"]},
    "publisher_rewrites": changed,
    "method_note": ("Development corpus. Every rewrite listed above clears a journal-name "
                    "fragment that the previous version had filed as a publisher."),
}
(ROOT / "reports" / "parser" / "PARSER_V0_10_TARGET_EVALUATION.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "publisher_rewrites"},
                 ensure_ascii=False, indent=2))
