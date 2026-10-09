"""Deterministic, metadata-only source selection for the human-gold benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .build_exclusion_registry import is_excluded, normalize_identity


def _required_int(config: dict, field: str) -> int:
    value = config.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid config {field}")
    return value


def _year(row: dict) -> int:
    value = row.get("publication_year", row.get("year"))
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"candidate requires integer publication_year: {row.get('document_id', '')}")
    return value


def _document_id(row: dict) -> str:
    value = row.get("document_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("candidate requires document_id")
    return value


def _stable_order(rows: list[dict], seed: int) -> list[dict]:
    document_ids = [_document_id(row) for row in rows]
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("duplicate candidate document_id")

    def key(row: dict):
        document_id = _document_id(row)
        digest = hashlib.sha256(f"{seed}|{document_id}".encode("utf-8")).hexdigest()
        return digest, document_id

    return sorted(rows, key=key)


def _band_for(year: int, bands: list[dict]) -> str | None:
    for band in bands:
        minimum = band.get("min_year")
        maximum = band.get("max_year")
        if (minimum is None or year >= minimum) and (maximum is None or year <= maximum):
            return band["name"]
    return None


def _validate_primary(primary: list[dict], config: dict, bands: list[dict], max_per_repository: int) -> None:
    if len(primary) != config["primary_n"]:
        raise ValueError("insufficient eligible candidates for primary selection")
    repositories = [row.get("repository") for row in primary]
    if any(not isinstance(value, str) or not value for value in repositories):
        raise ValueError("primary candidates require repository")
    if max(repositories.count(repository) for repository in set(repositories)) > max_per_repository:
        raise ValueError("primary repository cap violated")
    for field, minimum in (("repository", config["min_primary_repositories"]), ("country", config["min_countries"]), ("language", config["min_languages"])):
        values = {row.get(field) for row in primary if isinstance(row.get(field), str) and row[field]}
        if len(values) < minimum:
            raise ValueError(f"primary {field} diversity constraint cannot be satisfied")
    for band in bands:
        count = sum(_band_for(_year(row), bands) == band["name"] for row in primary)
        if count < band["min_n"]:
            raise ValueError(f"primary time band constraint cannot be satisfied: {band['name']}")


def _select_primary(candidates: list[dict], config: dict, bands: list[dict], max_per_repository: int) -> list[dict]:
    selected = []
    selected_ids = set()
    repository_counts = {}
    band_counts = {band["name"]: 0 for band in bands}
    countries = set()
    languages = set()
    repositories = set()
    while len(selected) < config["primary_n"]:
        choices = []
        for index, row in enumerate(candidates):
            document_id = _document_id(row)
            if document_id in selected_ids:
                continue
            repository = row.get("repository")
            if not isinstance(repository, str) or not repository:
                continue
            if repository_counts.get(repository, 0) >= max_per_repository:
                continue
            band_name = _band_for(_year(row), bands)
            time_priority = 1000 if band_name and band_counts[band_name] < next(band["min_n"] for band in bands if band["name"] == band_name) else 0
            repository_priority = 100 if repository not in repositories and len(repositories) < config["min_primary_repositories"] else 0
            country = row.get("country")
            country_priority = 10 if isinstance(country, str) and country and country not in countries and len(countries) < config["min_countries"] else 0
            language = row.get("language")
            language_priority = 1 if isinstance(language, str) and language and language not in languages and len(languages) < config["min_languages"] else 0
            choices.append((time_priority + repository_priority + country_priority + language_priority, -index, row, band_name))
        if not choices:
            break
        _, _, row, band_name = max(choices, key=lambda item: (item[0], item[1]))
        document_id = _document_id(row)
        selected.append(row)
        selected_ids.add(document_id)
        repository = row["repository"]
        repository_counts[repository] = repository_counts.get(repository, 0) + 1
        repositories.add(repository)
        if isinstance(row.get("country"), str) and row["country"]:
            countries.add(row["country"])
        if isinstance(row.get("language"), str) and row["language"]:
            languages.add(row["language"])
        if band_name:
            band_counts[band_name] += 1
    _validate_primary(selected, config, bands, max_per_repository)
    return selected


def _select_stress(stress_candidates: list[dict], config: dict, used_ids: set[str], exclusions: list[dict]) -> list[dict]:
    needed = config["stress_n"]
    if needed == 0:
        return []
    if not isinstance(stress_candidates, list):
        raise ValueError("stress_candidates must be a list")
    for row in stress_candidates:
        labels = row.get("visual_difficulty_labels")
        if not isinstance(labels, list) or not labels or not all(isinstance(label, str) and label.strip() for label in labels):
            raise ValueError("stress candidates require human-curated visual_difficulty_labels")
        _require_exclusion_identity(row)
    ordered = _stable_order([row for row in stress_candidates if not is_excluded(row, exclusions)], config["seed"])
    selected = []
    for row in ordered:
        if _document_id(row) not in used_ids:
            selected.append(row)
            used_ids.add(_document_id(row))
            if len(selected) == needed:
                return selected
    raise ValueError("insufficient separately curated stress candidates")


def _selected_rows(rows: list[dict], partition: str, seed: int, start_rank: int) -> list[dict]:
    result = []
    for offset, row in enumerate(rows):
        selected = dict(row)
        selected["partition"] = partition
        selected["selection_rank"] = start_rank + offset
        selected["selection_seed"] = seed
        selected["selected_before_biblioref_run"] = True
        result.append(selected)
    return result


def _require_exclusion_identity(row: dict) -> None:
    if not isinstance(row, dict):
        raise ValueError("candidate must be an object")
    if not normalize_identity(row):
        raise ValueError(f"candidate requires canonical exclusion-check identity: {row.get('document_id', '')}")


def sample_candidates(candidates: list[dict], config: dict) -> list[dict]:
    """Select pilot, primary, and separately curated stress documents from metadata."""
    if not isinstance(candidates, list) or not isinstance(config, dict):
        raise ValueError("candidates and config must be lists/dictionaries")
    for field in ("seed", "pilot_n", "primary_n", "stress_n", "min_primary_repositories", "min_countries", "min_languages"):
        _required_int(config, field)
    share = config.get("max_primary_share_per_repository")
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
        raise ValueError("invalid config max_primary_share_per_repository")
    bands = config.get("time_bands")
    if not isinstance(bands, list) or not bands:
        raise ValueError("invalid config time_bands")
    if any(not isinstance(band, dict) or not isinstance(band.get("name"), str) or not isinstance(band.get("min_n"), int) for band in bands):
        raise ValueError("invalid config time_bands")
    if len({band["name"] for band in bands}) != len(bands):
        raise ValueError("duplicate time band name")
    if "exclusion_rows" not in config:
        raise ValueError("exclusion_rows is required")
    exclusions = config["exclusion_rows"]
    if not isinstance(exclusions, list):
        raise ValueError("exclusion_rows must be a list")
    for row in candidates:
        _require_exclusion_identity(row)
    eligible = [row for row in candidates if not is_excluded(row, exclusions)]
    ordered = _stable_order(eligible, config["seed"])
    max_per_repository = math.floor(config["primary_n"] * share)
    if max_per_repository < 1 and config["primary_n"]:
        raise ValueError("primary repository cap rounds to zero")
    primary = _select_primary(ordered, config, bands, max_per_repository)
    primary_ids = {_document_id(row) for row in primary}
    pilot = [row for row in ordered if _document_id(row) not in primary_ids][:config["pilot_n"]]
    if len(pilot) != config["pilot_n"]:
        raise ValueError("insufficient eligible candidates for pilot selection")
    used_ids = primary_ids | {_document_id(row) for row in pilot}
    stress = _select_stress(config.get("stress_candidates", []), config, used_ids, exclusions)
    selected = []
    selected.extend(_selected_rows(pilot, "pilot", config["seed"], 1))
    selected.extend(_selected_rows(primary, "primary", config["seed"], len(selected) + 1))
    selected.extend(_selected_rows(stress, "stress", config["seed"], len(selected) + 1))
    return selected


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select leakage-safe human-gold source metadata.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stress-candidates", type=Path)
    parser.add_argument("--exclusions", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.config.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if args.stress_candidates:
        config["stress_candidates"] = _load_jsonl(args.stress_candidates)
    config["exclusion_rows"] = _load_jsonl(args.exclusions)
    _write_jsonl(args.output, sample_candidates(_load_jsonl(args.candidates), config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
