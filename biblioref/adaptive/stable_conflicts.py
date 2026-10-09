"""Diagnostic-only conflicts for zones already accepted by the stable route.

BiblioRef v0.8.10 introduces this module after the SEDICI-HUM v0.8.9 error
analysis.  Its purpose is deliberately narrow: flag stable zones whose document
context or segmentation structure deserves human review.  It never removes a
zone, never rewrites a boundary, never creates a record and never changes the
validated algorithm authority (v0.6.1).

The checks are transparent rules designed around *failure families*, not around
repository names or document identifiers.  They are therefore suitable for
regression fixtures and later evaluation on unseen documents.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Sequence

from biblioref.adaptive.context import classify_document_pages
from biblioref.adaptive.continuity import probable_author_without_date
from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, SIN_FECHA_RX, YEAR_RX


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


GENERIC_REFERENCE_HEADING_RX = re.compile(
    r"^(?:referencias?|bibliografia|bibliography|bibliographie)\s*[:.\-–—]*$",
    re.I,
)
MAP_TABLE_CONTEXT_RX = re.compile(
    r"\b(?:plano|mapa|map|leyenda|legend|cuadro|tabla|table|figura|figure|grafico|gráfico)\b",
    re.I,
)
TOC_CONTEXT_RX = re.compile(
    r"^(?:indice|índice|contents|table of contents|tabla de contenidos|contenido)\b",
    re.I,
)
ABBREVIATION_CONTEXT_RX = re.compile(
    r"\b(?:abreviaturas?|abbreviations?|siglas?)\b.*\b(?:referencias?|references?)\b",
    re.I,
)
EMBEDDED_BIB_HEADING_RX = re.compile(
    r"\b(?:bibliografia|bibliografía|references?|bibliography)\b.*\b(?:obligatoria|obligatory|required|complementaria|recommended|recomendada)\b",
    re.I,
)
EMBEDDED_DOCUMENT_CONTEXT_RX = re.compile(
    r"\b(?:programa|syllabus|curso|course|asignatura|subject|materia|unidad|unit|plan de estudios|curriculum|currículo|contenidos|objetivos|evaluacion|evaluación)\b",
    re.I,
)
BODY_TRANSITION_RX = re.compile(
    r"^(?:(?:capitulo|capítulo|chapter)\s+(?:\d+|[ivxlcdm]+)\b|"
    r"(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.\-:]?\s+"
    r"(?:marco\s+teorico|marco\s+teórico|introduccion|introducción|resultados?|discusion|discusión|conclusiones?)\b)",
    re.I,
)
SOURCE_METADATA_RX = re.compile(
    r"\b(?:journal|revista|editorial|editora|press|university|universidad|vol\.?|pp?\.?|doi\b|https?://|isbn\b)\b",
    re.I,
)


def _same_page_preceding(lines: Sequence[LayoutLine], heading: LayoutLine, limit: int = 24) -> List[LayoutLine]:
    indexed = [
        line for line in lines
        if int(line.page) == int(heading.page) and float(line.y0) < float(heading.y0) and line.text.strip()
    ]
    indexed.sort(key=lambda line: float(line.y0))
    return indexed[-limit:]


def _page_text(lines: Sequence[LayoutLine], page: int) -> str:
    return " ".join(line.text.strip() for line in lines if int(line.page) == int(page) and line.text.strip())


def _heading_is_generic(heading: str) -> bool:
    return bool(GENERIC_REFERENCE_HEADING_RX.match(_norm(heading)))


def _word_counts(records: Sequence[Dict]) -> List[int]:
    return [
        len(str(item.get("reference_text", "") or "").split())
        for item in records
        if str(item.get("reference_text", "") or "").strip()
    ]


def _bibliographic_line_ratio(lines: Sequence[LayoutLine]) -> float:
    texts = [line.text.strip() for line in lines if line.text.strip()]
    if not texts:
        return 0.0
    hits = 0
    for text in texts:
        if (
            parenthetical_author_year(text)
            or bare_author_year(text)
            or probable_author_without_date(text)
            or SOURCE_METADATA_RX.search(text)
            or YEAR_RX.search(text)
            or SIN_FECHA_RX.search(text)
        ):
            hits += 1
    return hits / len(texts)


def _allcaps_author_count(lines: Sequence[LayoutLine]) -> int:
    return sum(probable_author_without_date(line.text) for line in lines if line.text.strip())


def _hyphenated_ocr_ratio(lines: Sequence[LayoutLine]) -> float:
    """Weak OCR/layout-noise cue, intentionally not an OCR classifier.

    Historical scans often contain many physical lines broken at hyphens or
    slashes.  The metric is only used together with giant unresolved stable
    segments and low bibliographic start evidence.
    """
    texts = [line.text.rstrip() for line in lines if line.text.strip()]
    if not texts:
        return 0.0
    broken = sum(bool(re.search(r"(?:[-/]|\u00ad)\s*$", text)) for text in texts)
    return broken / len(texts)


def _corrupted_token_ratio(lines: Sequence[LayoutLine]) -> float:
    """Estimate visible text-layer corruption without trying to identify OCR.

    The score is deliberately conservative.  A token is considered suspicious
    when it contains private-use/control/replacement characters, unusual symbols
    outside ordinary bibliographic punctuation, or an alphabetic word with an
    embedded digit (a common OCR substitution such as ``AUT0R``).  URLs, DOIs
    and ordinary numeric identifiers are not penalized merely for containing
    punctuation or digits.

    This metric is diagnostic only and is never used to alter effective records
    or zones.
    """
    tokens = []
    for line in lines:
        tokens.extend(str(line.text or "").split())
    if not tokens:
        return 0.0

    ordinary_punct = set(".,;:()[]{}'\"¿?¡!-/–—&%+_=*°ºª…")

    def suspicious(token: str) -> bool:
        raw = str(token or "")
        if not raw:
            return False
        norm = raw.lower()
        # Common bibliographic/access tokens often mix punctuation and digits
        # legitimately; leave those to the character-level test below.
        access_like = (
            norm.startswith(("http://", "https://", "www."))
            or "doi.org/" in norm
            or norm.startswith("doi:")
        )
        for ch in raw:
            cat = unicodedata.category(ch)
            if ch == "\ufffd" or cat in {"Co", "Cs"}:
                return True
            if cat.startswith("C") and not ch.isspace():
                return True
            if not (ch.isalpha() or ch.isdigit() or ch in ordinary_punct):
                return True
        if not access_like and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]\d|\d[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", raw):
            return True
        return False

    return sum(suspicious(token) for token in tokens) / len(tokens)


def _toc_like_page(lines: Sequence[LayoutLine], page: int) -> bool:
    """Detect continuation pages of a table of contents without requiring an INDEX heading."""
    texts = [line.text.strip() for line in lines if int(line.page) == int(page) and line.text.strip()]
    if len(texts) < 6:
        return False
    trailing_page = sum(bool(re.search(r"(?:\.{2,}|…{2,})\s*\d{1,4}\s*$", text)) for text in texts)
    chapterish = sum(bool(re.match(r"^(?:cap[ií]tulo|chapter|\d+(?:\.\d+)+)\b", _norm(text))) for text in texts)
    return trailing_page >= 6 or (trailing_page >= 4 and chapterish >= 2)


def _overlap_signals(zone_id: int, summary: Dict, all_summaries: Sequence[Dict]) -> List[Dict]:
    start = int(summary.get("start_page", 0) or 0)
    end = int(summary.get("end_page", 0) or 0)
    signals: List[Dict] = []
    if not start or not end:
        return signals
    for other in all_summaries:
        other_id = int(other.get("zone_id", 0) or 0)
        if other_id == int(zone_id):
            continue
        other_start = int(other.get("start_page", 0) or 0)
        other_end = int(other.get("end_page", 0) or 0)
        if other_start <= end and start <= other_end:
            overlap_start = max(start, other_start)
            overlap_end = min(end, other_end)
            overlap_pages = overlap_end - overlap_start + 1
            # A single shared boundary page is common when adjacent genuine
            # bibliography subsections start/end on the same PDF page.  Treat
            # overlap itself as strong only when it spans >=2 pages; one-page
            # boundary errors are still caught by explicit body-transition or
            # other context signals.
            if overlap_pages >= 2:
                signals.append({
                    "signal": "stable_zone_page_overlap",
                    "other_zone_id": other_id,
                    "overlap_start_page": overlap_start,
                    "overlap_end_page": overlap_end,
                    "overlap_pages": overlap_pages,
                })
    return signals


def diagnose_stable_context_conflict(
    document_lines: Sequence[LayoutLine],
    zone: AdaptiveLayoutZone,
    summary: Dict,
    all_summaries: Sequence[Dict],
    zone_id: int,
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Flag strong context conflicts for a stable-accepted bibliography zone.

    The verdict is advisory only.  Stable output remains untouched.
    """
    full_lines = list(document_lines or [])
    heading_text = str(summary.get("heading") or zone.heading.text or "").strip()
    heading_norm = _norm(heading_text)
    preceding = _same_page_preceding(full_lines, zone.heading)
    preceding_text = " ".join(line.text.strip() for line in preceding)
    roles = page_roles if page_roles is not None else (classify_document_pages(full_lines) if full_lines else {})
    page_role = roles.get(int(zone.start_page), {}).get("role", "unknown")
    start_page_text = _page_text(full_lines, int(zone.start_page))

    signals: List[Dict] = []
    families: List[str] = []

    # 1) TOC/front index conflict.  The role classifier is strongest when an
    # explicit INDEX/CONTENTS heading is present; the lexical fallback covers
    # headings that were visually flattened by PDF extraction.
    if (
        page_role == "toc"
        or any(TOC_CONTEXT_RX.match(_norm(line.text)) for line in preceding[:8])
        or _toc_like_page(full_lines, int(zone.start_page))
    ):
        signals.append({"signal": "stable_zone_starts_in_table_of_contents", "page": int(zone.start_page)})
        families.append("stable_route_context_false_positive")

    # 2) Map/table legend headed merely REFERENCES.  A generic heading is not
    # enough: a nearby map/table/legend lexical anchor is required.
    if _heading_is_generic(heading_text) and MAP_TABLE_CONTEXT_RX.search(preceding_text):
        signals.append({"signal": "generic_reference_heading_inside_map_or_table_context", "page": int(zone.start_page)})
        families.append("stable_route_context_false_positive")

    # 3) Abbreviations/reference-key section or a lower-case inline token that
    # looks like a heading but sits inside running prose.
    if ABBREVIATION_CONTEXT_RX.search(heading_text) or ABBREVIATION_CONTEXT_RX.search(preceding_text):
        signals.append({"signal": "abbreviation_or_reference_key_context", "page": int(zone.start_page)})
        families.append("stable_route_context_false_positive")

    lower_inline = bool(
        heading_text
        and heading_text[:1].islower()
        and _heading_is_generic(heading_text)
        and preceding
        and len(preceding[-1].text.split()) >= 8
    )
    if lower_inline:
        signals.append({"signal": "lowercase_inline_reference_token_in_running_text", "page": int(zone.start_page)})
        families.append("stable_route_context_false_positive")

    # 4) Embedded program/syllabus bibliography.  Strong only when a scoped
    # bibliography heading and nearby course/program context co-occur.
    embedded_heading = bool(EMBEDDED_BIB_HEADING_RX.search(heading_text))
    embedded_context = bool(EMBEDDED_DOCUMENT_CONTEXT_RX.search(preceding_text))
    if embedded_heading and embedded_context:
        signals.append({"signal": "embedded_course_or_syllabus_bibliography", "page": int(zone.start_page)})
        families.append("stable_route_context_false_positive")

    # 5) Stable-zone overlap.  This is a separate family because the region can
    # be genuinely bibliographic yet its boundary is duplicated/overextended.
    overlap = _overlap_signals(zone_id, summary, all_summaries)
    if overlap:
        signals.extend(overlap)
        families.append("stable_zone_overlap_end_boundary")

    # Strong body transition inside a zone: a bibliography should normally stop
    # before an explicit chapter/theory/conclusion heading.  Require it to occur
    # after at least a few zone lines so the bibliography heading itself is not
    # confused with a structural heading.
    for idx, line in enumerate(zone.lines):
        # ``zone.lines`` excludes the bibliography heading itself, so an
        # explicit chapter/body heading is strong even when it is the first
        # captured line (a characteristic overextended-boundary failure).
        if BODY_TRANSITION_RX.match(_norm(line.text)):
            signals.append({
                "signal": "explicit_body_transition_inside_stable_zone",
                "page": int(line.page),
                "text": line.text.strip()[:160],
            })
            families.append("stable_zone_overlap_end_boundary")
            break

    families = sorted(set(families))
    requires_review = bool(signals)
    return {
        "verdict": "stable_context_conflict_requires_review" if requires_review else "stable_context_compatible",
        "requires_review": requires_review,
        "diagnostic_only": True,
        "auto_apply": False,
        "failure_families": families,
        "signals": signals,
        "metrics": {
            "start_page_role": page_role,
            "generic_reference_heading": _heading_is_generic(heading_text),
            "heading_text": heading_text,
            "start_page_text_chars": len(start_page_text),
        },
    }


