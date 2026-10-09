# -*- coding: utf-8 -*-
"""BiblioRef StyleProfiler v0.1 shadow.

The profiler observes references after parsing. It is intentionally incapable of
changing reference boundaries or parsed fields.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

from .features import extract_reference_features

STYLE_PROFILER_VERSION = "biblioref-styleprofiler-v0.1-shadow"
STYLE_PROFILE_SCHEMA_VERSION = "styleprofiler-1"
STYLE_PROFILER_STATUS = "shadow"

_BOOL_FEATURES = (
    "numbered_prefix", "bracketed_number", "year_parenthesized_after_author",
    "bare_year_after_author", "terminal_year", "uppercase_surname",
    "surname_then_initials", "initials_then_surname", "quoted_title",
    "volume_issue_pages", "year_volume_pages_sequence", "has_doi", "has_url",
    "has_access_date_cue", "place_colon_publisher", "legacy_year_final_parser_route",
    "parsed_author_present", "parsed_year_present", "parsed_journal_present",
    "parsed_publisher_present",
)


def _rate(rows: Sequence[Dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(bool(r.get(key)) for r in rows) / len(rows), 4)


def _numeric_monotonicity(rows: Sequence[Dict[str, Any]]) -> float:
    nums = [r.get("numeric_value") for r in rows if r.get("numeric_value") is not None]
    if len(nums) < 3:
        return 0.0
    good = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
    return round(good / max(1, len(nums) - 1), 4)


def _reference_guess(f: Dict[str, Any]) -> Dict[str, Any]:
    """Conservative local guess. Scores are explainable heuristics, not probabilities."""
    scores = {"apa_like": 0.0, "abnt_like": 0.0, "vancouver_like": 0.0, "ieee_like": 0.0}
    positive: List[str] = []

    if f["year_parenthesized_after_author"]:
        scores["apa_like"] += 2.0; positive.append("year_parenthesized_after_author")
    if f["surname_then_initials"]:
        scores["apa_like"] += 1.0; scores["vancouver_like"] += 0.7
    if f["uppercase_surname"]:
        scores["abnt_like"] += 2.0; positive.append("uppercase_surname")
    if f["bare_year_after_author"]:
        scores["abnt_like"] += 0.7
    if f["numbered_prefix"]:
        scores["vancouver_like"] += 1.2; scores["ieee_like"] += 1.2
    if f["bracketed_number"]:
        scores["ieee_like"] += 1.5; positive.append("bracketed_number")
    if f["year_volume_pages_sequence"]:
        scores["vancouver_like"] += 2.0; positive.append("year_volume_pages_sequence")
    if f["initials_then_surname"]:
        scores["ieee_like"] += 0.8

    best, score = max(scores.items(), key=lambda kv: kv[1])
    if score < 2.0:
        best = "unknown"
    family = "numeric" if f["numbered_prefix"] else ("author_year" if (f["parsed_year_present"] or f["year_parenthesized_after_author"] or f["terminal_year"]) else "unknown")
    variant = "legacy_year_final" if f["legacy_year_final_parser_route"] else None
    # Deliberately do not force legacy-year-final entries into a named normative style.
    if variant and best == "unknown":
        family = "author_year"
    return {
        "family": family,
        "likely_style": best,
        "variant": variant,
        "evidence_score": round(score, 3),
        "positive": positive,
    }


def profile_references(references: Sequence[Dict[str, Any]], zone_id: str = "bib-zone-01", context: Dict[str, Any] | None = None, include_references: bool = True) -> Dict[str, Any]:
    feats: List[Dict[str, Any]] = []
    ref_profiles: List[Dict[str, Any]] = []
    for idx, row in enumerate(references, 1):
        text = str(row.get("text") or row.get("reference_text") or row.get("raw_citation") or "")
        parsed = row.get("parsed") or {}
        f = extract_reference_features(text, parsed)
        feats.append(f)
        g = _reference_guess(f)
        ref_profiles.append({
            "reference_id": row.get("id") or f"r{idx:04d}",
            "order": row.get("order") or idx,
            "family": g["family"],
            "likely_style": g["likely_style"],
            "variant": g["variant"],
            "evidence_score": g["evidence_score"],
            "positive": g["positive"],
        })

    n = len(feats)
    rates = {k: _rate(feats, k) for k in _BOOL_FEATURES}
    monotonicity = _numeric_monotonicity(feats)
    style_counts = Counter(r["likely_style"] for r in ref_profiles if r["likely_style"] != "unknown")
    family_counts = Counter(r["family"] for r in ref_profiles if r["family"] != "unknown")
    variant_counts = Counter(r["variant"] for r in ref_profiles if r.get("variant"))

    style_distribution = {k: round(v / n, 4) for k, v in style_counts.items()} if n else {}
    family_distribution = {k: round(v / n, 4) for k, v in family_counts.items()} if n else {}

    dominant_style, dominant_count = (style_counts.most_common(1)[0] if style_counts else ("unknown", 0))
    dominant_family, family_count = (family_counts.most_common(1)[0] if family_counts else ("unknown", 0))
    dominant_variant, variant_count = (variant_counts.most_common(1)[0] if variant_counts else (None, 0))
    dominant_share = dominant_count / n if n else 0.0
    second_share = (style_counts.most_common(2)[1][1] / n) if len(style_counts) > 1 and n else 0.0
    mixed = bool(dominant_share < 0.85 and second_share >= 0.10)

    # Zone-level structural overrides are allowed only inside the profiler output.
    if rates.get("bracketed_number", 0) >= 0.70 and monotonicity >= 0.80:
        dominant_family = "numeric"
        if rates.get("year_volume_pages_sequence", 0) >= 0.35:
            dominant_style = "vancouver_like"
        elif rates.get("initials_then_surname", 0) >= 0.30:
            dominant_style = "ieee_like"
    elif rates.get("numbered_prefix", 0) >= 0.70 and monotonicity >= 0.80:
        dominant_family = "numeric"
        if rates.get("year_volume_pages_sequence", 0) >= 0.35:
            dominant_style = "vancouver_like"
    elif rates.get("year_parenthesized_after_author", 0) >= 0.65:
        dominant_family = "author_year"
        if rates.get("uppercase_surname", 0) >= 0.55:
            dominant_style = "abnt_like"
        elif rates.get("surname_then_initials", 0) >= 0.35:
            dominant_style = "apa_like"
    elif rates.get("legacy_year_final_parser_route", 0) >= 0.55:
        dominant_family = "author_year"
        dominant_style = "unknown"
        dominant_variant = "legacy_year_final"

    unknown_share = round(sum(r["likely_style"] == "unknown" for r in ref_profiles) / n, 4) if n else 1.0
    family_share = (family_count / n) if n else 0.0
    variant_share = (variant_count / n) if n else 0.0
    # Consistency measures structural homogeneity, not confidence in a named
    # style. A coherent unknown/local variant (e.g. Palma legacy-year-final)
    # can therefore be highly consistent without being labelled APA/ABNT/etc.
    consistency_basis = dominant_share if style_counts else max(variant_share, family_share)
    consistency = round(consistency_basis if n else 0.0, 4)
    status = "success" if n >= 3 else "insufficient_evidence"

    positive = []
    for k, v in sorted(rates.items(), key=lambda kv: kv[1], reverse=True):
        if v >= 0.50 and k not in {"has_url", "parsed_author_present", "parsed_year_present", "parsed_journal_present", "parsed_publisher_present"}:
            positive.append({"feature": k, "value": v})
        if len(positive) >= 6:
            break

    result: Dict[str, Any] = {
        "schema_version": STYLE_PROFILE_SCHEMA_VERSION,
        "profiler_version": STYLE_PROFILER_VERSION,
        "profiler_status": STYLE_PROFILER_STATUS,
        "status": status,
        "zone_id": zone_id,
        "family": "mixed" if mixed else dominant_family,
        "likely_style": "mixed" if mixed else dominant_style,
        "variant": dominant_variant,
        "confidence": None,
        "mixed_style": mixed,
        "consistency": consistency,
        "evidence": {
            "n_references": n,
            "feature_coverage": 1.0 if n else 0.0,
            "feature_rates": rates,
            "numeric_monotonicity": monotonicity,
            "positive": positive,
            "contradictory": [],
            "style_distribution": style_distribution,
            "family_distribution": family_distribution,
            "unknown_share": unknown_share,
            "note": "Heuristic shadow evidence scores are not calibrated probabilities or normative compliance scores.",
        },
        "context": {**(context or {}), "used_in_decision": False},
    }
    if include_references:
        result["references"] = ref_profiles
    return result


def profile_document(references: Sequence[Dict[str, Any]], context: Dict[str, Any] | None = None, include_references: bool = True) -> Dict[str, Any]:
    """Profile a document, respecting existing zone IDs when available."""
    by_zone: Dict[str, List[Dict[str, Any]]] = {}
    for row in references:
        zid = row.get("zone_id")
        key = str(zid if zid not in (None, "") else "unassigned")
        by_zone.setdefault(key, []).append(row)
    zones = [profile_references(rows, zone_id=key, context=context, include_references=include_references) for key, rows in by_zone.items()]
    return {
        "schema_version": STYLE_PROFILE_SCHEMA_VERSION,
        "profiler_version": STYLE_PROFILER_VERSION,
        "profiler_status": STYLE_PROFILER_STATUS,
        "status": "success" if zones else "insufficient_evidence",
        "n_zones": len(zones),
        "n_references": sum(len(v) for v in by_zone.values()),
        "zones": zones,
        "contract": {
            "mutates_extraction": False,
            "mutates_parser": False,
            "context_used_in_decision": False,
        },
    }
