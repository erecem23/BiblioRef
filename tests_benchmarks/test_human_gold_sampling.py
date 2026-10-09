import json
from collections import Counter

import pytest

from tools.human_gold.build_exclusion_registry import (
    build_exclusion_registry,
    is_excluded,
    normalize_identity,
)
from tools.human_gold.sample_sources import main as sample_sources_main
from tools.human_gold.sample_sources import sample_candidates


def _config(stress_candidates=None):
    return {
        "benchmark_version": "human_gold_v0_1",
        "seed": 20260913,
        "pilot_n": 6,
        "primary_n": 32,
        "stress_n": 8,
        "max_primary_share_per_repository": 0.25,
        "min_primary_repositories": 8,
        "min_countries": 4,
        "min_languages": 3,
        "exclusion_rows": [],
        "time_bands": [
            {"name": "pre_2015", "max_year": 2014, "min_n": 8},
            {"name": "2015_2020", "min_year": 2015, "max_year": 2020, "min_n": 8},
            {"name": "2021_2026", "min_year": 2021, "max_year": 2026, "min_n": 8},
        ],
        "stress_candidates": stress_candidates or [],
    }


def _candidate(index, repository, year):
    return {
        "document_id": f"candidate-{index:03d}",
        "repository": repository,
        "country": ("AR", "BR", "US", "PT", "MX")[index % 5],
        "language": ("es", "pt", "en")[index % 3],
        "publication_year": year,
        "source_item_url": f"https://repository.example/{repository}/{index}",
        "stable_source_id": f"hdl:{repository}/{index}",
    }


def _stress_candidate(index):
    row = _candidate(200 + index, f"stress-repo-{index}", 2024)
    row["visual_difficulty_labels"] = ["two-column", "page-spanning"]
    return row


def test_exact_sha_is_excluded():
    candidate = {"sha256": "a" * 64}
    exclusions = [{"sha256": "a" * 64, "reason": "SEDICI-10"}]
    assert is_excluded(candidate, exclusions)


def test_provenance_snapshot_sha_does_not_create_document_identity():
    snapshot_sha = "a" * 64
    candidate = {
        "stable_source_id": "hdl:candidate/1",
        "metadata_snapshot_sha256": snapshot_sha,
    }
    other_document = {
        "stable_source_id": "hdl:other/2",
        "metadata_snapshot_sha256": snapshot_sha,
    }

    assert f"sha256:{snapshot_sha}" not in normalize_identity(candidate)
    assert not is_excluded(candidate, [other_document])


def test_stable_url_is_normalized_before_exclusion_matching():
    candidate = {"source_item_url": "HTTPS://Repository.EXAMPLE/item/42/?utm_source=mail#record"}
    exclusions = [{"identity_type": "stable_url", "identity": "https://repository.example/item/42"}]
    assert is_excluded(candidate, exclusions)


def test_stable_identifier_is_excluded():
    candidate = {"stable_source_id": "  HDL:12345/ABC  "}
    exclusions = [{"identity_type": "stable_id", "identity": "hdl:12345/abc"}]
    assert is_excluded(candidate, exclusions)


def test_title_institution_year_fallback_is_normalized_before_matching():
    candidate = {
        "title": "  Análise  de  Dados: uma revisão ",
        "institution": "Universidade de São Paulo",
        "publication_year": 2020,
    }
    exclusions = [{
        "identity_type": "title_institution_year",
        "identity": "analise de dados uma revisao|universidade de sao paulo|2020",
    }]
    assert is_excluded(candidate, exclusions)
    assert "title_institution_year:analise de dados uma revisao|universidade de sao paulo|2020" in normalize_identity(candidate)


def test_registry_builder_collects_machine_rows_and_checked_in_manual_supplement(tmp_path):
    (tmp_path / "benchmarks" / "evidence").mkdir(parents=True)
    (tmp_path / "benchmarks" / "development.jsonl").write_text(
        json.dumps({"sha256": "b" * 64}) + "\n", encoding="utf-8"
    )
    (tmp_path / "benchmarks" / "migration.csv").write_text(
        "source_item_url\nhttps://repository.example/migration/1\n", encoding="utf-8"
    )
    (tmp_path / "benchmarks" / "evidence" / "challenge.json").write_text(
        json.dumps({"stable_source_id": "hdl:challenge/1"}), encoding="utf-8"
    )
    (tmp_path / "benchmarks" / "evidence" / "SHA256SUMS.txt").write_text(
        ("d" * 64) + "  known-development.pdf\n", encoding="utf-8"
    )
    (tmp_path / "CURRENT_FIELD_TEST_STATE.json").write_text(
        json.dumps({"title": "Known Case", "institution": "Example U", "publication_year": 2019}),
        encoding="utf-8",
    )
    manual = tmp_path / "manual.json"
    manual.write_text(json.dumps([{"sha256": "c" * 64, "reason": "report-only development PDF"}]), encoding="utf-8")

    registry = build_exclusion_registry(tmp_path, manual_supplement=manual)

    assert {row["identity_type"] for row in registry} >= {
        "sha256", "stable_url", "stable_id", "title_institution_year"
    }
    assert all(set(row) >= {"identity_type", "identity", "source_file", "reason"} for row in registry)
    assert is_excluded({"sha256": "c" * 64}, registry)
    assert is_excluded({"sha256": "d" * 64}, registry)


