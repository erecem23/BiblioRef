"""Style-agnostic line signatures assembled from grammar primitives."""

from __future__ import annotations

from typing import Dict, List

from biblioref.adaptive.continuity import institutional_author_date, institutional_author_late_date, standard_document_start, particle_author_date, dot_initial_author_date
from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.grammar.inheritance import DATE_ONLY_START_RX
from biblioref.grammar.dates import undated_author_start
from biblioref.grammar.primitives import GrammarPrimitive
from biblioref.grammar.repeated_author import detect_repeated_author_marker
from biblioref.legacy.engine import BRACKET_KEY_RX, DOI_URL_AT_START_RX, NUMERIC_MARKER_RX


def line_grammar_signature(text: str) -> Dict:
    raw = str(text).strip()
    signals: List[str] = []
    numeric = NUMERIC_MARKER_RX.match(raw)
    bracket_key = BRACKET_KEY_RX.match(raw)
    repeated = detect_repeated_author_marker(raw)

    if numeric:
        signals.append(GrammarPrimitive.NUMERIC_ENTRY_MARKER.value)
        if raw.startswith("["):
            signals.append(GrammarPrimitive.BRACKET_ENTRY_MARKER.value)
    elif bracket_key:
        signals.append(GrammarPrimitive.BRACKET_KEY_MARKER.value)

    if parenthetical_author_year(raw):
        signals.extend([
            GrammarPrimitive.AUTHOR_EXPLICIT.value,
            GrammarPrimitive.YEAR_PARENTHETICAL.value,
        ])
    elif bare_author_year(raw):
        signals.extend([
            GrammarPrimitive.AUTHOR_EXPLICIT.value,
            GrammarPrimitive.YEAR_BARE.value,
        ])

    if particle_author_date(raw):
        signals.append(GrammarPrimitive.AUTHOR_EXPLICIT.value)
    if institutional_author_date(raw) or institutional_author_late_date(raw):
        signals.extend([
            GrammarPrimitive.AUTHOR_EXPLICIT.value,
            GrammarPrimitive.INSTITUTIONAL_AUTHOR.value,
        ])
    if standard_document_start(raw):
        signals.append(GrammarPrimitive.STANDARD_DOCUMENT_START.value)
    if dot_initial_author_date(raw):
        signals.extend([
            GrammarPrimitive.AUTHOR_EXPLICIT.value,
            GrammarPrimitive.YEAR_PARENTHETICAL.value,
        ])
    if undated_author_start(raw):
        signals.extend([
            GrammarPrimitive.AUTHOR_EXPLICIT.value,
            GrammarPrimitive.UNDATED_DATE.value,
        ])
    if DATE_ONLY_START_RX.match(raw):
        signals.append(GrammarPrimitive.YEAR_ONLY_START.value)
    if repeated["is_repeated_author_marker"]:
        signals.append(GrammarPrimitive.REPEATED_AUTHOR_MARKER.value)
    if DOI_URL_AT_START_RX.match(raw):
        signals.append(GrammarPrimitive.DOI_OR_URL.value)

    institutional = institutional_author_date(raw) or institutional_author_late_date(raw)
    if numeric:
        start_kind = "numeric"
    elif bracket_key:
        start_kind = "bracket_key"
    elif repeated["is_repeated_author_marker"]:
        start_kind = "repeated_author"
    elif institutional:
        start_kind = "institutional_author"
    elif dot_initial_author_date(raw) or undated_author_start(raw) or parenthetical_author_year(raw) or bare_author_year(raw) or particle_author_date(raw):
        start_kind = "person_author"
    elif DATE_ONLY_START_RX.match(raw):
        start_kind = "inherited_author"
    else:
        start_kind = "unknown"

    bibliographic_evidence = bool(signals)
    # Preserve first occurrence order while removing duplicates.
    unique = list(dict.fromkeys(signals))
    return {
        "signals": unique,
        "repeated_author": repeated,
        "numeric_marker": bool(numeric),
        "bracket_key_marker": bool(bracket_key),
        "reference_start_kind": start_kind,
        "bibliographic_evidence": bibliographic_evidence,
    }


__all__ = ["line_grammar_signature"]