def diagnose_stable_segmentation_conflict(
    zone: AdaptiveLayoutZone,
    effective_records: Sequence[Dict],
    shadow_report: Dict,
) -> Dict:
    """Classify review-only segmentation failure families.

    This diagnosis consumes the already-computed shadow comparison.  It does
    not change either hypothesis.
    """
    counts = _word_counts(effective_records)
    baseline_n = len(counts)
    baseline_max = max(counts, default=0)
    baseline_giant = sum(value >= 500 for value in counts)
    shadow_eval = dict(shadow_report.get("shadow_candidate", {}) or {})
    comparison = dict(shadow_report.get("comparison", {}) or {})
    shadow_n = int(shadow_eval.get("n_segments", 0) or 0)
    candidate_safe = bool(comparison.get("candidate_passes_safety_checks"))
    status = str(comparison.get("status", ""))
    allcaps_count = _allcaps_author_count(zone.lines)
    bibliographic_ratio = _bibliographic_line_ratio(zone.lines)
    hyphen_ratio = _hyphenated_ocr_ratio(zone.lines)
    corrupted_token_ratio = _corrupted_token_ratio(zone.lines)

    signals: List[Dict] = []
    families: List[str] = []

    # Family 3: severe stable under-segmentation while a materially richer and
    # structurally safe shadow candidate exists.
    material_gain = shadow_n >= max(baseline_n + 4, baseline_n * 2 if baseline_n else 8)
    if (
        baseline_giant > 0
        and material_gain
        and candidate_safe
        and status in {"candidate_supported", "candidate_worth_reviewing", "ambiguous"}
    ):
        signals.append({
            "signal": "safe_shadow_materially_outsegments_giant_stable_baseline",
            "stable_segments": baseline_n,
            "shadow_segments": shadow_n,
            "comparison_status": status,
        })
        families.append("stable_style_hijack_missed_author_year")

    # Family 5: old all-caps/bare-author starts.  This can coexist with the
    # general style-conflict family, but is surfaced separately for fixtures.
    if (
        baseline_giant > 0
        and zone.style.style in {"author_year_bare", "author_date", "mixed", "bulleted"}
        and allcaps_count >= 4
        and allcaps_count >= max(4, int(len(zone.lines) * 0.08))
    ):
        signals.append({
            "signal": "multiple_uppercase_or_bare_author_starts_inside_giant_stable_zone",
            "uppercase_or_bare_author_start_count": allcaps_count,
        })
        families.append("older_allcaps_bare_author_chapter_bibliography")

    # Family 4: unresolved giant segments plus strong physical-line break noise,
    # weak bibliographic start evidence *and* direct evidence that the extracted
    # text layer is corrupted.  The corruption gate prevents ordinary body text
    # in an overextended zone (e.g. SEDICI-HUM-092) from being mislabeled as an
    # OCR-degraded bibliography merely because it is long.
    unresolved = not (candidate_safe and material_gain)
    ocr_layout_cue = (
        hyphen_ratio >= 0.12
        or (baseline_n <= 5 and len(zone.lines) >= 50 and bibliographic_ratio < 0.25)
    )
    ocr_text_corruption_cue = corrupted_token_ratio >= 0.08
    if (
        baseline_giant > 0
        and unresolved
        and ocr_layout_cue
        and ocr_text_corruption_cue
        and bibliographic_ratio < 0.45
    ):
        signals.append({
            "signal": "giant_stable_segments_with_corrupted_text_layer_and_weak_start_evidence",
            "hyphenated_or_slash_line_ratio": round(hyphen_ratio, 3),
            "corrupted_token_ratio": round(corrupted_token_ratio, 3),
            "bibliographic_line_ratio": round(bibliographic_ratio, 3),
        })
        families.append("ocr_degraded_scanned_bibliography")

    families = sorted(set(families))
    requires_review = bool(signals)
    return {
        "verdict": "stable_segmentation_conflict_requires_review" if requires_review else "stable_segmentation_structurally_plausible",
        "requires_review": requires_review,
        "diagnostic_only": True,
        "auto_apply": False,
        "failure_families": families,
        "signals": signals,
        "metrics": {
            "stable_segments": baseline_n,
            "stable_max_reference_words": baseline_max,
            "stable_giant_segments_500w": baseline_giant,
            "shadow_segments": shadow_n,
            "shadow_comparison_status": status,
            "shadow_candidate_safe": candidate_safe,
            "uppercase_or_bare_author_start_count": allcaps_count,
            "bibliographic_line_ratio": round(bibliographic_ratio, 3),
            "hyphenated_or_slash_line_ratio": round(hyphen_ratio, 3),
            "corrupted_token_ratio": round(corrupted_token_ratio, 3),
        },
    }


