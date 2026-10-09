"""Frozen matching and scoring rules for the human-gold benchmark.

This module is deliberately stdlib-only.  It scores evaluation-only records and
does not import, configure, or otherwise affect the extraction pipeline.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Iterable, Sequence


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _prf(true_positive: int, predicted: int, gold: int) -> dict:
    precision = _ratio(true_positive, predicted)
    recall = _ratio(true_positive, gold)
    return {
        "true_positive": int(true_positive),
        "predicted": int(predicted),
        "gold": int(gold),
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * true_positive, predicted + gold),
    }


def _page_set(zones: Iterable[dict]) -> set[int]:
    pages = set()
    for zone in zones:
        pages.update(range(int(zone["start_page"]), int(zone["end_page"]) + 1))
    return pages


def _zone_iou(gold: dict, predicted: dict) -> float:
    gold_pages = set(range(int(gold["start_page"]), int(gold["end_page"]) + 1))
    predicted_pages = set(range(int(predicted["start_page"]), int(predicted["end_page"]) + 1))
    return _ratio(len(gold_pages & predicted_pages), len(gold_pages | predicted_pages))


def match_zones(gold_zones, predicted_zones, iou_threshold=0.50) -> dict:
    """Greedily match page intervals one-to-one by descending IoU and order.

    Page intervals are inclusive.  Sorting by the two input indexes makes exact
    IoU ties reproducible and prevents a later zone from winning arbitrarily.
    """
    gold_zones = list(gold_zones)
    predicted_zones = list(predicted_zones)
    candidates = [
        (index_gold, index_predicted, _zone_iou(gold, predicted))
        for index_gold, gold in enumerate(gold_zones)
        for index_predicted, predicted in enumerate(predicted_zones)
    ]
    candidates.sort(key=lambda item: (-item[2], item[0], item[1]))
    used_gold, used_predicted, matched = set(), set(), []
    for index_gold, index_predicted, iou in candidates:
        if iou < iou_threshold or index_gold in used_gold or index_predicted in used_predicted:
            continue
        used_gold.add(index_gold)
        used_predicted.add(index_predicted)
        matched.append({"gold_index": index_gold, "predicted_index": index_predicted, "iou": iou})
    matched.sort(key=lambda pair: (pair["gold_index"], pair["predicted_index"]))

    gold_pages = _page_set(gold_zones)
    predicted_pages = _page_set(predicted_zones)
    exact_starts = sum(
        gold_zones[pair["gold_index"]]["start_page"] == predicted_zones[pair["predicted_index"]]["start_page"]
        for pair in matched
    )
    exact_ends = sum(
        gold_zones[pair["gold_index"]]["end_page"] == predicted_zones[pair["predicted_index"]]["end_page"]
        for pair in matched
    )
    return {
        "page": _prf(len(gold_pages & predicted_pages), len(predicted_pages), len(gold_pages)),
        "iou": _prf(len(matched), len(predicted_zones), len(gold_zones)),
        "matched_pairs": matched,
        "missed_zone_count": len(gold_zones) - len(matched),
        "spurious_zone_count": len(predicted_zones) - len(matched),
        "exact_start_page": {"correct": exact_starts, "gold": len(gold_zones), "accuracy": _ratio(exact_starts, len(gold_zones))},
        "exact_end_page": {"correct": exact_ends, "gold": len(gold_zones), "accuracy": _ratio(exact_ends, len(gold_zones))},
    }


def _canonical(text: str) -> str:
    """Apply the only permitted canonicalization: soft hyphen and whitespace."""
    return " ".join(str(text).replace("\u00ad", "").split())


def _opening_text(predicted: dict) -> str:
    return str(predicted.get("reference_text", predicted.get("text", predicted.get("start_anchor", ""))))


def _boundary_match(gold: dict, predicted: dict, y_tolerance: float) -> tuple[bool, bool]:
    """Return ``(matches, used_anchor_fallback)`` for a single start pair."""
    if gold.get("start_page") != predicted.get("start_page"):
        return False, False
    gold_y = gold.get("start_y_ratio")
    predicted_y = predicted.get("start_y_ratio")
    if gold_y is not None and predicted_y is not None:
        distance = abs(float(gold_y) - float(predicted_y))
        return distance <= y_tolerance or math.isclose(distance, y_tolerance, rel_tol=0.0, abs_tol=1e-12), False
    anchor = _canonical(gold.get("start_anchor", "")).casefold()
    opening = _canonical(_opening_text(predicted)).casefold()
    return bool(anchor and opening.startswith(anchor)), True


def _monotonic_pairs(gold_refs: Sequence[dict], predicted_refs: Sequence[dict], y_tolerance: float) -> list[tuple[int, int, bool]]:
    """Find a maximum-cardinality compatible subsequence without reordering."""
    gold_n, predicted_n = len(gold_refs), len(predicted_refs)
    compatible = [[_boundary_match(gold, predicted, y_tolerance) for predicted in predicted_refs] for gold in gold_refs]
    table = [[0] * (predicted_n + 1) for _ in range(gold_n + 1)]
    for index_gold in range(gold_n - 1, -1, -1):
        for index_predicted in range(predicted_n - 1, -1, -1):
            best = max(table[index_gold + 1][index_predicted], table[index_gold][index_predicted + 1])
            if compatible[index_gold][index_predicted][0]:
                best = max(best, 1 + table[index_gold + 1][index_predicted + 1])
            table[index_gold][index_predicted] = best
    pairs = []
    index_gold = index_predicted = 0
    while index_gold < gold_n and index_predicted < predicted_n:
        matches, fallback = compatible[index_gold][index_predicted]
        if matches and table[index_gold][index_predicted] == 1 + table[index_gold + 1][index_predicted + 1]:
            pairs.append((index_gold, index_predicted, fallback))
            index_gold += 1
            index_predicted += 1
        elif table[index_gold + 1][index_predicted] >= table[index_gold][index_predicted + 1]:
            index_gold += 1
        else:
            index_predicted += 1
    return pairs


def _sequence_gap_errors(pairs: Sequence[tuple[int, int, bool]], gold_n: int, predicted_n: int) -> tuple[int, int]:
    merge_count = split_count = 0
    # Only gaps bounded by two true matches identify a split or merge.  Leading,
    # trailing, and wholly-unmatched spans are misses/spurious starts instead.
    for previous, following in zip(pairs, pairs[1:]):
        missing_gold = following[0] - previous[0] - 1
        missing_predicted = following[1] - previous[1] - 1
        if missing_gold and not missing_predicted:
            merge_count += missing_gold
        if missing_predicted and not missing_gold:
            split_count += missing_predicted
    return merge_count, split_count


def align_boundaries(gold_refs, predicted_refs, y_tolerance=0.015) -> dict:
    """Align reference starts monotonically under the frozen matching rule."""
    gold_refs, predicted_refs = list(gold_refs), list(predicted_refs)
    pairs = _monotonic_pairs(gold_refs, predicted_refs, y_tolerance)
    matched_gold = {pair[0] for pair in pairs}
    matched_predicted = {pair[1] for pair in pairs}
    merge_count, split_count = _sequence_gap_errors(pairs, len(gold_refs), len(predicted_refs))
    unresolved = sum(
        index not in matched_predicted and predicted.get("start_y_ratio") is None
        for index, predicted in enumerate(predicted_refs)
    )
    return {
        "boundary": _prf(len(pairs), len(predicted_refs), len(gold_refs)),
        "matched_pairs": [{"gold_index": gold_index, "predicted_index": predicted_index} for gold_index, predicted_index, _ in pairs],
        "missed_gold_indices": [index for index in range(len(gold_refs)) if index not in matched_gold],
        "spurious_predicted_indices": [index for index in range(len(predicted_refs)) if index not in matched_predicted],
        "missed_first_reference_count": int(bool(gold_refs) and 0 not in matched_gold),
        "missed_last_reference_count": int(bool(gold_refs) and len(gold_refs) - 1 not in matched_gold),
        "spurious_predicted_start_count": len(predicted_refs) - len(pairs),
        "merge_count": merge_count,
        "split_count": split_count,
        "anchor_fallback_match_count": sum(pair[2] for pair in pairs),
        "unresolved_predicted_start_count": unresolved,
    }


def _levenshtein(left: Sequence, right: Sequence) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, 1):
        current = [left_index]
        for right_index, right_value in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[right_index] + 1, previous[right_index - 1] + (left_value != right_value)))
        previous = current
    return previous[-1]


def text_fidelity(gold_text: str, predicted_text: str) -> dict:
    """Score visible text without deleting punctuation or substantive content."""
    gold_raw, predicted_raw = str(gold_text), str(predicted_text)
    character_errors = _levenshtein(gold_raw, predicted_raw)
    gold_words, predicted_words = gold_raw.split(), predicted_raw.split()
    word_errors = _levenshtein(gold_words, predicted_words)
    gold_canonical, predicted_canonical = _canonical(gold_raw), _canonical(predicted_raw)
    canonical_errors = _levenshtein(gold_canonical, predicted_canonical)
    return {
        "character_errors": character_errors,
        "gold_characters": len(gold_raw),
        "predicted_characters": len(predicted_raw),
        "character_error_rate": _ratio(character_errors, len(gold_raw)),
        "word_errors": word_errors,
        "gold_words": len(gold_words),
        "predicted_words": len(predicted_words),
        "word_error_rate": _ratio(word_errors, len(gold_words)),
        "canonical_levenshtein_distance": canonical_errors,
        "canonical_length": max(len(gold_canonical), len(predicted_canonical)),
        "normalized_levenshtein": 1.0 - _ratio(canonical_errors, max(len(gold_canonical), len(predicted_canonical))),
        "exact_canonical": gold_canonical == predicted_canonical,
    }


def _metric_total(metrics: Sequence[dict]) -> dict:
    true_positive = sum(int(metric.get("true_positive", 0)) for metric in metrics)
    predicted = sum(int(metric.get("predicted", 0)) for metric in metrics)
    gold = sum(int(metric.get("gold", 0)) for metric in metrics)
    return _prf(true_positive, predicted, gold)


def _text_samples(document: dict) -> list[dict]:
    value = document.get("text", document.get("text_results", []))
    if isinstance(value, dict):
        return [value]
    return list(value)


def _is_reviewed(document: dict) -> bool:
    return bool(document.get("review_required", document.get("needs_review", document.get("review", False))))


def _boundary_parts(document: dict) -> tuple[dict, dict]:
    details = document.get("boundary", document.get("boundary_result", {}))
    if "boundary" in details:
        return details["boundary"], details
    return details, details


def _detail_value(document: dict, details: dict, key: str) -> int:
    return int(details.get(key, document.get(key, 0)))


def _aggregate_documents(document_results: Sequence[dict]) -> dict:
    boundary_parts = [_boundary_parts(document) for document in document_results]
    boundaries = [metric for metric, _ in boundary_parts]
    boundary_details = [details for _, details in boundary_parts]
    zones = [document.get("zone", document.get("zone_result", {})) for document in document_results]
    boundary = _metric_total(boundaries)
    page = _metric_total([item.get("page", {}) for item in zones])
    iou = _metric_total([item.get("iou", {}) for item in zones])
    macro_f1 = statistics.fmean(float(item.get("f1", 0.0)) for item in boundaries) if boundaries else 0.0
    gold_counts = [int(document.get("gold_reference_count", item.get("gold", 0))) for document, item in zip(document_results, boundaries)]
    predicted_counts = [int(document.get("predicted_reference_count", item.get("predicted", 0))) for document, item in zip(document_results, boundaries)]
    absolute_errors = [abs(predicted - gold) for predicted, gold in zip(predicted_counts, gold_counts)]
    documents_with_references = sum(gold > 0 for gold in gold_counts)
    first_misses = sum(_detail_value(document, details, "missed_first_reference_count") for document, details in zip(document_results, boundary_details))
    last_misses = sum(_detail_value(document, details, "missed_last_reference_count") for document, details in zip(document_results, boundary_details))
    merge_count = sum(_detail_value(document, details, "merge_count") for document, details in zip(document_results, boundary_details))
    split_count = sum(_detail_value(document, details, "split_count") for document, details in zip(document_results, boundary_details))
    fallback_matches = sum(_detail_value(document, details, "anchor_fallback_match_count") for document, details in zip(document_results, boundary_details))
    unresolved_starts = sum(_detail_value(document, details, "unresolved_predicted_start_count") for document, details in zip(document_results, boundary_details))
    samples = [sample for document in document_results for sample in _text_samples(document)]
    character_errors = sum(int(sample.get("character_errors", 0)) for sample in samples)
    gold_characters = sum(int(sample.get("gold_characters", 0)) for sample in samples)
    word_errors = sum(int(sample.get("word_errors", 0)) for sample in samples)
    gold_words = sum(int(sample.get("gold_words", 0)) for sample in samples)
    canonical_exact_matches = sum(bool(sample.get("exact_canonical", False)) for sample in samples)
    reviewed = [document for document in document_results if _is_reviewed(document)]
    unreviewed = [document for document in document_results if not _is_reviewed(document)]

    def error_rate(documents: Sequence[dict]) -> float:
        if not documents:
            return 0.0
        return statistics.fmean(1.0 - float(_boundary_parts(document)[0].get("f1", 0.0)) for document in documents)

    exact_start_correct = sum(int(item.get("exact_start_page", {}).get("correct", 0)) for item in zones)
    exact_start_gold = sum(int(item.get("exact_start_page", {}).get("gold", 0)) for item in zones)
    exact_end_correct = sum(int(item.get("exact_end_page", {}).get("correct", 0)) for item in zones)
    exact_end_gold = sum(int(item.get("exact_end_page", {}).get("gold", 0)) for item in zones)
    first_reference_miss = {"missed": first_misses, "eligible": documents_with_references, "rate": _ratio(first_misses, documents_with_references)}
    last_reference_miss = {"missed": last_misses, "eligible": documents_with_references, "rate": _ratio(last_misses, documents_with_references)}

    return {
        "zone": {
            "page": page,
            "iou": iou,
            "exact_start_page": {"correct": exact_start_correct, "gold": exact_start_gold, "accuracy": _ratio(exact_start_correct, exact_start_gold)},
            "exact_end_page": {"correct": exact_end_correct, "gold": exact_end_gold, "accuracy": _ratio(exact_end_correct, exact_end_gold)},
        },
        "boundary": boundary,
        "macro_boundary_f1": macro_f1,
        "count": {
            "mae": statistics.fmean(absolute_errors) if absolute_errors else 0.0,
            "median_ae": statistics.median(absolute_errors) if absolute_errors else 0.0,
            "absolute_error_total": sum(absolute_errors),
            "exact_count_rate": _ratio(sum(error == 0 for error in absolute_errors), len(absolute_errors)),
            "exact_count_documents": sum(error == 0 for error in absolute_errors),
            "documents": len(document_results),
        },
        "first_reference_miss": first_reference_miss,
        "last_reference_miss": last_reference_miss,
        "first_reference_miss_rate": first_reference_miss["rate"],
        "last_reference_miss_rate": last_reference_miss["rate"],
        "merge_count": merge_count,
        "split_count": split_count,
        "boundary_status": {
            "anchor_fallback_matches": fallback_matches,
            "unresolved_predicted_starts": unresolved_starts,
        },
        "text": {
            "character_errors": character_errors,
            "gold_characters": gold_characters,
            "character_error_rate": _ratio(character_errors, gold_characters) if gold_characters else (statistics.fmean(float(sample.get("character_error_rate", 0.0)) for sample in samples) if samples else 0.0),
            "word_errors": word_errors,
            "gold_words": gold_words,
            "word_error_rate": _ratio(word_errors, gold_words) if gold_words else (statistics.fmean(float(sample.get("word_error_rate", 0.0)) for sample in samples) if samples else 0.0),
            "normalized_levenshtein": statistics.fmean(float(sample.get("normalized_levenshtein", 0.0)) for sample in samples) if samples else 0.0,
            "canonical_exact_matches": canonical_exact_matches,
            "exact_canonical_rate": _ratio(canonical_exact_matches, len(samples)),
            "samples": len(samples),
        },
        "review": {
            "review_documents": len(reviewed),
            "no_review_documents": len(unreviewed),
            "review_fraction": _ratio(len(reviewed), len(document_results)),
            "review_error_rate": error_rate(reviewed),
            "no_review_error_rate": error_rate(unreviewed),
            "catastrophic_no_review_errors": sum(
                int(_boundary_parts(document)[0].get("gold", 0) > 0
                    and _boundary_parts(document)[0].get("true_positive", 0) == 0)
                for document in unreviewed
            ),
        },
    }


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _at_path(summary: dict, path: Sequence[str]):
    value = summary
    for key in path:
        value = value[key]
    return value


def _ci95(resamples: Sequence[dict], path: Sequence[str]) -> list[float]:
    values = [float(_at_path(sample, path)) for sample in resamples]
    return [_percentile(values, 0.025), _percentile(values, 0.975)]


def _attach_bootstrap_intervals(summary: dict, resamples: Sequence[dict]) -> None:
    """Attach intervals from one shared set of document-level resamples."""
    for metric_path in (("zone", "page"), ("zone", "iou"), ("boundary",)):
        metric = _at_path(summary, metric_path)
        for field in ("precision", "recall", "f1"):
            metric[f"{field}_ci95"] = _ci95(resamples, (*metric_path, field))
    for metric_path in (("zone", "exact_start_page"), ("zone", "exact_end_page")):
        metric = _at_path(summary, metric_path)
        metric["accuracy_ci95"] = _ci95(resamples, (*metric_path, "accuracy"))
    summary["macro_boundary_f1_ci95"] = _ci95(resamples, ("macro_boundary_f1",))
    for field in ("mae", "median_ae", "exact_count_rate"):
        summary["count"][f"{field}_ci95"] = _ci95(resamples, ("count", field))
    for label in ("first_reference_miss", "last_reference_miss"):
        summary[label]["rate_ci95"] = _ci95(resamples, (label, "rate"))
        summary[f"{label}_ci95"] = summary[label]["rate_ci95"]
    for field in ("merge_count", "split_count"):
        summary[f"{field}_ci95"] = _ci95(resamples, (field,))
    for field in ("character_error_rate", "word_error_rate", "normalized_levenshtein", "exact_canonical_rate"):
        summary["text"][f"{field}_ci95"] = _ci95(resamples, ("text", field))
    for field in ("review_fraction", "review_error_rate", "no_review_error_rate", "catastrophic_no_review_errors"):
        summary["review"][f"{field}_ci95"] = _ci95(resamples, ("review", field))


def summarize_documents(document_results, bootstrap_seed=20260913, bootstrap_n=10000) -> dict:
    """Aggregate document results and bootstrap documents (never references)."""
    document_results = list(document_results)
    document_ids = [document.get("document_id") for document in document_results]
    if any(not document_id for document_id in document_ids):
        raise ValueError("document_id is required for document-cluster bootstrap")
    if len(set(document_ids)) != len(document_ids):
        raise ValueError("duplicate document_id in document_results")
    if bootstrap_n < 0:
        raise ValueError("bootstrap_n must be non-negative")
    summary = _aggregate_documents(document_results)
    if not document_results or bootstrap_n == 0:
        _attach_bootstrap_intervals(summary, [summary])
        return summary
    generator = random.Random(bootstrap_seed)
    resamples = []
    for _ in range(bootstrap_n):
        sample = [document_results[generator.randrange(len(document_results))] for _ in document_results]
        resamples.append(_aggregate_documents(sample))
    _attach_bootstrap_intervals(summary, resamples)
    return summary


def summarize_partitions(document_results, bootstrap_seed=20260913, bootstrap_n=10000) -> dict:
    """Summarize frozen partitions without ever pooling pilot into headlines.

    Primary is the sole headline result.  Stress and pilot remain independently
    resampled diagnostics; this keeps a small pilot from quietly changing the
    reported benchmark performance.
    """
    rows = list(document_results)
    by_partition = {
        partition: [row for row in rows if row.get("partition") == partition]
        for partition in ("primary", "stress", "pilot")
    }
    summaries = {
        partition: summarize_documents(values, bootstrap_seed=bootstrap_seed, bootstrap_n=bootstrap_n)
        for partition, values in by_partition.items()
    }
    return {"headline": summaries["primary"], "headline_observed": bool(by_partition["primary"]), **summaries}
