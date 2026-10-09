"""Training-row schema for future human-corrected boundary data.

v0.8.3 does not train or apply a statistical model.  This module only provides
an auditable way to convert explicit human labels into a flat dataset later.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Mapping, Sequence

from biblioref.adaptive.scoring import WEIGHTS, collect_boundary_candidates
from biblioref.legacy.engine import AdaptiveLayoutZone


FEATURE_COLUMNS = tuple(WEIGHTS.keys()) + ("margin_delta", "vertical_gap")


def build_boundary_training_rows(
    document_id: str,
    zone: AdaptiveLayoutZone,
    labels: Mapping[int, bool],
    *,
    zone_id: int = 1,
    source: str = "manual_audit",
) -> list[Dict]:
    """Create flat labelled rows for line indices explicitly reviewed by a human."""
    candidates = {int(item["line_index"]): item for item in collect_boundary_candidates(zone)}
    rows: list[Dict] = []
    for line_index, label in sorted((int(key), bool(value)) for key, value in labels.items()):
        candidate = candidates.get(line_index)
        if candidate is None:
            continue
        features = candidate.get("features", {})
        row: Dict = {
            "document_id": str(document_id),
            "zone_id": int(zone_id),
            "line_index": int(line_index),
            "page": int(candidate["page"]),
            "text": candidate["text_preview"],
            "heuristic_score": float(candidate["score"]),
            "heuristic_label": candidate["label"],
            "boundary_label": int(label),
            "source": str(source),
        }
        for column in FEATURE_COLUMNS:
            value = features.get(column)
            if isinstance(value, bool):
                value = int(value)
            row[f"feature_{column}"] = value
        rows.append(row)
    return rows


def write_boundary_training_csv(rows: Sequence[Dict], path: str | Path) -> Path:
    """Write labelled rows without introducing a pandas dependency in the core."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        fieldnames = [
            "document_id", "zone_id", "line_index", "page", "text",
            "heuristic_score", "heuristic_label", "boundary_label", "source",
            *[f"feature_{column}" for column in FEATURE_COLUMNS],
        ]
    else:
        fieldnames = list(rows[0].keys())
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target
