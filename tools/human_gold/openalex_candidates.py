"""Deterministically normalize metadata-only OpenAlex dissertation candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def _required_string(value: dict, field: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item:
        raise ValueError(f"invalid transform config {field}")
    return item


def transform_openalex_snapshot(snapshot: dict, config: dict) -> list[dict]:
    """Return canonical candidates using only fields in an OpenAlex response."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("results"), list):
        raise ValueError("OpenAlex snapshot requires results")
    if not isinstance(config, dict) or config.get("schema_version") != "openalex_candidate_transform_v1":
        raise ValueError("invalid transform config schema_version")
    prefix = _required_string(config, "document_id_prefix")
    metadata_source = _required_string(config, "metadata_source")
    cache_policy = _required_string(config, "cache_policy")
    country_by_tld = config.get("country_by_tld")
    if not isinstance(country_by_tld, dict) or not all(
        isinstance(key, str) and key and isinstance(value, str) and value
        for key, value in country_by_tld.items()
    ):
        raise ValueError("invalid transform config country_by_tld")

    rows = []
    for work in snapshot["results"]:
        if not isinstance(work, dict):
            continue
        location = work.get("primary_location") or {}
        open_access = work.get("open_access") or {}
        pdf_url = location.get("pdf_url")
        source_item_url = location.get("landing_page_url")
        language = work.get("language")
        publication_year = work.get("publication_year")
        openalex_id = work.get("id")
        if not (
            isinstance(pdf_url, str) and pdf_url
            and isinstance(source_item_url, str) and source_item_url
            and isinstance(language, str) and language
            and isinstance(publication_year, int) and not isinstance(publication_year, bool)
            and isinstance(openalex_id, str) and openalex_id
        ):
            continue
        repository = urlsplit(pdf_url).hostname or ""
        tld = repository.rsplit(".", 1)[-1].casefold() if "." in repository else ""
        country = country_by_tld.get(tld)
        if not country:
            continue
        work_id = openalex_id.rstrip("/").rsplit("/", 1)[-1]
        if not work_id:
            continue
        oa_status = open_access.get("oa_status")
        license_value = location.get("license")
        license_note = (
            f"location license={license_value}"
            if isinstance(license_value, str) and license_value
            else "location license unavailable"
        )
        row = {
            "document_id": f"{prefix}{work_id.casefold()}",
            "repository": repository,
            "institution": repository,
            "country": country,
            "language": language,
            "publication_year": publication_year,
            "title": work.get("title") if isinstance(work.get("title"), str) else "",
            "source_item_url": source_item_url,
            "bitstream_url": pdf_url,
            "stable_source_id": openalex_id,
            "openalex_id": openalex_id,
            "openalex_oa_status": oa_status,
            "openalex_location_license": license_value,
            "metadata_source": metadata_source,
            "license_or_access_note": (
                f"OpenAlex OA status={oa_status}; {license_note}; {cache_policy}"
            ),
        }
        source_query = config.get("metadata_source_query")
        snapshot_sha = config.get("metadata_snapshot_sha256")
        work_type = work.get("type")
        if (
            isinstance(source_query, str) and source_query
            and isinstance(snapshot_sha, str) and snapshot_sha
        ):
            if isinstance(work_type, str) and work_type:
                row["metadata_work_type"] = work_type
            row["metadata_source_query"] = source_query
            row["metadata_snapshot_sha256"] = snapshot_sha
        rows.append(row)
    rows.sort(key=lambda row: row["document_id"])
    if len({row["document_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate normalized OpenAlex document_id")
    return rows


def apply_rejections(candidates: list[dict], rejections: list[dict]) -> list[dict]:
    """Remove candidates named by a structured objective-acquisition ledger."""
    if not isinstance(candidates, list) or not isinstance(rejections, list):
        raise ValueError("candidates and rejections must be lists")
    rejected_ids = set()
    for rejection in rejections:
        if not isinstance(rejection, dict):
            raise ValueError("rejection must be an object")
        document_id = rejection.get("document_id")
        reason_code = rejection.get("reason_code")
        evidence = rejection.get("evidence")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("rejection requires document_id")
        if not isinstance(reason_code, str) or not reason_code:
            raise ValueError(f"rejection requires reason_code: {document_id}")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError(f"rejection requires evidence: {document_id}")
        if document_id in rejected_ids:
            raise ValueError(f"duplicate rejection document_id: {document_id}")
        rejected_ids.add(document_id)
    candidate_ids = {row.get("document_id") for row in candidates}
    unknown = rejected_ids - candidate_ids
    if unknown:
        raise ValueError(f"rejection not present in candidates: {sorted(unknown)[0]}")
    return [row for row in candidates if row.get("document_id") not in rejected_ids]


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build metadata-only candidates from OpenAlex.")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--transform-config", type=Path, required=True)
    parser.add_argument("--rejections", type=Path, required=True)
    parser.add_argument("--candidates-output", type=Path, required=True)
    parser.add_argument("--eligible-output", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.snapshot.open(encoding="utf-8") as stream:
        snapshot = json.load(stream)
    with args.transform_config.open(encoding="utf-8") as stream:
        config = json.load(stream)
    candidates = transform_openalex_snapshot(snapshot, config)
    _write_jsonl(args.candidates_output, candidates)
    _write_jsonl(args.eligible_output, apply_rejections(candidates, _load_jsonl(args.rejections)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
