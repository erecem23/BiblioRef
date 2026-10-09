"""Dominant bibliography-regime helpers.

Regimes are structural descriptions, not named citation styles and not an
automatic authority to alter validated output.
"""

from __future__ import annotations

from typing import Dict


def regime_strengths(
    *,
    n_numeric: int,
    numeric_consistency: float,
    n_bracket_keys: int,
    n_author_keys: int,
    alphabetical_consistency: float,
) -> Dict[str, float]:
    numeric = float(numeric_consistency) * min(max(n_numeric, 0) / 8.0, 1.0)
    bracket = min(max(n_bracket_keys, 0) / 8.0, 1.0)
    alphabetical = float(alphabetical_consistency) * min(max(n_author_keys, 0) / 8.0, 1.0)
    return {
        "numeric": round(numeric, 3),
        "bracket_key": round(bracket, 3),
        "alphabetical": round(alphabetical, 3),
    }


def choose_dominant_regime(
    *,
    n_numeric: int,
    numeric_consistency: float,
    n_bracket_keys: int,
    n_author_keys: int,
    alphabetical_consistency: float,
) -> Dict:
    """Apply the v0.8.5-a priority: strong numeric before weak alphabetic."""
    strengths = regime_strengths(
        n_numeric=n_numeric,
        numeric_consistency=numeric_consistency,
        n_bracket_keys=n_bracket_keys,
        n_author_keys=n_author_keys,
        alphabetical_consistency=alphabetical_consistency,
    )

    strong_numeric = n_numeric >= 4 and numeric_consistency >= 0.80
    strong_bracket = n_bracket_keys >= 4
    strong_alpha = n_author_keys >= 5 and alphabetical_consistency >= 0.80
    weak_numeric = n_numeric >= 3 and numeric_consistency >= 0.60
    weak_alpha = n_author_keys >= 4 and alphabetical_consistency >= 0.65

    if strong_numeric:
        dominant = "numeric"
        strength_label = "strong"
        order_type = "numeric_order"
    elif strong_bracket:
        dominant = "bracket_key"
        strength_label = "strong"
        order_type = "bracket_key_order"
    elif strong_alpha:
        dominant = "alphabetical"
        strength_label = "strong"
        order_type = "strong_alphabetical_order"
    elif weak_numeric:
        dominant = "numeric"
        strength_label = "weak"
        order_type = "weak_numeric_order"
    elif weak_alpha:
        dominant = "alphabetical"
        strength_label = "weak"
        order_type = "weak_alphabetical_order"
    else:
        active = [name for name, value in strengths.items() if value >= 0.25]
        dominant = "mixed" if len(active) >= 2 else "unknown"
        strength_label = "ambiguous" if dominant == "mixed" else "none"
        order_type = "no_detectable_order"

    sorted_strengths = sorted(strengths.values(), reverse=True)
    margin = (sorted_strengths[0] - sorted_strengths[1]) if len(sorted_strengths) >= 2 else sorted_strengths[0]
    return {
        "dominant_regime": dominant,
        "regime_strength": strength_label,
        "order_type": order_type,
        "regime_margin": round(float(margin), 3),
        "mixed_regime": dominant == "mixed",
        "regime_strengths": strengths,
        "diagnostic_only": True,
    }


__all__ = ["regime_strengths", "choose_dominant_regime"]