def combine_stable_conflict_diagnostics(context: Dict, segmentation: Dict) -> Dict:
    context_families = set(context.get("failure_families", []))
    segmentation = dict(segmentation)
    if "stable_route_context_false_positive" in context_families:
        # Once a strong context conflict shows that the zone is probably not a
        # thesis bibliography, do not additionally label its noisy body text as
        # an OCR-bibliography segmentation family.  The raw metrics remain
        # available in the segmentation diagnostic.
        seg_families = [
            value for value in segmentation.get("failure_families", [])
            if value != "ocr_degraded_scanned_bibliography"
        ]
        seg_signals = [
            item for item in segmentation.get("signals", [])
            if item.get("signal") != "giant_stable_segments_with_high_physical_break_noise_and_weak_start_evidence"
        ]
        segmentation["failure_families"] = seg_families
        segmentation["signals"] = seg_signals
        segmentation["requires_review"] = bool(seg_signals)
        segmentation["verdict"] = (
            "stable_segmentation_conflict_requires_review"
            if seg_signals else "stable_segmentation_structurally_plausible"
        )
    families = sorted(context_families | set(segmentation.get("failure_families", [])))
    signals = [*context.get("signals", []), *segmentation.get("signals", [])]
    requires_review = bool(context.get("requires_review") or segmentation.get("requires_review"))
    return {
        "verdict": "stable_structural_conflict_requires_review" if requires_review else "stable_structurally_plausible",
        "requires_review": requires_review,
        "diagnostic_only": True,
        "auto_apply": False,
        "failure_families": families,
        "signals": signals,
        "context": context,
        "segmentation": segmentation,
    }


