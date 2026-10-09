"""Context-aware numeric marker grammars for the adaptive shadow pipeline.

The validated stable engine deliberately keeps its historical marker regex.
This module adds *shadow-only* support for bibliographies where the numeric
marker is extracted on a physical line by itself, e.g. ``1`` or ``1.`` followed by the
reference body on the next line.
"""
from __future__ import annotations

import re
from typing import Dict, Sequence

from biblioref.legacy.engine import LayoutLine, YEAR_RX, SIN_FECHA_RX

MARKER_ONLY_RX = re.compile(r"^\s*(?P<number>\d{1,4})(?:\.)?\s*$")
PREFIX_NUMERIC_RX = re.compile(r"^\s*(?P<number>\d{1,4})\s+(?P<body>\S.+?)\s*$")
COMMA_NUMERIC_RX = re.compile(r"^\s*(?P<number>\d{1,4})\s*,\s*(?P<body>\S.+?)\s*$")
BODY_EVIDENCE_RX = re.compile(
    r"(?:\b(?:18|19|20)\d{2}[a-z]?\b|https?://|www\.|\bdoi\b|\b(?:vol\.?|pp?\.?|journal|"
    r"press|university|universidad|institute|instituto|department|departamento|health|review)\b)",
    re.I,
)


def marker_only_number(text: str) -> int | None:
    m = MARKER_ONLY_RX.fullmatch(str(text).strip())
    return int(m.group("number")) if m else None


def prefix_numeric_entry(text: str) -> tuple[int, str] | None:
    """Return ``(number, body)`` for delimiter-free numeric prefixes.

    Recognition alone is intentionally *not* authority: ``infer_prefix_numeric``
    requires a monotonic sequence plus bibliographic body evidence before any
    line is treated as a marker.  This keeps headings such as ``1 Introduction``
    from becoming references merely because they begin with an integer.
    """
    m = PREFIX_NUMERIC_RX.fullmatch(str(text).strip())
    if not m:
        return None
    return int(m.group("number")), m.group("body").strip()



def comma_numeric_entry(text: str) -> tuple[int, str] | None:
    """Return ``(number, body)`` for historical ``1, Author...`` markers.

    A comma-prefixed integer is only an observable token.  Authority comes
    from :func:`infer_comma_numeric`, which requires a monotonic regional
    sequence and bibliographic body evidence.
    """
    m = COMMA_NUMERIC_RX.fullmatch(str(text).strip())
    if not m:
        return None
    return int(m.group("number")), m.group("body").strip()

