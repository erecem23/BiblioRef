"""JSON and CSV exporters kept outside the extraction pipeline."""

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional


def write_json(data: Mapping, destination: str | Path) -> Path:
    path = Path(destination)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_csv_rows(rows: Iterable[Mapping], destination: str | Path) -> Optional[Path]:
    materialized = list(rows)
    if not materialized:
        return None
    path = Path(destination)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)
    return path


def write_result_files(
    result: Mapping,
    *,
    json_out: str | Path | None = None,
    csv_out: str | Path | None = None,
    zones_out: str | Path | None = None,
) -> dict[str, Optional[Path]]:
    """Write only the requested formats and report their resulting paths."""
    written: dict[str, Optional[Path]] = {
        "json": None,
        "references_csv": None,
        "zones_csv": None,
    }
    if json_out:
        written["json"] = write_json(result, json_out)
    if csv_out:
        written["references_csv"] = write_csv_rows(result.get("records", []), csv_out)
    if zones_out:
        written["zones_csv"] = write_csv_rows(result.get("zones", []), zones_out)
    return written
