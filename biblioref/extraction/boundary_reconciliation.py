"""Conservative post-segmentation boundary reconciliation (algorithm v0.6.5).

This layer runs *after* a bibliography zone has been detected and initially
segmented, but *before* downstream metadata parsing.  Its purpose is not to
parse citation fields.  It asks a narrower question: in a zone with a strong
hanging-indent geometry, do the physical first-line boundaries disagree with the textual segmentation?
The layer can recover a missed start or remove a weak continuation-margin start,
but only when the hanging-indent geometry and local bibliography evidence agree.

The repair is deliberately evidence-gated.  It auto-applies only when the zone
has a well-separated start/continuation margin, the proposed boundaries are
bibliographically dense, and the candidate segmentation remains close to the
validated segmentation.  This makes institutional authors, wrapped author
lists and an atypical first entry recoverable without weakening the global
start regexes.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from biblioref.core.patterns import AUTHOR_LIST_TAIL_RX, YEAR_OR_SOURCE_RX
from biblioref.legacy.engine import AdaptiveLayoutZone, LayoutLine, YEAR_RX, SIN_FECHA_RX


BOUNDARY_RECONCILIATION_VERSION = "0.6.5-hanging-indent-boundary2"

_PAGE_NUMBER_RX = re.compile(r"^\s*(?:\[?\d{1,4}\]?|[-–—]?\s*\d{1,4}\s*[-–—]?)\s*$")
_AUTHOR_LEAD_RX = re.compile(r"^[A-ZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇ0-9][^\n]{2,}")
_NORMALIZE_RX = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _NORMALIZE_RX.sub(" ", str(text or "")).strip().casefold()


def _is_heading_line(line: LayoutLine, zone: AdaptiveLayoutZone) -> bool:
    h = zone.heading
    return bool(
        int(line.page) == int(h.page)
        and abs(float(line.y0) - float(h.y0)) <= 1.5
        and _norm(line.text) == _norm(h.text)
    )


def _local_repeated_decorations(lines: Sequence[LayoutLine]) -> set[Tuple[str, str]]:
    """Return repeated top/bottom decoration keys using only the zone lines.

    Full-document decoration detection already exists in the adaptive layer,
    but the effective repair intentionally remains self-contained.  Requiring
    the same normalized text on >=3 pages in the same outer band is enough to
    suppress running headers/footers without touching ordinary references.
    """
    by_key: Dict[Tuple[str, str], set[int]] = {}
    for line in lines:
        text = _norm(line.text)
        if not text or len(text) > 180:
            continue
        height = max(float(getattr(line, "page_height", 0.0) or 0.0), 1.0)
        rel = float(line.y0) / height
        band = "top" if rel <= 0.075 else "bottom" if rel >= 0.90 else ""
        if not band:
            continue
        by_key.setdefault((text, band), set()).add(int(line.page))
    return {key for key, pages in by_key.items() if len(pages) >= 3}


def _is_local_decoration(line: LayoutLine, keys: set[Tuple[str, str]]) -> bool:
    height = max(float(getattr(line, "page_height", 0.0) or 0.0), 1.0)
    rel = float(line.y0) / height
    band = "top" if rel <= 0.075 else "bottom" if rel >= 0.90 else ""
    return bool(band and (_norm(line.text), band) in keys)


def _clean_zone_lines(zone: AdaptiveLayoutZone) -> List[LayoutLine]:
    keys = _local_repeated_decorations(zone.lines)
    out = []
    for line in zone.lines:
        text = str(line.text or "").strip()
        if not text:
            continue
        if _is_heading_line(line, zone):
            continue
        if _is_local_decoration(line, keys):
            continue
        # Standalone page numbers are never reference starts; keeping them in a
        # segment only contaminates the text, so discard them here as well.
        if _PAGE_NUMBER_RX.fullmatch(text) and float(line.x0) > float(zone.layout.start_margin) + 40:
            continue
        out.append(line)
    return out


def _near_start_margin(line: LayoutLine, start_margin: float, tolerance: float) -> bool:
    return abs(float(line.x0) - start_margin) <= tolerance


def _candidate_author_shape(text: str) -> bool:
    text = str(text or "").strip()
    if not text or len(text) < 4 or len(text) > 360:
        return False
    if _PAGE_NUMBER_RX.fullmatch(text):
        return False
    if not _AUTHOR_LEAD_RX.match(text):
        return False
    # A boundary line may be an institutional author (no comma), a personal
    # author list, or a digit-leading organisation such as ``5G Américas``.
    # Do not require a comma/year here: those are precisely the failure modes
    # this reconciliation layer is meant to recover.
    return True


def _window_has_bibliographic_evidence(lines: Sequence[LayoutLine], start: int, stop: int) -> bool:
    # The date can be delayed by a wrapped author list or by an institutional
    # author line.  Inspect up to the first three physical lines of the proposed
    # record, never crossing the next geometric boundary.
    probe = " ".join(str(lines[i].text or "").strip() for i in range(start, min(stop, start + 3)))
    probe = _NORMALIZE_RX.sub(" ", probe).strip()
    if not probe:
        return False
    return bool(YEAR_RX.search(probe[:700]) or SIN_FECHA_RX.search(probe[:700]) or YEAR_OR_SOURCE_RX.search(probe[:700]))


def _build_raw_candidates(lines: Sequence[LayoutLine], start_margin: float, tolerance: float) -> List[int]:
    return [
        i for i, line in enumerate(lines)
        if _near_start_margin(line, start_margin, tolerance) and _candidate_author_shape(line.text)
    ]


def _filter_candidates(lines: Sequence[LayoutLine], raw: Sequence[int]) -> Tuple[List[int], int]:
    accepted: List[int] = []
    rejected_no_evidence = 0
    for pos, index in enumerate(raw):
        next_index = raw[pos + 1] if pos + 1 < len(raw) else len(lines)
        if _window_has_bibliographic_evidence(lines, index, next_index):
            accepted.append(index)
        else:
            rejected_no_evidence += 1
    return accepted, rejected_no_evidence


def _segment(lines: Sequence[LayoutLine], starts: Sequence[int], style: str) -> List[Dict]:
    segments: List[Dict] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        source = list(lines[start:end])
        if not source:
            continue
        text = _NORMALIZE_RX.sub(
            " ", " ".join(str(line.text or "").strip() for line in source if str(line.text or "").strip())
        ).strip()
        if not text:
            continue
        pages = sorted({int(line.page) for line in source})
        segments.append({
            "reference_text": text,
            "annotation_text": "",
            "style": style,
            "reference_start_page": pages[0],
            "reference_end_page": pages[-1],
            "reference_start_x": round(float(source[0].x0), 2),
            "boundary_evidence": "hanging_indent_start_margin+local_bibliographic_evidence",
            "audit_flags": "cross_page" if len(pages) > 1 else "",
            "boundary_reconciliation_version": BOUNDARY_RECONCILIATION_VERSION,
        })
    return segments


def _quality(segments: Sequence[Dict]) -> Dict:
    texts = [str(s.get("reference_text", "")).strip() for s in segments if str(s.get("reference_text", "")).strip()]
    words = [len(t.split()) for t in texts]
    evidence = sum(bool(YEAR_OR_SOURCE_RX.search(t) or YEAR_RX.search(t) or SIN_FECHA_RX.search(t)) for t in texts)
    return {
        "n_segments": len(texts),
        "median_words": round(float(statistics.median(words)), 2) if words else 0.0,
        "max_words": max(words) if words else 0,
        "n_giant_segments": sum(w >= 500 for w in words),
        "evidence_ratio": round(evidence / max(len(texts), 1), 3),
    }


def _base_start_margin_support(base_records: Sequence[Dict], start_margin: float, tolerance: float) -> float:
    xs = []
    for record in base_records:
        try:
            xs.append(float(record.get("reference_start_x")))
        except (TypeError, ValueError):
            continue
    if not xs:
        return 0.0
    return sum(abs(x - start_margin) <= tolerance for x in xs) / len(xs)


_REPEATED_AUTHOR_YEAR_START_RX = re.compile(
    r"^\s*(?:\((?:18|19|20)\d{2}[a-z]?\)[.)]?|(?:18|19|20)\d{2}[a-z]?[.)])\s+",
    re.I,
)


def _previous_record_is_complete(base_records: Sequence[Dict], index: int) -> bool:
    """¿El registro de arriba termina como una referencia, o como una cabecera?

    v0.6.10: ``(1995). Título…`` fuera del margen es ambiguo. Es una entrada de
    autor repetido cuando el registro de arriba ya está completo, y es la
    continuación de ese registro cuando el año se fue a la línea siguiente —el
    caso en que la lista de autores ocupa toda la primera línea—. Lo que los
    separa es cómo termina el de arriba: una referencia no termina en
    ``& Apellido, X.``.
    """
    if index <= 0:
        return False
    previous = str(base_records[index - 1].get("reference_text") or "").strip()
    if not previous:
        return False
    return not AUTHOR_LIST_TAIL_RX.search(previous)


def _off_margin_baseline_diagnostics(
    base_records: Sequence[Dict], start_margin: float, tolerance: float
) -> Dict[str, int]:
    """Characterise baseline starts that disagree with the hanging-indent margin.

    v0.6.5 may *remove* weak false boundaries.  Repeated-author entries such as
    ``(1995). Title...`` are protected: they are a legitimate convention in
    which a new record can begin at the continuation margin and must not be
    swallowed by geometric reconciliation.

    v0.6.10: la licencia para quitar un borde se decidía por la *etiqueta* de la
    regla que lo había producido (``author+bare_year+local_geometry``).  Eso
    acopla la reparación al rotulado aguas arriba: cualquier cambio que haga que
    el mismo borde lo produzca otra regla revoca el permiso aunque el borde siga
    estando mal.  En una bibliografía autor-año con sangría francesa —lo único
    que llega hasta acá— un arranque fuera del margen que no sea una entrada de
    autor repetido es débil por geometría, sin importar quién lo produjo.
    """
    off_margin = 0
    weak_local_geometry = 0
    protected_repeated_author = 0
    other_strong = 0
    for index, record in enumerate(base_records):
        try:
            x = float(record.get("reference_start_x"))
        except (TypeError, ValueError):
            continue
        if abs(x - start_margin) <= tolerance:
            continue
        off_margin += 1
        text = str(record.get("reference_text") or "").strip()
        if _REPEATED_AUTHOR_YEAR_START_RX.match(text) and _previous_record_is_complete(
            base_records, index
        ):
            protected_repeated_author += 1
        else:
            weak_local_geometry += 1
    return {
        "n_baseline_off_margin_starts": off_margin,
        "n_baseline_off_margin_weak_local_geometry": weak_local_geometry,
        "n_baseline_off_margin_protected_repeated_author": protected_repeated_author,
        "n_baseline_off_margin_other": other_strong,
    }


def _first_record_head_missing(base_records: Sequence[Dict], segments: Sequence[Dict]) -> bool:
    if not base_records or not segments:
        return False
    base = _norm(base_records[0].get("reference_text", ""))
    candidate = _norm(segments[0].get("reference_text", ""))
    if not base or not candidate:
        return False
    # Use a compact prefix because PDF hyphenation can change later text.
    prefix = candidate[: min(48, len(candidate))]
    return not base.startswith(prefix)


def build_hanging_indent_boundary_repair(zone: AdaptiveLayoutZone, base_records: Sequence[Dict]) -> Dict:
    """Propose an effective second-pass segmentation for strong hanging indents.

    The function does *not* depend on a citation style name, repository or
    language.  It learns the first-line margin from the zone geometry and uses
    textual evidence only as a local confirmation.  Acceptance is intentionally
    conservative because an accepted proposal becomes effective extraction.
    """
    base_records = list(base_records or [])
    layout = zone.layout
    style = str(zone.style.style)
    base_n = len(base_records)

    if style in {"numeric", "bracket_key", "bulleted"}:
        return {"accepted": False, "reason": "boundary_reconciliation_not_author_year_like"}
    if not bool(getattr(layout, "hanging_indent_detected", False)):
        return {"accepted": False, "reason": "no_hanging_indent_geometry"}
    if base_n < 5:
        return {"accepted": False, "reason": "too_few_baseline_records", "n_base_segments": base_n}

    start_margin = float(getattr(layout, "start_margin", 0.0) or 0.0)
    continuation_margin = float(getattr(layout, "continuation_margin", start_margin) or start_margin)
    separation = continuation_margin - start_margin
    if separation < 14.0:
        return {
            "accepted": False,
            "reason": "start_continuation_margin_not_well_separated",
            "margin_separation": round(separation, 2),
        }

    # Never let the candidate tolerance consume the continuation cluster.
    declared_tol = float(getattr(layout, "start_margin_tolerance", 12.0) or 12.0)
    tolerance = max(2.0, min(6.0, declared_tol * 0.5, separation * 0.22))
    lines = _clean_zone_lines(zone)
    raw = _build_raw_candidates(lines, start_margin, tolerance)
    starts, n_rejected_no_evidence = _filter_candidates(lines, raw)
    segments = _segment(lines, starts, style)
    q = _quality(segments)

    new_n = len(segments)
    delta = new_n - base_n
    base_margin_support = _base_start_margin_support(base_records, start_margin, max(tolerance, 3.0))
    candidate_evidence_purity = new_n / max(len(raw), 1)
    head_missing = _first_record_head_missing(base_records, segments)

    # v0.6.5 keeps the original missed-boundary repair but also permits a
    # narrowly gated *negative* delta when a strong hanging indent proves that
    # the baseline created weak starts at the continuation margin.  This is the
    # symmetric failure mode observed in the UNC holdout: eight continuation
    # lines containing bare years were split, while one institutional author
    # with its year on the next line was missed.
    max_gain = max(8, min(60, int(base_n * 0.15) + 3))
    base_diag = _off_margin_baseline_diagnostics(
        base_records, start_margin, max(tolerance, 3.0)
    )
    common_quality_gate = bool(
        new_n >= 5
        and len(raw) >= new_n
        and candidate_evidence_purity >= 0.94
        and base_margin_support >= 0.90
        and q["n_giant_segments"] == 0
        and q["evidence_ratio"] >= 0.90
        and 3 <= q["median_words"] <= 150
        and q["max_words"] < 500
    )
    missed_boundary_accept = bool(
        common_quality_gate
        and delta >= 1
        and delta <= max_gain
    )
    false_boundary_accept = bool(
        common_quality_gate
        and delta < 0
        and abs(delta) <= max_gain
        and candidate_evidence_purity >= 0.97
        and base_diag["n_baseline_off_margin_weak_local_geometry"] >= abs(delta)
        and base_diag["n_baseline_off_margin_protected_repeated_author"] == 0
        and base_diag["n_baseline_off_margin_other"] == 0
    )
    accepted = missed_boundary_accept or false_boundary_accept

    return {
        "accepted": accepted,
        "reason": (
            "hanging_indent_missing_boundaries_reconciled"
            if accepted and delta > 0 else
            "hanging_indent_weak_false_boundaries_removed_and_missing_reconciled"
            if accepted and delta < 0 else
            "hanging_indent_boundary_reconciliation_failed_gate"
        ),
        "version": BOUNDARY_RECONCILIATION_VERSION,
        "n_base_segments": base_n,
        "n_reconciled_segments": new_n,
        "delta": delta,
        "max_allowed_gain": max_gain,
        "repair_direction": (
            "recover_missing_boundaries" if delta > 0 else
            "remove_weak_false_boundaries_and_reconcile" if delta < 0 else
            "no_change"
        ),
        **base_diag,
        "start_margin": round(start_margin, 2),
        "continuation_margin": round(continuation_margin, 2),
        "margin_separation": round(separation, 2),
        "start_margin_tolerance_effective": round(tolerance, 2),
        "base_start_margin_support": round(base_margin_support, 3),
        "n_raw_geometric_candidates": len(raw),
        "n_candidates_rejected_without_local_evidence": n_rejected_no_evidence,
        "candidate_evidence_purity": round(candidate_evidence_purity, 3),
        "first_reference_recovered": bool(head_missing and accepted),
        **q,
        "segments": segments,
    }
