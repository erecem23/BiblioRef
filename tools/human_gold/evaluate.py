"""Evaluate BiblioRef's public PDF pipeline against completed human gold.

This is intentionally an adapter, not an extraction mode.  It invokes the
public pipeline exactly once for each manifest document and derives scoring
coordinates without mutating the pipeline's report or records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION
from biblioref import pipeline

from .metrics import align_boundaries, match_zones, summarize_partitions, text_fidelity
from .validate_gold import exclusion_sha256, validate_paths


BENCHMARK_VERSION = "human_gold_v0_1"
SELECTION_SEED = 20260913
BOUNDARY_Y_TOLERANCE = 0.015
BOOTSTRAP_SEED = 20260913
BOOTSTRAP_N = 10000
_BUNDLE_FILES = (
    "results.json", "per_document.jsonl", "summary.md", "bootstrap.json",
    "environment.json", "SHA256SUMS.txt",
)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(text: Any) -> str:
    return " ".join(str(text or "").replace("\u00ad", "").split()).casefold()


def _git_sha(explicit_candidate: str | None) -> str:
    """Resolve and verify an explicitly frozen candidate commit."""
    if not isinstance(explicit_candidate, str) or not explicit_candidate.strip():
        raise ValueError("candidate git SHA is required")
    explicit_candidate = explicit_candidate.strip().casefold()
    if not re.fullmatch(r"[0-9a-f]{40}", explicit_candidate):
        raise ValueError("candidate git SHA must be a full 40-character hexadecimal commit")
    try:
        evaluator_root = Path(__file__).resolve().parents[2]
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=evaluator_root, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not root:
            raise ValueError("candidate git SHA is unknown")
        resolved = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{explicit_candidate}^{{commit}}"],
            cwd=root, text=True, stderr=subprocess.DEVNULL,
        ).strip().casefold()
        if resolved != explicit_candidate:
            raise ValueError("candidate git SHA cannot be resolved")
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True,
            stderr=subprocess.DEVNULL,
        )
        if dirty.strip():
            raise ValueError("candidate git worktree has tracked changes")
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip().casefold()
        if head != resolved:
            raise ValueError("explicit candidate git SHA does not match HEAD")
        return head
    except subprocess.CalledProcessError:
        raise ValueError("candidate git SHA cannot be resolved") from None
    except OSError:
        raise ValueError("candidate git SHA is unknown") from None

def _pdf_path(manifest_row: dict, cache_root: Path) -> Path:
    configured = manifest_row.get("pdf_filename", manifest_row.get("cache_filename", manifest_row.get("pdf_path")))
    candidates = [configured] if isinstance(configured, str) and configured else []
    candidates.append(f"{manifest_row['document_id']}.pdf")
    root = cache_root.resolve()
    for candidate in candidates:
        path = (root / candidate).resolve()
        if path.parent == root and path.is_file():
            return path
    raise ValueError(f"cached PDF not found: {manifest_row['document_id']}")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _start_page(record: dict) -> int | None:
    for key in ("start_page", "reference_start_page", "page"):
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            return value
    return None


def _metadata_y_ratio(record: dict) -> float | None:
    for key in ("start_y_ratio", "reference_start_y_ratio", "y_ratio"):
        value = _number(record.get(key))
        if value is not None and 0 <= value <= 1:
            return value
    page_height = _number(record.get("page_height"))
    for key in ("reference_start_y", "start_y", "y0"):
        value = _number(record.get(key))
        if value is not None and page_height and page_height > 0:
            return value / page_height
    return None


def _metadata_x(record: dict) -> float | None:
    for key in ("reference_start_x", "start_x", "x0"):
        value = _number(record.get(key))
        if value is not None:
            return value
    return None


def _opening(record: dict) -> str:
    return str(record.get("reference_text", record.get("text", record.get("start_anchor", ""))))


def _layout_lines_for_pages(pdf_path: Path, pages: list[int]) -> dict[int, list[dict]]:
    """Read each requested page once through the pinned public PDFium backend."""
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        output: dict[int, list[dict]] = {}
        for page_number in sorted(set(pages)):
            page = document[page_number - 1]
            textpage = page.get_textpage()
            rect_count = textpage.count_rects()
            width, height = page.get_size()
            chunks = []
            for index in range(rect_count):
                left, bottom, right, top = textpage.get_rect(index)
                text = textpage.get_text_bounded(left, bottom, right, top).strip()
                if text:
                    chunks.append({"text": text, "x0": float(left), "y0": float(height - top), "height": float(height)})
            chunks.sort(key=lambda line: (line["y0"], line["x0"], line["text"]))
            output[page_number] = chunks
        return output
    finally:
        document.close()


def _numeric_marker(text: str) -> str | None:
    compact = _canonical(text)
    if not compact:
        return None
    marker = compact.split(" ", 1)[0].lstrip("([{")
    return marker.rstrip(".)]}") if marker[:1].isdigit() else None


def _without_numeric_marker(text: str) -> str:
    return re.sub(r"^\s*[\[(]?\d+[.)\]]?\s*", "", _canonical(text))


def _opening_matches(opening: str, line: dict) -> bool:
    expected, observed = _canonical(opening), _canonical(line.get("text", ""))
    if len(expected) < 6 or len(observed) < 6:
        return False
    expected_marker, observed_marker = _numeric_marker(expected), _numeric_marker(observed)
    if expected_marker and observed_marker and expected_marker != observed_marker:
        return False
    if expected_marker or observed_marker:
        expected, observed = _without_numeric_marker(expected), _without_numeric_marker(observed)
    return observed.startswith(expected) or expected.startswith(observed)


def localize_predicted_starts(records, pdf_path: Path) -> list[dict]:
    """Return copied scoring records with explicit localization diagnostics.

    Metadata is preferred.  When unavailable, the public layout reader is
    used only to score a copied record; pipeline output is never changed.
    """
    localized = []
    needs_layout: dict[int, list[tuple[int, dict]]] = {}
    for index, source in enumerate(records or []):
        record = dict(source)
        page = _start_page(record)
        y_ratio = _metadata_y_ratio(record)
        if page is not None and y_ratio is not None:
            record.update({"start_page": page, "start_y_ratio": y_ratio, "localization_status": "metadata"})
        elif page is not None:
            record["start_page"] = page
            needs_layout.setdefault(page, []).append((index, record))
        else:
            record["localization_status"] = "unresolved"
        localized.append(record)
    if not needs_layout:
        return localized
    try:
        layouts = _layout_lines_for_pages(pdf_path, list(needs_layout))
    except Exception:
        for page_records in needs_layout.values():
            for _, record in page_records:
                record["localization_status"] = "unresolved"
        return localized
    for page, page_records in needs_layout.items():
        # Production uses zone_id/ref_in_zone as its reference order.  Sorting
        # only for matching preserves the original report positions in output.
        ordered = sorted(page_records, key=lambda item: (item[1].get("zone_id", 1), item[1].get("ref_in_zone", item[0] + 1), item[0]))
        column_cursors: dict[tuple[Any, float], float] = {}
        used = set()
        for _, record in ordered:
            expected_x = _metadata_x(record)
            candidates = [
                (line_index, line) for line_index, line in enumerate(layouts.get(page, []))
                if line_index not in used and _opening_matches(_opening(record), line)
            ]
            candidates.sort(key=lambda item: (abs(item[1]["x0"] - expected_x) if expected_x is not None else 0.0, item[1]["y0"], item[1]["x0"]))
            candidates = [
                (line_index, line) for line_index, line in candidates
                if line["y0"] >= column_cursors.get((record.get("zone_id", 1), round(line["x0"], 3)), -1.0)
            ]
            if candidates:
                line_index, line = candidates[0]
                used.add(line_index)
                column_cursors[(record.get("zone_id", 1), round(line["x0"], 3))] = line["y0"]
                record.update({"start_y_ratio": max(0.0, min(1.0, line["y0"] / line["height"])), "localization_status": "layout_match"})
            elif _opening(record):
                record["localization_status"] = "anchor_only"
            else:
                record["localization_status"] = "unresolved"
    return localized


def _gold_references(gold: dict) -> list[dict]:
    return [reference for zone in gold.get("zones", []) for reference in zone.get("references", [])]


def _prediction_zones(report: dict) -> list[dict]:
    zones = []
    for position, zone in enumerate(report.get("zones", []) or [], 1):
        try:
            start, end = int(zone["start_page"]), int(zone["end_page"])
        except (KeyError, TypeError, ValueError):
            continue
        if start >= 1 and end >= start:
            zones.append({"start_page": start, "end_page": end, "zone_id": zone.get("zone_id", position)})
    return zones


def _zone_boundary_alignment(gold: dict, predicted_zones: list[dict], localized: list[dict], zone: dict) -> dict:
    """Align starts only inside matched zone pairs, retaining global indexes."""
    gold_zones = list(gold.get("zones", []))
    gold_refs = _gold_references(gold)
    gold_positions = {id(reference): index for index, reference in enumerate(gold_refs)}
    predicted_positions = {id(reference): index for index, reference in enumerate(localized)}
    records_by_zone: dict[Any, list[dict]] = {}
    if len(predicted_zones) == 1:
        default_zone = predicted_zones[0]["zone_id"]
    else:
        default_zone = None
    for record in localized:
        zone_id = record.get("zone_id", default_zone)
        records_by_zone.setdefault(zone_id, []).append(record)
    for records in records_by_zone.values():
        records.sort(key=lambda item: (item.get("ref_in_zone", 10**9), predicted_positions[id(item)]))
    gold_matched, predicted_matched, pairs = set(), set(), []
    details = {"missed_first_reference_count": 0, "missed_last_reference_count": 0, "merge_count": 0, "split_count": 0,
               "anchor_fallback_match_count": 0, "unresolved_predicted_start_count": 0}
    for pair in zone["matched_pairs"]:
        gold_index, prediction_index = pair["gold_index"], pair["predicted_index"]
        gold_matched.add(gold_index)
        production_zone = predicted_zones[prediction_index]
        predicted_matched.add(production_zone["zone_id"])
        local = align_boundaries(gold_zones[gold_index].get("references", []), records_by_zone.get(production_zone["zone_id"], []), BOUNDARY_Y_TOLERANCE)
        details.update({key: details[key] + int(local.get(key, 0)) for key in details})
        local_gold = gold_zones[gold_index].get("references", [])
        local_predicted = records_by_zone.get(production_zone["zone_id"], [])
        pairs.extend({"gold_index": gold_positions[id(local_gold[item["gold_index"]])], "predicted_index": predicted_positions[id(local_predicted[item["predicted_index"]])]} for item in local["matched_pairs"])
    unmatched_gold = [reference for index, item in enumerate(gold_zones) if index not in gold_matched for reference in item.get("references", [])]
    unmatched_predicted = [reference for zone_id, records in records_by_zone.items() if zone_id not in predicted_matched for reference in records]
    tp = len(pairs); predicted_count = len(localized); gold_count = len(gold_refs)
    precision = tp / predicted_count if predicted_count else 0.0; recall = tp / gold_count if gold_count else 0.0
    matched_gold = {pair["gold_index"] for pair in pairs}; matched_predicted = {pair["predicted_index"] for pair in pairs}
    details["unresolved_predicted_start_count"] += sum(
        row.get("start_y_ratio") is None for row in unmatched_predicted
    )
    details["missed_first_reference_count"] = int(bool(gold_refs) and 0 not in matched_gold)
    details["missed_last_reference_count"] = int(bool(gold_refs) and gold_count - 1 not in matched_gold)
    return {"boundary": {"true_positive": tp, "predicted": predicted_count, "gold": gold_count, "precision": precision, "recall": recall, "f1": (2 * tp / (predicted_count + gold_count) if predicted_count + gold_count else 0.0)},
            "matched_pairs": sorted(pairs, key=lambda item: item["gold_index"]),
            "missed_gold_indices": [index for index in range(gold_count) if index not in matched_gold],
            "spurious_predicted_indices": [index for index in range(predicted_count) if index not in matched_predicted],
            "spurious_predicted_start_count": predicted_count - tp,
            **details}


def _text_results(gold: dict, localized: list[dict], boundary: dict) -> list[dict]:
    sample_ids = set(gold.get("full_text_sample_ids", []))
    refs = _gold_references(gold)
    predictions_by_gold = {
        pair["gold_index"]: localized[pair["predicted_index"]]
        for pair in boundary.get("matched_pairs", [])
    }
    samples = []
    for index, reference in enumerate(refs):
        if reference.get("gold_ref_id") not in sample_ids or "visible_text_gold" not in reference:
            continue
        samples.append(text_fidelity(
            reference["visible_text_gold"], _opening(predictions_by_gold.get(index, {}))
        ))
    return samples


def _document_result(manifest_row: dict, gold: dict, pdf_path: Path, report: dict) -> dict:
    localized = localize_predicted_starts(report.get("records", []), pdf_path)
    predicted_zones = _prediction_zones(report)
    zone = match_zones(gold.get("zones", []), predicted_zones)
    boundary = _zone_boundary_alignment(gold, predicted_zones, localized, zone)
    audit = report.get("post_extraction_audit", {})
    audit_status = audit.get("status") if isinstance(audit, dict) else None
    audit_requires_review = bool(audit_status and audit_status not in {"looks_consistent", "no_reference_sections", "not_run"})
    result = {
        "document_id": manifest_row["document_id"],
        "partition": manifest_row["partition"],
        "pdf_sha256": _sha256_path(pdf_path),
        "gold_reference_count": len(_gold_references(gold)),
        "predicted_reference_count": len(localized),
        "zone": zone,
        "boundary": boundary,
        "text": _text_results(gold, localized, boundary),
        "review_required": bool(report.get("needs_review", report.get("review_required", False)) or audit_requires_review),
        "post_extraction_audit": {"status": audit_status, "version": audit.get("version"), "recommendation_count": len(audit.get("recommendations", []) or [])} if isinstance(audit, dict) else {"status": None},
        "localization_status_counts": {
            status: sum(row.get("localization_status") == status for row in localized)
            for status in ("metadata", "layout_match", "anchor_only", "unresolved")
        },
        "predicted_starts": [
            {key: row[key] for key in ("zone_id", "ref_in_zone", "start_page", "start_y_ratio", "localization_status", "reference_text") if key in row}
            for row in localized
        ],
    }
    return result


def _provenance(manifest_path: Path, gold_path: Path, report_versions: list[dict], bootstrap_n: int, exclusions_path=None, candidate_git_sha=None) -> dict:
    first = report_versions[0] if report_versions else {}
    versions = {(row.get("software_version", SOFTWARE_VERSION), row.get("algorithm_version", ALGORITHM_VERSION)) for row in report_versions}
    if len(versions) > 1:
        raise ValueError("inconsistent software/algorithm versions across reports")
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "candidate_git_sha": candidate_git_sha,
        "software_version": first.get("software_version", SOFTWARE_VERSION),
        "algorithm_version": first.get("algorithm_version", ALGORITHM_VERSION),
        "manifest_sha256": _sha256_path(manifest_path),
        "gold_sha256": _sha256_path(gold_path),
        "exclusion_registry_sha256": exclusion_sha256(exclusions_path),
        "selection_seed": SELECTION_SEED,
        "boundary_y_tolerance": BOUNDARY_Y_TOLERANCE,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_n": bootstrap_n,
    }


def _summary_markdown(provenance: dict, summary: dict, partition_summaries: dict) -> str:
    boundary = summary["boundary"]
    lines = [
        "# Human-gold evaluation", "",
        f"- Benchmark: `{provenance['benchmark_version']}`",
        f"- Candidate git SHA: `{provenance['candidate_git_sha']}`",
        "- Headline partition: primary" if partition_summaries["headline_observed"] else "- Headline partition: primary (unobserved)",
        f"- Primary boundary precision / recall / F1: {boundary['precision']:.4f} / {boundary['recall']:.4f} / {boundary['f1']:.4f}",
        f"- Bootstrap: seed {provenance['bootstrap_seed']}, n={provenance['bootstrap_n']}",
        "", "## Partition summaries", "",
    ]
    for partition in ("primary", "stress", "pilot"):
        item = partition_summaries[partition]
        item_boundary = item["boundary"]
        lines.append(f"- {partition}: {item['count']['documents']} documents; boundary F1 {item_boundary['f1']:.4f}")
    return "\n".join((*lines, ""))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_bundle(output_dir: Path, results: dict, documents: list[dict], summary: dict, partition_summaries: dict, provenance: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "results.json", results)
    with (output_dir / "per_document.jsonl").open("w", encoding="utf-8") as stream:
        for document in documents:
            stream.write(json.dumps(document, sort_keys=True) + "\n")
    (output_dir / "summary.md").write_text(_summary_markdown(provenance, summary, partition_summaries), encoding="utf-8")
    _write_json(output_dir / "bootstrap.json", {
        "bootstrap_seed": provenance["bootstrap_seed"], "bootstrap_n": provenance["bootstrap_n"],
        "headline": summary, "headline_observed": partition_summaries["headline_observed"],
        "partition_summaries": partition_summaries,
    })
    _write_json(output_dir / "environment.json", {
        "python": sys.version,
        "platform": platform.platform(), "provenance": provenance,
    })
    checksums = []
    for name in _BUNDLE_FILES[:-1]:
        checksums.append(f"{_sha256_path(output_dir / name)}  {name}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def evaluate(manifest, gold, pdf_cache, output_dir, *, bootstrap_n: int = BOOTSTRAP_N, exclusions=None, candidate_git_sha=None) -> dict:
    """Run one public extraction per document and write the evaluator bundle."""
    resolved_candidate = _git_sha(candidate_git_sha)
    manifest_path, gold_path = Path(manifest), Path(gold)
    manifest_rows, gold_rows = validate_paths(manifest_path, gold_path, exclusions)
    gold_by_document = {row["document_id"]: row for row in gold_rows}
    cache_root = Path(pdf_cache)
    documents, report_versions = [], []
    for manifest_row in manifest_rows:
        pdf_path = _pdf_path(manifest_row, cache_root)
        actual_digest = _sha256_path(pdf_path)
        if actual_digest.lower() != manifest_row["sha256"].lower():
            raise ValueError(f"cached PDF SHA-256 does not match manifest: {manifest_row['document_id']}")
        # This is deliberately the sole extraction call for this document.
        report = pipeline.process_pdf(pdf_path, scope="all_reference_sections")
        documents.append(_document_result(manifest_row, gold_by_document[manifest_row["document_id"]], pdf_path, report))
        report_versions.append(report)
    provenance = _provenance(manifest_path, gold_path, report_versions, bootstrap_n, exclusions, resolved_candidate)
    summaries = summarize_partitions(documents, bootstrap_seed=BOOTSTRAP_SEED, bootstrap_n=bootstrap_n)
    summary = summaries["headline"]
    results = {**provenance, "provenance": provenance, "summary": summary, "partition_summaries": summaries, "documents": len(documents)}
    _write_bundle(Path(output_dir), results, documents, summary, summaries, provenance)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate BiblioRef against human-gold JSONL.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--pdf-cache", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--exclusions")
    parser.add_argument("--candidate-git-sha", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        evaluate(args.manifest, args.gold, args.pdf_cache, args.output_dir, exclusions=args.exclusions, candidate_git_sha=args.candidate_git_sha)
    except ValueError as exc:
        raise SystemExit(f"human-gold evaluation failed: {exc}") from exc
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the public CLI
    raise SystemExit(main())
