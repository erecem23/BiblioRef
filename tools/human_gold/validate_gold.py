"""Command-line validation for the frozen human-gold inputs."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from .schema import load_jsonl, validate_gold, validate_manifest
from .build_exclusion_registry import is_excluded, normalize_identity


def exclusion_sha256(exclusions_path) -> str | None:
    if exclusions_path is None:
        return None
    return hashlib.sha256(Path(exclusions_path).read_bytes()).hexdigest()


def validate_paths(manifest_path, gold_path, exclusions_path=None) -> tuple[list[dict], list[dict]]:
    """Load and fail closed on malformed benchmark manifest or annotations."""
    manifest_rows = load_jsonl(manifest_path)
    gold_rows = load_jsonl(gold_path)
    validate_manifest(manifest_rows)
    validate_gold(manifest_rows, gold_rows)
    exclusions = load_jsonl(exclusions_path) if exclusions_path is not None else []
    for row in manifest_rows:
        if exclusions_path is not None:
            if row.get("development_overlap") is not False:
                raise ValueError(f"development_overlap must be false: {row['document_id']}")
            if not normalize_identity(row):
                raise ValueError(f"candidate requires canonical exclusion-check identity: {row['document_id']}")
        if row.get("development_overlap") is True:
            raise ValueError(f"development exclusion overlap: {row['document_id']}")
        if exclusions:
            # Keep all identity policy in the registry module so the sampler and
            # evaluator cannot drift into different normalization rules.
            if is_excluded(row, exclusions):
                raise ValueError(f"development exclusion overlap: {row['document_id']}")
    return manifest_rows, gold_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate human-gold benchmark JSONL inputs.")
    parser.add_argument("--manifest", required=True, help="Selected-document manifest JSONL")
    parser.add_argument("--gold", required=True, help="Completed human annotations JSONL")
    parser.add_argument("--exclusions", help="Optional development-exclusion registry JSONL")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest_rows, gold_rows = validate_paths(args.manifest, args.gold, args.exclusions)
    except ValueError as exc:
        raise SystemExit(f"human-gold validation failed: {exc}") from exc
    print(f"validated {len(manifest_rows)} manifest documents and {len(gold_rows)} gold documents")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the public CLI
    raise SystemExit(main())
