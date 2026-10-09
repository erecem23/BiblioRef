"""Global, interpretable validation of segmentation hypotheses."""

from __future__ import annotations

import statistics
from typing import Dict, Sequence

from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import SIN_FECHA_RX, YEAR_RX


def _texts(segments: Sequence[Dict]) -> list[str]:
    return [str(item.get("reference_text", "")).strip() for item in segments if str(item.get("reference_text", "")).strip()]


def evaluate_hypothesis(segments: Sequence[Dict], name: str) -> Dict:
    """Evaluate a complete segmentation without treating the score as probability."""
    texts = _texts(segments)
    words = [len(text.split()) for text in texts]
    n = len(texts)
    evidence_count = sum(bool(YEAR_OR_SOURCE_RX.search(text) or SIN_FECHA_RX.search(text)) for text in texts)
    year_count = sum(bool(YEAR_RX.search(text) or SIN_FECHA_RX.search(text)) for text in texts)
    short = sum(value < 3 for value in words)
    very_short = sum(value < 2 for value in words)
    long = sum(value >= 180 for value in words)
    giant = sum(value >= 500 for value in words)
    evidence_ratio = evidence_count / max(n, 1)
    year_ratio = year_count / max(n, 1)
    short_ratio = short / max(n, 1)
    long_ratio = long / max(n, 1)
    median_words = float(statistics.median(words)) if words else 0.0

    if n == 0:
        return {
            "name": name,
            "n_segments": 0,
            "median_words": 0.0,
            "evidence_ratio": 0.0,
            "year_or_undated_ratio": 0.0,
            "short_segment_ratio": 0.0,
            "n_very_short_segments": 0,
            "long_segment_ratio": 0.0,
            "n_giant_segments": 0,
            "structural_score_0_10": 0.0,
            "score_components": [],
            "flags": ["no_segments"],
        }

    # Transparent 0-10 structural score.  It is a checklist summary, not a
    # calibrated probability and never decides by itself.
    points = 0.0
    checks = []

    def add(condition: bool, value: float, label: str) -> None:
        nonlocal points
        if condition:
            points += value
            checks.append({"check": label, "points": value})

    add(evidence_ratio >= 0.85, 3.0, "evidence_ratio>=0.85")
    add(0.65 <= evidence_ratio < 0.85, 2.0, "evidence_ratio>=0.65")
    add(0.50 <= evidence_ratio < 0.65, 1.0, "evidence_ratio>=0.50")
    add(3 <= median_words <= 140, 2.0, "median_words_plausible")
    add(giant == 0, 2.0, "no_giant_segments")
    add(short_ratio <= 0.05, 1.5, "few_short_segments")
    add(long_ratio <= 0.10, 1.0, "few_long_segments")
    add(year_ratio >= 0.55, 0.5, "year_or_undated_in_majority")

    flags = []
    if giant:
        flags.append("giant_segments")
    if short_ratio > 0.10:
        flags.append("many_short_segments")
    if evidence_ratio < 0.55:
        flags.append("low_bibliographic_evidence")
    if not 3 <= median_words <= 140:
        flags.append("implausible_median_length")

    return {
        "name": name,
        "n_segments": n,
        "median_words": round(median_words, 2),
        "evidence_ratio": round(evidence_ratio, 3),
        "year_or_undated_ratio": round(year_ratio, 3),
        "short_segment_ratio": round(short_ratio, 3),
        "n_very_short_segments": very_short,
        "long_segment_ratio": round(long_ratio, 3),
        "n_giant_segments": giant,
        "structural_score_0_10": round(min(points, 10.0), 2),
        "score_components": checks,
        "flags": flags,
    }


def compare_hypotheses(baseline: Dict, candidate: Dict) -> Dict:
    """Conservative comparison used only to classify the shadow finding."""
    count_delta = int(candidate["n_segments"]) - int(baseline["n_segments"])
    score_delta = float(candidate["structural_score_0_10"]) - float(baseline["structural_score_0_10"])
    evidence_delta = float(candidate["evidence_ratio"]) - float(baseline["evidence_ratio"])
    short_delta = float(candidate["short_segment_ratio"]) - float(baseline["short_segment_ratio"])

    candidate_safe = (
        candidate["n_giant_segments"] == 0
        and candidate["evidence_ratio"] >= 0.55
        and candidate["short_segment_ratio"] <= 0.12
        and 3 <= candidate["median_words"] <= 140
    )
    baseline_weak = (
        baseline["structural_score_0_10"] < 6.0
        or baseline["n_giant_segments"] > 0
        or baseline["evidence_ratio"] < 0.55
    )

    reasons = []
    status = "stable_preferred"
    baseline_available = int(baseline["n_segments"]) > 0
    if not baseline_available and candidate_safe and int(candidate["n_segments"]) >= 2:
        # With no baseline segmentation there is nothing substantive to beat.
        # Structural plausibility is enough to surface the candidate, but not
        # to call it "supported".  It remains review-only.
        status = "candidate_worth_reviewing"
        reasons.append("candidate_is_structurally_plausible_but_no_baseline_exists")
    elif candidate_safe and count_delta >= 2 and score_delta >= 1.0 and evidence_delta >= -0.05:
        status = "candidate_supported"
        reasons.append("candidate_improves_structure_with_material_boundary_gain")
    elif baseline_weak and candidate["structural_score_0_10"] < 6.0:
        status = "manual_review_required"
        reasons.append("neither_hypothesis_is_structurally_strong")
    elif count_delta >= 2 and abs(score_delta) < 1.0:
        status = "ambiguous"
        reasons.append("material_boundary_difference_without_clear_structural_winner")
    elif count_delta >= 2 and candidate_safe and evidence_delta >= 0.0 and short_delta <= 0.03:
        status = "candidate_worth_reviewing"
        reasons.append("candidate_adds_boundaries_without_obvious_global_penalty")
    else:
        reasons.append("no_safe_material_improvement_over_effective_baseline")

    return {
        "status": status,
        "auto_apply": False,
        "requires_review": status in {
            "candidate_supported",
            "candidate_worth_reviewing",
            "ambiguous",
            "manual_review_required",
        },
        "n_segment_delta": count_delta,
        "structural_score_delta": round(score_delta, 2),
        "evidence_ratio_delta": round(evidence_delta, 3),
        "short_segment_ratio_delta": round(short_delta, 3),
        "candidate_passes_safety_checks": candidate_safe,
        "reasons": reasons,
    }
