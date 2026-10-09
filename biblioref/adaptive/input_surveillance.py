"""Pre-segmentation uncertainty flags for BiblioRef v0.8.5-c."""
from __future__ import annotations

from typing import Dict, Sequence

from biblioref.adaptive.input_hygiene import decoration_status
from biblioref.grammar.signatures import line_grammar_signature
from biblioref.legacy.engine import LayoutLine


def input_line_watch(line: LayoutLine, decoration_report: Dict | None = None) -> Dict:
    status = decoration_status(line, decoration_report)
    signature = line_grammar_signature(line.text)
    flags = []
    if status == "DECORATION_WATCH":
        flags.append("DECORATION_WATCH")
    if signature.get("reference_start_kind") == "institutional_author":
        flags.append("INSTITUTIONAL_START_WATCH")
    if signature.get("reference_start_kind") == "unknown" and signature.get("bibliographic_evidence"):
        flags.append("REFERENCE_SIGNATURE_WEAK")
    return {
        "decoration_status": status,
        "reference_start_kind": signature.get("reference_start_kind"),
        "flags": flags,
    }


def summarize_input_surveillance(lines: Sequence[LayoutLine], decoration_report: Dict | None = None) -> Dict:
    items = []
    for index, line in enumerate(lines):
        watch = input_line_watch(line, decoration_report)
        if watch["flags"]:
            items.append({"line_index": index, "page": int(line.page), "text_preview": line.text.strip()[:180], **watch})
    return {
        "diagnostic_only": True,
        "auto_apply": False,
        "n_flagged_lines": len(items),
        "items": items[:200],
    }


def summarize_candidate_conflicts(candidates: Sequence[Dict]) -> Dict:
    """Expose contradictory boundary evidence without changing the decision."""
    items = []
    for item in candidates:
        f = item.get("features", {})
        flags = []
        if (
            f.get("strong_alphabetical_inversion")
            and item.get("semantic_anchor")
            and not item.get("active_shadow_boundary")
        ):
            flags.append("ORDER_CONFLICT_WATCH")
        if (
            f.get("source_metadata_continuation")
            and (f.get("author_bare_date") or f.get("spaced_smallcaps_author") or f.get("author_form_with_nearby_evidence"))
        ):
            flags.append("SOURCE_CONTINUATION_CONFLICT_WATCH")
        if flags:
            items.append({
                "line_index": item.get("line_index"),
                "page": item.get("page"),
                "text_preview": item.get("text_preview"),
                "score": item.get("score"),
                "active_shadow_boundary": item.get("active_shadow_boundary"),
                "flags": flags,
            })
    return {
        "diagnostic_only": True,
        "auto_apply": False,
        "n_conflicts": len(items),
        "items": items[:200],
    }


__all__ = ["input_line_watch", "summarize_input_surveillance", "summarize_candidate_conflicts"]
