"""Conservative verification of bibliography-region candidates.

The adaptive discovery stage can find repeated text/layout patterns that merely
*look* reference-like.  This module is a separate gate: before a discovered
region is segmented in adaptive shadow mode, it asks whether several
independent bibliographic signal families converge.

Scores are explicit checklist totals, never probabilities.  The verifier is
intentionally asymmetric: false rejection means "send to audit", while a false
acceptance could make a non-bibliographic list look like a segmentation
candidate.  Therefore generic years and repeated layout are insufficient.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.adaptive.context import region_document_context
from biblioref.adaptive.order_profile import infer_order_profile
from biblioref.grammar.numeric import infer_marker_only_numeric, infer_prefix_numeric, infer_comma_numeric
from biblioref.grammar.dates import undated_author_start
from biblioref.adaptive.continuity import institutional_author_date, probable_author_without_date, dot_initial_author_date
from biblioref.legacy.engine import (
    BRACKET_KEY_RX,
    BULLET_RX,
    DOI_URL_AT_START_RX,
    NUMERIC_MARKER_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    LayoutLine,
    is_ref_heading,
)

# Source/publisher metadata that is uncommon in ordinary narrative lists.  The
# vocabulary is deliberately compact and multilingual enough for the current
# development corpus; it is evidence, not a requirement.
SOURCE_METADATA_RX = re.compile(
    r"(?:\bdoi\s*:|https?://|www\.|\b10\.\d{4,9}/|\bISBN\b|\bISSN\b|"
    r"\b(?:vol(?:umen|ume)?|n(?:ú|u)m(?:ero)?|no\.?|issue)\s*\d|"
    r"\bpp?\.?\s*\d|\b(?:editorial|publisher|press)\b|"
    r"\b(?:revista|journal|proceedings|actas?)\b|"
    r"\b(?:ed\.|eds\.|edition|edici[oó]n)\b)",
    re.I,
)

IDENTIFIER_RX = re.compile(
    r"(?:\bdoi\s*:|https?://|www\.|\b10\.\d{4,9}/|\bISBN\b|\bISSN\b)", re.I
)

LEGAL_BIBLIO_RX = re.compile(
    r"(?:\b(?:Ley|Decreto|Resoluci[oó]n|Ordenanza)\s+\d|"
    r"\bExp(?:te|ediente)\b|\bFallos?\b|\bCSJN\b|\bSala\s+[IVX\d]+\b)",
    re.I,
)

# A bibliographic date is frequently placed very early in a record, often
# after the author/institution and punctuation.  This is stronger than the mere
# presence of a year somewhere in the sentence.
DATE_AFTER_SEPARATOR_RX = re.compile(
    r"(?:[.)\]]\s*|\.\s+)(?:\(?\s*)?(?:18|19|20)\d{2}[a-z]?\)?(?:\s*[.,;:])",
    re.I,
)

# Narrative prose often integrates years with temporal prepositions.  This is
# only a negative cue; individual references may contain the same words.
NARRATIVE_YEAR_CONTEXT_RX = re.compile(
    r"\b(?:en|durante|desde|hasta|entre|hacia|during|since|between|from|in)\s+"
    r"(?:el\s+|the\s+)?(?:18|19|20)\d{2}\b",
    re.I,
)

NARRATIVE_START_RX = re.compile(
    r"^(?:el|la|los|las|un|una|unos|unas|este|esta|estos|estas|"
    r"the|this|these|a|an)\s+",
    re.I,
)


def _region_lines(lines: Sequence[LayoutLine], region: Dict) -> List[LayoutLine]:
    start_page = int(region["start_page"])
    end_page = int(region["end_page"])
    start_y = float(region.get("start_y", 0.0) or 0.0)
    page_profiles = {
        int(item["page"]): item for item in region.get("page_profiles", [])
        if item.get("page") is not None
    }

    selected: List[LayoutLine] = []
    for line in lines:
        page = int(line.page)
        if not start_page <= page <= end_page:
            continue
        if page == start_page and float(line.y0) < start_y - 4.0:
            continue
        profile = page_profiles.get(page)
        if profile and profile.get("start_margin") is not None:
            margin = float(profile["start_margin"])
            # Region verification focuses on repeated start-like lines rather
            # than wrapped continuations at deeper indentation.
            if abs(float(line.x0) - margin) > 16.0:
                continue
        text = line.text.strip()
        if not text or len(text) > 900:
            continue
        selected.append(line)
    return selected


def _nearby_reference_heading(lines: Sequence[LayoutLine], region: Dict) -> Dict:
    start_page = int(region["start_page"])
    start_y = float(region.get("start_y", 0.0) or 0.0)
    candidates = [
        line for line in lines
        if int(line.page) == start_page
        and float(line.y1) <= start_y + 2.0
        and start_y - float(line.y1) <= 150.0
        and line.text.strip()
    ]
    candidates.sort(key=lambda line: float(line.y0), reverse=True)
    for line in candidates[:12]:
        text = line.text.strip()
        if len(text) <= 140 and is_ref_heading(text):
            return {
                "found": True,
                "page": start_page,
                "text": text,
                "distance": round(max(0.0, start_y - float(line.y1)), 2),
            }
    return {"found": False, "page": start_page, "text": "", "distance": None}


def _early_date(text: str) -> bool:
    match = YEAR_RX.search(text) or SIN_FECHA_RX.search(text)
    if not match:
        return False
    limit = min(95, max(28, int(len(text) * 0.45)))
    return int(match.start()) <= limit


def _marker(text: str) -> bool:
    return bool(
        NUMERIC_MARKER_RX.match(text)
        or BRACKET_KEY_RX.match(text)
        or BULLET_RX.match(text)
    )


def _citation_punctuation(text: str) -> bool:
    # Multiple bibliographic chunks separated by periods/semicolons are a weak
    # but useful record-level cue.  Avoid counting decimal/initial noise only.
    separators = len(re.findall(r"(?:\.\s+|;\s+)", text))
    return separators >= 2


def verify_discovered_region(
    lines: Sequence[LayoutLine],
    region: Dict,
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Return an auditable bibliography-region verification decision.

    Verdicts:
    - ``verified_bibliographic_region``: enough independent evidence exists to
      permit *shadow* segmentation.  It still never authorizes auto-extraction.
    - ``plausible_but_unverified``: worth human inspection, but segmentation is
      skipped.
    - ``insufficient_bibliographic_evidence``: repeated layout/year evidence is
      not enough to proceed.
    """
    region_lines = _region_lines(lines, region)
    heading = _nearby_reference_heading(lines, region)
    document_context = region_document_context(lines, region, page_roles=page_roles)
    texts = [line.text.strip() for line in region_lines]
    n = len(texts)

    if n == 0:
        return {
            "verdict": "insufficient_bibliographic_evidence",
            "allows_shadow_segmentation": False,
            "score_0_12": 0.0,
            "score_components": [],
            "penalties": [],
            "signal_families": [],
            "n_candidate_lines": 0,
            "heading": heading,
            "metrics": {},
            "document_context": document_context,
            "reasons": ["region_has_no_start_like_lines"],
        }

    def ratio(predicate) -> float:
        return sum(bool(predicate(text)) for text in texts) / n

    early_date_ratio = ratio(_early_date)
    author_ratio = ratio(lambda text: parenthetical_author_year(text) or bare_author_year(text) or institutional_author_date(text) or dot_initial_author_date(text) or undated_author_start(text))
    order_profile = infer_order_profile(region_lines)
    marker_only_profile = infer_marker_only_numeric(region_lines)
    prefix_numeric_profile = infer_prefix_numeric(region_lines)
    comma_numeric_profile = infer_comma_numeric(region_lines)
    strong_alpha_order = order_profile.get("order_type") == "strong_alphabetical_order"
    uppercase_author_indices = [i for i, text in enumerate(texts) if probable_author_without_date(text)]
    uppercase_author_supported = 0
    for i in uppercase_author_indices:
        neighborhood = " ".join(texts[i:min(n, i + 5)])
        if YEAR_RX.search(neighborhood) or SIN_FECHA_RX.search(neighborhood) or SOURCE_METADATA_RX.search(neighborhood):
            uppercase_author_supported += 1

    marker_numbers = []
    marker_supported = 0
    for i, text in enumerate(texts):
        m = NUMERIC_MARKER_RX.match(text) or BRACKET_KEY_RX.match(text)
        if not m:
            continue
        groups = [g for g in m.groups() if g is not None]
        if groups and str(groups[0]).isdigit():
            marker_numbers.append(int(groups[0]))
        neighborhood = " ".join(texts[i:min(n, i + 4)])
        if YEAR_RX.search(neighborhood) or SIN_FECHA_RX.search(neighborhood) or SOURCE_METADATA_RX.search(neighborhood):
            marker_supported += 1
    marker_pairs = list(zip(marker_numbers, marker_numbers[1:]))
    marker_sequence_consistency = (
        sum(b == a + 1 for a, b in marker_pairs) / len(marker_pairs) if marker_pairs else 0.0
    )
    numbered_bibliography = bool(
        len(marker_numbers) >= 4
        and marker_sequence_consistency >= 0.80
        and marker_supported >= max(3, int(len(marker_numbers) * 0.75))
    )
    marker_only_bibliography = bool(marker_only_profile.get("detected"))
    prefix_numeric_bibliography = bool(prefix_numeric_profile.get("detected"))
    comma_numeric_bibliography = bool(comma_numeric_profile.get("detected"))
    source_ratio = ratio(lambda text: bool(SOURCE_METADATA_RX.search(text)))
    identifier_ratio = ratio(lambda text: bool(IDENTIFIER_RX.search(text)))
    marker_ratio = ratio(_marker)
    legal_ratio = ratio(lambda text: bool(LEGAL_BIBLIO_RX.search(text)))
    date_separator_ratio = ratio(lambda text: bool(DATE_AFTER_SEPARATOR_RX.search(text)))
    punctuation_ratio = ratio(_citation_punctuation)
    narrative_year_ratio = ratio(lambda text: bool(NARRATIVE_YEAR_CONTEXT_RX.search(text)))
    narrative_start_ratio = ratio(lambda text: bool(NARRATIVE_START_RX.search(text)))
    url_at_start_ratio = ratio(lambda text: bool(DOI_URL_AT_START_RX.match(text)))

    points = 0.0
    components: List[Dict] = []
    penalties: List[Dict] = []

    def add(condition: bool, value: float, label: str) -> None:
        nonlocal points
        if condition:
            points += value
            components.append({"check": label, "points": value})

    def subtract(condition: bool, value: float, label: str) -> None:
        nonlocal points
        if condition:
            points -= value
            penalties.append({"check": label, "points": -value})

    # Positive families. Generic layout and generic year density are never
    # sufficient by themselves.
    add(bool(heading["found"]), 4.0, "recognized_bibliography_heading_near_region")
    add(author_ratio >= 0.50, 3.0, "author_date_signature_ratio>=0.50")
    add(0.25 <= author_ratio < 0.50, 1.5, "author_date_signature_ratio>=0.25")
    add(source_ratio >= 0.50, 2.5, "source_metadata_ratio>=0.50")
    add(0.25 <= source_ratio < 0.50, 1.5, "source_metadata_ratio>=0.25")
    add(identifier_ratio >= 0.10, 1.5, "identifier_ratio>=0.10")
    add(legal_ratio >= 0.25, 2.0, "legal_bibliographic_signature_ratio>=0.25")
    add(marker_ratio >= 0.75, 1.5, "consistent_explicit_record_markers")
    add(early_date_ratio >= 0.80, 2.0, "early_date_ratio>=0.80")
    add(0.50 <= early_date_ratio < 0.80, 1.0, "early_date_ratio>=0.50")
    add(date_separator_ratio >= 0.50, 1.5, "date_after_record_separator_ratio>=0.50")
    add(punctuation_ratio >= 0.60, 1.0, "citation_like_punctuation_ratio>=0.60")
    add(url_at_start_ratio >= 0.20, 0.5, "repeated_url_or_doi_starts")
    add(strong_alpha_order, 1.5, "strong_local_alphabetical_order")
    add(uppercase_author_supported >= 6, 3.0, "six_or_more_uppercase_author_starts_with_nearby_evidence")
    add(4 <= uppercase_author_supported < 6, 2.0, "four_or_more_uppercase_author_starts_with_nearby_evidence")
    add(numbered_bibliography, 2.5, "consecutive_numbered_records_with_nearby_bibliographic_evidence")
    add(marker_only_bibliography, 3.0, "consecutive_marker_only_numeric_records_with_body_evidence")
    add(prefix_numeric_bibliography, 3.0, "consecutive_numeric_prefix_records_with_body_evidence")
    add(comma_numeric_bibliography, 3.0, "consecutive_numeric_comma_records_with_body_evidence")
    add(n >= 5, 0.5, "at_least_5_start_like_lines")

    # Negative families deliberately target the failure observed in v0.8.1:
    # aligned narrative sentences containing years.
    subtract(narrative_year_ratio >= 0.50, 4.0, "narrative_temporal_context_ratio>=0.50")
    subtract(0.25 <= narrative_year_ratio < 0.50, 2.0, "narrative_temporal_context_ratio>=0.25")
    subtract(narrative_start_ratio >= 0.60, 1.5, "narrative_sentence_start_ratio>=0.60")

    strong_nonheading_anchor = any((
        author_ratio >= 0.25,
        source_ratio >= 0.25,
        identifier_ratio >= 0.10,
        marker_ratio >= 0.75,
        date_separator_ratio >= 0.50,
        legal_ratio >= 0.25,
        uppercase_author_supported >= 4,
        numbered_bibliography,
        marker_only_bibliography,
        prefix_numeric_bibliography,
        comma_numeric_bibliography,
    ))
    subtract(
        not heading["found"] and not strong_nonheading_anchor,
        3.0,
        "no_heading_and_no_strong_bibliographic_anchor",
    )
    subtract(
        not heading["found"]
        and author_ratio == 0.0
        and source_ratio == 0.0
        and identifier_ratio == 0.0
        and marker_ratio < 0.75
        and legal_ratio == 0.0,
        2.0,
        "generic_year_layout_only",
    )

    families = []
    if heading["found"]:
        families.append("heading")
    if author_ratio >= 0.25:
        families.append("author_date")
    if source_ratio >= 0.25:
        families.append("source_metadata")
    if identifier_ratio >= 0.10:
        families.append("identifier")
    if marker_ratio >= 0.75:
        families.append("record_markers")
    if legal_ratio >= 0.25:
        families.append("legal_source")
    if date_separator_ratio >= 0.50:
        families.append("date_separator")
    if punctuation_ratio >= 0.60:
        families.append("citation_punctuation")
    if strong_alpha_order:
        families.append("alphabetical_order")
    if uppercase_author_supported >= 4:
        families.append("uppercase_author_starts")
    if numbered_bibliography:
        families.append("numbered_records")

    # A verified region needs both score and diversity. Heading/layout/markers
    # are structural evidence, not enough by themselves. At least one semantic
    # bibliographic family must be present.
    semantic_anchor = any((
        author_ratio >= 0.25,
        source_ratio >= 0.25,
        identifier_ratio >= 0.10,
        date_separator_ratio >= 0.50,
        legal_ratio >= 0.25,
        uppercase_author_supported >= 4,
        numbered_bibliography,
        marker_only_bibliography,
        prefix_numeric_bibliography,
        comma_numeric_bibliography,
    ))
    score = max(0.0, min(points, 12.0))
    bibliographic_gate = bool(score >= 7.0 and len(families) >= 2 and semantic_anchor)
    context_blocks = bool(document_context.get("strong_negative") and not heading.get("found"))
    if bibliographic_gate and not context_blocks:
        verdict = "verified_bibliographic_region"
        allows = True
        reasons = ["multiple_independent_bibliographic_signal_families_converge"]
        if document_context.get("positive_evidence"):
            reasons.append("document_context_is_structurally_compatible")
    elif bibliographic_gate and context_blocks:
        verdict = "context_conflict_requires_review"
        allows = False
        reasons = ["bibliographic_evidence_is_strong_but_document_role_is_incompatible"]
    elif score >= 4.0 and len(families) >= 1:
        verdict = "plausible_but_unverified"
        allows = False
        reasons = ["some_bibliographic_evidence_but_verification_threshold_not_met"]
    else:
        verdict = "insufficient_bibliographic_evidence"
        allows = False
        reasons = ["layout_or_year_repetition_without_sufficient_bibliographic_evidence"]

    return {
        "verdict": verdict,
        "allows_shadow_segmentation": allows,
        "score_0_12": round(score, 2),
        "score_components": components,
        "penalties": penalties,
        "signal_families": families,
        "n_candidate_lines": n,
        "heading": heading,
        "document_context": document_context,
        "metrics": {
            "early_date_ratio": round(early_date_ratio, 3),
            "author_date_signature_ratio": round(author_ratio, 3),
            "source_metadata_ratio": round(source_ratio, 3),
            "identifier_ratio": round(identifier_ratio, 3),
            "record_marker_ratio": round(marker_ratio, 3),
            "legal_bibliographic_signature_ratio": round(legal_ratio, 3),
            "date_after_separator_ratio": round(date_separator_ratio, 3),
            "citation_punctuation_ratio": round(punctuation_ratio, 3),
            "narrative_temporal_context_ratio": round(narrative_year_ratio, 3),
            "narrative_sentence_start_ratio": round(narrative_start_ratio, 3),
            "order_type": order_profile.get("order_type"),
            "alphabetical_consistency": order_profile.get("alphabetical_consistency", 0.0),
            "uppercase_author_starts_supported": uppercase_author_supported,
            "numbered_marker_count": len(marker_numbers),
            "numbered_sequence_consistency": round(float(marker_sequence_consistency), 3),
            "numbered_marker_supported": marker_supported,
        },
        "reasons": reasons,
    }
