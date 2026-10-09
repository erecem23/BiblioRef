from __future__ import annotations

import hashlib

from tools.human_gold.finalize_sources import choose_partitions


def acquired(i, *, repo, country, language, year):
    body = f"pdf-{i}".encode()
    return {
        "document_id": f"d{i:03d}",
        "repository": repo,
        "institution": repo,
        "country": country,
        "language": language,
        "publication_year": year,
        "title": f"Thesis {i}",
        "source_item_url": f"https://{repo}/items/{i}",
        "bitstream_url": f"https://{repo}/pdf/{i}.pdf",
        "stable_source_id": f"oai:{repo}:{i}",
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "metadata_snapshot_sha256": "a" * 64,
        "selected_before_biblioref_run": True,
        "development_overlap": False,
        "acquisition_accepted": True,
    }


def config():
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
        "time_bands": [
            {"name": "pre_2015", "max_year": 2014, "min_n": 8},
            {"name": "2015_2020", "min_year": 2015, "max_year": 2020, "min_n": 8},
            {"name": "2021_2026", "min_year": 2021, "max_year": 2026, "min_n": 8},
        ],
    }


def pool():
    rows = []
    countries = ["AR", "BR", "GB", "PE"]
    languages = ["es", "pt", "en", "es"]
    years = [2010, 2018, 2024]
    for i in range(48):
        rows.append(acquired(
            i,
            repo=f"repo{i % 12}.example",
            country=countries[i % len(countries)],
            language=languages[i % len(languages)],
            year=years[i % len(years)],
        ))
    return rows


def profiles(rows):
    return {
        row["document_id"]: {
            "page_count": 100 + index * 10,
            "sample_count": 5,
            "landscape_share": 0.0,
            "aspect_ratio_span": 0.0,
            "median_ink_fraction": 0.10,
            "ink_fraction_span": 0.03,
            "two_column_like_share": 0.0,
        }
        for index, row in enumerate(rows)
    }


def test_choose_partitions_selects_stress_first_then_valid_primary():
    rows = pool()
    result = choose_partitions(
        rows,
        profiles(rows),
        selection_config=config(),
        pilot_document_ids={"pilot-a", "pilot-b"},
        exclusions=[],
    )
    manifest = result["manifest"]
    primary = [row for row in manifest if row["partition"] == "primary"]
    stress = [row for row in manifest if row["partition"] == "stress"]
    assert len(primary) == 32
    assert len(stress) == 8
    assert result["stress_selected_first"] is True
    assert all(row["visual_difficulty_labels"] for row in stress)
    assert all(row["selected_before_biblioref_run"] is True for row in manifest)


def test_choose_partitions_deduplicates_pdf_sha_before_selection():
    rows = pool()
    duplicate = dict(rows[-1])
    duplicate["document_id"] = "duplicate-id"
    duplicate["stable_source_id"] = "oai:duplicate"
    rows.append(duplicate)
    result = choose_partitions(
        rows,
        profiles(rows),
        selection_config=config(),
        pilot_document_ids=set(),
        exclusions=[],
    )
    shas = [row["sha256"] for row in result["manifest"]]
    assert len(shas) == len(set(shas))