def _page_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start) + 1)


def build_effective_zone_conflict_diagnostics(
    document_lines: Sequence[LayoutLine],
    layout_zones: Sequence[AdaptiveLayoutZone],
    summaries: Sequence[Dict],
    effective_records_by_zone: Dict[int, Sequence[Dict]],
    discovered_shadow_report: Dict | None = None,
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Diagnose already-effective zones even when the base method is a fallback.

    The fallback branch of the validated v0.6.1 route can still return accepted
    bibliography zones (for example ``audit_required``).  v0.8.9's adaptive
    report then focused on *discovered* regions and did not attach diagnostics to
    those effective zones.  This helper closes that observability gap without
    re-running or changing the stable extractor.

    When a discovered shadow candidate overlaps an effective zone, its existing
    comparison is reused as segmentation evidence.  No candidate is applied.
    """
    full_lines = list(document_lines or [])
    roles = page_roles if page_roles is not None else (classify_document_pages(full_lines) if full_lines else {})
    discovered = list((discovered_shadow_report or {}).get("zones", []) or [])
    zone_reports: List[Dict] = []

    for zone_id, zone in enumerate(layout_zones, 1):
        if zone_id > len(summaries):
            break
        summary = summaries[zone_id - 1]
        start = int(summary.get("start_page", zone.start_page) or zone.start_page)
        end = int(summary.get("end_page", zone.end_page) or zone.end_page)

        best = None
        best_key = (-1, -1)
        for candidate in discovered:
            region = candidate.get("discovered_region", {}) or {}
            c_start = int(region.get("start_page", 0) or 0)
            c_end = int(region.get("end_page", c_start) or c_start)
            overlap = _page_overlap(start, end, c_start, c_end)
            if overlap <= 0:
                continue
            n_segments = int((candidate.get("shadow_candidate", {}) or {}).get("n_segments", 0) or 0)
            key = (overlap, n_segments)
            if key > best_key:
                best = candidate
                best_key = key

        shadow_evidence = best if best is not None else {
            "shadow_candidate": {"n_segments": 0},
            "comparison": {
                "status": "not_available",
                "candidate_passes_safety_checks": False,
            },
        }

        context_diag = diagnose_stable_context_conflict(
            full_lines, zone, summary, summaries, zone_id, page_roles=roles
        )
        segmentation_diag = diagnose_stable_segmentation_conflict(
            zone, effective_records_by_zone.get(zone_id, []), shadow_evidence
        )
        combined = combine_stable_conflict_diagnostics(context_diag, segmentation_diag)
        zone_reports.append({
            "zone_id": zone_id,
            "heading": str(summary.get("heading", "")),
            "start_page": start,
            "end_page": end,
            "matched_discovered_region_id": (
                int((best.get("discovered_region", {}) or {}).get("region_id", 0) or 0)
                if best is not None else None
            ),
            "stable_conflict_diagnostics": combined,
        })

    context_ids = [
        item["zone_id"] for item in zone_reports
        if item["stable_conflict_diagnostics"].get("context", {}).get("requires_review")
    ]
    segmentation_ids = [
        item["zone_id"] for item in zone_reports
        if item["stable_conflict_diagnostics"].get("segmentation", {}).get("requires_review")
    ]
    structural_ids = sorted(set(context_ids) | set(segmentation_ids))
    families = sorted({
        family
        for item in zone_reports
        for family in item["stable_conflict_diagnostics"].get("failure_families", [])
    })
    return {
        "diagnostic_only": True,
        "auto_apply": False,
        "source": "effective_v0_6_1_zones_with_reused_shadow_evidence",
        "stable_context_conflict_zone_ids": context_ids,
        "stable_segmentation_conflict_zone_ids": segmentation_ids,
        "stable_structural_conflict_zone_ids": structural_ids,
        "n_stable_structural_conflicts": len(structural_ids),
        "failure_families": families,
        "zones": zone_reports,
    }
