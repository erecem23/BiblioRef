"""Narrow explicit-heading repair for an omitted first reference."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Sequence

from biblioref.ingestion import extract_layout_lines_range


_HEADING_KEYS = {
    "bibliografia",
    "bibliografía",
    "bibliography",
    "references",
    "reference",
    "referencias",
    "referencies",
    "referenciasbibliograficas",
    "listofreferences",
    "referencelist",
}
_YEAR_RE = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
_DEFERRED_YEAR_RE = re.compile(
    r"^[A-ZÁÉÍÓÚÜÑ]\.?\s*\((?:18|19|20)\d{2}[a-z]?\)",
    re.I,
)
_EVIDENCE_PREFIX = "core_first_reference_repair_v0_6_8"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _compact_ocr_word(text: str) -> str:
    return re.sub(r"[^a-záéíóúüñ]+", "", _norm(text).lower())


def _looks_like_bibliography_heading(text: str) -> bool:
    return _compact_ocr_word(text) in _HEADING_KEYS


def _candidate_key(text: str) -> str:
    return re.sub(
        r"[^a-z0-9áéíóúüñ]+",
        " ",
        _norm(text).lower(),
    ).strip()


def _line_opens_record(line_text: str, record_text: str) -> bool:
    """Conservatively locate the physical line that opens a returned record."""
    line = _candidate_key(line_text)
    record = _candidate_key(record_text)
    if not line or not record:
        return False
    tokens = line.split()
    prefix = " ".join(tokens[: min(6, len(tokens))])
    if len(prefix) >= 8 and record.startswith(prefix):
        return True
    record_tokens = record.split()
    record_prefix = " ".join(record_tokens[: min(6, len(record_tokens))])
    return bool(
        record_prefix
        and line.startswith(record_prefix)
        and len(record_prefix) >= 8
    )


def _author_opening_score(lines, idx: int) -> float:
    text = _norm(lines[idx].text)
    if not text or _looks_like_bibliography_heading(text):
        return -8.0
    score = 0.0
    if re.search(r"\((?:18|19|20)\d{2}[a-z]?\)", text, re.I):
        score += 5.0
    if re.search(
        r"(?:^|[,;]\s*)(?:18|19|20)\d{2}[a-z]?(?:[,.:)]|\s)",
        text,
        re.I,
    ):
        score += 3.5
    if re.search(r"\b(?:eds?\.?|coords?\.?|comps?\.?)\b", text, re.I):
        score += 2.0
    if ";" in text:
        score += 2.2
    if "," in text:
        score += 1.2
    if re.search(r"\b[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]{2,}\b", text):
        score += 0.8
    if re.search(r"\b[A-ZÁÉÍÓÚÜÑ]\.?\s*(?:[,;]|$)", text):
        score += 1.0
    lookahead = " ".join(
        _norm(lines[j].text)
        for j in range(idx + 1, min(len(lines), idx + 3))
    )
    if (
        re.search(r"\((?:18|19|20)\d{2}[a-z]?\)", lookahead, re.I)
        and ("," in text or ";" in text)
    ):
        score += 4.2
    if re.match(r"^[a-záéíóúüñ]", text):
        score -= 3.0
    if re.match(r"^[)\].,:;]", text):
        score -= 2.5
    return score


def _evidence(kind: str, existing: str = "") -> str:
    label = f"{_EVIDENCE_PREFIX}+{kind}"
    return _norm(f"{existing}+{label}") if existing else label


def apply_first_reference_repair(
    pdf_path: str | Path,
    zones: Sequence[dict],
    records: Sequence[dict],
) -> tuple[list[dict], list[dict]]:
    """Repair only a physically evidenced prefix after an explicit heading."""
    repaired = deepcopy(list(records or []))
    repairs: list[dict] = []
    if not repaired or not zones:
        return repaired, repairs

    for zone in zones:
        zone_id = zone.get("zone_id")
        indices = [
            index
            for index, record in enumerate(repaired)
            if record.get("zone_id") == zone_id
        ]
        if not indices:
            continue
        first_index = indices[0]
        first = repaired[first_index]
        try:
            page = int(
                first.get("reference_start_page")
                or zone.get("start_page")
                or 0
            )
        except (TypeError, ValueError):
            continue
        if page <= 0:
            continue
        try:
            lines = extract_layout_lines_range(pdf_path, page, page)
        except Exception:
            continue
        if not lines:
            continue

        first_text = _norm(first.get("reference_text") or "")
        first_line_index = next(
            (
                index
                for index, line in enumerate(lines)
                if _line_opens_record(line.text, first_text)
            ),
            None,
        )
        if first_line_index is None:
            continue

        heading_index = next(
            (
                index
                for index in range(first_line_index - 1, -1, -1)
                if _looks_like_bibliography_heading(lines[index].text)
            ),
            None,
        )
        if heading_index is None:
            continue

        prefix = [
            line
            for line in lines[heading_index + 1 : first_line_index]
            if _norm(line.text)
        ]
        if not prefix:
            continue
        prefix_text = _norm(" ".join(line.text for line in prefix))
        if (
            not prefix_text
            or _author_opening_score(lines, heading_index + 1) < 1.0
        ):
            continue

        try:
            prefix_start_x = float(prefix[0].x0)
        except (AttributeError, TypeError, ValueError):
            continue

        prefix_has_year = bool(_YEAR_RE.search(prefix_text))
        first_is_deferred = bool(_DEFERRED_YEAR_RE.match(first_text))
        if not prefix_has_year and first_is_deferred:
            first["reference_text"] = _norm(f"{prefix_text} {first_text}")
            first["reference_start_x"] = prefix_start_x
            first["boundary_evidence"] = _evidence(
                "prepend_deferred_author",
                first.get("boundary_evidence") or "",
            )
            repairs.append({
                "zone_id": zone_id,
                "kind": "prepend_deferred_author",
                "page": page,
                "text": prefix_text,
            })
            continue

        if not prefix_has_year:
            continue

        new_record = deepcopy(first)
        new_record["reference_text"] = prefix_text
        new_record["reference_start_page"] = page
        new_record["reference_end_page"] = page
        new_record["reference_start_x"] = prefix_start_x
        new_record["boundary_evidence"] = _evidence(
            "insert_omitted_first_reference"
        )
        new_record["audit_flags"] = ""
        new_record["ref_in_zone"] = 1
        new_record["reference_fingerprint"] = ""
        new_record["duplicate_group_id"] = ""
        for field in (
            "duplicate_occurrence_count",
            "duplicate_zone_ids",
            "is_repeated_across_zones",
        ):
            new_record.pop(field, None)
        repaired.insert(first_index, new_record)
        for record in repaired[first_index + 1 :]:
            if (
                record.get("zone_id") == zone_id
                and isinstance(record.get("ref_in_zone"), int)
            ):
                record["ref_in_zone"] += 1
        repairs.append({
            "zone_id": zone_id,
            "kind": "insert_omitted_first_reference",
            "page": page,
            "text": prefix_text,
        })

    return repaired, repairs
