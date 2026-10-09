"""Deterministic source-freeze helpers for human-gold v0.1."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

_REQUIRED_MANIFEST_FIELDS = (
    "document_id", "repository", "country", "language", "publication_year",
    "source_item_url", "bitstream_url", "stable_source_id", "sha256", "bytes",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pinned_snapshot(path: Path, expected_sha256: str):
    path = Path(path)
    actual = sha256_file(path)
    if actual != expected_sha256.casefold():
        raise ValueError(f"metadata snapshot SHA-256 mismatch: {path}")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def next_expansion_query(protocol: dict, completed_rounds: list[int], accepted_count: int | None = None) -> dict | None:
    target = protocol.get("target_nonpilot", 40)
    if accepted_count is not None and accepted_count >= target:
        return None
    completed = set(completed_rounds)
    expansions = protocol.get("expansions", [])
    if not isinstance(expansions, list):
        raise ValueError("protocol expansions must be a list")
    pending = [row for row in expansions if isinstance(row, dict) and row.get("round") not in completed]
    if not pending:
        return None
    return min(pending, key=lambda row: row["round"])


def append_acquisition_round(history: list[dict], row: dict) -> None:
    if not isinstance(history, list) or not isinstance(row, dict):
        raise ValueError("invalid acquisition round")
    round_no = row.get("round")
    if isinstance(round_no, bool) or not isinstance(round_no, int) or round_no < 1:
        raise ValueError("acquisition round must be positive")
    if history and round_no <= history[-1].get("round", 0):
        raise ValueError("acquisition round must increase")
    history.append(dict(row))


def _validate_acquired(row: dict) -> None:
    document_id = row.get("document_id", "")
    for field in _REQUIRED_MANIFEST_FIELDS:
        value = row.get(field)
        if value is None or value == "":
            raise ValueError(f"acquired candidate missing {field}: {document_id}")
    if row.get("acquisition_accepted") is not True:
        raise ValueError(f"candidate not acquisition-accepted: {document_id}")
    if row.get("development_overlap") is True:
        raise ValueError(f"development overlap: {document_id}")
    if row.get("selected_before_biblioref_run") is not True:
        raise ValueError(f"selected_before_biblioref_run must be true: {document_id}")
    sha = row.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        raise ValueError(f"invalid sha256: {document_id}")
    snapshot_sha = row.get("metadata_snapshot_sha256")
    if not isinstance(snapshot_sha, str) or len(snapshot_sha) != 64:
        raise ValueError(f"missing pinned metadata snapshot: {document_id}")


def verify_frozen_composition(primary_rows: list[dict]) -> dict:
    if len(primary_rows) != 32:
        raise ValueError(f"primary must contain exactly 32 documents: {len(primary_rows)}")
    for row in primary_rows:
        _validate_acquired(row)
    shas = [row["sha256"].casefold() for row in primary_rows]
    if len(shas) != len(set(shas)):
        raise ValueError("duplicate sha256 in primary")
    repos = Counter(row["repository"] for row in primary_rows)
    max_per_repo = max(repos.values())
    if max_per_repo > 8:
        raise ValueError("primary repository cap violated")
    if len(repos) < 8:
        raise ValueError("primary repositories constraint violated")
    countries = {row["country"] for row in primary_rows}
    languages = {row["language"] for row in primary_rows}
    if len(countries) < 4:
        raise ValueError("primary countries constraint violated")
    if len(languages) < 3:
        raise ValueError("primary languages constraint violated")
    pre = sum(row["publication_year"] <= 2014 for row in primary_rows)
    middle = sum(2015 <= row["publication_year"] <= 2020 for row in primary_rows)
    recent = sum(2021 <= row["publication_year"] <= 2026 for row in primary_rows)
    for name, count in (("pre_2015", pre), ("2015_2020", middle), ("2021_2026", recent)):
        if count < 8:
            raise ValueError(f"primary time band constraint violated: {name}")
    return {
        "primary_n": 32,
        "repositories": len(repos),
        "max_per_repository": max_per_repo,
        "countries": len(countries),
        "languages": len(languages),
        "time_bands": {"pre_2015": pre, "2015_2020": middle, "2021_2026": recent},
    }


def _manifest_row(row: dict, partition: str, rank: int, selection_seed: int) -> dict:
    _validate_acquired(row)
    result = dict(row)
    result.pop("cache_path", None)
    result.pop("rounds", None)
    if isinstance(result.get("resolved_bitstream_url"), str) and result["resolved_bitstream_url"]:
        result["bitstream_url"] = result["resolved_bitstream_url"]
    result["partition"] = partition
    result["selection_rank"] = rank
    result["selection_seed"] = selection_seed
    result["selected_before_biblioref_run"] = True
    if "pre_output_eligibility" not in result:
        result["pre_output_eligibility"] = {"eligible": True, "reason_code": None}
    return result


def freeze_source_manifest(primary_rows: list[dict], stress_rows: list[dict], *, pilot_document_ids: set[str], selection_seed: int) -> list[dict]:
    verify_frozen_composition(primary_rows)
    if len(stress_rows) != 8:
        raise ValueError(f"stress must contain exactly 8 documents: {len(stress_rows)}")
    all_rows = list(primary_rows) + list(stress_rows)
    ids = [row.get("document_id") for row in all_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate document_id in source freeze")
    if set(ids) & set(pilot_document_ids):
        raise ValueError("pilot document reserved from primary/stress freeze")
    all_shas = [row.get("sha256", "").casefold() for row in all_rows]
    if len(all_shas) != len(set(all_shas)):
        raise ValueError("duplicate sha256 in source freeze")
    for row in stress_rows:
        _validate_acquired(row)
        labels = row.get("visual_difficulty_labels")
        if not isinstance(labels, list) or not labels or not all(isinstance(item, str) and item.strip() for item in labels):
            raise ValueError("stress candidate requires visual_difficulty_labels")
    manifest = []
    for row in primary_rows:
        manifest.append(_manifest_row(row, "primary", len(manifest) + 1, selection_seed))
    for row in stress_rows:
        manifest.append(_manifest_row(row, "stress", len(manifest) + 1, selection_seed))
    return manifest


def write_sha256sums(root: Path, files: list[Path], output: Path) -> None:
    root = Path(root).resolve()
    entries = []
    for file_path in files:
        path = Path(file_path).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"hash file outside root: {path}") from exc
        entries.append((relative, sha256_file(path)))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for relative, digest in sorted(entries):
            stream.write(f"{digest}  {relative}\n")


def _load_jsonl(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the 32 primary + 8 stress source manifest.")
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--stress", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selection-seed", type=int, default=20260913)
    args = parser.parse_args(argv)
    pilot_ids = {row["document_id"] for row in _load_jsonl(args.pilot_manifest)}
    manifest = freeze_source_manifest(
        _load_jsonl(args.primary),
        _load_jsonl(args.stress),
        pilot_document_ids=pilot_ids,
        selection_seed=args.selection_seed,
    )
    _write_jsonl(args.output, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
