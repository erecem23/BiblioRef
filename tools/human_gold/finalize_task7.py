"""Execute the preregistered human-gold v0.1 Task 7 source freeze.

This runner never imports or executes BiblioRef and never accesses PDF text.
It acquires public PDF bytes, verifies them, computes visual-only PDFium
profiles, freezes stress before primary, and writes auditable source evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .acquire_sources import acquisition_ruling, acquire_candidate
from .build_exclusion_registry import build_exclusion_registry, is_excluded
from .finalize_sources import choose_partitions
from .freeze_sources import write_sha256sums
from .openalex_candidates import transform_openalex_snapshot
from .visual_stress import profile_pdf


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _stable_order(rows: list[dict], seed: int) -> list[dict]:
    unique: dict[str, dict] = {}
    for row in rows:
        unique.setdefault(row["document_id"], row)
    return sorted(
        unique.values(),
        key=lambda row: (
            hashlib.sha256(f"{seed}|{row['document_id']}".encode("utf-8")).hexdigest(),
            row["document_id"],
        ),
    )


def run_source_freeze(root: Path) -> dict:
    root = Path(root).resolve()
    bench = root / "benchmarks" / "human_gold_v0_1"
    freeze = bench / "source_freeze"
    provisional = freeze / "provisional"
    cache = bench / "pdf_cache"
    artifact_cache = root / "task7_selected_pdf_cache"
    freeze.mkdir(parents=True, exist_ok=True)
    provisional.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    protocol = _read_json(bench / "source_freeze_protocol.json")
    selection_config = _read_json(bench / "selection_config.json")
    pilot_manifest = _read_jsonl(bench / "pilot" / "source_manifest.jsonl")
    pilot_ids = {row["document_id"] for row in pilot_manifest}
    seed = protocol["selection_seed"]
    target = protocol["target_nonpilot"]

    registry = build_exclusion_registry(root)
    _write_jsonl(bench / "exclusion_registry.jsonl", registry)

    base_transform = _read_json(bench / "pilot" / "candidate_transform.json")
    initial_spec = protocol["initial_pool"]
    initial_snapshot_path = root / initial_spec["snapshot"]
    initial_sha = _sha256_file(initial_snapshot_path)
    if initial_sha != initial_spec["snapshot_sha256"]:
        raise RuntimeError(f"initial snapshot hash mismatch: {initial_sha}")
    initial_transform = copy.deepcopy(base_transform)
    initial_transform["metadata_source_query"] = initial_spec["query"]
    initial_transform["metadata_snapshot_sha256"] = initial_sha
    _write_json(freeze / "initial_transform_config.json", initial_transform)
    initial_rows = transform_openalex_snapshot(_read_json(initial_snapshot_path), initial_transform)

    def eligible_source_rows(rows: list[dict], source_round: str) -> list[dict]:
        result = []
        for original in rows:
            if original["document_id"] in pilot_ids or is_excluded(original, registry):
                continue
            row = dict(original)
            row["development_overlap"] = False
            row["selected_before_biblioref_run"] = True
            row["source_round"] = source_round
            row["pre_output_eligibility"] = acquisition_ruling(row)
            result.append(row)
        return result

    initial_candidates = _stable_order(eligible_source_rows(initial_rows, "initial_20260913"), seed)
    _write_jsonl(freeze / "initial_candidates.jsonl", initial_candidates)

    acquisition = protocol["acquisition"]
    ledger: list[dict] = []
    seen_ids: set[str] = set()
    history: list[dict] = []
    visual_profiles: dict[str, dict] = {}
    final_result: dict | None = None

    def acquire_one(row: dict) -> dict:
        return acquire_candidate(
            row,
            cache,
            retries=acquisition["retries"],
            timeout=acquisition["timeout_seconds"],
            max_bytes=acquisition["max_bytes"],
        )

    def acquire_batch(rows: list[dict], round_name: str, workers: int = 6) -> list[dict]:
        if not rows:
            return []
        round_dir = provisional / round_name
        _write_jsonl(round_dir / "attempted_candidates.jsonl", rows)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(acquire_one, row) for row in rows]
            results = [future.result() for future in futures]
        for result in results:
            seen_ids.add(result["document_id"])
            ledger.append(result)
        rejected = [row for row in results if not row.get("accepted")]
        summary = {
            "round": round_name,
            "observations": len(results),
            "accepted": sum(bool(row.get("accepted")) for row in results),
            "rejected": len(rejected),
            "rejection_reasons": dict(sorted(Counter(row.get("reason_code") for row in rejected).items())),
        }
        _write_jsonl(round_dir / "acquisition_ledger.jsonl", results)
        _write_json(round_dir / "summary.json", summary)
        history.append({"event": "acquisition_round", **summary})
        print(json.dumps(summary, sort_keys=True), flush=True)
        return results

    def unique_accepted() -> list[dict]:
        rows = []
        seen_sha = set()
        seen_doc = set()
        for row in ledger:
            if not row.get("accepted"):
                continue
            sha = row.get("sha256", "").casefold()
            if row["document_id"] in seen_doc or sha in seen_sha:
                continue
            seen_doc.add(row["document_id"])
            seen_sha.add(sha)
            rows.append(row)
        return rows

    def try_finalize(tag: str) -> bool:
        nonlocal final_result
        accepted = unique_accepted()
        if len(accepted) < target:
            return False
        for row in accepted:
            document_id = row["document_id"]
            if document_id not in visual_profiles:
                visual_profiles[document_id] = profile_pdf(cache / f"{document_id}.pdf")
        try:
            final_result = choose_partitions(
                accepted,
                visual_profiles,
                selection_config=selection_config,
                pilot_document_ids=pilot_ids,
                exclusions=registry,
            )
        except ValueError as exc:
            history.append({
                "event": "provisional_selection_failed",
                "stage": tag,
                "accepted_unique_pool_n": len(accepted),
                "reason": str(exc),
            })
            print(f"provisional selection failed at {tag}: {exc}", flush=True)
            return False
        history.append({
            "event": "provisional_selection_succeeded",
            "stage": tag,
            "accepted_unique_pool_n": len(accepted),
            "primary_summary": final_result["primary_summary"],
            "stress_document_ids": final_result["stress_document_ids"],
        })
        return True

    # Reconstruct the transfer checkpoint first, without inventing lost data.
    checkpoint = initial_candidates[:18]
    acquire_batch(checkpoint, "round_000_initial_checkpoint", workers=4)
    checkpoint_rejected = [row for row in ledger if not row.get("accepted")]
    checkpoint_summary = {
        "observations": len(ledger),
        "accepted": sum(bool(row.get("accepted")) for row in ledger),
        "rejected": len(checkpoint_rejected),
        "rejection_reasons": dict(sorted(Counter(row.get("reason_code") for row in checkpoint_rejected).items())),
        "transfer_checkpoint_reference": {
            "observations": 18,
            "accepted": 7,
            "rejected": 11,
            "rejection_reasons": {
                "access_denied": 4,
                "http_server_error": 2,
                "non_pdf_response": 4,
                "transport_failure": 1,
            },
        },
        "note": (
            "Current reconstruction includes review fixes such as fail-closed multilingual fragment "
            "detection; exact equality is informative, not forced."
        ),
    }
    checkpoint_summary["matches_transfer_checkpoint_counts"] = (
        checkpoint_summary["observations"] == 18
        and checkpoint_summary["accepted"] == 7
        and checkpoint_summary["rejected"] == 11
        and checkpoint_summary["rejection_reasons"]
        == checkpoint_summary["transfer_checkpoint_reference"]["rejection_reasons"]
    )
    _write_json(freeze / "transfer_checkpoint_reconstruction.json", checkpoint_summary)

    unobserved_initial = [row for row in initial_candidates if row["document_id"] not in seen_ids]
    batch_index = 1
    expansion_needed = False

    while final_result is None:
        accepted_n = len(unique_accepted())
        if accepted_n >= target and try_finalize(f"initial_{batch_index:03d}"):
            break
        if not unobserved_initial:
            expansion_needed = True
            break
        if accepted_n + len(unobserved_initial) < target:
            expansion_needed = True
            history.append({
                "event": "expansion_activated",
                "reason": "accepted_plus_unobserved_initial_below_target",
                "accepted_unique": accepted_n,
                "unobserved_initial": len(unobserved_initial),
                "target_nonpilot": target,
            })
            break
        batch = unobserved_initial[:12]
        unobserved_initial = unobserved_initial[12:]
        acquire_batch(batch, f"round_{batch_index:03d}_initial_continuation")
        batch_index += 1

    expansion_snapshot_path: Path | None = None
    expansion_sha: str | None = None
    expansion_candidates: list[dict] = []
    if final_result is None:
        expansion_needed = True

    if expansion_needed:
        expansion_spec = protocol["expansions"][0]
        expansion_snapshot_path = root / expansion_spec["snapshot"]
        request = urllib.request.Request(
            expansion_spec["query"],
            headers={"User-Agent": "BiblioRef-human-gold-v0.1 source-freeze"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise RuntimeError("OpenAlex expansion snapshot unexpectedly large")
        expansion_snapshot = json.loads(raw.decode("utf-8"))
        expansion_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        expansion_snapshot_path.write_bytes(raw)
        expansion_sha = _sha256_bytes(raw)
        expansion_transform = copy.deepcopy(base_transform)
        expansion_transform["metadata_source_query"] = expansion_spec["query"]
        expansion_transform["metadata_snapshot_sha256"] = expansion_sha
        _write_json(freeze / "expansion_transform_config.json", expansion_transform)
        expansion_rows = transform_openalex_snapshot(expansion_snapshot, expansion_transform)
        expansion_candidates = eligible_source_rows(expansion_rows, "expansion_20260914")
        _write_jsonl(freeze / "expansion_candidates.jsonl", _stable_order(expansion_candidates, seed))
        history.append({
            "event": "metadata_expansion_snapshot_frozen",
            "metadata_seed": expansion_spec["metadata_seed"],
            "snapshot": expansion_spec["snapshot"],
            "snapshot_sha256": expansion_sha,
            "candidate_count_after_transform_and_exclusions": len(expansion_candidates),
        })

        remaining_union = _stable_order(unobserved_initial + expansion_candidates, seed)
        remaining_union = [row for row in remaining_union if row["document_id"] not in seen_ids]
        while remaining_union and final_result is None:
            batch = remaining_union[:12]
            remaining_union = remaining_union[12:]
            acquire_batch(batch, f"round_{batch_index:03d}_expanded_union")
            batch_index += 1
            if len(unique_accepted()) >= target:
                try_finalize(f"expanded_{batch_index:03d}")

    if final_result is None:
        _write_jsonl(freeze / "acquisition_ledger.jsonl", ledger)
        _write_jsonl(freeze / "selection_history.jsonl", history)
        raise RuntimeError("source freeze exhausted preregistered pools without a valid 32 primary + 8 stress composition")

    manifest = final_result["manifest"]
    _write_jsonl(bench / "source_manifest.jsonl", manifest)
    _write_jsonl(freeze / "acquisition_ledger.jsonl", ledger)
    _write_jsonl(freeze / "selection_history.jsonl", history)
    _write_jsonl(
        freeze / "visual_profiles.jsonl",
        [
            {"document_id": document_id, "method": "pdfium_raster_geometry_v1", **profile}
            for document_id, profile in sorted(visual_profiles.items())
        ],
    )

    all_candidates = _stable_order(initial_candidates + expansion_candidates, seed)
    _write_jsonl(freeze / "eligible_candidates.jsonl", all_candidates)
    rejections = []
    for row in ledger:
        if row.get("accepted"):
            continue
        rejections.append({
            "document_id": row["document_id"],
            "reason_code": row.get("reason_code"),
            "pre_output_eligibility": row.get("pre_output_eligibility"),
            "rounds": row.get("rounds", []),
            "source_round": row.get("source_round"),
        })
    _write_jsonl(freeze / "objective_rejections.jsonl", rejections)

    snapshot_receipts = [{
        "provider": "OpenAlex",
        "metadata_seed": initial_spec["metadata_seed"],
        "query": initial_spec["query"],
        "path": initial_spec["snapshot"],
        "sha256": initial_sha,
    }]
    if expansion_snapshot_path is not None:
        snapshot_receipts.append({
            "provider": "OpenAlex",
            "metadata_seed": protocol["expansions"][0]["metadata_seed"],
            "query": protocol["expansions"][0]["query"],
            "path": protocol["expansions"][0]["snapshot"],
            "sha256": expansion_sha,
        })
    _write_jsonl(freeze / "snapshot_receipts.jsonl", snapshot_receipts)

    selected_pdf_paths = []
    for row in manifest:
        document_id = row["document_id"]
        path = cache / f"{document_id}.pdf"
        actual = _sha256_file(path)
        if actual != row["sha256"]:
            raise RuntimeError(f"selected PDF hash mismatch: {document_id}")
        selected_pdf_paths.append(path)

    summary = {
        "pilot_n": len(pilot_manifest),
        "primary_n": len([row for row in manifest if row["partition"] == "primary"]),
        "stress_n": len([row for row in manifest if row["partition"] == "stress"]),
        "acquisition_observations": len(ledger),
        "acquisition_accepted_unique": len(unique_accepted()),
        "rejection_reasons": dict(sorted(Counter(row.get("reason_code") for row in ledger if not row.get("accepted")).items())),
        "primary_summary": final_result["primary_summary"],
        "stress_document_ids": final_result["stress_document_ids"],
        "selection_seed": seed,
        "selected_before_biblioref_run": all(row.get("selected_before_biblioref_run") is True for row in manifest),
        "expansion_used": expansion_snapshot_path is not None,
        "expansion_snapshot_sha256": expansion_sha,
        "human_annotation_exists": False,
        "primary_metrics_observed": False,
    }
    _write_json(freeze / "source_freeze_summary.json", summary)

    hash_files = [
        bench / "selection_config.json",
        bench / "exclusion_registry.jsonl",
        bench / "source_freeze_protocol.json",
        initial_snapshot_path,
        bench / "source_manifest.jsonl",
        freeze / "acquisition_ledger.jsonl",
        freeze / "selection_history.jsonl",
        freeze / "visual_profiles.jsonl",
        freeze / "snapshot_receipts.jsonl",
        freeze / "source_freeze_summary.json",
    ]
    if expansion_snapshot_path is not None:
        hash_files.append(expansion_snapshot_path)
    hash_files.extend(selected_pdf_paths)
    write_sha256sums(bench, hash_files, bench / "SHA256SUMS.txt")

    if artifact_cache.exists():
        shutil.rmtree(artifact_cache)
    artifact_cache.mkdir(parents=True)
    for path in selected_pdf_paths:
        shutil.copy2(path, artifact_cache / path.name)

    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def main() -> int:
    run_source_freeze(Path.cwd())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
