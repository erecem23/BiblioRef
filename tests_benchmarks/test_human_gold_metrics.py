import pytest

from tools.human_gold.metrics import align_boundaries, match_zones, summarize_documents, text_fidelity


def _boundary(tp, predicted, gold):
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    return {
        "true_positive": tp,
        "predicted": predicted,
        "gold": gold,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def _document(document_id, tp, predicted, gold, *, review_required=False, merges=0, splits=0, missed_first=False):
    return {
        "document_id": document_id,
        "boundary": _boundary(tp, predicted, gold),
        "gold_reference_count": gold,
        "predicted_reference_count": predicted,
        "missed_first_reference_count": int(missed_first),
        "missed_last_reference_count": 0,
        "merge_count": merges,
        "split_count": splits,
        "review_required": review_required,
        "text": [{
            "character_error_rate": 0.1,
            "word_error_rate": 0.2,
            "normalized_levenshtein": 0.9,
            "exact_canonical": False,
        }],
    }


def test_summary_reports_explicit_boundary_numerators_count_errors_and_review_breakdown():
    summary = summarize_documents([
        _document("d1", 2, 2, 2, review_required=True, merges=1),
        _document("d2", 1, 2, 2, splits=1, missed_first=True),
    ], bootstrap_n=20)

    expected_boundary = {
        "true_positive": 3,
        "predicted": 4,
        "gold": 4,
        "precision": 0.75,
        "recall": 0.75,
        "f1": 0.75,
    }
    assert {key: summary["boundary"][key] for key in expected_boundary} == expected_boundary
    assert summary["macro_boundary_f1"] == 0.75
    expected_count = {
        "mae": 0.0,
        "median_ae": 0.0,
        "exact_count_rate": 1.0,
        "exact_count_documents": 2,
        "documents": 2,
    }
    assert {key: summary["count"][key] for key in expected_count} == expected_count
    assert summary["merge_count"] == 1
    assert summary["split_count"] == 1
    assert summary["first_reference_miss_rate"] == 0.5
    expected_review = {
        "review_documents": 1,
        "no_review_documents": 1,
        "review_fraction": 0.5,
        "review_error_rate": 0.0,
        "no_review_error_rate": 0.5,
        "catastrophic_no_review_errors": 0,
    }
    assert {key: summary["review"][key] for key in expected_review} == expected_review


def test_summary_aggregates_text_fidelity_metrics():
    summary = summarize_documents([_document("d1", 1, 1, 1)], bootstrap_n=20)

    assert summary["text"]["character_error_rate"] == 0.1
    assert summary["text"]["word_error_rate"] == 0.2
    assert summary["text"]["normalized_levenshtein"] == 0.9
    assert summary["text"]["exact_canonical_rate"] == 0.0
    assert summary["text"]["samples"] == 1


def test_document_cluster_bootstrap_is_deterministic():
    results = [
        _document("d1", 1, 1, 1),
        _document("d2", 0, 1, 1),
        _document("d3", 1, 2, 1),
    ]

    s1 = summarize_documents(results, bootstrap_seed=20260913, bootstrap_n=1000)
    s2 = summarize_documents(results, bootstrap_seed=20260913, bootstrap_n=1000)

    assert s1["macro_boundary_f1_ci95"] == s2["macro_boundary_f1_ci95"]
    assert len(s1["macro_boundary_f1_ci95"]) == 2
    assert s1["macro_boundary_f1_ci95"][0] <= s1["macro_boundary_f1"] <= s1["macro_boundary_f1_ci95"][1]


def test_summary_rejects_duplicate_document_ids_for_cluster_bootstrap():
    with pytest.raises(ValueError, match="duplicate document_id"):
        summarize_documents([_document("d1", 1, 1, 1), _document("d1", 1, 1, 1)], bootstrap_n=2)


def _real_document(document_id, gold_refs, predicted_refs, texts, *, review_required=False):
    return {
        "document_id": document_id,
        "zone": match_zones([{"start_page": 1, "end_page": 1}], [{"start_page": 1, "end_page": 1}]),
        "boundary": align_boundaries(gold_refs, predicted_refs),
        "gold_reference_count": len(gold_refs),
        "predicted_reference_count": len(predicted_refs),
        "text": [text_fidelity(gold, predicted) for gold, predicted in texts],
        "review_required": review_required,
    }


def test_summary_aggregates_explicit_counters_from_real_matcher_and_text_outputs():
    documents = [
        _real_document(
            "d1",
            [{"start_page": 1, "start_y_ratio": 0.1, "start_anchor": "Alpha"}],
            [{"start_page": 1, "reference_text": "Alpha title"}],
            [("alpha beta gamma delta", "alpha beta gamma")],
            review_required=True,
        ),
        _real_document(
            "d2",
            [
                {"start_page": 1, "start_y_ratio": 0.1, "start_anchor": "Beta"},
                {"start_page": 1, "start_y_ratio": 0.5, "start_anchor": "Gamma"},
            ],
            [{"start_page": 1, "reference_text": "Different author"}],
            [("one two", "one")],
        ),
    ]

    summary = summarize_documents(documents, bootstrap_n=2)

    expected_boundary = {
        "true_positive": 1,
        "predicted": 2,
        "gold": 3,
        "precision": 0.5,
        "recall": pytest.approx(1 / 3),
        "f1": 0.4,
    }
    assert {key: summary["boundary"][key] for key in expected_boundary} == expected_boundary
    assert {key: summary["first_reference_miss"][key] for key in ("missed", "eligible", "rate")} == {"missed": 1, "eligible": 2, "rate": 0.5}
    assert {key: summary["last_reference_miss"][key] for key in ("missed", "eligible", "rate")} == {"missed": 1, "eligible": 2, "rate": 0.5}
    assert summary["count"]["absolute_error_total"] == 1
    assert summary["text"]["canonical_exact_matches"] == 0
    assert summary["text"]["samples"] == 2
    assert summary["boundary_status"] == {
        "anchor_fallback_matches": 1,
        "unresolved_predicted_starts": 1,
    }

    text_samples = [sample for document in documents for sample in document["text"]]
    assert summary["text"]["character_errors"] == sum(sample["character_errors"] for sample in text_samples)
    assert summary["text"]["gold_characters"] == sum(sample["gold_characters"] for sample in text_samples)
    assert summary["text"]["character_error_rate"] == pytest.approx(
        summary["text"]["character_errors"] / summary["text"]["gold_characters"]
    )
    assert summary["text"]["word_error_rate"] == pytest.approx(
        summary["text"]["word_errors"] / summary["text"]["gold_words"]
    )


def test_bootstrap_uses_shared_document_resamples_for_all_headline_intervals():
    documents = [
        _real_document(
            "good",
            [{"start_page": 1, "start_y_ratio": 0.1, "start_anchor": "One"}],
            [{"start_page": 1, "start_y_ratio": 0.1, "start_anchor": "One"}],
            [("one two", "one two")],
        ),
        _real_document(
            "bad",
            [{"start_page": 1, "start_y_ratio": 0.1, "start_anchor": "Two"}],
            [],
            [("one two", "one")],
        ),
    ]

    # Seed 0 draws the second document twice for its one two-document resample.
    summary = summarize_documents(documents, bootstrap_seed=0, bootstrap_n=1)

    assert summary["zone"]["page"]["f1_ci95"] == [1.0, 1.0]
    assert summary["zone"]["iou"]["f1_ci95"] == [1.0, 1.0]
    assert summary["boundary"]["f1_ci95"] == [0.0, 0.0]
    assert summary["macro_boundary_f1_ci95"] == [0.0, 0.0]
    assert summary["count"]["mae_ci95"] == [1.0, 1.0]
    assert summary["first_reference_miss_ci95"] == [1.0, 1.0]
    assert summary["text"]["character_error_rate_ci95"] == [pytest.approx(4 / 7), pytest.approx(4 / 7)]
    assert summary["text"]["word_error_rate_ci95"] == [0.5, 0.5]
    assert summary["text"]["exact_canonical_rate_ci95"] == [0.0, 0.0]
