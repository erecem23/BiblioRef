import pytest

from tools.human_gold.metrics import align_boundaries, match_zones, text_fidelity


def _zone(start, end):
    return {"start_page": start, "end_page": end}


def _ref(page, y, anchor):
    value = {"start_page": page, "start_anchor": anchor}
    if y is not None:
        value["start_y_ratio"] = y
    return value


def test_zone_matching_reports_exact_and_partial_page_overlap():
    result = match_zones([_zone(2, 4)], [_zone(2, 4), _zone(4, 6)])

    assert result["page"] == {
        "true_positive": 3,
        "predicted": 5,
        "gold": 3,
        "precision": 0.6,
        "recall": 1.0,
        "f1": 0.75,
    }
    assert result["iou"] == {
        "true_positive": 1,
        "predicted": 2,
        "gold": 1,
        "precision": 0.5,
        "recall": 1.0,
        "f1": pytest.approx(2 / 3),
    }
    assert result["matched_pairs"] == [{"gold_index": 0, "predicted_index": 0, "iou": 1.0}]


def test_zone_matching_counts_missed_and_extra_zones():
    result = match_zones([_zone(1, 1), _zone(3, 3)], [_zone(1, 1), _zone(5, 5)])

    assert result["missed_zone_count"] == 1
    assert result["spurious_zone_count"] == 1
    assert result["iou"]["true_positive"] == 1


def test_zone_matching_breaks_equal_iou_ties_by_input_order():
    result = match_zones([_zone(1, 2), _zone(3, 4)], [_zone(1, 4)])

    assert result["matched_pairs"] == [{"gold_index": 0, "predicted_index": 0, "iou": 0.5}]
    assert result["missed_zone_count"] == 1


def test_boundary_alignment_matches_exact_boundaries():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")],
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")],
    )

    assert result["boundary"] == {
        "true_positive": 2,
        "predicted": 2,
        "gold": 2,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert result["matched_pairs"] == [{"gold_index": 0, "predicted_index": 0}, {"gold_index": 1, "predicted_index": 1}]


def test_boundary_alignment_counts_missed_first_reference():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")], [_ref(1, 0.5, "Two")]
    )

    assert result["boundary"]["recall"] == 0.5
    assert result["missed_first_reference_count"] == 1
    assert result["missed_last_reference_count"] == 0


def test_boundary_alignment_classifies_merged_pair_from_sequence_gap():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.3, "Two"), _ref(1, 0.5, "Three")],
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Three")],
    )

    assert result["merge_count"] == 1
    assert result["split_count"] == 0


def test_boundary_alignment_classifies_split_reference_from_sequence_gap():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Three")],
        [_ref(1, 0.1, "One"), _ref(1, 0.3, "Two fragment"), _ref(1, 0.5, "Three")],
    )

    assert result["merge_count"] == 0
    assert result["split_count"] == 1
    assert result["spurious_predicted_start_count"] == 1


def test_boundary_alignment_marks_spurious_start_and_same_count_shift_as_errors():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")],
        [_ref(1, 0.1, "One"), _ref(1, 0.7, "Two")],
    )

    assert result["boundary"]["predicted"] == result["boundary"]["gold"] == 2
    assert result["boundary"]["f1"] == 0.5
    assert result["spurious_predicted_start_count"] == 1


def test_boundary_alignment_rejects_page_mismatch():
    result = align_boundaries([_ref(1, 0.1, "One")], [_ref(2, 0.1, "One")])

    assert result["boundary"]["true_positive"] == 0
    assert result["boundary"]["f1"] == 0.0


def test_boundary_alignment_uses_anchor_fallback_only_when_predicted_y_is_missing():
    result = align_boundaries(
        [_ref(1, 0.1, "García, M. (2020)")],
        [{"start_page": 1, "reference_text": "  García, M. (2020). Title"}],
    )

    assert result["boundary"]["true_positive"] == 1
    assert result["anchor_fallback_match_count"] == 1
    assert result["unresolved_predicted_start_count"] == 0


def test_boundary_alignment_counts_unresolved_prediction_when_anchor_does_not_match():
    result = align_boundaries(
        [_ref(1, 0.1, "García, M. (2020)")],
        [{"start_page": 1, "reference_text": "Different author"}],
    )

    assert result["boundary"]["true_positive"] == 0
    assert result["unresolved_predicted_start_count"] == 1


def test_boundary_alignment_accepts_the_inclusive_y_tolerance_but_rejects_just_outside_it():
    gold = [_ref(1, 0.002, "One")]

    inclusive = align_boundaries(gold, [_ref(1, 0.017, "One")])
    outside = align_boundaries(gold, [_ref(1, 0.017001, "One")])

    assert inclusive["boundary"]["true_positive"] == 1
    assert outside["boundary"]["true_positive"] == 0


def test_boundary_alignment_does_not_call_empty_or_unmatched_prefixes_split_or_merge():
    gold = [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")]
    exact_predictions = [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")]

    no_predictions = align_boundaries(gold, [])
    no_gold = align_boundaries([], exact_predictions)
    unmatched_prefix = align_boundaries(gold, [_ref(1, 0.02, "Noise"), *exact_predictions])

    for result in (no_predictions, no_gold, unmatched_prefix):
        assert result["merge_count"] == 0
        assert result["split_count"] == 0


def test_boundary_alignment_never_reorders_reversed_predictions():
    result = align_boundaries(
        [_ref(1, 0.1, "One"), _ref(1, 0.5, "Two")],
        [_ref(1, 0.5, "Two"), _ref(1, 0.1, "One")],
    )

    pairs = result["matched_pairs"]
    assert result["boundary"]["f1"] == 0.5
    assert all(left["gold_index"] < right["gold_index"] and left["predicted_index"] < right["predicted_index"]
               for left, right in zip(pairs, pairs[1:]))


def test_text_fidelity_only_normalizes_whitespace_and_soft_hyphen():
    whitespace = text_fidelity("Smith, J.\n\u00adTitle", " Smith,  J. Title ")
    punctuation = text_fidelity("Smith, J.", "Smith J.")

    assert whitespace["exact_canonical"] is True
    assert whitespace["normalized_levenshtein"] == 1.0
    assert punctuation["exact_canonical"] is False
    assert punctuation["normalized_levenshtein"] < 1.0
