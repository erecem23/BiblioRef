from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.human_gold.freeze_sources import (
    append_acquisition_round,
    freeze_source_manifest,
    load_pinned_snapshot,
    next_expansion_query,
    verify_frozen_composition,
    write_sha256sums,
)


def acquired(i, *, partition=None, repo=None, country="AR", language="es", year=2010, labels=None):
    body = f"pdf-{i}".encode()
    row = {
        "document_id": f"d{i:03d}",
        "repository": repo or f"repo{i % 10}.example",
        "country": country,
        "language": language,
        "publication_year": year,
        "title": f"Thesis {i}",
        "source_item_url": f"https://repo.example/items/{i}",
        "bitstream_url": f"https://repo.example/pdf/{i}",
        "stable_source_id": f"oai:{i}",
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "metadata_snapshot_sha256": "a" * 64,
        "selected_before_biblioref_run": True,
        "development_overlap": False,
        "acquisition_accepted": True,
    }
    if partition:
        row["partition"] = partition
    if labels:
        row["visual_difficulty_labels"] = labels
    return row


def primary_rows():
    rows = []
    years = [2010] * 8 + [2018] * 8 + [2024] * 8 + [2012, 2016, 2022, 2014, 2020, 2025, 2013, 2019]
    langs = ["es", "pt", "en", "es"] * 8
    countries = ["AR", "BR", "GB", "PE"] * 8
    for i in range(32):
        rows.append(acquired(i, repo=f"repo{i % 8}.example", country=countries[i], language=langs[i], year=years[i]))
    return rows


def test_pinned_snapshot_hash_is_required(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text('{"results": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="metadata snapshot SHA-256 mismatch"):
        load_pinned_snapshot(path, "0" * 64)


def test_freeze_requires_exact_32_primary_8_stress_and_reserves_pilot():
    primary = primary_rows()
    stress = [acquired(100 + i, repo=f"stress{i}.example", country="CA", language="en", year=2021, labels=["two_column"]) for i in range(8)]
    pilot_ids = {"pilot-a", "pilot-b"}
    manifest = freeze_source_manifest(primary, stress, pilot_document_ids=pilot_ids, selection_seed=20260913)
    assert len([r for r in manifest if r["partition"] == "primary"]) == 32
    assert len([r for r in manifest if r["partition"] == "stress"]) == 8
    assert not ({r["document_id"] for r in manifest} & pilot_ids)
    assert all(r["selected_before_biblioref_run"] is True for r in manifest)


def test_stress_requires_visual_labels():
    with pytest.raises(ValueError, match="stress candidate requires visual_difficulty_labels"):
        freeze_source_manifest(primary_rows(), [acquired(100 + i) for i in range(8)], pilot_document_ids=set(), selection_seed=20260913)


def test_primary_composition_constraints_are_verified():
    summary = verify_frozen_composition(primary_rows())
    assert summary["primary_n"] == 32
    assert summary["max_per_repository"] == 4
    assert summary["repositories"] == 8
    assert summary["countries"] >= 4
    assert summary["languages"] >= 3
    assert summary["time_bands"] == {"pre_2015": 11, "2015_2020": 11, "2021_2026": 10}


def test_primary_requires_eight_repositories_at_final_freeze():
    rows = primary_rows()
    for i, row in enumerate(rows):
        row["repository"] = f"repo{i % 7}.example"
    with pytest.raises(ValueError, match="primary repositories constraint violated"):
        verify_frozen_composition(rows)


def test_duplicate_sha_is_rejected():
    rows = primary_rows()
    rows[1]["sha256"] = rows[0]["sha256"]
    with pytest.raises(ValueError, match="duplicate sha256"):
        verify_frozen_composition(rows)


def test_sha256sums_pins_protocol_registry_snapshot_manifest_and_pdfs(tmp_path):
    files = []
    for name, content in [
        ("selection_config.json", b"{}"),
        ("exclusion_registry.jsonl", b"{}\n"),
        ("source_freeze_protocol.json", b"{}"),
        ("source_manifest.jsonl", b"{}\n"),
        ("source_freeze/openalex_expansion_20260914.json", b'{"results":[]}'),
        ("pdf_cache/d001.pdf", b"%PDF-test"),
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append(path)
    out = tmp_path / "SHA256SUMS.txt"
    write_sha256sums(tmp_path, files, out)
    text = out.read_text(encoding="utf-8")
    for path in files:
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert f"{expected}  {path.relative_to(tmp_path).as_posix()}" in text


def test_first_expansion_is_preregistered_with_20260914_but_selection_seed_stays_20260913():
    protocol = {
        "selection_seed": 20260913,
        "target_nonpilot": 40,
        "expansions": [
            {
                "round": 1,
                "provider": "OpenAlex",
                "metadata_seed": 20260914,
                "query": "https://api.openalex.org/works?filter=type:dissertation&sample=200&seed=20260914&per_page=200",
            }
        ],
    }
    pending = next_expansion_query(protocol, completed_rounds=[], accepted_count=7)
    assert pending["metadata_seed"] == 20260914
    assert protocol["selection_seed"] == 20260913


def test_expansion_stays_inactive_when_nonpilot_target_is_already_met():
    protocol = {
        "target_nonpilot": 40,
        "expansions": [{"round": 1, "metadata_seed": 20260914}],
    }
    assert next_expansion_query(protocol, completed_rounds=[], accepted_count=40) is None


def test_acquisition_round_history_is_append_only_and_monotonic():
    history = []
    append_acquisition_round(history, {"round": 1, "accepted": 7, "rejected": 11})
    append_acquisition_round(history, {"round": 2, "accepted": 14, "rejected": 9})
    assert history == [
        {"round": 1, "accepted": 7, "rejected": 11},
        {"round": 2, "accepted": 14, "rejected": 9},
    ]
    with pytest.raises(ValueError, match="acquisition round must increase"):
        append_acquisition_round(history, {"round": 2, "accepted": 1, "rejected": 0})