def _same_line_body_plausible(body: str) -> bool:
    raw = str(body).strip()
    if not raw:
        return False
    # Strong bibliographic cues. A date is especially informative for Vancouver
    # / NLM-like lists, while DOI/URL/source metadata covers undated entries.
    if YEAR_RX.search(raw) or SIN_FECHA_RX.search(raw) or BODY_EVIDENCE_RX.search(raw):
        return True
    # Person-like citation morphology: surname/author list followed by initials
    # or another comma, plus citation-like punctuation. This is deliberately
    # stricter than "capitalized text" to reject numbered section headings.
    if re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]{1,40}(?:,|\s+[A-Z][A-Za-z'’\-]{1,30},)", raw):
        return bool(re.search(r"[.;:]", raw))
    return False


def infer_prefix_numeric(lines: Sequence[LayoutLine]) -> Dict:
    """Infer ``1 Author...`` / ``2 Author...`` numeric bibliographies.

    Safety requirements mirror marker-only numeric inference:
    - at least four prefixed lines;
    - >=80% +1 sequence consistency;
    - >=75% bibliographically plausible same-line bodies;
    - unique marker values.

    The detector is global/region-level on purpose. A single ``12 Results``
    line is never a numeric bibliography boundary by itself.
    """
    raw = []
    for i, line in enumerate(lines):
        parsed = prefix_numeric_entry(line.text)
        if parsed is None:
            continue
        n, body = parsed
        raw.append((i, n, body, _same_line_body_plausible(body)))
    values = [n for _, n, _, _ in raw]
    pairs = list(zip(values, values[1:]))
    consistency = (sum(b == a + 1 for a, b in pairs) / len(pairs)) if pairs else 0.0
    body_ratio = (sum(ok for _, _, _, ok in raw) / len(raw)) if raw else 0.0
    unique = len(values) == len(set(values))
    strong = bool(len(raw) >= 4 and consistency >= 0.80 and body_ratio >= 0.75 and unique)
    accepted = {i: n for i, n, _, ok in raw if strong and ok}
    return {
        "detected": strong,
        "n_markers": len(raw),
        "values": values[:120],
        "numeric_consistency": round(float(consistency), 3),
        "body_support_ratio": round(float(body_ratio), 3),
        "line_to_value": accepted,
        "diagnostic_only": True,
    }



def _comma_chain_body_plausible(
    lines: Sequence[LayoutLine], index: int, body: str, next_chain_index: int | None
) -> bool:
    """Check evidence inside one inferred comma-number record.

    Once the global +1 chain is known, apparent comma-number continuation
    lines (page/article numbers) inside the record are allowed.  Evidence is
    collected only up to the next *accepted chain marker*.
    """
    if _same_line_body_plausible(body):
        return True
    chunks = [str(body).strip()]
    stop = next_chain_index if next_chain_index is not None else min(len(lines), index + 5)
    for line in lines[index + 1 : min(stop, index + 5)]:
        raw = line.text.strip()
        if raw:
            chunks.append(raw)
    joined = " ".join(chunks)
    return bool(YEAR_RX.search(joined) or SIN_FECHA_RX.search(joined) or BODY_EVIDENCE_RX.search(joined))


def _longest_plus_one_chain(raw: Sequence[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Return longest document-order subsequence whose values increment by one."""
    if not raw:
        return []
    best = [[item] for item in raw]
    for i, item in enumerate(raw):
        _, value, _ = item
        for j in range(i):
            if raw[j][1] + 1 == value and len(best[j]) + 1 > len(best[i]):
                best[i] = best[j] + [item]
    return max(best, key=len)


def infer_comma_numeric(lines: Sequence[LayoutLine]) -> Dict:
    """Infer historical ``1, Author...`` / ``2, Author...`` bibliographies.

    All comma-number candidates are collected first.  The longest exact +1
    sequence in document order becomes the structural hypothesis, which makes
    the detector robust to continuation lines such as ``17, 506 (1964)``.
    The chain is accepted only with >=4 markers, >=75% bibliographic body
    support and >=60% coverage of all comma-number candidates.
    """
    raw = []
    for i, line in enumerate(lines):
        parsed = comma_numeric_entry(line.text)
        if parsed is not None:
            n, body = parsed
            raw.append((i, n, body))
    chain = _longest_plus_one_chain(raw)
    values = [n for _, n, _ in raw]
    chain_values = [n for _, n, _ in chain]
    supported = []
    for pos, (i, n, body) in enumerate(chain):
        next_i = chain[pos + 1][0] if pos + 1 < len(chain) else None
        supported.append((i, n, body, _comma_chain_body_plausible(lines, i, body, next_i)))
    body_ratio = (sum(ok for _, _, _, ok in supported) / len(supported)) if supported else 0.0
    candidate_ratio = (len(chain) / len(raw)) if raw else 0.0
    unique = len(chain_values) == len(set(chain_values))
    strong = bool(len(chain) >= 4 and body_ratio >= 0.75 and candidate_ratio >= 0.60 and unique)
    # Once the region-level chain is strongly established, every chain marker
    # is a boundary. Individual records may legitimately lack a year/source cue.
    accepted = {i: n for i, n, _ in chain} if strong else {}
    return {
        "detected": strong,
        "n_markers": len(raw),
        "n_chain_markers": len(chain),
        "values": values[:120],
        "chain_values": chain_values[:120],
        "numeric_consistency": round(float(candidate_ratio), 3),
        "body_support_ratio": round(float(body_ratio), 3),
        "line_to_value": accepted,
        "diagnostic_only": True,
    }


def _body_plausible(lines: Sequence[LayoutLine], index: int) -> bool:
    """Require bibliographic-looking content immediately after a bare marker."""
    chunks = []
    for line in lines[index + 1 : min(len(lines), index + 4)]:
        raw = line.text.strip()
        if not raw:
            continue
        if marker_only_number(raw) is not None:
            break
        chunks.append(raw)
    if not chunks:
        return False
    joined = " ".join(chunks)
    # A body can be valid without a year on its first line, but should expose
    # at least one bibliographic cue within a short physical window.
    return bool(YEAR_RX.search(joined) or SIN_FECHA_RX.search(joined) or BODY_EVIDENCE_RX.search(joined))


def infer_marker_only_numeric(lines: Sequence[LayoutLine]) -> Dict:
    """Infer a marker-only numeric regime from a *sequence*, never one number.

    Safety requirements:
    - at least four bare integer lines;
    - at least 80% consecutive +1 transitions;
    - at least 75% markers followed by plausible bibliographic body text;
    - no duplicate marker values in the inferred sequence.

    This prevents isolated page numbers or years from becoming boundaries.
    """
    raw = []
    for i, line in enumerate(lines):
        n = marker_only_number(line.text)
        if n is not None:
            raw.append((i, n, _body_plausible(lines, i)))
    values = [n for _, n, _ in raw]
    pairs = list(zip(values, values[1:]))
    consistency = (sum(b == a + 1 for a, b in pairs) / len(pairs)) if pairs else 0.0
    body_ratio = (sum(ok for _, _, ok in raw) / len(raw)) if raw else 0.0
    unique = len(values) == len(set(values))
    strong = bool(len(raw) >= 4 and consistency >= 0.80 and body_ratio >= 0.75 and unique)
    accepted = {i: n for i, n, ok in raw if strong and ok}
    return {
        "detected": strong,
        "n_markers": len(raw),
        "values": values[:120],
        "numeric_consistency": round(float(consistency), 3),
        "body_support_ratio": round(float(body_ratio), 3),
        "line_to_value": accepted,
        "diagnostic_only": True,
    }


__all__ = ["MARKER_ONLY_RX", "PREFIX_NUMERIC_RX", "COMMA_NUMERIC_RX", "marker_only_number", "prefix_numeric_entry", "comma_numeric_entry", "infer_marker_only_numeric", "infer_prefix_numeric", "infer_comma_numeric"]
