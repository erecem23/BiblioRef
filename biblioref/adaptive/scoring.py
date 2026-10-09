"""Interpretable boundary evidence and rule-based scoring.

This module deliberately does *not* estimate probabilities.  The score is an
explicit sum of auditable pieces of evidence whose only purpose is to rank and
inspect candidate boundaries in shadow mode.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple

from biblioref.adaptive.geometry import local_bibliographic_density, vertical_gap_profile, x0_cluster_profile
from biblioref.adaptive.order_profile import infer_order_profile, local_order_evidence
from biblioref.grammar.inheritance import infer_author_inheritance
from biblioref.grammar.dates import undated_author_start
from biblioref.grammar.signatures import line_grammar_signature
from biblioref.grammar.continuation_roles import classify_continuation_role
from biblioref.adaptive.continuity import (
    institutional_author_date,
    institutional_author_late_date,
    standard_document_start,
    probable_author_without_date,
    numeric_page_continuation,
    particle_author_date,
    source_metadata_continuation,
    wrapped_author_continuation,
    wrapped_author_start,
    wrapped_date_continuation,
    publisher_year_continuation,
    conference_event_continuation,
    web_resource_start,
    dot_initial_author_date,
    implicit_inherited_title_start,
    thesis_metadata_continuation,
    split_location_publisher_continuation,
    quoted_title_continuation,
    lowercase_source_continuation,
    access_metadata_continuation,
    embedded_access_metadata_continuation,
    source_with_link_continuation,
    author_title_start,
    compact_person_author_year_start,
    journal_volume_pages_link_continuation,
    punctuation_inherited_author_start,
    late_author_title_start,
    title_led_reference_start,
    late_source_tail_continuation,
    strong_person_author_date,
)
from biblioref.detection.signals import (
    REPEATED_MARK_RX,
    bare_author_year,
    is_spaced_smallcaps_author,
    nearby_bibliographic_evidence,
    page_start_margins,
    parenthetical_author_year,
)
from biblioref.legacy.engine import (
    BRACKET_KEY_RX,
    BULLET_RX,
    DOI_URL_AT_START_RX,
    NUMERIC_MARKER_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    AdaptiveLayoutZone,
    LayoutLine,
    _is_footer,
    _is_reference_heading,
)

DATE_ONLY_ENTRY_RX = re.compile(
    r"^\(\s*(?:18|19|20)\d{2}[a-z]?(?:\s*\[[^\]]+\])?\s*\)", re.I
)
LOWERCASE_START_RX = re.compile(r"^[a-záéíóúàâêôãõçüñ]")
URLISH_START_RX = re.compile(r"^(?:https?://|www\.|doi\s*:|10\.\d{4,9}/)", re.I)

# Explicit weights.  They are configuration-like constants, not fitted model
# coefficients.  Every non-zero contribution is exposed in the output.
WEIGHTS = {
    "numeric_marker": 6.0,
    "marker_only_numeric": 6.0,
    "numeric_prefix_marker": 6.0,
    "numeric_comma_marker": 6.0,
    "bullet_marker": 6.0,
    "bracket_key": 5.0,
    "author_parenthetical_date": 3.5,
    "author_bare_date": 3.5,
    "spaced_smallcaps_author": 2.5,
    "repeated_author_mark": 2.5,
    "date_only_entry": 2.0,
    "inherited_date_indent": 2.0,
    "at_page_margin": 2.0,
    "near_page_margin": 0.75,
    "large_vertical_gap": 1.5,
    "nearby_bibliographic_evidence": 1.0,
    "capitalized_start": 0.5,
    "layout_start_bundle": 1.5,
    "inferred_left_cluster": 1.25,
    "adaptive_large_gap": 1.25,
    "high_local_density": 0.75,
    "particle_author_date": 3.5,
    "institutional_author_date": 3.5,
    "institutional_author_late_date": 4.0,
    "standard_document_start": 4.0,
    "dot_initial_author_date": 3.5,
    "undated_author_start": 3.5,
    "implicit_inherited_title_start": 4.5,
    "author_form_with_nearby_evidence": 3.0,
    "wrapped_author_start": 4.0,
    "author_title_start": 4.0,
    "compact_person_author_year_start": 3.5,
    "punctuation_inherited_author_start": 4.0,
    "late_author_title_start": 4.0,
    "title_led_reference_start": 4.0,
    "web_resource_start": 3.5,
    "alphabetical_sequence_support": 1.25,
    "starts_lowercase": -2.5,
    "urlish_start": -4.0,
    "previous_ends_colon": -1.5,
    "previous_ends_hyphen": -2.0,
    "previous_ends_linking_word": -4.0,
    "deep_indentation": -1.5,
    "wrapped_author_continuation": -5.5,
    "wrapped_date_continuation": -7.0,
    "publisher_year_continuation": -7.0,
    "conference_event_continuation": -8.0,
    "numeric_page_continuation": -8.0,
    "source_metadata_continuation": -5.0,
    "thesis_metadata_continuation": -7.0,
    "split_location_publisher_continuation": -7.0,
    "quoted_title_continuation": -7.0,
    "lowercase_source_continuation": -6.0,
    "access_metadata_continuation": -8.0,
    "embedded_access_metadata_continuation": -8.0,
    "source_with_link_continuation": -8.0,
    "journal_volume_pages_link_continuation": -8.0,
    "late_source_tail_continuation": -8.0,
    "strong_alphabetical_inversion": -1.5,
    "numeric_regime_missing_marker": -6.0,
    "bibliographic_continuation_role": -8.0,
    "bulleted_nonmarker_continuation": -8.0,
    "hanging_indent_cluster_continuation": -8.0,
    "continuation_role_start_protected": 4.5,
}


def _vertical_gap(index: int, lines: Sequence[LayoutLine]) -> float | None:
    if index <= 0:
        return None
    line = lines[index]
    previous = lines[index - 1]
    if previous.page != line.page:
        return None
    return max(0.0, float(line.y0) - float(previous.y1))


def _feature_map(
    index: int,
    zone: AdaptiveLayoutZone,
    page_margins: Dict[int, float],
    global_margin: float,
    geometry: Dict,
    order_profile: Dict,
) -> Dict[str, bool | float | str]:
    line = zone.lines[index]
    text = line.text.strip()
    previous_text = zone.lines[index - 1].text.strip() if index else ""
    margin = page_margins.get(line.page, global_margin)
    margin_delta = float(line.x0) - float(margin)
    gap = _vertical_gap(index, zone.lines)
    font = max(float(line.median_font_size or 0.0), 1.0)
    at_margin = abs(margin_delta) <= 12.0
    near_margin = abs(margin_delta) <= 24.0
    date_only = bool(DATE_ONLY_ENTRY_RX.match(text))
    nearby = nearby_bibliographic_evidence(index, zone.lines)
    x0_profile = geometry.get("x0_profile", {})
    left_center = x0_profile.get("left_cluster_center")
    cluster_tolerance = float(x0_profile.get("tolerance") or 8.0)
    inferred_left = bool(left_center is not None and abs(float(line.x0) - float(left_center)) <= cluster_tolerance)
    gap_profile = geometry.get("gap_profile", {})
    adaptive_threshold = float(gap_profile.get("adaptive_large_gap_threshold") or 0.0)
    adaptive_large_gap = bool(gap is not None and adaptive_threshold > 0 and gap >= adaptive_threshold)
    local_density = local_bibliographic_density(index, zone.lines, radius=3)
    order_ev = local_order_evidence(index, order_profile)

    parenthetical = parenthetical_author_year(text)
    bare_author = bool(bare_author_year(text) and not parenthetical)
    particle_author = particle_author_date(text)
    institutional_author = institutional_author_date(text)
    institutional_author_late = institutional_author_late_date(text)
    standard_start = standard_document_start(text)
    dot_initial_author = dot_initial_author_date(text)
    undated_author = undated_author_start(text)
    inherited_title = implicit_inherited_title_start(index, zone.lines)
    author_form_nearby = bool(
        probable_author_without_date(text)
        and nearby
        and (not text[:1].islower() or particle_author)
    )
    wrapped_author = wrapped_author_continuation(index, zone.lines)
    wrapped_start = wrapped_author_start(index, zone.lines)
    author_title = author_title_start(index, zone.lines)
    compact_author = compact_person_author_year_start(text)
    punctuation_inherited = punctuation_inherited_author_start(index, zone.lines)
    late_author_title = late_author_title_start(index, zone.lines)
    title_led_start = title_led_reference_start(index, zone.lines)
    late_source_tail = late_source_tail_continuation(index, zone.lines)
    if wrapped_author:
        late_author_title = False
        parenthetical = False
        bare_author = False
        institutional_author_late = False
    numeric_continuation = numeric_page_continuation(index, zone.lines)
    source_continuation = source_metadata_continuation(index, zone.lines)
    wrapped_date = wrapped_date_continuation(index, zone.lines)
    publisher_year = publisher_year_continuation(index, zone.lines)
    conference_event = conference_event_continuation(index, zone.lines)
    thesis_continuation = thesis_metadata_continuation(index, zone.lines)
    split_location = split_location_publisher_continuation(index, zone.lines)
    quoted_continuation = quoted_title_continuation(index, zone.lines)
    lower_source_continuation = lowercase_source_continuation(index, zone.lines)
    access_metadata = access_metadata_continuation(index, zone.lines)
    embedded_access_metadata = embedded_access_metadata_continuation(index, zone.lines)
    source_with_link = source_with_link_continuation(index, zone.lines)
    journal_link_tail = journal_volume_pages_link_continuation(index, zone.lines)
    web_start = web_resource_start(index, zone.lines)
    continuation_role = classify_continuation_role(index, zone.lines)
    grammar_signature = line_grammar_signature(text)
    previous_author_key = None
    if index > 0:
        prior_entries = [
            item for item in order_profile.get("entries", [])
            if int(item.get("line_index", -1)) < int(index) and item.get("key")
        ]
        if prior_entries:
            previous_author_key = str(prior_entries[-1]["key"])
    inheritance = infer_author_inheritance(
        text,
        previous_author_key=previous_author_key,
        previous_record_index=index - 1 if index > 0 else None,
        bibliographic_context=True,
    )
    dominant_regime = order_profile.get("dominant_regime", "unknown")
    # A page-number + DOI tail is a continuation in author-year layouts, but a
    # true numeric bibliography may legitimately contain ``89. http://...`` as
    # record 89. Regional order evidence outranks the local tail heuristic.
    if dominant_regime == "numeric" and NUMERIC_MARKER_RX.match(text):
        numeric_continuation = False
    marker_only_map = order_profile.get("marker_only_line_values", {}) or {}
    marker_only_numeric = str(index) in marker_only_map
    prefix_numeric_map = order_profile.get("prefix_numeric_line_values", {}) or {}
    numeric_prefix_marker = str(index) in prefix_numeric_map
    comma_numeric_map = order_profile.get("comma_numeric_line_values", {}) or {}
    numeric_comma_marker = str(index) in comma_numeric_map
    bullet_marker = bool(
        BULLET_RX.match(text)
        and getattr(zone.style, "style", "") == "bulleted"
        and nearby
    )

    # v0.8.9: structural continuation guards learned from the 121-thesis
    # development audit. They are deliberately geometry/style driven rather
    # than repository-specific.
    strong_explicit_start = bool(
        strong_person_author_date(text)
        or parenthetical
        or compact_author
        or particle_author
        or dot_initial_author
        or standard_start
        or undated_author
        or bool(REPEATED_MARK_RX.match(text))
        or date_only
        or marker_only_numeric
        or numeric_prefix_marker
        or numeric_comma_marker
        or bool(NUMERIC_MARKER_RX.match(text))
        or bool(BRACKET_KEY_RX.match(text))
        or bullet_marker
    )

    bulleted_nonmarker_continuation = bool(
        getattr(zone.style, "style", "") == "bulleted"
        and not bullet_marker
        and nearby
        and not strong_explicit_start
    )

    continuation_center = x0_profile.get("continuation_cluster_center")
    hanging_indent_cluster_continuation = bool(
        x0_profile.get("hanging_indent_detected")
        and continuation_center is not None
        and abs(float(line.x0) - float(continuation_center)) <= max(cluster_tolerance, 6.0)
        and nearby
        and not strong_explicit_start
    )
    # A marker admitted by the region-level comma sequence is stronger than
    # local text-role heuristics such as ``thesis metadata`` or ``publisher``.
    # Those heuristics describe the *body* of this numbered record and must not
    # veto its globally established boundary.
    if continuation_role.get("start_protected"):
        source_continuation = False
        publisher_year = False
        conference_event = False
        thesis_continuation = False
        split_location = False
        access_metadata = False
        embedded_access_metadata = False
        source_with_link = False
        journal_link_tail = False
        late_source_tail = False
    elif continuation_role.get("is_continuation"):
        # A strong continuation role can itself trigger generic start detectors
        # (e.g. a university + place + year looks like a late-date institution).
        # Neutralize only those ambiguous local positives; do not touch numeric,
        # bracket, repeated-author, or explicit person/date starts.
        role_set = set(continuation_role.get("roles") or [])
        if role_set & {
            "thesis_institution", "location_publisher", "conference_source",
            "journal_source", "journal_metadata", "document_revision",
            "access_metadata", "access_date", "thesis_title_continuation",
            "title_or_source", "institution_access", "source_with_link",
            "journal_volume_pages_link", "publisher_year_tail", "late_source_tail",
        }:
            institutional_author_late = False
            inherited_title = False
            author_form_nearby = False
            web_start = False
            if role_set & {"late_source_tail", "journal_source", "journal_metadata", "location_publisher", "thesis_institution"}:
                late_author_title = False
                title_led_start = False
            # Bare author-year is especially vulnerable to place/publisher/year
            # and institution/location/year continuations.
            if role_set & {"thesis_institution", "location_publisher", "conference_source", "journal_source", "journal_metadata"}:
                bare_author = False
    if numeric_comma_marker or bullet_marker:
        # Region-supported structural markers outrank local continuation-role
        # heuristics.  v0.8.9 extends this protection to bibliographies whose
        # stable style is explicitly bulleted (including private-use Wingdings
        # glyphs and dash-attached surnames).
        numeric_continuation = False
        source_continuation = False
        wrapped_date = False
        publisher_year = False
        conference_event = False
        thesis_continuation = False
        split_location = False
        quoted_continuation = False
        lower_source_continuation = False
        access_metadata = False
        embedded_access_metadata = False
        source_with_link = False
        journal_link_tail = False
        late_source_tail = False
    numeric_regime_missing_marker = bool(
        dominant_regime == "numeric"
        and not NUMERIC_MARKER_RX.match(text)
        and not BRACKET_KEY_RX.match(text)
        and not marker_only_numeric
        and not numeric_prefix_marker
        and not numeric_comma_marker
        and not bullet_marker
    )
    if numeric_regime_missing_marker:
        # In a strong numeric regime, unnumbered person-like body text must not
        # regain boundary authority merely through the new author-title grammar.
        author_title = False
        compact_author = False
        punctuation_inherited = False
        late_author_title = False
        title_led_start = False
    large_gap = bool(gap is not None and gap >= max(4.0, font * 0.65))
    capitalized = bool(text[:1].isupper())
    layout_bundle = bool(at_margin and large_gap and nearby and capitalized)
    return {
        "numeric_marker": bool(NUMERIC_MARKER_RX.match(text)),
        "marker_only_numeric": marker_only_numeric,
        "numeric_prefix_marker": numeric_prefix_marker,
        "numeric_comma_marker": numeric_comma_marker,
        "bullet_marker": bullet_marker,
        "bulleted_nonmarker_continuation": bulleted_nonmarker_continuation,
        "hanging_indent_cluster_continuation": hanging_indent_cluster_continuation,
        "bracket_key": bool(BRACKET_KEY_RX.match(text)),
        "author_parenthetical_date": parenthetical,
        "author_bare_date": bare_author,
        "spaced_smallcaps_author": is_spaced_smallcaps_author(text),
        "repeated_author_mark": bool(REPEATED_MARK_RX.match(text)),
        "date_only_entry": date_only,
        "inherited_date_indent": bool(date_only and margin_delta >= 18.0),
        "at_page_margin": at_margin,
        "near_page_margin": near_margin and not at_margin,
        "large_vertical_gap": large_gap,
        "nearby_bibliographic_evidence": nearby,
        "capitalized_start": capitalized,
        "layout_start_bundle": layout_bundle,
        "inferred_left_cluster": inferred_left,
        "adaptive_large_gap": adaptive_large_gap,
        "high_local_density": bool(local_density >= 0.65),
        "particle_author_date": particle_author,
        "institutional_author_date": institutional_author,
        "institutional_author_late_date": institutional_author_late,
        "standard_document_start": standard_start,
        "dot_initial_author_date": dot_initial_author,
        "undated_author_start": undated_author,
        "implicit_inherited_title_start": inherited_title,
        "author_form_with_nearby_evidence": author_form_nearby,
        "wrapped_author_start": wrapped_start,
        "author_title_start": author_title,
        "compact_person_author_year_start": compact_author,
        "punctuation_inherited_author_start": punctuation_inherited,
        "late_author_title_start": late_author_title,
        "title_led_reference_start": title_led_start,
        "alphabetical_sequence_support": bool(order_ev.get("support")),
        "strong_alphabetical_inversion": bool(order_ev.get("inversion")),
        "numeric_regime_missing_marker": numeric_regime_missing_marker,
        "bibliographic_continuation_role": bool(
            continuation_role.get("is_continuation")
            and not marker_only_numeric
            and not numeric_prefix_marker
            and not numeric_comma_marker
            and not bullet_marker
            and not NUMERIC_MARKER_RX.match(text)
            and not BRACKET_KEY_RX.match(text)
        ),
        "continuation_role_start_protected": bool(continuation_role.get("start_protected")),
        "continuation_roles": continuation_role.get("roles", []),
        "continuation_role_evidence": continuation_role.get("evidence", []),
        "continuation_role_start_kind": continuation_role.get("start_kind"),
        "wrapped_author_continuation": wrapped_author,
        "numeric_page_continuation": numeric_continuation,
        "source_metadata_continuation": source_continuation,
        "wrapped_date_continuation": wrapped_date,
        "publisher_year_continuation": publisher_year,
        "conference_event_continuation": conference_event,
        "thesis_metadata_continuation": thesis_continuation,
        "split_location_publisher_continuation": split_location,
        "quoted_title_continuation": quoted_continuation,
        "lowercase_source_continuation": lower_source_continuation,
        "access_metadata_continuation": access_metadata,
        "embedded_access_metadata_continuation": embedded_access_metadata,
        "source_with_link_continuation": source_with_link,
        "journal_volume_pages_link_continuation": journal_link_tail,
        "late_source_tail_continuation": late_source_tail,
        "web_resource_start": web_start,
        "starts_lowercase": bool(LOWERCASE_START_RX.match(text) and not particle_author),
        "urlish_start": bool(URLISH_START_RX.match(text) or DOI_URL_AT_START_RX.match(text)),
        "previous_ends_colon": previous_text.endswith(":") if previous_text else False,
        "previous_ends_hyphen": previous_text.endswith(("-", "–", "—")) if previous_text else False,
        "previous_ends_linking_word": bool(re.search(r"\b(?:de|do|da|dos|das|em|en|in|of|and|et|y|e)\s*$", previous_text, re.I)) if previous_text else False,
        "deep_indentation": bool(margin_delta >= 30.0 and not date_only),
        "margin_delta": round(margin_delta, 2),
        "vertical_gap": round(gap, 2) if gap is not None else None,
        "adaptive_gap_threshold": round(adaptive_threshold, 2),
        "local_bibliographic_density": round(float(local_density), 3),
        "inferred_left_cluster_center": left_center,
        "order_type": order_profile.get("order_type"),
        "dominant_regime": dominant_regime,
        "regime_strength": order_profile.get("regime_strength"),
        "regime_margin": order_profile.get("regime_margin", 0.0),
        "alphabetical_consistency": order_profile.get("alphabetical_consistency", 0.0),
        "numeric_consistency": order_profile.get("numeric_consistency", 0.0),
        "grammar_signals": grammar_signature.get("signals", []),
        "inheritance_candidate": bool(inheritance.get("inheritance_candidate")),
        "inheritance_type": inheritance.get("inheritance_type"),
        "order_evidence_reason": order_ev.get("reason"),
        "order_previous_key": order_ev.get("previous_key"),
        "order_current_key": order_ev.get("current_key"),
        "order_next_key": order_ev.get("next_key"),
    }


def score_boundary(features: Dict[str, bool | float | str]) -> Tuple[float, List[Dict]]:
    """Return an explicit evidence score and its non-zero contributions."""
    contributions: List[Dict] = []
    score = 0.0
    for feature, weight in WEIGHTS.items():
        if bool(features.get(feature)):
            score += weight
            contributions.append({"signal": feature, "weight": weight})
    return round(score, 2), contributions


def _semantic_anchor(features: Dict[str, bool | float | str]) -> bool:
    return any(
        bool(features.get(name))
        for name in (
            "numeric_marker",
            "marker_only_numeric",
            "numeric_prefix_marker",
            "numeric_comma_marker",
            "bullet_marker",
            "bracket_key",
            "author_parenthetical_date",
            "author_bare_date",
            "spaced_smallcaps_author",
            "repeated_author_mark",
            "date_only_entry",
            "particle_author_date",
            "institutional_author_date",
            "institutional_author_late_date",
            "standard_document_start",
            "dot_initial_author_date",
            "undated_author_start",
            "implicit_inherited_title_start",
            "author_form_with_nearby_evidence",
            "wrapped_author_start",
            "author_title_start",
            "compact_person_author_year_start",
            "punctuation_inherited_author_start",
            "late_author_title_start",
            "title_led_reference_start",
            "web_resource_start",
            "continuation_role_start_protected",
        )
    )


def collect_boundary_candidates(zone: AdaptiveLayoutZone) -> List[Dict]:
    """Describe every non-noise line as a possible record boundary.

    Candidate labels are descriptive only:
    - ``strong``: score >= 7
    - ``plausible``: score >= 5
    - ``weak``: score >= 3
    - ``continuation``: lower score

    A line becomes an active shadow boundary at score >= 5 when it has a
    semantic anchor, or >= 6.5 from convergent non-semantic evidence.
    """
    page_margins, global_margin = page_start_margins(zone)
    geometry = {
        "x0_profile": x0_cluster_profile(zone.lines),
        "gap_profile": vertical_gap_profile(zone.lines),
    }
    order_profile = infer_order_profile(zone.lines)
    output: List[Dict] = []
    for index, line in enumerate(zone.lines):
        text = line.text.strip()
        if not text or _is_footer(line) or _is_reference_heading(line):
            continue
        features = _feature_map(index, zone, page_margins, global_margin, geometry, order_profile)
        score, contributions = score_boundary(features)
        label = (
            "strong" if score >= 7.0
            else "plausible" if score >= 5.0
            else "weak" if score >= 3.0
            else "continuation"
        )
        semantic_anchor = _semantic_anchor(features)
        layout_bundle = bool(features.get("layout_start_bundle"))
        active = bool((score >= 5.0 and semantic_anchor) or (score >= 6.0 and layout_bundle))
        output.append({
            "line_index": index,
            "page": int(line.page),
            "x0": round(float(line.x0), 2),
            "y0": round(float(line.y0), 2),
            "text_preview": text[:180],
            "score": score,
            "label": label,
            "active_shadow_boundary": active,
            "semantic_anchor": semantic_anchor,
            "layout_bundle": layout_bundle,
            "contributions": contributions,
            "features": features,
        })
    return output


def evidence_summary(candidates: Sequence[Dict]) -> Dict:
    return {
        "n_lines_evaluated": len(candidates),
        "n_active_boundaries": sum(bool(item["active_shadow_boundary"]) for item in candidates),
        "n_strong": sum(item["label"] == "strong" for item in candidates),
        "n_plausible": sum(item["label"] == "plausible" for item in candidates),
        "n_weak": sum(item["label"] == "weak" for item in candidates),
    }
