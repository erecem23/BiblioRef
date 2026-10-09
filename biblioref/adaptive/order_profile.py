"""Local bibliography order diagnostics for BiblioRef v0.8.4.

The module does not assume APA or any named citation style.  It asks whether
start-like lines in the current bibliography region exhibit a sufficiently
strong local ordering regime (currently alphabetical or numeric).  The result
is diagnostic evidence used by the shadow boundary scorer; it never creates or
removes validated records by itself.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Sequence

from biblioref.detection.signals import REPEATED_MARK_RX
from biblioref.grammar.regimes import choose_dominant_regime
from biblioref.grammar.numeric import infer_marker_only_numeric, infer_prefix_numeric, infer_comma_numeric
from biblioref.grammar.dates import UNDATED_RX
from biblioref.legacy.engine import BRACKET_KEY_RX, NUMERIC_MARKER_RX, YEAR_RX, SIN_FECHA_RX, LayoutLine

# Surname particles are treated only when followed by a surname-like token and
# an author separator.  This avoids the previous blanket penalty on any line
# beginning with a lowercase word.
PARTICLE_AUTHOR_RX = re.compile(
    r"^(?P<prefix>(?:(?:de|del|de\s+la|de\s+los|da|das|do|dos|di|du|van|von|der|den|ter|ten|la|le|"
    r"De|Del|Da|Das|Do|Dos|Di|Du|Van|Von|Der|Den|Ter|Ten|La|Le)\s+)+"
    r"[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^,\n]{0,70}),\s*"
)

# General author/institution prefix.  It is intentionally stricter than
# "capitalized line": a comma or a nearby bibliographic date is required.
AUTHOR_PREFIX_RX = re.compile(r"^(?P<prefix>[^,\n]{1,100}),\s*")
AUTHOR_AFTER_COMMA_RX = re.compile(
    r"^[^,\n]{1,100},\s*(?:[A-ZÁÉÍÓÚÑ](?:\.|\b)|[A-ZÁÉÍÓÚÑ][a-záéíóúñ'’\-]{2,})(?:\s|,|&|and|y|e)",
)
INSTITUTION_DATE_RX = re.compile(
    r"^(?P<prefix>[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^.\n]{2,100})\.\s*\(?(?:18|19|20)\d{2}",
    re.I,
)
ABNT_UPPER_AUTHOR_RX = re.compile(
    r"^(?P<prefix>[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ'’\- ]{1,70}),\s*"
)


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_particle_for_sort(key: str) -> str:
    """Return a comparison key while preserving the original key for audit.

    Bibliographies differ on whether particles are filing elements.  For local
    consistency we compare both variants elsewhere; this helper provides the
    particle-stripped form used when that improves monotonicity.
    """
    return re.sub(
        r"^(?:(?:de|del|da|das|do|dos|di|du|van|von|der|den|ter|ten|la|le)\s+)+",
        "",
        key,
        flags=re.I,
    ).strip() or key


def author_sort_key(text: str, inherited_key: str | None = None) -> Dict:
    """Extract an auditable probable author/institution sort key from one line."""
    raw = str(text).strip()
    if not raw:
        return {"key": None, "key_without_particle": None, "kind": "none", "initial": None}

    if REPEATED_MARK_RX.match(raw):
        key = inherited_key
        return {
            "key": key,
            "key_without_particle": _strip_particle_for_sort(key) if key else None,
            "kind": "repeated_author" if key else "repeated_author_unresolved",
            "initial": key[:1] if key else None,
        }

    # Numeric and alphanumeric bracket-key bibliographies are distinct regimes.
    numeric = NUMERIC_MARKER_RX.match(raw)
    if numeric:
        number = next((g for g in numeric.groups() if g is not None), None)
        return {
            "key": None,
            "key_without_particle": None,
            "kind": "numeric_marker",
            "numeric_value": int(number) if number else None,
            "initial": None,
        }
    bracket_key = BRACKET_KEY_RX.match(raw)
    if bracket_key:
        return {
            "key": None,
            "key_without_particle": None,
            "kind": "bracket_key_marker",
            "bracket_key_value": str(bracket_key.group(1)).casefold(),
            "initial": None,
        }

    match = PARTICLE_AUTHOR_RX.match(raw)
    kind = "particle_author"
    if not match:
        match = ABNT_UPPER_AUTHOR_RX.match(raw)
        kind = "abnt_upper_author"
    if not match:
        generic = AUTHOR_PREFIX_RX.match(raw)
        if generic:
            prefix = generic.group("prefix").strip(" .;:'\"‘’“”")
            words = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+", prefix)
            plausible_prefix = bool(
                prefix
                and prefix[:1].isupper()
                and not re.search(r"\d", prefix)
                and 1 <= len(words) <= 8
            )
            # Generic person authors require morphology after the comma (initial
            # or given name), not merely a late year. This prevents wrapped
            # titles such as ``Poetry, 1966-1993`` from contaminating order.
            has_date = bool(YEAR_RX.search(raw[:320]) or SIN_FECHA_RX.search(raw[:320]) or UNDATED_RX.search(raw[:320]))
            if plausible_prefix and has_date and AUTHOR_AFTER_COMMA_RX.match(raw):
                match = generic
                kind = "author_date"
    if not match:
        match = INSTITUTION_DATE_RX.match(raw)
        kind = "institution_date"

    if not match:
        return {"key": None, "key_without_particle": None, "kind": "none", "initial": None}

    prefix = match.group("prefix").strip(" .;:'\"‘’“”")
    # For person-like strings, the sort key is the surname/prefix before comma.
    # Institutional strings remain whole because their leading phrase is the
    # filing key actually visible to a reader.
    key = _norm(prefix)
    if not key or len(key) > 100:
        return {"key": None, "key_without_particle": None, "kind": "none", "initial": None}
    return {
        "key": key,
        "key_without_particle": _strip_particle_for_sort(key),
        "kind": kind,
        "initial": key[:1],
    }


def _consistency(keys: Sequence[str]) -> Dict:
    pairs = [(a, b) for a, b in zip(keys, keys[1:]) if a and b]
    if not pairs:
        return {"ordered_pairs": 0, "adjacent_pairs": 0, "violations": 0, "consistency": 0.0}
    ordered = sum(a <= b for a, b in pairs)
    return {
        "ordered_pairs": ordered,
        "adjacent_pairs": len(pairs),
        "violations": len(pairs) - ordered,
        "consistency": round(ordered / len(pairs), 3),
    }


def infer_order_profile(lines: Sequence[LayoutLine]) -> Dict:
    """Infer a local order regime from probable author/numeric starts.

    ``strong_alphabetical_order`` requires at least five comparable author keys
    and >= .80 adjacent-pair consistency.  The threshold is deliberately high:
    order may support or suppress a shadow boundary only when the region itself
    demonstrates that convention.
    """
    entries: List[Dict] = []
    previous_author_key: str | None = None
    numeric_values: List[int] = []
    bracket_key_values: List[str] = []
    marker_only = infer_marker_only_numeric(lines)
    marker_only_map = marker_only.get("line_to_value", {}) if marker_only.get("detected") else {}
    prefix_numeric = infer_prefix_numeric(lines)
    prefix_numeric_map = prefix_numeric.get("line_to_value", {}) if prefix_numeric.get("detected") else {}
    comma_numeric = infer_comma_numeric(lines)
    comma_numeric_map = comma_numeric.get("line_to_value", {}) if comma_numeric.get("detected") else {}

    for index, line in enumerate(lines):
        if index in marker_only_map:
            item = {
                "key": None, "key_without_particle": None, "kind": "marker_only_numeric",
                "numeric_value": int(marker_only_map[index]), "initial": None,
            }
        elif index in prefix_numeric_map:
            item = {
                "key": None, "key_without_particle": None, "kind": "numeric_prefix_marker",
                "numeric_value": int(prefix_numeric_map[index]), "initial": None,
            }
        elif index in comma_numeric_map:
            item = {
                "key": None, "key_without_particle": None, "kind": "numeric_comma_marker",
                "numeric_value": int(comma_numeric_map[index]), "initial": None,
            }
        else:
            item = author_sort_key(line.text, inherited_key=previous_author_key)
        if item.get("key"):
            previous_author_key = str(item["key"])
        if item.get("numeric_value") is not None:
            numeric_values.append(int(item["numeric_value"]))
        bracket = BRACKET_KEY_RX.match(line.text.strip())
        if bracket and not NUMERIC_MARKER_RX.match(line.text.strip()):
            bracket_key_values.append(str(bracket.group(1)).casefold())
        entries.append({
            "line_index": index,
            "page": int(line.page),
            "text_preview": line.text.strip()[:160],
            **item,
        })

    keyed = [item for item in entries if item.get("key")]
    raw_keys = [str(item["key"]) for item in keyed]
    stripped_keys = [str(item["key_without_particle"] or item["key"]) for item in keyed]
    raw_stats = _consistency(raw_keys)
    stripped_stats = _consistency(stripped_keys)
    # Use whichever filing convention is more self-consistent locally, while
    # exposing both numbers so the decision remains auditable.
    use_stripped = stripped_stats["consistency"] > raw_stats["consistency"] + 0.05
    chosen_keys = stripped_keys if use_stripped else raw_keys
    chosen_stats = stripped_stats if use_stripped else raw_stats

    numeric_pairs = list(zip(numeric_values, numeric_values[1:]))
    numeric_consistency = (
        sum(b == a + 1 for a, b in numeric_pairs) / len(numeric_pairs)
        if numeric_pairs else 0.0
    )

    regime = choose_dominant_regime(
        n_numeric=len(numeric_values),
        numeric_consistency=float(numeric_consistency),
        n_bracket_keys=len(bracket_key_values),
        n_author_keys=len(chosen_keys),
        alphabetical_consistency=float(chosen_stats["consistency"]),
    )
    order_type = regime["order_type"]

    comparable = []
    for item, chosen in zip(keyed, chosen_keys):
        comparable.append({**item, "comparison_key": chosen})

    return {
        "order_type": order_type,
        "filing_convention": "particle_stripped" if use_stripped else "literal_prefix",
        "n_author_keys": len(chosen_keys),
        "initial_sequence": [key[:1] for key in chosen_keys[:80]],
        "key_sequence": chosen_keys[:80],
        "raw_alphabetical": raw_stats,
        "particle_stripped_alphabetical": stripped_stats,
        "alphabetical_consistency": chosen_stats["consistency"],
        "numeric_values": numeric_values[:80],
        "numeric_consistency": round(float(numeric_consistency), 3),
        "marker_only_numeric": {
            k: v for k, v in marker_only.items() if k != "line_to_value"
        },
        "marker_only_line_values": {str(k): int(v) for k, v in marker_only_map.items()},
        "prefix_numeric": {k: v for k, v in prefix_numeric.items() if k != "line_to_value"},
        "prefix_numeric_line_values": {str(k): int(v) for k, v in prefix_numeric_map.items()},
        "comma_numeric": {k: v for k, v in comma_numeric.items() if k != "line_to_value"},
        "comma_numeric_line_values": {str(k): int(v) for k, v in comma_numeric_map.items()},
        "bracket_key_values": bracket_key_values[:80],
        "n_bracket_keys": len(bracket_key_values),
        "dominant_regime": regime["dominant_regime"],
        "regime_strength": regime["regime_strength"],
        "regime_margin": regime["regime_margin"],
        "mixed_regime": regime["mixed_regime"],
        "regime_strengths": regime["regime_strengths"],
        "diagnostic_only": True,
        "entries": comparable,
    }


def local_order_evidence(line_index: int, profile: Dict) -> Dict:
    """Return support/inversion evidence for one potential boundary line.

    Inversion is treated as veto-like evidence only when the local filing regime
    is exceptionally coherent. At 0.80–0.89 consistency, order may support a
    boundary but does not suppress a strong semantic start.
    """
    if profile.get("order_type") != "strong_alphabetical_order":
        return {"available": False, "support": False, "inversion": False, "reason": "order_not_strong"}
    hard_inversion_allowed = bool(
        float(profile.get("alphabetical_consistency", 0.0)) >= 0.90
        and int(profile.get("n_author_keys", 0)) >= 6
        and float(profile.get("regime_margin", 0.0)) >= 0.15
    )

    entries = profile.get("entries", [])
    pos = next((i for i, item in enumerate(entries) if int(item["line_index"]) == int(line_index)), None)
    if pos is None:
        return {"available": False, "support": False, "inversion": False, "reason": "no_author_key"}

    current = entries[pos]["comparison_key"]
    previous = entries[pos - 1]["comparison_key"] if pos > 0 else None
    following = entries[pos + 1]["comparison_key"] if pos + 1 < len(entries) else None

    support = False
    inversion = False
    reason = "edge_of_sequence"
    if previous is not None and following is not None:
        support = bool(previous <= current <= following)
        inversion = bool((not support) and hard_inversion_allowed)
        reason = "between_neighbors" if support else ("violates_neighbor_order_strong" if inversion else "order_conflict_soft")
    elif previous is not None:
        support = bool(previous <= current)
        inversion = not support
        reason = "after_previous" if support else "less_than_previous"
    elif following is not None:
        support = bool(current <= following)
        inversion = not support
        reason = "before_next" if support else "greater_than_next"

    return {
        "available": True,
        "support": support,
        "inversion": inversion,
        "reason": reason,
        "previous_key": previous,
        "current_key": current,
        "next_key": following,
    }