def test_registry_builder_classifies_field_test_manifests_by_relative_path(tmp_path):
    manifest = tmp_path / "field_test_examples" / "UNC_FERREYRA_V099_EXTERNAL_CASE.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"sha256": "f" * 64}), encoding="utf-8")

    registry = build_exclusion_registry(tmp_path)

    assert is_excluded({"sha256": "f" * 64}, registry)


def test_registry_builder_ignores_current_human_gold_selection_artifacts(tmp_path):
    current = tmp_path / "benchmarks" / "human_gold_v0_1" / "pilot" / "candidates.jsonl"
    current.parent.mkdir(parents=True)
    current.write_text(
        json.dumps({"stable_source_id": "openalex:future-primary"}) + "\n",
        encoding="utf-8",
    )
    historical = tmp_path / "benchmarks" / "development.jsonl"
    historical.write_text(
        json.dumps({"stable_source_id": "hdl:historical/development"}) + "\n",
        encoding="utf-8",
    )

    registry = build_exclusion_registry(tmp_path)

    assert not is_excluded({"stable_source_id": "openalex:future-primary"}, registry)
    assert is_excluded({"stable_source_id": "hdl:historical/development"}, registry)


def test_sampling_is_deterministic_and_enforces_primary_constraints():
    candidates = []
    years = (2012, 2017, 2023, 2019)
    repository_sizes = (44,) + (4,) * 9
    index = 0
    for repository_index, size in enumerate(repository_sizes):
        for offset in range(size):
            candidates.append(_candidate(index, f"repo-{repository_index}", years[offset % len(years)]))
            index += 1
    config = _config([_stress_candidate(index) for index in range(8)])

    sample_a = sample_candidates(candidates, config)
    sample_b = sample_candidates(list(reversed(candidates)), config)
    primary = [row for row in sample_a if row["partition"] == "primary"]

    assert [row["document_id"] for row in sample_a] == [row["document_id"] for row in sample_b]
    assert len(primary) == 32
    assert len([row for row in sample_a if row["partition"] == "pilot"]) == 6
    assert len([row for row in sample_a if row["partition"] == "stress"]) == 8
    assert max(Counter(row["repository"] for row in primary).values()) <= 8
    uncapped_config = dict(config)
    uncapped_config["max_primary_share_per_repository"] = 1
    uncapped_primary = [row for row in sample_candidates(candidates, uncapped_config) if row["partition"] == "primary"]
    assert max(Counter(row["repository"] for row in uncapped_primary).values()) > 8
    assert len({row["repository"] for row in primary}) >= 8
    assert len({row["country"] for row in primary}) >= 4
    assert len({row["language"] for row in primary}) >= 3
    assert sum(row["publication_year"] <= 2014 for row in primary) >= 8
    assert sum(2015 <= row["publication_year"] <= 2020 for row in primary) >= 8
    assert sum(2021 <= row["publication_year"] <= 2026 for row in primary) >= 8
    assert all(row["selection_seed"] == 20260913 for row in sample_a)
    assert all(row["selected_before_biblioref_run"] is True for row in sample_a)
    assert [row["selection_rank"] for row in sample_a] == list(range(1, 47))


def test_stress_candidates_require_human_curated_visual_difficulty_labels():
    candidates = [_candidate(index, f"repo-{index % 10}", (2012, 2017, 2023)[index % 3]) for index in range(80)]
    stress = [_candidate(200 + index, f"stress-{index}", 2024) for index in range(8)]

    try:
        sample_candidates(candidates, _config(stress))
    except ValueError as exc:
        assert "visual_difficulty_labels" in str(exc)
    else:
        raise AssertionError("stress selections without human-curated labels must be rejected")


def test_stress_candidates_are_filtered_by_the_mandatory_exclusion_registry():
    candidates = [_candidate(index, f"repo-{index % 10}", (2012, 2017, 2023)[index % 3]) for index in range(80)]
    stress = [_stress_candidate(index) for index in range(9)]
    stress[0]["sha256"] = "e" * 64
    config = _config(stress)
    config["exclusion_rows"] = [{"sha256": "e" * 64}]

    selected = sample_candidates(candidates, config)

    assert "candidate-200" not in {row["document_id"] for row in selected}
    assert len([row for row in selected if row["partition"] == "stress"]) == 8


def test_sampling_requires_an_explicit_exclusion_registry_and_candidate_identity():
    config = _config()
    config.pop("exclusion_rows")
    with pytest.raises(ValueError, match="exclusion_rows is required"):
        sample_candidates([], config)

    with pytest.raises(ValueError, match="canonical exclusion-check identity: opaque"):
        sample_candidates([{"document_id": "opaque"}], _config())


def test_stress_candidates_require_a_canonical_exclusion_check_identity():
    candidates = [_candidate(index, f"repo-{index % 10}", (2012, 2017, 2023)[index % 3]) for index in range(80)]
    stress = [{"document_id": "opaque-stress", "visual_difficulty_labels": ["two-column"]}]

    with pytest.raises(ValueError, match="canonical exclusion-check identity: opaque-stress"):
        sample_candidates(candidates, _config(stress))


def test_sampler_cli_requires_an_exclusion_registry(tmp_path):
    candidates_path = tmp_path / "candidates.jsonl"
    config_path = tmp_path / "config.json"
    candidates_path.write_text("", encoding="utf-8")
    config_path.write_text(json.dumps(_config()), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        sample_sources_main([
            "--candidates", str(candidates_path),
            "--config", str(config_path),
            "--output", str(tmp_path / "selected.jsonl"),
        ])

    assert exc.value.code == 2
