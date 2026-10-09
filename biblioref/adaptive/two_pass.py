"""Experimental two-pass PDF localization for v0.9.0 shadow.

This module is deliberately diagnostic-only. It proposes page windows from a cheap
plain-text pass and may extract detailed layout only inside those windows, but the
validated v0.6.1 output continues to use the full layout path.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from biblioref.ingestion.backend_context import pymupdf

from biblioref.ingestion.pdf import extract_layout_lines_range

YEAR_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
DOI_URL_RX = re.compile(r"(?:https?://|doi\s*:|10\.\d{4,9}/)", re.I)
REF_HEADING_RX = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?:bibliograf[ií]a|referencias(?:\s+bibliogr[aá]ficas)?|references|bibliography|obras\s+citadas|fuentes\s+y\s+bibliograf[ií]a)\s*[:.]?\s*$",
    re.I,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def cheap_page_profiles(pdf_path: str | Path) -> Tuple[List[Dict], float]:
    """Read plain text only and summarize page-level bibliography signals."""
    started = time.perf_counter()
    profiles: List[Dict] = []
    with pymupdf.open(pdf_path) as doc:
        n_pages = doc.page_count
        for index, page in enumerate(doc):
            text = page.get_text("text") or ""
            lines = [_clean(x) for x in text.splitlines() if _clean(x)]
            heading_lines = [x for x in lines if REF_HEADING_RX.match(x)]
            year_lines = sum(bool(YEAR_RX.search(x)) for x in lines)
            url_lines = sum(bool(DOI_URL_RX.search(x)) for x in lines)
            punct_lines = sum(bool(re.search(r"[.;:].*[.;:]", x)) for x in lines if len(x) >= 25)
            n_lines = len(lines)
            evidence_lines = sum(
                bool(YEAR_RX.search(x) or DOI_URL_RX.search(x)) and 12 <= len(x) <= 700
                for x in lines
            )
            density = evidence_lines / max(n_lines, 1)
            profiles.append({
                "page": index + 1,
                "n_pages": n_pages,
                "char_count": len(text.strip()),
                "n_lines": n_lines,
                "heading_hit": bool(heading_lines),
                "heading_text": heading_lines[0][:160] if heading_lines else "",
                "year_lines": year_lines,
                "url_doi_lines": url_lines,
                "punctuation_lines": punct_lines,
                "evidence_lines": evidence_lines,
                "evidence_density": round(density, 4),
            })
    return profiles, time.perf_counter() - started


def _merge_windows(windows: Sequence[Tuple[int, int]], page_count: int) -> List[Tuple[int, int]]:
    clean = sorted((max(1, a), min(page_count, b)) for a, b in windows if a <= b)
    merged: List[List[int]] = []
    for start, end in clean:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(a, b) for a, b in merged]


def propose_candidate_windows(
    profiles: Sequence[Dict],
    *,
    margin_before: int = 1,
    margin_after: int = 2,
    density_threshold: float = 0.18,
    min_evidence_lines: int = 4,
) -> Dict:
    """Propose conservative windows from headings and sustained reference-like density.

    Heading evidence is strongest: once a recognized reference heading appears, the
    candidate extends through subsequent text-bearing pages while bibliography-like
    evidence remains plausible, with generous tolerance for sparse pages. Density-only
    runs require two nearby supporting pages and remain diagnostic-only.
    """
    if not profiles:
        return {"windows": [], "confidence": "none", "reasons": ["empty_document"]}
    page_count = len(profiles)
    windows: List[Tuple[int, int]] = []
    reasons: List[str] = []
    heading_pages = [int(p["page"]) for p in profiles if p.get("heading_hit")]

    for hp in heading_pages:
        end = hp
        sparse_run = 0
        for page_no in range(hp, page_count + 1):
            p = profiles[page_no - 1]
            plausible = (
                int(p.get("evidence_lines", 0)) >= 2
                or float(p.get("evidence_density", 0.0)) >= 0.08
                or int(p.get("url_doi_lines", 0)) >= 1
                or int(p.get("char_count", 0)) < 80
            )
            if plausible:
                sparse_run = 0
                end = page_no
            else:
                sparse_run += 1
                if sparse_run <= 2:
                    end = page_no
                else:
                    break
        windows.append((hp - margin_before, end + margin_after))
    if heading_pages:
        reasons.append("recognized_reference_heading")

    dense_pages = []
    for p in profiles:
        if int(p.get("evidence_lines", 0)) >= min_evidence_lines and float(p.get("evidence_density", 0.0)) >= density_threshold:
            dense_pages.append(int(p["page"]))
    if dense_pages:
        groups: List[List[int]] = [[dense_pages[0]]]
        for page in dense_pages[1:]:
            if page - groups[-1][-1] <= 2:
                groups[-1].append(page)
            else:
                groups.append([page])
        for group in groups:
            # avoid single noisy pages unless very late and very dense
            if len(group) >= 2 or float(profiles[group[0]-1].get("evidence_density", 0)) >= 0.35:
                windows.append((group[0] - margin_before, group[-1] + margin_after))
        reasons.append("sustained_bibliographic_density")

    merged = _merge_windows(windows, page_count)
    covered = sum(b - a + 1 for a, b in merged)
    fraction = covered / page_count if page_count else 0.0
    if heading_pages:
        confidence = "heading_supported"
    elif merged:
        confidence = "density_only"
    else:
        confidence = "insufficient"
    return {
        "windows": [{"start_page": a, "end_page": b, "n_pages": b-a+1} for a, b in merged],
        "confidence": confidence,
        "reasons": reasons or ["no_safe_candidate"],
        "candidate_pages": covered,
        "page_count": page_count,
        "candidate_fraction": round(fraction, 4),
        "safe_to_narrow": bool(heading_pages and merged),
        "auto_apply": False,
    }


def detailed_layout_for_windows(pdf_path: str | Path, windows: Sequence[Dict]) -> Tuple[List, float]:
    started = time.perf_counter()
    lines = []
    for window in windows:
        lines.extend(extract_layout_lines_range(pdf_path, int(window["start_page"]), int(window["end_page"])))
    return lines, time.perf_counter() - started


def _effective_zone_ranges(report: Dict) -> List[Tuple[int, int]]:
    ranges = []
    for z in report.get("zones", []) or []:
        try:
            ranges.append((int(z["start_page"]), int(z["end_page"])))
        except Exception:
            pass
    return ranges


def assess_zone_coverage(windows: Sequence[Dict], effective_report: Dict) -> Dict:
    ranges = _effective_zone_ranges(effective_report)
    wranges = [(int(w["start_page"]), int(w["end_page"])) for w in windows]
    rows = []
    for start, end in ranges:
        fully = any(ws <= start and we >= end for ws, we in wranges)
        overlap = any(not (we < start or ws > end) for ws, we in wranges)
        rows.append({"start_page": start, "end_page": end, "overlap": overlap, "fully_covered": fully})
    n = len(rows)
    return {
        "n_effective_zones": n,
        "n_overlap": sum(x["overlap"] for x in rows),
        "n_fully_covered": sum(x["fully_covered"] for x in rows),
        "zone_overlap_recall": round(sum(x["overlap"] for x in rows) / n, 4) if n else None,
        "zone_full_coverage_recall": round(sum(x["fully_covered"] for x in rows) / n, 4) if n else None,
        "zones": rows,
    }


def build_two_pass_shadow(pdf_path: str | Path, effective_report: Dict) -> Dict:
    profiles, cheap_s = cheap_page_profiles(pdf_path)
    proposal = propose_candidate_windows(profiles)
    detail_lines, detail_s = detailed_layout_for_windows(pdf_path, proposal["windows"]) if proposal["windows"] else ([], 0.0)
    coverage = assess_zone_coverage(proposal["windows"], effective_report)
    return {
        "version": "0.9.0-two-pass-shadow1",
        "mode": "shadow",
        "diagnostic_only": True,
        "auto_apply": False,
        "effective_output_unchanged": True,
        "first_pass": {
            "seconds": round(cheap_s, 6),
            "page_profiles": profiles,
        },
        "proposal": proposal,
        "second_pass": {
            "seconds": round(detail_s, 6),
            "n_detailed_layout_lines": len(detail_lines),
            "windows": proposal["windows"],
        },
        "effective_zone_coverage": coverage,
        "eligibility_gate": {
            "eligible_for_future_safe_narrowing": bool(
                proposal.get("safe_to_narrow")
                and coverage.get("zone_full_coverage_recall") in (1.0, None)
            ),
            "requires_external_holdout_before_auto_apply": True,
        },
    }
