"""Build and query a provenance-only development-exclusion registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_DOCUMENT_SHA256_FIELDS = frozenset({"sha256", "document_sha256", "pdf_sha256"})
_IDENTIFIER_FIELDS = (
    "stable_source_id",
    "stable_id",
    "identifier",
    "doi",
    "handle",
    "oai_id",
    "repository_item_id",
)
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _normalise_text(value: object) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", text)).strip(" _")


def _normalise_identifier(value: object) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    return re.sub(r"\s+", "", str(value)).casefold()


def _normalise_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, urlencode(sorted(query)), ""))


def _title_institution_year(row: dict) -> str:
    title = _normalise_text(row.get("title", row.get("document_title")))
    institution = _normalise_text(row.get("institution", row.get("university")))
    year = row.get("publication_year", row.get("year"))
    if isinstance(year, bool) or not isinstance(year, (str, int)):
        return ""
    normalized_year = str(year).strip()
    if not title or not institution or not normalized_year:
        return ""
    return f"{title}|{institution}|{normalized_year}"


def _identities_from_typed_identity(identity_type: object, identity: object) -> set[str]:
    if not isinstance(identity_type, str):
        return set()
    normalized_type = identity_type.casefold().replace("-", "_")
    if normalized_type == "sha256" and isinstance(identity, str) and _SHA256.fullmatch(identity):
        return {f"sha256:{identity.casefold()}"}
    if normalized_type in {"stable_url", "url"}:
        normalized = _normalise_url(identity)
        return {f"stable_url:{normalized}"} if normalized else set()
    if normalized_type in {"stable_id", "identifier", "id"}:
        normalized = _normalise_identifier(identity)
        return {f"stable_id:{normalized}"} if normalized else set()
    if normalized_type in {"title_institution_year", "title_institution_year_fallback"} and isinstance(identity, str):
        title, separator, remainder = identity.partition("|")
        institution, separator2, year = remainder.partition("|")
        if separator and separator2:
            normalized = _title_institution_year({
                "title": title,
                "institution": institution,
                "publication_year": year,
            })
            return {f"title_institution_year:{normalized}"} if normalized else set()
    return set()


def normalize_identity(row: dict) -> set[str]:
    """Return canonical, type-prefixed identities present in metadata *row*."""
    if not isinstance(row, dict):
        return set()
    identities = _identities_from_typed_identity(row.get("identity_type"), row.get("identity"))
    for key, value in row.items():
        if key.casefold() in _DOCUMENT_SHA256_FIELDS and isinstance(value, str) and _SHA256.fullmatch(value):
            identities.add(f"sha256:{value.casefold()}")
        if key.casefold().endswith("url") or key.casefold() in {"url", "uri"}:
            normalized_url = _normalise_url(value)
            if normalized_url:
                identities.add(f"stable_url:{normalized_url}")
    for field in _IDENTIFIER_FIELDS:
        normalized_id = _normalise_identifier(row.get(field))
        if normalized_id:
            identities.add(f"stable_id:{normalized_id}")
    fallback = _title_institution_year(row)
    if fallback:
        identities.add(f"title_institution_year:{fallback}")
    return identities


def is_excluded(candidate: dict, exclusion_rows: list[dict]) -> bool:
    """Whether any canonical candidate identity occurs in the registry."""
    candidate_identities = normalize_identity(candidate)
    if not candidate_identities:
        return False
    exclusion_identities = set()
    for row in exclusion_rows:
        exclusion_identities.update(normalize_identity(row))
    return bool(candidate_identities & exclusion_identities)


def _registry_entries(row: dict, source_file: str, reason: str) -> list[dict]:
    entries = []
    for identity in normalize_identity(row):
        identity_type, value = identity.split(":", 1)
        entries.append({
            "identity_type": identity_type,
            "identity": value,
            "source_file": source_file,
            "reason": row.get("reason") if isinstance(row.get("reason"), str) and row["reason"].strip() else reason,
        })
    return entries


def _walk_records(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_records(child)


def _read_records(path: Path):
    try:
        if path.suffix.casefold() == ".txt":
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    match = re.match(r"\s*([0-9a-fA-F]{64})(?:\s|$)", line)
                    if match:
                        yield {"sha256": match.group(1)}
            return
        if path.suffix.casefold() == ".csv":
            with path.open(encoding="utf-8", newline="") as stream:
                yield from csv.DictReader(stream)
            return
        if path.suffix.casefold() == ".jsonl":
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        yield from _walk_records(json.loads(line))
            return
        with path.open(encoding="utf-8") as stream:
            yield from _walk_records(json.load(stream))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, csv.Error):
        return


def _candidate_source_files(root: Path, manual_supplement: Path | None) -> list[Path]:
    benchmark_root = root / "benchmarks"
    current_human_gold_root = benchmark_root / "human_gold_v0_1"
    files = set()
    if benchmark_root.exists():
        files.update(path for path in benchmark_root.rglob("*") if path.suffix.casefold() in {".json", ".jsonl", ".csv"})
        evidence_root = benchmark_root / "evidence"
        if evidence_root.exists():
            files.update(path for path in evidence_root.rglob("*") if path.suffix.casefold() == ".txt")
    field_state = root / "CURRENT_FIELD_TEST_STATE.json"
    if field_state.exists():
        files.add(field_state)
    known_names = re.compile(r"(challenge|development|migration|holdout|regression|field[_-]?test)", re.I)
    for path in root.rglob("*"):
        if path.suffix.casefold() in {".json", ".jsonl", ".csv"} and known_names.search(_source_name(root, path)):
            files.add(path)
    files = {path for path in files if current_human_gold_root not in path.parents}
    if manual_supplement:
        files.discard(manual_supplement)
    return sorted(files)


def _source_name(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_exclusion_registry(root: Path, manual_supplement: Path | None = None) -> list[dict]:
    """Collect documented development identities without inspecting extractor output."""
    root = Path(root)
    if manual_supplement is None:
        manual_supplement = root / "benchmarks" / "human_gold_v0_1" / "exclusion_manual_supplement.json"
    manual_supplement = Path(manual_supplement)
    entries = []
    for path in _candidate_source_files(root, manual_supplement):
        source_file = _source_name(root, path)
        reason = f"known development/evaluation artifact: {source_file}"
        for record in _read_records(path):
            entries.extend(_registry_entries(record, source_file, reason))
    if manual_supplement.exists():
        source_file = _source_name(root, manual_supplement)
        for record in _read_records(manual_supplement):
            entries.extend(_registry_entries(record, source_file, "documented report-only development PDF"))
    unique = {}
    for row in entries:
        key = (row["identity_type"], row["identity"])
        if key not in unique or (row["source_file"], row["reason"]) < (unique[key]["source_file"], unique[key]["reason"]):
            unique[key] = row
    return [unique[key] for key in sorted(unique)]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the human-gold development exclusion registry.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manual-supplement", type=Path)
    args = parser.parse_args(argv)
    _write_jsonl(args.output, build_exclusion_registry(args.root, args.manual_supplement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
