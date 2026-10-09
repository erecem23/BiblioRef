"""Document-context shadow analysis for BiblioRef v0.8.3.

The goal is not to impose a universal thesis grammar.  It assigns auditable,
rule-based page roles and derives *context evidence* for discovered regions.
The context layer can veto obviously incompatible regions (e.g. a Publications
list in front matter) before shadow segmentation, but it never creates records
and never upgrades weak bibliographic evidence by itself.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Sequence

from biblioref.legacy.engine import LayoutLine, is_ref_heading


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


TOC_RX = re.compile(r"^(?:indice|tabla de contenidos|contenido|contents|table of contents)\b", re.I)
PUBLICATIONS_RX = re.compile(
    r"^(?:publications?|publicaciones?|produccion cientifica|produccion academica|"
    r"publicaciones derivadas|lista de publicaciones)\b",
    re.I,
)
CHAPTER_RX = re.compile(
    r"^(?:(?:capitulo|chapter)\s+(?:\d+|[ivxlcdm]+)|"
    r"(?:\d+(?:\.\d+)*)\s+[A-ZÁÉÍÓÚÑÜ])",
    re.I,
)
BACK_MATTER_RX = re.compile(
    r"^(?:curriculum(?: vitae)?|cv|anexos?|appendix|appendices|apendices?|"
    r"agradecimientos|acknowledg(?:e)?ments|glosario|glossary)\b",
    re.I,
)
ABSTRACT_RX = re.compile(r"^(?:resumen|abstract|sumario|summary)\b", re.I)


def _top_lines(lines: Sequence[LayoutLine]) -> List[LayoutLine]:
    return [
        line for line in lines
        if line.text.strip() and float(line.y0) <= 0.33 * float(line.page_height)
    ]


def classify_document_pages(lines: Sequence[LayoutLine]) -> Dict[int, Dict]:
    """Assign simple structural roles to pages using transparent rules.

    Roles are deliberately coarse: ``cover``, ``front_matter``, ``toc``,
    ``publications``, ``chapter_open``, ``body``, ``back_matter`` and
    ``bibliography_heading``.  They are evidence labels, not semantic truth.
    """
    by_page: Dict[int, List[LayoutLine]] = defaultdict(list)
    for line in lines:
        by_page[int(line.page)].append(line)
    if not by_page:
        return {}

    max_page = max(by_page)
    explicit: Dict[int, Dict] = {}
    chapter_pages: List[int] = []
    back_pages: List[int] = []

    for page in range(1, max_page + 1):
        page_lines = sorted(by_page.get(page, []), key=lambda x: (x.y0, x.x0))
        tops = _top_lines(page_lines)
        signals: List[str] = []
        role = None
        heading_text = ""
        for line in tops[:12]:
            text = line.text.strip()
            norm = _norm(text)
            if len(text) <= 160 and is_ref_heading(text):
                role = "bibliography_heading"
                heading_text = text
                signals.append("recognized_reference_heading")
                break
            if PUBLICATIONS_RX.search(norm):
                role = "publications"
                heading_text = text
                signals.append("publications_heading")
                break
            if TOC_RX.search(norm):
                role = "toc"
                heading_text = text
                signals.append("toc_heading")
                break
            if BACK_MATTER_RX.search(norm):
                role = "back_matter"
                heading_text = text
                signals.append("back_matter_heading")
                back_pages.append(page)
                break
            if CHAPTER_RX.search(text):
                role = "chapter_open"
                heading_text = text
                signals.append("chapter_heading")
                chapter_pages.append(page)
                break
            if ABSTRACT_RX.search(norm):
                signals.append("abstract_heading")

        explicit[page] = {
            "page": page,
            "role": role,
            "heading_text": heading_text,
            "signals": signals,
        }

    first_chapter = min(chapter_pages) if chapter_pages else None
    first_back = min(back_pages) if back_pages else None

    output: Dict[int, Dict] = {}
    for page in range(1, max_page + 1):
        item = dict(explicit[page])
        role = item["role"]
        if role is None:
            if page == 1 and max_page > 1:
                role = "cover"
                item["signals"].append("first_page_default")
            elif first_chapter is not None and page < first_chapter:
                role = "front_matter"
                item["signals"].append("before_first_chapter")
            elif first_back is not None and page >= first_back:
                role = "back_matter"
                item["signals"].append("after_back_matter_open")
            else:
                role = "body"
        item["role"] = role
        item["page_fraction"] = round(page / max_page, 3)
        output[page] = item
    return output


def region_document_context(
    lines: Sequence[LayoutLine],
    region: Dict,
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    """Describe whether document structure supports or contradicts a region.

    Strongly incompatible roles can block *shadow segmentation* after the
    bibliographic verifier, but positive context never verifies a bibliography
    on its own.
    """
    roles = page_roles or classify_document_pages(lines)
    if not roles:
        return {
            "dominant_role": "unknown",
            "role_counts": {},
            "positive_evidence": [],
            "negative_evidence": [],
            "strong_negative": False,
            "context_score": 0.0,
            "next_structural_role": None,
            "previous_structural_role": None,
        }

    start = int(region["start_page"])
    end = int(region["end_page"])
    page_count = max(roles)
    region_roles = [roles[p]["role"] for p in range(start, end + 1) if p in roles]
    counts: Dict[str, int] = defaultdict(int)
    for role in region_roles:
        counts[role] += 1
    dominant = max(counts, key=lambda key: (counts[key], key)) if counts else "unknown"

    previous = roles.get(start - 1, {}).get("role")
    next_role = roles.get(end + 1, {}).get("role")
    positive: List[Dict] = []
    negative: List[Dict] = []
    score = 0.0

    def add(value: float, signal: str) -> None:
        nonlocal score
        score += value
        positive.append({"signal": signal, "points": value})

    def sub(value: float, signal: str) -> None:
        nonlocal score
        score -= value
        negative.append({"signal": signal, "points": -value})

    if dominant == "bibliography_heading":
        add(3.0, "region_page_has_reference_heading_role")
    if next_role == "chapter_open":
        add(2.0, "next_page_opens_new_chapter")
    if end >= max(1, int(page_count * 0.70)) and dominant in {"body", "bibliography_heading"}:
        add(1.0, "late_document_body_or_reference_region")
    if previous in {"body", "chapter_open"} and next_role in {"chapter_open", "back_matter", None}:
        add(0.5, "structurally_plausible_bibliography_transition")

    if dominant == "publications":
        sub(6.0, "publications_section_is_not_primary_bibliography")
    if dominant == "toc":
        sub(6.0, "table_of_contents_is_not_bibliography")
    if dominant == "front_matter":
        sub(2.0, "generic_front_matter_context")
    if dominant == "cover":
        sub(3.0, "cover_context")
    if dominant == "back_matter" and not any(
        roles.get(p, {}).get("role") == "bibliography_heading" for p in range(start, end + 1)
    ):
        sub(1.5, "generic_back_matter_without_reference_heading")

    strong_negative = any(
        item["signal"] in {
            "publications_section_is_not_primary_bibliography",
            "table_of_contents_is_not_bibliography",
        }
        for item in negative
    )
    return {
        "dominant_role": dominant,
        "region_page_roles": region_roles,
        "role_counts": dict(sorted(counts.items())),
        "positive_evidence": positive,
        "negative_evidence": negative,
        "strong_negative": strong_negative,
        "context_score": round(score, 2),
        "previous_structural_role": previous,
        "next_structural_role": next_role,
        "page_count": page_count,
    }


def summarize_document_context(
    lines: Sequence[LayoutLine],
    page_roles: Dict[int, Dict] | None = None,
) -> Dict:
    roles = page_roles if page_roles is not None else classify_document_pages(lines)
    counts: Dict[str, int] = defaultdict(int)
    for item in roles.values():
        counts[item["role"]] += 1
    return {
        "page_count": max(roles, default=0),
        "role_counts": dict(sorted(counts.items())),
        "pages": [roles[p] for p in sorted(roles)],
    }
