"""Finalize acquired sources into frozen primary and stress partitions."""

from __future__ import annotations

import copy

from .build_exclusion_registry import is_excluded
from .freeze_sources import freeze_source_manifest, verify_frozen_composition
from .sample_sources import sample_candidates
from .visual_stress import rank_stress_profiles


def _deduplicate_acquired(rows: list[dict], pilot_document_ids: set[str], exclusions: list[dict]) -> list[dict]:
    result = []
    seen_ids = set()
    seen_shas = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("acquisition_accepted") is not True:
            continue
        document_id = row.get("document_id")
        sha = row.get("sha256")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("accepted source requires document_id")
        if not isinstance(sha, str) or not sha:
            raise ValueError(f"accepted source requires sha256: {document_id}")
        if document_id in pilot_document_ids or is_excluded(row, exclusions):
            continue
        if document_id in seen_ids or sha.casefold() in seen_shas:
            continue
        seen_ids.add(document_id)
        seen_shas.add(sha.casefold())
        result.append(dict(row))
    return result


def choose_partitions(
    acquired_rows: list[dict],
    visual_profiles: dict[str, dict],
    *,
    selection_config: dict,
    pilot_document_ids: set[str],
    exclusions: list[dict],
) -> dict:
    """Select stress from visual evidence first, then a constrained primary set."""
    if not isinstance(selection_config, dict):
        raise ValueError("selection_config must be an object")
    accepted = _deduplicate_acquired(acquired_rows, pilot_document_ids, exclusions)
    stress_n = selection_config.get("stress_n")
    if isinstance(stress_n, bool) or not isinstance(stress_n, int) or stress_n < 0:
        raise ValueError("invalid stress_n")
    primary_n = selection_config.get("primary_n")
    if isinstance(primary_n, bool) or not isinstance(primary_n, int) or primary_n < 0:
        raise ValueError("invalid primary_n")
    if len(accepted) < primary_n + stress_n:
        raise ValueError("insufficient acquisition-accepted unique sources")

    stress = rank_stress_profiles(
        accepted,
        visual_profiles,
        n=stress_n,
        selection_seed=selection_config["seed"],
    )
    stress_ids = {row["document_id"] for row in stress}
    primary_pool = [row for row in accepted if row["document_id"] not in stress_ids]

    primary_config = copy.deepcopy(selection_config)
    primary_config["pilot_n"] = 0
    primary_config["stress_n"] = 0
    primary_config["exclusion_rows"] = exclusions
    selected_primary = sample_candidates(primary_pool, primary_config)
    primary = [row for row in selected_primary if row.get("partition") == "primary"]
    if len(primary) != primary_n:
        raise ValueError("primary selection did not produce requested size")

    # Freeze is the final guard: exact counts, unique SHAs and all primary quotas.
    manifest = freeze_source_manifest(
        primary,
        stress,
        pilot_document_ids=pilot_document_ids,
        selection_seed=selection_config["seed"],
    )
    primary_summary = verify_frozen_composition([row for row in manifest if row["partition"] == "primary"])
    return {
        "manifest": manifest,
        "stress_selected_first": True,
        "stress_document_ids": [row["document_id"] for row in stress],
        "primary_document_ids": [row["document_id"] for row in primary],
        "accepted_unique_pool_n": len(accepted),
        "primary_summary": primary_summary,
    }
