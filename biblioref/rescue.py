"""Selective post-extraction rescue router for BiblioRef v0.9.3.

The v0.9.0 effective extraction path is always produced first; its effective algorithm remains v0.6.1.  Holdout-derived
heuristics live here as optional, explainable rescue profiles.  They are never
silently promoted into the default path.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import copy
import re
from typing import Callable, Dict, Iterable, List, Sequence

from biblioref.adaptive.geometry import detect_repeated_decorations, _norm
from biblioref.adaptive.stable_conflicts import _corrupted_token_ratio
from biblioref.adaptive.two_pass import cheap_page_profiles
from biblioref.core.patterns import YEAR_OR_SOURCE_RX
from biblioref.detection.repair import repair_decision
from biblioref.extraction.effective_repairs import (
    build_author_year_boundary_repair,
    build_repeated_decoration_repair,
    build_vertical_gap_repair,
    strong_appendix_guideline_conflict,
    toc_reference_coverage,
)
from biblioref.extraction.column_reflow import (
    build_column_reflow_repair,
    build_column_reflow_repair_v2,
)
from biblioref.extraction.numeric_rescue import (
    build_numeric_layout_resegmentation,
    numeric_filter_candidate,
    numeric_filter_support,
)
from biblioref.extraction.structural_reconciliation import (
    structural_reconciliation_plan,
    build_trimmed_zone,
)
from biblioref.ingestion import extract_layout_lines
from biblioref.legacy.engine import (
    SCOPE_DEFINITIONS,
    _annotate_duplicates,
    _numeric_sequence_diagnostics,
    _select_scope,
    classify_zone_role,
    detect_adaptive_layout_zones,
    is_ref_heading,
    segment_adaptive_layout_zone,
    diagnose_adaptive_style,
    diagnose_adaptive_layout,
)

RESCUE_PROFILES = (
    "stable",
    "heading_artifact",
    "continuation_density",
    "numeric_filter",
    "numeric_layout_resegmentation",
    "multi_column_reflow_v2",
    "structural_zone_reconciliation",
    "repeated_decoration",
    "vertical_gap",
    "author_year_boundary",
    "appendix_context",
)

# Backward-compatible explicit profile names from v0.9.2. They remain callable
# but are not shown in the normal rescue menu and are never recommended.
RESCUE_COMPAT_ALIASES = ("numeric_sequence", "multi_column_reflow")
VALID_RESCUE_PROFILES = RESCUE_PROFILES + RESCUE_COMPAT_ALIASES


PROFILE_LABELS = {
    "stable": "Ruta efectiva v0.9.0 (sin rescate)",
    "heading_artifact": "Recuperar encabezado dañado por PDF",
    "continuation_density": "Extender zona por continuidad bibliográfica",
    "numeric_filter": "Filtrar límites numéricos falsos con secuencia completa",
    "numeric_layout_resegmentation": "Resegmentar numeración desde el layout",
    "multi_column_reflow_v2": "Releer bibliografía en columnas (v2)",
    "structural_zone_reconciliation": "Reconciliar índice, zonas y nuevos capítulos",
    "repeated_decoration": "Filtrar encabezados/pies repetidos",
    "vertical_gap": "Separar referencias por espacio vertical",
    "author_year_boundary": "Reparar límites autor-año (números + espaciado)",
    "appendix_context": "Excluir References dentro de guías/apéndices",
    "numeric_sequence": "[Compatibilidad v0.9.2] Depurar numeración",
    "multi_column_reflow": "[Compatibilidad v0.9.2] Releer dos columnas",
}


_ARTIFACT_REF_RX = re.compile(
    r"^\s*\d{1,4}[A-Za-z]\s*(?P<body>(?:[IVXLCDM]{1,8}|\d{1,3})(?:[.\-:]|\s).*)$",
    re.I,
)


def _record_quality(records: Sequence[Dict]) -> Dict:
    texts = [str(r.get("reference_text", "")).strip() for r in records if str(r.get("reference_text", "")).strip()]
    evidence = sum(bool(YEAR_OR_SOURCE_RX.search(t)) for t in texts)
    giant = sum(len(t.split()) >= 500 for t in texts)
    numeric_starts = sum(bool(re.match(r"^\s*\d{1,4}\s*[.)]\s+", t)) for t in texts)
    return {
        "n_records": len(texts),
        "evidence_ratio": round(evidence / max(1, len(texts)), 3),
        "n_giant_records": giant,
        "n_numeric_like_starts": numeric_starts,
    }


def _base_records_by_zone(result: Dict) -> Dict[int, List[Dict]]:
    output: Dict[int, List[Dict]] = defaultdict(list)
    # all-reference-sections is the diagnostic source; caller should pass that
    # baseline whenever possible.
    for record in result.get("records", []):
        output[int(record.get("zone_id", 0))].append(record)
    return output


def _summary_from_layout(zone, zone_id: int, segments: Sequence[Dict]) -> Dict:
    summary = {
        "zone_id": zone_id,
        "heading": zone.heading.text,
        "zone_role": classify_zone_role(zone.heading.text),
        "start_page": zone.start_page,
        "end_page": zone.end_page,
        "style": zone.style.style,
        "n_segments": len(segments),
        "termination_reason": zone.termination_reason,
        "zone_completeness": zone.zone_completeness,
        "start_confidence_score": zone.start_confidence_score,
        "start_confidence_label": zone.start_confidence_label,
        "start_confidence_reasons": zone.start_confidence_reasons,
        "end_confidence_score": zone.end_confidence_score,
        "end_confidence_label": zone.end_confidence_label,
        "end_confidence_reasons": zone.end_confidence_reasons,
        "combined_confidence_score": zone.confidence_score,
        "combined_confidence_label": zone.confidence_label,
        "adaptive_soft_limit_pages": zone.adaptive_soft_limit_pages,
        "zone_span_pages": zone.zone_span_pages,
        "adaptive_limit_exceeded": zone.adaptive_limit_exceeded,
        "confidence_reasons": zone.confidence_reasons,
        "start_margin": zone.layout.start_margin,
        "start_margin_tolerance": zone.layout.start_margin_tolerance,
        "bibliography_font_size": zone.layout.bibliography_font_size,
        "continuation_margin": zone.layout.continuation_margin,
        "candidate_support": zone.layout.candidate_support,
        "hanging_indent_detected": zone.layout.hanging_indent_detected,
    }
    if zone.style.style == "numeric":
        summary.update(_numeric_sequence_diagnostics(list(segments)))
    return summary


def _attach_zone_metadata(segment: Dict, zone_id: int, ref_in_zone: int, summary: Dict) -> Dict:
    record = dict(segment)
    record.update({
        "zone_id": zone_id,
        "ref_in_zone": ref_in_zone,
        "zone_heading": summary["heading"],
        "zone_role": summary["zone_role"],
        "zone_start_page": summary["start_page"],
        "zone_end_page": summary["end_page"],
        "zone_start_confidence_score": summary.get("start_confidence_score"),
        "zone_start_confidence_label": summary.get("start_confidence_label"),
        "zone_end_confidence_score": summary.get("end_confidence_score"),
        "zone_end_confidence_label": summary.get("end_confidence_label"),
        "zone_completeness": summary.get("zone_completeness"),
        "zone_termination_reason": summary.get("termination_reason"),
        "zone_adaptive_limit_exceeded": summary.get("adaptive_limit_exceeded"),
    })
    return record


def _rebuild(base: Dict, zones: List[Dict], records: List[Dict], scope: str, profile: str, details: Dict) -> Dict:
    occurrences, duplicate_groups = _annotate_duplicates(records)
    active_ids = sorted({int(z.get("zone_id", 0)) for z in zones})
    final_id = max(active_ids) if active_ids else None
    selected = _select_scope(occurrences, scope, final_zone_id=final_id)
    result = copy.deepcopy(base)
    result.update({
        "scope": scope,
        "scope_definition": SCOPE_DEFINITIONS[scope],
        "n_zones": len(zones),
        "n_occurrences_all_zones": len(occurrences),
        "n_unique_references": len(_select_scope(occurrences, "unique_references")),
        "n_duplicate_groups": len(duplicate_groups),
        "n_occurrences_in_duplicate_groups": sum(g["occurrence_count"] for g in duplicate_groups),
        "n_repeated_occurrences_beyond_first": sum(g["occurrence_count"] - 1 for g in duplicate_groups),
        "n_records_selected": len(selected),
        "zones": zones,
        "records": selected,
        "duplicate_groups": duplicate_groups,
        "rescue_applied": {
            "profile": profile,
            "label": PROFILE_LABELS[profile],
            "explicit": True,
            **details,
        },
    })
    result["detection_decision"] = {
        **dict(base.get("detection_decision", {})),
        "method": f"selective_rescue_{profile}",
        "requires_confirmation": True,
        "reason": "explicit_user_selected_rescue_profile",
    }
    return result


def _apply_zone_repair(pdf_path, base: Dict, scope: str, profile: str, builder: Callable) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements: Dict[int, List[Dict]] = {}
    reports = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        base_records = by_zone.get(zone_id, [])
        attempt = builder(layout_zone, lines, base_records) if profile == "repeated_decoration" else builder(layout_zone, base_records)
        reports.append({"zone_id": zone_id, "heading": summary.get("heading", ""), **{k:v for k,v in attempt.items() if k != "segments"}})
        if not attempt.get("accepted"):
            continue
        candidate = attempt.get("segments", [])
        summary["n_segments"] = len(candidate)
        summary["segmentation_method"] = f"selective_rescue_{profile}"
        replacements[zone_id] = [
            _attach_zone_metadata(seg, zone_id, i, summary)
            for i, seg in enumerate(candidate, 1)
        ]
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile": profile, "label": PROFILE_LABELS[profile], "explicit": True, "changed": False, "reports": reports}
        return unchanged
    records = []
    for zone_id in range(1, len(summaries)+1):
        records.extend(replacements.get(zone_id, by_zone.get(zone_id, [])))
    return _rebuild(base, summaries, records, scope, profile, {"changed": True, "reports": reports})


def _artifact_normalized_lines(lines):
    changed = []
    hits = []
    for line in lines:
        m = _ARTIFACT_REF_RX.match(line.text.strip())
        if not m:
            changed.append(line)
            continue
        body = m.group("body").strip()
        # Only alter lines where stripping the compact PDF token reveals a real
        # reference heading. Ordinary numbered text is left untouched.
        if is_ref_heading(body):
            changed.append(replace(line, text=body))
            hits.append({"page": int(line.page), "original": line.text, "normalized": body})
        else:
            changed.append(line)
    return changed, hits


def _apply_heading_artifact(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    normalized, hits = _artifact_normalized_lines(lines)
    if not hits:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"heading_artifact","label":PROFILE_LABELS["heading_artifact"],"explicit":True,"changed":False,"hits":[]}
        return unchanged
    zones = detect_adaptive_layout_zones(normalized)
    if len(zones) <= int(base.get("n_zones", 0)):
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"heading_artifact","label":PROFILE_LABELS["heading_artifact"],"explicit":True,"changed":False,"hits":hits,"candidate_zones":len(zones)}
        return unchanged
    summaries: List[Dict] = []
    records: List[Dict] = []
    for zone_id, zone in enumerate(zones, 1):
        segments = segment_adaptive_layout_zone(zone)
        summary = _summary_from_layout(zone, zone_id, segments)
        summaries.append(summary)
        records.extend(_attach_zone_metadata(seg, zone_id, i, summary) for i, seg in enumerate(segments,1))
    return _rebuild(base, summaries, records, scope, "heading_artifact", {"changed": True, "hits": hits})


def _apply_appendix_context(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    blocked = []
    for zone_id, zone in enumerate(layout_zones, 1):
        gate = strong_appendix_guideline_conflict(zone, lines)
        if gate.get("blocked"):
            blocked.append({"zone_id":zone_id,"heading":zone.heading.text,**gate})
    if not blocked:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"appendix_context","label":PROFILE_LABELS["appendix_context"],"explicit":True,"changed":False,"blocked":[]}
        return unchanged
    blocked_ids = {int(x["zone_id"]) for x in blocked}
    zones = [dict(z) for z in base.get("zones", []) if int(z.get("zone_id",0)) not in blocked_ids]
    records = [dict(r) for r in base.get("records", []) if int(r.get("zone_id",0)) not in blocked_ids]
    return _rebuild(base, zones, records, scope, "appendix_context", {"changed": True, "blocked": blocked})




def _layout_page_profiles(lines: Sequence) -> List[Dict]:
    """Cheap density profiles from the already parsed layout; no second PDF open."""
    by_page: Dict[int, List] = defaultdict(list)
    for line in lines:
        by_page[int(line.page)].append(line)
    page_count = max(by_page, default=0)
    profiles: List[Dict] = []
    for page in range(1, page_count + 1):
        items = [x for x in by_page.get(page, []) if str(getattr(x, "text", "")).strip()]
        evidence = 0
        url_doi = 0
        heading = False
        chars = 0
        for line in items:
            text = str(line.text).strip()
            chars += len(text)
            if is_ref_heading(text):
                heading = True
            has_url = bool(re.search(r"(?:https?://|www\.|doi\s*:|10\.\d{4,9}/)", text, re.I))
            has_year = bool(YEAR_OR_SOURCE_RX.search(text))
            url_doi += int(has_url)
            evidence += int(has_url or has_year)
        n = len(items)
        profiles.append({
            "page": page, "heading_hit": heading, "evidence_lines": evidence,
            "evidence_density": round(evidence / n, 4) if n else 0.0,
            "url_doi_lines": url_doi, "char_count": chars,
        })
    return profiles

def _proposed_density_extension(profiles: Sequence[Dict], end_page: int) -> Dict:
    """Find a strong bibliographic-density run immediately after a detected zone."""
    if end_page >= len(profiles):
        return {"eligible": False, "reason": "zone_reaches_document_end"}
    def strong(page_no: int) -> bool:
        p = profiles[page_no - 1]
        return int(p.get("evidence_lines", 0)) >= 8 and float(p.get("evidence_density", 0.0)) >= 0.30
    if end_page + 2 > len(profiles) or not (strong(end_page + 1) and strong(end_page + 2)):
        return {"eligible": False, "reason": "no_two_page_post_zone_density_run"}
    proposed = end_page
    weak_run = 0
    evidence = []
    for page_no in range(end_page + 1, len(profiles) + 1):
        p = profiles[page_no - 1]
        is_strong = strong(page_no)
        evidence.append({"page": page_no, "evidence_lines": p.get("evidence_lines"), "density": p.get("evidence_density")})
        if is_strong:
            proposed = page_no
            weak_run = 0
        else:
            weak_run += 1
            if weak_run >= 1:
                break
    gain = proposed - end_page
    return {
        "eligible": gain >= 2,
        "reason": "strong_reference_density_continues_after_detected_zone" if gain >= 2 else "insufficient_extension",
        "base_end_page": end_page,
        "proposed_end_page": proposed,
        "extension_pages": gain,
        "evidence": evidence[:6],
    }


def _apply_continuation_density(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    profiles, _ = cheap_page_profiles(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements: Dict[int, List[Dict]] = {}
    reports = []
    for zone_id, (zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        ext = _proposed_density_extension(profiles, int(summary.get("end_page", zone.end_page)))
        report = {"zone_id": zone_id, "heading": summary.get("heading", ""), **ext}
        if not ext.get("eligible"):
            reports.append(report)
            continue
        proposed_end = int(ext["proposed_end_page"])
        extra = [line for line in lines if int(zone.end_page) < int(line.page) <= proposed_end]
        candidate_lines = list(zone.lines) + extra
        style = diagnose_adaptive_style([line.text for line in candidate_lines])
        layout = diagnose_adaptive_layout(candidate_lines, style)
        candidate_zone = replace(
            zone, lines=candidate_lines, end_page=proposed_end, style=style, layout=layout,
            termination_reason="selective_rescue_continuation_density",
            zone_span_pages=proposed_end - int(zone.start_page) + 1,
        )
        segments = segment_adaptive_layout_zone(candidate_zone)
        q = _record_quality(segments)
        base_n, new_n = len(by_zone.get(zone_id, [])), len(segments)
        accepted = bool(
            new_n >= base_n + 5
            and q.get("n_giant_records", 0) == 0
            and float(q.get("evidence_ratio", 0.0)) >= 0.75
        )
        report.update({"accepted": accepted, "base_records": base_n, "candidate_records": new_n, **q})
        reports.append(report)
        if not accepted:
            continue
        summary["end_page"] = proposed_end
        summary["n_segments"] = new_n
        summary["segmentation_method"] = "selective_rescue_continuation_density"
        replacements[zone_id] = [
            _attach_zone_metadata(seg, zone_id, i, summary)
            for i, seg in enumerate(segments, 1)
        ]
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"continuation_density","label":PROFILE_LABELS["continuation_density"],"explicit":True,"changed":False,"reports":reports}
        return unchanged
    records = []
    for zone_id in range(1, len(summaries)+1):
        records.extend(replacements.get(zone_id, by_zone.get(zone_id, [])))
    return _rebuild(base, summaries, records, scope, "continuation_density", {"changed": True, "reports": reports})


def _leading_numeric_value(text: str):
    m = re.match(r"^\s*\[?(\d{1,4})\]?\s*[.)]?\s+", str(text or ""))
    return int(m.group(1)) if m else None


def _numeric_sequence_support(records: Sequence[Dict]) -> Dict:
    """Backward-compatible wrapper around v0.9.3 ``numeric_filter``."""
    support = numeric_filter_support(records)
    extras = support.get("extras", [])
    return {
        **support,
        "outliers": [
            {"position": int(item.get("record_position", -1)), "value": int(item.get("value", 0))}
            for item in extras
        ],
    }


def _numeric_sequence_candidate(records: Sequence[Dict]) -> Dict:
    """Backward-compatible wrapper around v0.9.3 ``numeric_filter``."""
    candidate = numeric_filter_candidate(records)
    candidate.setdefault("enhanced_sequence_score", 1.0 if candidate.get("accepted") else 0.0)
    candidate.setdefault("outliers", [
        {"position": int(item.get("record_position", -1)), "value": int(item.get("value", 0))}
        for item in candidate.get("extras", [])
    ])
    return candidate


def _apply_numeric_filter(base: Dict, scope: str, profile: str = "numeric_filter") -> Dict:
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements = {}
    reports = []
    for summary in summaries:
        zone_id = int(summary.get("zone_id", 0) or 0)
        base_records = by_zone.get(zone_id, [])
        if not base_records:
            continue
        attempt = numeric_filter_candidate(base_records)
        reports.append({"zone_id": zone_id, "heading": summary.get("heading", ""), **{k:v for k,v in attempt.items() if k != "segments"}})
        if not attempt.get("accepted"):
            continue
        candidate = attempt["segments"]
        summary["n_segments"] = len(candidate)
        summary["segmentation_method"] = f"selective_rescue_{profile}"
        if str(summary.get("style", "")) == "numeric":
            summary.update(_numeric_sequence_diagnostics(candidate))
        replacements[zone_id] = candidate
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":profile,"label":PROFILE_LABELS[profile],"explicit":True,"changed":False,"reports":reports}
        return unchanged
    records = []
    for zone_id in range(1, len(summaries) + 1):
        zone_records = replacements.get(zone_id, by_zone.get(zone_id, []))
        for i, rec in enumerate(zone_records, 1):
            item = dict(rec)
            item["ref_in_zone"] = i
            records.append(item)
    return _rebuild(base, summaries, records, scope, profile, {"changed":True,"reports":reports})


def _apply_numeric_sequence(base: Dict, scope: str) -> Dict:
    return _apply_numeric_filter(base, scope, profile="numeric_sequence")


def _apply_numeric_layout_resegmentation(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements = {}
    reports = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        base_records = by_zone.get(zone_id, [])
        if not base_records:
            continue
        attempt = build_numeric_layout_resegmentation(pdf_path, layout_zone, base_records)
        reports.append({"zone_id":zone_id,"heading":summary.get("heading", ""), **{k:v for k,v in attempt.items() if k != "segments"}})
        if not attempt.get("accepted"):
            continue
        candidate = attempt.get("segments", [])
        summary["n_segments"] = len(candidate)
        summary["original_style"] = summary.get("style")
        summary["style"] = "numeric"
        candidate_pages = [int(seg.get("reference_end_page") or seg.get("reference_start_page") or summary.get("end_page", 0)) for seg in candidate]
        if candidate_pages:
            summary["end_page"] = max(candidate_pages)
            summary["zone_span_pages"] = max(1, int(summary["end_page"]) - int(summary.get("start_page", summary["end_page"])) + 1)
        summary["segmentation_method"] = "selective_rescue_numeric_layout_resegmentation"
        summary.update(_numeric_sequence_diagnostics(candidate))
        replacements[zone_id] = [
            _attach_zone_metadata(seg, zone_id, i, summary)
            for i, seg in enumerate(candidate, 1)
        ]
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"numeric_layout_resegmentation","label":PROFILE_LABELS["numeric_layout_resegmentation"],"explicit":True,"changed":False,"reports":reports}
        return unchanged
    records=[]
    for zone_id in range(1, len(summaries)+1):
        records.extend(replacements.get(zone_id, by_zone.get(zone_id, [])))
    return _rebuild(base, summaries, records, scope, "numeric_layout_resegmentation", {"changed":True,"reports":reports})


def _column_reflow_trigger(summary: Dict, base_records: Sequence[Dict]) -> bool:
    span = max(1, int(summary.get("zone_span_pages", 0) or (int(summary.get("end_page", 0) or 0) - int(summary.get("start_page", 0) or 0) + 1)))
    n = len(base_records)
    style = str(summary.get("style", ""))
    sparse_multpage = span >= 2 and n <= max(6, span * 2)
    numeric_broken = False
    if style == "numeric" and n >= 8:
        missing = str(summary.get("numeric_missing_markers", "") or "")
        first = summary.get("numeric_first_marker")
        last = summary.get("numeric_last_marker")
        numeric_broken = bool(missing and first is not None and last is not None and int(last) >= n + 8)
    return bool(sparse_multpage or numeric_broken)


def _apply_multi_column_reflow(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements = {}
    reports = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        base_records = by_zone.get(zone_id, [])
        if not _column_reflow_trigger(summary, base_records):
            continue
        attempt = build_column_reflow_repair(pdf_path, layout_zone, base_records)
        reports.append({"zone_id":zone_id,"heading":summary.get("heading", ""), **{k:v for k,v in attempt.items() if k != "segments"}})
        if not attempt.get("accepted"):
            continue
        candidate = attempt.get("segments", [])
        candidate_style = attempt.get("candidate_style", summary.get("style"))
        sequence_cleanup = None
        if candidate_style == "numeric":
            sequence_cleanup = _numeric_sequence_candidate(candidate)
            if sequence_cleanup.get("accepted"):
                candidate = sequence_cleanup.get("segments", candidate)
        summary["n_segments"] = len(candidate)
        summary["original_style"] = summary.get("style")
        summary["style"] = candidate_style
        summary["segmentation_method"] = "selective_rescue_multi_column_reflow"
        if summary["style"] == "numeric":
            summary.update(_numeric_sequence_diagnostics(candidate))
        if sequence_cleanup and sequence_cleanup.get("accepted"):
            attempt["post_reflow_numeric_sequence_cleanup"] = {k:v for k,v in sequence_cleanup.items() if k != "segments"}
            attempt["n_enhanced_segments_after_cleanup"] = len(candidate)
        replacements[zone_id] = [
            _attach_zone_metadata(seg, zone_id, i, summary)
            for i, seg in enumerate(candidate, 1)
        ]
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"multi_column_reflow","label":PROFILE_LABELS["multi_column_reflow"],"explicit":True,"changed":False,"reports":reports}
        return unchanged
    records=[]
    for zone_id in range(1, len(summaries)+1):
        records.extend(replacements.get(zone_id, by_zone.get(zone_id, [])))
    return _rebuild(base, summaries, records, scope, "multi_column_reflow", {"changed":True,"reports":reports})


def _apply_multi_column_reflow_v2(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    replacements = {}
    reports = []
    for zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, summaries), 1):
        base_records = by_zone.get(zone_id, [])
        if not base_records or int(summary.get("zone_span_pages", 1) or 1) < 2:
            continue
        attempt = build_column_reflow_repair_v2(pdf_path, layout_zone, base_records)
        reports.append({"zone_id":zone_id,"heading":summary.get("heading", ""), **{k:v for k,v in attempt.items() if k != "segments"}})
        if not attempt.get("accepted"):
            continue
        candidate = attempt.get("segments", [])
        candidate_style = attempt.get("candidate_style", summary.get("style"))
        # A column-major reconstruction can expose a complete numeric backbone
        # plus a few isolated layout/body-number boundaries (Ball).  Reuse the
        # strict numeric_filter *after* reflow only when that filter proves a
        # complete backbone; otherwise preserve the reflow candidate unchanged.
        post_filter = None
        if candidate_style == "numeric":
            post_filter = numeric_filter_candidate(candidate)
            if post_filter.get("accepted"):
                candidate = post_filter.get("segments", candidate)
                attempt["post_reflow_numeric_filter"] = {
                    k: v for k, v in post_filter.items() if k != "segments"
                }
                attempt["n_enhanced_segments_after_filter"] = len(candidate)
        summary["n_segments"] = len(candidate)
        summary["original_style"] = summary.get("style")
        summary["style"] = candidate_style
        summary["segmentation_method"] = "selective_rescue_multi_column_reflow_v2"
        if candidate_style == "numeric":
            summary.update(_numeric_sequence_diagnostics(candidate))
        replacements[zone_id] = [
            _attach_zone_metadata(seg, zone_id, i, summary)
            for i, seg in enumerate(candidate, 1)
        ]
    if not replacements:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"multi_column_reflow_v2","label":PROFILE_LABELS["multi_column_reflow_v2"],"explicit":True,"changed":False,"reports":reports}
        return unchanged
    records=[]
    for zone_id in range(1, len(summaries)+1):
        records.extend(replacements.get(zone_id, by_zone.get(zone_id, [])))
    return _rebuild(base, summaries, records, scope, "multi_column_reflow_v2", {"changed":True,"reports":reports})


def _apply_structural_zone_reconciliation(pdf_path, base: Dict, scope: str) -> Dict:
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    stable_summaries = [dict(z) for z in base.get("zones", [])]
    by_zone = _base_records_by_zone(base)
    plan = structural_reconciliation_plan(layout_zones, stable_summaries, lines)
    if not plan.get("eligible"):
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {
            "profile":"structural_zone_reconciliation",
            "label":PROFILE_LABELS["structural_zone_reconciliation"],
            "explicit":True,"changed":False,
            "drop_zone_ids":[],"trim_zones":{},"evidence":plan.get("evidence", []),
        }
        return unchanged

    dropped = {int(x) for x in plan.get("drop_zone_ids", [])}
    trimmed = {int(k): v for k, v in plan.get("trim_zones", {}).items()}
    new_summaries: List[Dict] = []
    new_records: List[Dict] = []
    reports: List[Dict] = []
    new_zone_id = 0
    for old_zone_id, (layout_zone, summary) in enumerate(zip(layout_zones, stable_summaries), 1):
        if old_zone_id in dropped:
            reports.append({"old_zone_id":old_zone_id,"action":"drop","heading":summary.get("heading", "")})
            continue
        new_zone_id += 1
        new_summary = dict(summary)
        candidate_records = [dict(r) for r in by_zone.get(old_zone_id, [])]
        if old_zone_id in trimmed:
            boundary = trimmed[old_zone_id]
            boundary_page = int(boundary["page"])
            top_fraction = float(boundary.get("top_fraction", 1.0))
            stable_records = [dict(r) for r in by_zone.get(old_zone_id, [])]
            # If a new chapter starts at the top of the next page, the stable
            # records before that page are already the least destructive source.
            # Re-segmenting old/scanned typography can lose valid boundaries
            # (Morton), so preserve those records verbatim.
            if top_fraction <= 0.15 and boundary_page > int(summary.get("start_page", layout_zone.start_page)):
                kept_records = [
                    r for r in stable_records
                    if int(r.get("reference_end_page") or r.get("reference_start_page") or 10**9) < boundary_page
                ]
                if kept_records:
                    candidate_records = kept_records
                    new_summary["end_page"] = boundary_page - 1
                    new_summary["zone_span_pages"] = max(1, (boundary_page - 1) - int(new_summary.get("start_page", layout_zone.start_page)) + 1)
                    new_summary["termination_reason"] = "selective_rescue_structural_new_section"
                    new_summary["segmentation_method"] = "selective_rescue_structural_preserve_stable_before_page_boundary"
            else:
                trimmed_zone, segments = build_trimmed_zone(layout_zone, boundary)
                if segments:
                    candidate_records = [dict(seg) for seg in segments]
                    new_summary["end_page"] = int(trimmed_zone.end_page)
                    new_summary["zone_span_pages"] = int(trimmed_zone.zone_span_pages)
                    new_summary["termination_reason"] = trimmed_zone.termination_reason
                    new_summary["style"] = trimmed_zone.style.style
                    new_summary["segmentation_method"] = "selective_rescue_structural_zone_reconciliation"
            reports.append({
                "old_zone_id":old_zone_id,"action":"trim","heading":summary.get("heading", ""),
                "old_end_page":summary.get("end_page"),"new_end_page":new_summary.get("end_page"),
                "old_records":len(by_zone.get(old_zone_id, [])),"new_records":len(candidate_records),
                "boundary":boundary,
            })
        new_summary["zone_id"] = new_zone_id
        new_summary["n_segments"] = len(candidate_records)
        new_summaries.append(new_summary)
        for i, record in enumerate(candidate_records, 1):
            if old_zone_id in trimmed:
                item = _attach_zone_metadata(record, new_zone_id, i, new_summary)
            else:
                item = dict(record)
                item["zone_id"] = new_zone_id
                item["ref_in_zone"] = i
                item["zone_heading"] = new_summary.get("heading", item.get("zone_heading", ""))
                item["zone_start_page"] = new_summary.get("start_page", item.get("zone_start_page"))
                item["zone_end_page"] = new_summary.get("end_page", item.get("zone_end_page"))
            new_records.append(item)

    if not new_summaries:
        unchanged = copy.deepcopy(base)
        unchanged["rescue_applied"] = {"profile":"structural_zone_reconciliation","label":PROFILE_LABELS["structural_zone_reconciliation"],"explicit":True,"changed":False,"reason":"candidate_removed_all_zones"}
        return unchanged
    return _rebuild(base, new_summaries, new_records, scope, "structural_zone_reconciliation", {
        "changed":True,
        "drop_zone_ids":sorted(dropped),
        "trim_zones":trimmed,
        "reports":reports,
        "evidence":plan.get("evidence", []),
    })

def apply_rescue(pdf_path, base: Dict, scope: str, profile: str) -> Dict:
    if profile == "stable":
        return copy.deepcopy(base)
    if profile == "heading_artifact":
        return _apply_heading_artifact(pdf_path, base, scope)
    if profile == "continuation_density":
        return _apply_continuation_density(pdf_path, base, scope)
    if profile == "numeric_filter":
        return _apply_numeric_filter(base, scope)
    if profile == "numeric_layout_resegmentation":
        return _apply_numeric_layout_resegmentation(pdf_path, base, scope)
    if profile == "multi_column_reflow_v2":
        return _apply_multi_column_reflow_v2(pdf_path, base, scope)
    if profile == "structural_zone_reconciliation":
        return _apply_structural_zone_reconciliation(pdf_path, base, scope)
    # v0.9.2 compatibility aliases, explicit-only.
    if profile == "numeric_sequence":
        return _apply_numeric_sequence(base, scope)
    if profile == "multi_column_reflow":
        return _apply_multi_column_reflow(pdf_path, base, scope)
    if profile == "repeated_decoration":
        return _apply_zone_repair(pdf_path, base, scope, profile, build_repeated_decoration_repair)
    if profile == "vertical_gap":
        return _apply_zone_repair(pdf_path, base, scope, profile, build_vertical_gap_repair)
    if profile == "author_year_boundary":
        return _apply_zone_repair(pdf_path, base, scope, profile, build_author_year_boundary_repair)
    if profile == "appendix_context":
        return _apply_appendix_context(pdf_path, base, scope)
    raise ValueError(f"Unknown rescue profile {profile!r}")


TOPOLOGY_CHANGING_RESCUES = {"heading_artifact", "appendix_context", "structural_zone_reconciliation"}


def apply_rescue_chain(pdf_path, base: Dict, scope: str, profiles: Sequence[str]) -> Dict:
    """Apply an explicit ordered rescue chain without automatic preference.

    This supports the user-facing iterative workflow (e.g. Ball:
    ``numeric_filter`` then ``multi_column_reflow_v2``).  Profiles that alter
    zone topology are allowed only as the final step because subsequent rescue
    modules align against the original detected layout zones.
    """
    chain = [str(p) for p in profiles if str(p) and str(p) != "stable"]
    if not chain:
        return copy.deepcopy(base)
    unknown = [p for p in chain if p not in VALID_RESCUE_PROFILES]
    if unknown:
        raise ValueError(f"Unknown rescue profiles in chain: {unknown!r}")
    for i, profile in enumerate(chain[:-1]):
        if profile in TOPOLOGY_CHANGING_RESCUES:
            raise ValueError(
                f"Topology-changing rescue {profile!r} must be the final step in a rescue chain"
            )
    current = copy.deepcopy(base)
    steps = []
    for profile in chain:
        before_records = len(current.get("records", []) or [])
        before_zones = len(current.get("zones", []) or [])
        current = apply_rescue(pdf_path, current, scope, profile)
        steps.append({
            "profile": profile,
            "label": PROFILE_LABELS[profile],
            "changed": bool(current.get("rescue_applied", {}).get("changed", False)),
            "before_records": before_records,
            "after_records": len(current.get("records", []) or []),
            "before_zones": before_zones,
            "after_zones": len(current.get("zones", []) or []),
        })
    current = dict(current)
    current["rescue_chain_applied"] = {
        "profiles": chain,
        "steps": steps,
        "automatic_preference": False,
        "explicit": True,
    }
    return current


#: v0.9.4 (P1) plausibility thresholds.  Deliberately conservative and
#: expressed as document-level properties, never as per-thesis constants.
UNUSABLE_TEXT_LAYER_RATIO = 0.08        # same threshold as the v0.8.10 OCR cue
IMPLAUSIBLE_YIELD_PER_100_PAGES = 8.0   # a doctoral thesis below this is not credible
MIN_PAGES_FOR_YIELD_CHECK = 40          # short documents are exempt

BIBLIOGRAPHIC_HEADING_HINT_RX = re.compile(
    r"(referenc|refer[êe]ncia|bibliograf|bibliograph|works\s+cited|"
    r"literat(?:ure|ura)\s+cit|literaturverzeichnis)", re.I)


def _output_plausibility(lines, base_all: Dict, coverage: Dict, quality: Dict) -> Dict:
    """v0.9.4 (P1): document-level checks that do NOT depend on zones existing.

    Every issue detector in this module iterates over detected zones or records.
    When the stable route abstains there are no zones, so no detector can fire
    and the audit status collapses to ``looks_consistent`` no matter how bad the
    outcome is.  These checks close that hole.  They are diagnostic only: they
    change the reported *status*, never the effective records or zones.
    """
    n_records = int(quality.get("n_records", 0) or 0)
    page_count = max((int(getattr(l, "page", 0) or 0) for l in lines), default=0)
    corrupted = _corrupted_token_ratio(lines) if lines else 0.0
    yield_per_100 = (100.0 * n_records / page_count) if page_count else None

    heading_hint = any(
        BIBLIOGRAPHIC_HEADING_HINT_RX.search(str(getattr(l, "text", "") or ""))
        for l in lines)

    low_output = (n_records == 0) or (
        yield_per_100 is not None and page_count >= MIN_PAGES_FOR_YIELD_CHECK
        and yield_per_100 < IMPLAUSIBLE_YIELD_PER_100_PAGES)

    reasons: List[Dict] = []
    # The corruption heuristic penalizes alphabetic tokens containing digits, so
    # gene/protein nomenclature (``rem1``, ``cig2``, ``Cdc2``) pushes healthy
    # molecular-biology and chemistry theses just over the threshold.  A text
    # layer that yielded a full bibliography is usable *by demonstration*, which
    # directly falsifies the claim this signal makes, so it requires corroboration
    # from the output itself rather than a tuned threshold.
    if corrupted >= UNUSABLE_TEXT_LAYER_RATIO and low_output:
        reasons.append({
            "signal": "unusable_text_layer",
            "detail": "extracted_text_layer_is_largely_not_readable_text",
            "corrupted_token_ratio": round(corrupted, 4),
            "threshold": UNUSABLE_TEXT_LAYER_RATIO,
            "corroborated_by_low_output": True,
            "rescue_applicable": False,
        })
    if n_records == 0:
        reasons.append({
            "signal": "zero_records",
            "detail": "no_reference_was_extracted_from_the_whole_document",
            "bibliographic_heading_present_in_text": bool(heading_hint),
            "n_toc_reference_candidates": int(coverage.get("n_toc_reference_candidates", 0) or 0),
        })
    if coverage.get("possible_incomplete_coverage"):
        reasons.append({
            "signal": "possible_incomplete_coverage",
            "detail": "table_of_contents_announces_references_but_no_zone_was_detected",
            "n_toc_reference_candidates": int(coverage.get("n_toc_reference_candidates", 0) or 0),
        })
    if (yield_per_100 is not None and n_records > 0
            and page_count >= MIN_PAGES_FOR_YIELD_CHECK
            and yield_per_100 < IMPLAUSIBLE_YIELD_PER_100_PAGES
            and heading_hint):
        reasons.append({
            "signal": "implausible_reference_yield",
            "detail": "reference_density_far_below_any_credible_doctoral_thesis",
            "references_per_100_pages": round(yield_per_100, 2),
            "threshold": IMPLAUSIBLE_YIELD_PER_100_PAGES,
        })

    return {
        "version": "0.9.4-output-plausibility",
        "implausible": bool(reasons),
        "n_records": n_records,
        "page_count": page_count,
        "references_per_100_pages": round(yield_per_100, 2) if yield_per_100 is not None else None,
        "corrupted_token_ratio": round(corrupted, 4),
        "bibliographic_heading_present_in_text": bool(heading_hint),
        "reasons": reasons,
        "diagnostic_only": True,
        "effective_output_changed": False,
    }


def diagnose_and_recommend(pdf_path, base_all: Dict) -> Dict:
    """Audit a completed v0.9.0 effective extraction and rank selective rescue profiles."""
    lines = extract_layout_lines(pdf_path)
    layout_zones = detect_adaptive_layout_zones(lines)
    profiles = _layout_page_profiles(lines)
    by_zone = _base_records_by_zone(base_all)
    issues: List[Dict] = []
    recs: Dict[str, Dict] = {}

    def recommend(profile: str, severity: str, reason: str, **extra):
        rank = {"critical":4,"strong":3,"moderate":2,"mild":1}.get(severity,1)
        current = recs.get(profile)
        item = {"profile":profile,"label":PROFILE_LABELS[profile],"severity":severity,"rank":rank,"reason":reason,**extra}
        if current is None or rank > current["rank"]:
            recs[profile] = item

    normalized, artifact_hits = _artifact_normalized_lines(lines)
    if artifact_hits:
        detected_pages = {int(z.get("start_page", -1)) for z in base_all.get("zones", [])}
        hidden = [h for h in artifact_hits if int(h["page"]) not in detected_pages]
        if hidden:
            issues.append({"type":"hidden_reference_heading_artifact","severity":"critical","evidence":hidden})
            recommend("heading_artifact","critical","reference_heading_visible_after_stripping_compact_pdf_artifact", evidence=hidden)

    decorations = detect_repeated_decorations(lines)
    repeated_texts = [
        str(x.get("normalized_text", "")).strip()
        for x in decorations.get("items", [])
        if len(re.sub(r"[^a-z]+", "", str(x.get("normalized_text", "")), flags=re.I)) >= 8
    ]
    contaminated = []
    for record in base_all.get("records", []):
        text = str(record.get("reference_text", ""))
        normalized_record = _norm(text)
        for deco in repeated_texts:
            if deco and deco in normalized_record:
                contaminated.append({"zone_id":record.get("zone_id"),"ref_in_zone":record.get("ref_in_zone"),"decoration":deco})
                break
    if len(contaminated) >= 2:
        issues.append({"type":"repeated_page_decoration_in_records","severity":"strong","count":len(contaminated),"examples":contaminated[:5]})
        recommend("repeated_decoration","strong","repeated_header_or_footer_text_leaked_into_reference_records", count=len(contaminated))

    appendix_conflicts = []
    for zone_id, zone in enumerate(layout_zones, 1):
        gate = strong_appendix_guideline_conflict(zone, lines)
        if gate.get("blocked"):
            appendix_conflicts.append({"zone_id":zone_id,"heading":zone.heading.text,**gate})
    if appendix_conflicts:
        issues.append({"type":"appendix_guideline_reference_regions","severity":"strong","zones":appendix_conflicts})
        recommend("appendix_context","strong","references_heading_occurs_inside_appendix_author_guidelines", zones=[x["zone_id"] for x in appendix_conflicts])

    continuation_candidates = []
    for summary in base_all.get("zones", []):
        ext = _proposed_density_extension(profiles, int(summary.get("end_page", 0) or 0))
        if ext.get("eligible"):
            continuation_candidates.append({"zone_id": int(summary.get("zone_id", 0) or 0), "heading": summary.get("heading", ""), **ext})
    if continuation_candidates:
        issues.append({"type":"post_zone_reference_density","severity":"critical","zones":continuation_candidates})
        recommend("continuation_density","critical","strong_bibliographic_density_continues_for_multiple_pages_after_detected_zone", zones=continuation_candidates)

    numeric_filter_candidates = []
    for summary in base_all.get("zones", []):
        zone_id = int(summary.get("zone_id", 0) or 0)
        base_records = by_zone.get(zone_id, [])
        if not base_records:
            continue
        sequence = numeric_filter_candidate(base_records)
        if sequence.get("accepted"):
            numeric_filter_candidates.append({
                "zone_id": zone_id,
                "base": len(base_records),
                "candidate": sequence.get("n_enhanced_segments"),
                "extras": sequence.get("extras", []),
                "backbone_end": sequence.get("backbone_end"),
            })
    if numeric_filter_candidates:
        issues.append({"type":"numeric_extra_boundary_risk","severity":"strong","zones":numeric_filter_candidates})
        recommend("numeric_filter","strong","complete_numeric_backbone_contains_safe_extra_boundaries", zones=numeric_filter_candidates)

    numeric_layout_candidates = []
    for zone_id, zone in enumerate(layout_zones, 1):
        base_records = by_zone.get(zone_id, [])
        if not base_records:
            continue
        attempt = build_numeric_layout_resegmentation(pdf_path, zone, base_records)
        if attempt.get("accepted"):
            numeric_layout_candidates.append({
                "zone_id":zone_id,
                "base":len(base_records),
                "candidate":attempt.get("n_enhanced_segments"),
                "mode":attempt.get("mode"),
                "sequence_last":attempt.get("sequence_last"),
                "marker_x":attempt.get("marker_x"),
            })
    if numeric_layout_candidates:
        max_ratio = max(float(x["candidate"]) / max(1.0, float(x["base"])) for x in numeric_layout_candidates)
        severity = "critical" if max_ratio >= 1.5 else "strong"
        issues.append({"type":"raw_numeric_layout_undersegmentation","severity":severity,"zones":numeric_layout_candidates})
        recommend("numeric_layout_resegmentation",severity,"raw_pdf_numeric_markers_form_a_complete_sequence_not_represented_by_stable_records", zones=numeric_layout_candidates)

    column_candidates = []
    for zone_id, zone in enumerate(layout_zones, 1):
        summary = next((z for z in base_all.get("zones", []) if int(z.get("zone_id",0) or 0)==zone_id), {})
        base_records = by_zone.get(zone_id, [])
        if not base_records or int(summary.get("zone_span_pages", 1) or 1) < 2:
            continue
        attempt = build_column_reflow_repair_v2(pdf_path, zone, base_records)
        if attempt.get("accepted"):
            column_candidates.append({
                "zone_id": zone_id,
                "base": len(base_records),
                "candidate": attempt.get("n_enhanced_segments"),
                "candidate_style": attempt.get("candidate_style"),
                "column_pages": attempt.get("column_pages", []),
                "reason": attempt.get("reason"),
            })
    if column_candidates:
        max_ratio = max(float(x["candidate"]) / max(1.0, float(x["base"])) for x in column_candidates)
        severity = "critical" if max_ratio >= 1.5 else "strong"
        issues.append({"type":"multi_column_reading_order_risk_v2","severity":severity,"zones":column_candidates})
        recommend("multi_column_reflow_v2",severity,"column_major_reflow_recovers_a_complete_or_higher_quality_reference_sequence", zones=column_candidates)

    structural = structural_reconciliation_plan(layout_zones, base_all.get("zones", []), lines)
    if structural.get("eligible"):
        drop_ids = list(structural.get("drop_zone_ids", []))
        trim_zones = dict(structural.get("trim_zones", {}))
        # Prefer a more specific geometry/numbering rescue when it already
        # explains the same zone.  Structural reconciliation remains available
        # explicitly, but it should not compete in the recommendation ranking
        # with a raw numeric or multi-column diagnosis (Adan/Ball).
        specifically_explained = {int(x["zone_id"]) for x in numeric_layout_candidates}
        specifically_explained.update(int(x["zone_id"]) for x in column_candidates)
        trim_zones = {int(k): v for k, v in trim_zones.items() if int(k) not in specifically_explained}
        evidence = [
            item for item in structural.get("evidence", [])
            if item.get("action") == "drop" or int(item.get("zone_id", -1)) in trim_zones
        ]
        if drop_ids or trim_zones:
            severity = "critical" if len(drop_ids) >= 2 else "strong"
            issue = {
                "type":"document_structure_reference_zone_conflict",
                "severity":severity,
                "drop_zone_ids":drop_ids,
                "trim_zones":trim_zones,
                "evidence":evidence,
            }
            issues.append(issue)
            recommend("structural_zone_reconciliation",severity,"detected_reference_zones_conflict_with_toc_or_strong_new_chapter_structure", drop_zone_ids=drop_ids, trim_zones=trim_zones)

    gap_candidates = []
    numeric_candidates = []
    for zone_id, zone in enumerate(layout_zones, 1):
        base_records = by_zone.get(zone_id, [])
        if not base_records:
            continue
        summary = next((z for z in base_all.get("zones", []) if int(z.get("zone_id", 0) or 0) == zone_id), {})
        effective_style = str(summary.get("style", zone.style.style) or "")
        # Author-year/gap rescues are not meaningful after a raw numeric
        # resegmentation has already established explicit numeric boundaries.
        if effective_style in {"numeric", "bracket_key"}:
            continue
        gap = build_vertical_gap_repair(zone, base_records)
        # Gap rescue is recommended only for the specific rare layout that
        # motivated it: references aligned to the same left margin without a
        # hanging-indent signal.  Hanging-indent bibliographies stay on the
        # stable path even when an alternative gap segmentation is plausible.
        if gap.get("accepted") and not zone.layout.hanging_indent_detected:
            gap_candidates.append({"zone_id":zone_id,"base":len(base_records),"candidate":gap.get("n_enhanced_segments"),"gap_only":gap.get("n_gap_only_starts")})
        numeric = build_author_year_boundary_repair(zone, base_records)
        if numeric.get("accepted"):
            candidate_n = int(numeric.get("n_enhanced_segments", len(base_records)))
            suppressed_n = int(numeric.get("n_suppressed_numeric_starts", 0) or 0)
            suspicious_n = int(numeric.get("n_suspicious_numeric_starts", 0) or 0)
            gap_n = int(numeric.get("n_gap_only_starts", 0) or 0)
            # Recommendation gate is narrower than candidate construction:
            # hanging-indent zones need explicit suspicious numeric starts;
            # pure gap evidence is reserved for same-margin/no-hanging layouts.
            symptom_specific = suspicious_n >= 2 or (not zone.layout.hanging_indent_detected and gap_n >= 2)
            if symptom_specific and (abs(candidate_n - len(base_records)) >= 2 or suppressed_n >= 2):
                numeric_candidates.append({
                    "zone_id":zone_id,"base":len(base_records),"candidate":candidate_n,
                    "suppressed":suppressed_n,"suspicious":suspicious_n,"gap_only":gap_n,
                })
    if numeric_candidates:
        issues.append({"type":"numeric_continuation_boundary_risk","severity":"moderate","zones":numeric_candidates})
        recommend("author_year_boundary","moderate","author_year_zone_contains_multiple_numeric_boundaries_that_can_be_continuations", zones=numeric_candidates)
    if gap_candidates:
        # If numeric guard already explains the same zone, prefer it because it
        # is more specific and therefore safer.
        numeric_zone_ids = {x["zone_id"] for x in numeric_candidates}
        pure_gap = [x for x in gap_candidates if x["zone_id"] not in numeric_zone_ids]
        if pure_gap:
            severity = "moderate" if max(abs(int(x["candidate"])-int(x["base"])) for x in pure_gap) <= 20 else "strong"
            issues.append({"type":"vertical_gap_boundary_signal","severity":severity,"zones":pure_gap})
            recommend("vertical_gap",severity,"large_same_margin_paragraph_gaps_reveal_additional_plausible_boundaries", zones=pure_gap)

    shadow_status = str(base_all.get("adaptive_shadow", {}).get("overall_status", ""))
    coverage = toc_reference_coverage(lines, base_all.get("zones", []))
    quality = _record_quality(base_all.get("records", []))
    plausibility = _output_plausibility(lines, base_all, coverage, quality)

    recommendations = sorted(recs.values(), key=lambda x:(-x["rank"], x["profile"]))
    for item in recommendations:
        item.pop("rank", None)

    if any(i.get("severity") == "critical" for i in issues):
        status = "critical_review"
    elif issues:
        status = "needs_review"
    elif shadow_status == "manual_review_required":
        status = "shadow_review_without_specific_rescue"
    elif shadow_status == "ambiguous":
        status = "looks_consistent_shadow_caution"
    else:
        status = "looks_consistent"

    # v0.9.4 (P1): an implausible output is never reported as consistent.  When a
    # symptom-matched rescue already exists the more actionable status is kept,
    # because it names something the caller can actually try; otherwise the audit
    # must abstain explicitly instead of asserting that the extraction is fine.
    if plausibility["implausible"] and not recommendations:
        status = "manual_review_required"

    return {
        "version":"0.9.4-selective-router3-plausibility",
        "effective_extraction_version":"0.9.0-effective/0.6.1-algorithm",
        "status":status,
        "default_output_changed":False,
        "policy":"extract_stable_first_then_run_only_symptom-matched_rescue_hypotheses",
        "shadow_status":shadow_status,
        "record_quality":quality,
        "document_coverage":coverage,
        "output_plausibility":plausibility,
        "review_reasons":[r["signal"] for r in plausibility["reasons"]],
        "issues":issues,
        "recommendations":recommendations,
        "menu": [{"profile":p,"label":PROFILE_LABELS[p]} for p in RESCUE_PROFILES],
    }
