from __future__ import annotations

import re
import statistics
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Sequence

from biblioref.ingestion import extract_layout_lines_range, page_dimensions
from biblioref_page_boundary import evaluate_page_boundary
from biblioref_page_decorations import filter_repeated_page_decorations

YEAR_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
PAREN_YEAR_RX = re.compile(r"\((?:18|19|20)\d{2}[a-z]?\)", re.I)
BARE_YEAR_RX = re.compile(r"[,;]\s*(?:18|19|20)\d{2}[a-z]?\s*[,.:]", re.I)
EDITOR_RX = re.compile(r"\b(?:eds?\.?|editors?|coords?\.?|comp(?:s|iladores?)?\.?)\b", re.I)
AUTHOR_PREFIX_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+(?:\s+[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+){0,5}"
    r"(?:\s*[,;:]|\s+(?:and|y|&|et\s+al\.?))|[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+,\s*[A-Z])",
    re.I,
)


_UPPER = r"A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ"
_LOWER = r"a-záéíóúüñß-öø-ÿ"
_WORD = rf"[{_UPPER}][{_UPPER}{_LOWER}\w'’\-]*"
_PARTICLE = (r"(?:de\s+la|de\s+los|van\s+der|van\s+den|de|del|da|das|do|dos|van|von"
             r"|di|della|le|ten|ter|y|e)")
#: Frase de nombre propio, con partícula al frente o adentro: "van Dijk",
#: "Lunazzi de Juabny", "UN DESA".
_NAME = rf"(?:{_PARTICLE}\s+)?{_WORD}(?:\s+(?:{_PARTICLE}\s+)?{_WORD}){{0,4}}"
RECORD_HEAD_RX = re.compile(rf"^{_NAME}\s*[,.;:]")
LEGAL_HEAD_RX = re.compile(
    r"^(?:ley|decreto|resoluci[oó]n|ordenanza|c[oó]digo|constituci[oó]n|disposici[oó]n)\b",
    re.I,
)
DATE_OR_SOURCE_RX = re.compile(
    r"\((?:1[6-9]|20)\d\d|\b(?:1[6-9]|20)\d\d\b|https?://|www\.|doi\s*:"
    r"|\bs\.?\s*/?\s*f\.?\b|\bs-f\b|\ben\s+prensa\b",
    re.I,
)
TERMINATED_RX = re.compile(r"[.)\]»”\d]\s*$")
#: "Disorders, 5 (1): 368-376." es el nombre de una revista partido en dos
#: líneas, no un apellido: a un nombre propio le sigue la inicial o el año, no
#: el número de volumen.
VOLUME_TAIL_RX = re.compile(r"^(?!(?:1[6-9]|20)\d\d(?![0-9]))\d")


#: Lista de al menos dos autores con iniciales: "Castro, D. M., & Allegri, R. F.".
#: Un nombre de revista partido en dos líneas nunca tiene esta forma, así que
#: alcanza por sí sola aunque la referencia no llegue a mostrar su fecha.
AUTHOR_LIST_HEAD_RX = re.compile(
    rf"^{_NAME},\s*[{_UPPER}]\.(?:\s*[{_UPPER}]\.)*\s*[,;]\s*"
    rf"(?:&|y|and|\.\.\.|…)?\s*{_NAME},\s*[{_UPPER}]\."
)


def cut_opens_a_record(text_after_cut: str, window: int = 400) -> bool:
    """¿El texto que sigue al corte abre una referencia nueva?

    Cuando un párrafo del PDF aparece además adentro de una referencia ya
    extraída, el aviso ofrece dividir esa referencia justo ahí. Eso es correcto
    si dos referencias quedaron pegadas, y es un falso positivo si el párrafo
    era la segunda línea de una sola referencia: dividir ahí la parte en dos.

    Lo que separa un caso del otro es si el texto que sigue al corte abre como
    un registro —nombre propio y puntuación— y trae su propia fecha o fuente.
    """
    fragment = str(text_after_cut or "").lstrip()
    if len(fragment) < 12:
        return False
    if LEGAL_HEAD_RX.match(fragment):
        return bool(DATE_OR_SOURCE_RX.search(fragment[:window]))
    head = RECORD_HEAD_RX.match(fragment)
    if not head:
        return False
    if " " not in head.group(0).strip(" ,.;:"):
        if VOLUME_TAIL_RX.match(fragment[head.end():].lstrip()):
            return False
    if DATE_OR_SOURCE_RX.search(fragment[:window]):
        return True
    if AUTHOR_LIST_HEAD_RX.match(fragment):
        return True
    # Una cola corta y cortada al medio —sin punto final— puede estar truncada
    # antes de llegar a su fecha: ahí no hay con qué decidir y el aviso se deja
    # accionable. Una cola corta pero terminada es una decisión, no una duda.
    return len(fragment) < 120 and not TERMINATED_RX.search(fragment)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _match_score_normalized(aa: str, bb: str) -> float:
    aa = str(aa or "")[:220]
    bb = str(bb or "")[:220]
    if not aa or not bb:
        return 0.0
    if aa in bb or bb in aa:
        return min(len(aa), len(bb)) / max(len(aa), len(bb)) if max(len(aa), len(bb)) else 0.0
    return SequenceMatcher(None, aa, bb).ratio()


def _match_score(a: str, b: str) -> float:
    return _match_score_normalized(_norm(a), _norm(b))


def _first_norm_token(text: str) -> str:
    normalized = _norm(text)
    return normalized.split(" ", 1)[0] if normalized else ""


def _best_existing_match(
    text: str, ref_norms: Sequence[str], token_index: dict[str, list[int]], first_line: str = ""
) -> float:
    """Exact-equivalent fuzzy fallback with fast exact-prefix checks."""
    candidate = _norm(text)[:220]
    first = _norm(first_line)[:220]
    if not candidate or not ref_norms:
        return 0.0
    token = (first or candidate).split(" ", 1)[0]
    likely = token_index.get(token, []) if token else []
    if first:
        for index in likely:
            ref_norm = ref_norms[index]
            if ref_norm.startswith(first):
                return 1.0
    best = 0.0
    visited: set[int] = set()
    for index in likely:
        visited.add(index)
        score = _match_score_normalized(candidate, ref_norms[index])
        if score > best:
            best = score
        if best >= 0.62:
            return best
    # Full fallback deliberately preserves the historical semantics for OCR or
    # normalization cases not captured by the lead-token acceleration.
    for index, ref_norm in enumerate(ref_norms):
        if index in visited:
            continue
        score = _match_score_normalized(candidate, ref_norm)
        if score > best:
            best = score
        if best >= 0.62:
            return best
    return best


def _candidate_text(lines: Sequence[Any], i: int) -> tuple[str, bool]:
    first = str(lines[i].text or "").strip()
    joined = " ".join(str(x.text or "").strip() for x in lines[i:i+3]).strip()
    if not first or not first[:1].isupper():
        return joined, False
    authorish = bool(AUTHOR_PREFIX_RX.match(first))
    if not authorish and EDITOR_RX.search(first):
        authorish = bool(re.match(r"^[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+", first))
    has_year = bool(PAREN_YEAR_RX.search(joined[:280]) or BARE_YEAR_RX.search(joined[:280]) or (EDITOR_RX.search(first) and YEAR_RX.search(joined[:320])))
    return joined, bool(authorish and has_year)


def _dominant_record_start_margin(records: Sequence[dict[str, Any]]) -> tuple[float | None, float]:
    """Return a strong dominant physical start margin, if records expose one."""
    xs: list[float] = []
    for record in records:
        try:
            xs.append(float(record.get("reference_start_x")))
        except (TypeError, ValueError):
            continue
    if len(xs) < 20:
        return None, 0.0
    center = float(statistics.median(xs))
    support = sum(abs(x - center) <= 6.0 for x in xs) / len(xs)
    return (center if support >= 0.85 else None), support


def _record_start_margin_modes(records: Sequence[dict[str, Any]]) -> tuple[list[float], float]:
    """Return strong multi-modal physical start margins for mirrored layouts."""
    xs: list[float] = []
    for record in records:
        try:
            xs.append(float(record.get("reference_start_x")))
        except (TypeError, ValueError):
            continue
    if len(xs) < 20:
        return [], 0.0
    groups: list[list[float]] = []
    for value in sorted(xs):
        if not groups or abs(value - statistics.median(groups[-1])) > 4.0:
            groups.append([value])
        else:
            groups[-1].append(value)
    strong = [group for group in groups if len(group) >= max(4, int(round(len(xs) * 0.04)))]
    support = sum(len(group) for group in strong) / len(xs) if xs else 0.0
    if len(strong) < 2 or support < 0.85:
        return [], support
    return [float(statistics.median(group)) for group in strong], support


def _line_in_section(line: Any, section: dict[str, Any]) -> bool:
    sp = int(section.get("start_page") or section.get("zone_start_page") or 1)
    ep = int(section.get("end_page") or section.get("zone_end_page") or sp)
    sy = float(section.get("start_y") or 0.0)
    ey = section.get("end_y")
    if line.page < sp or line.page > ep:
        return False
    if line.page == sp and float(line.y0) <= sy + 0.5:
        return False
    if line.page == ep and ey not in (None, "") and float(line.y0) >= float(ey) - 0.5:
        return False
    return True


def build_coverage_report(pdf_path: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    """Re-scan reference sections permissively and flag plausible starts not represented by records."""
    zones = list(result.get("zones") or [])
    records = list(result.get("records") or [])
    if not zones:
        return {"version": "0.9.10-coverage2", "status": "no_reference_sections", "possible_missing": [], "summary": {"n_possible_missing": 0}}

    possible_missing: list[dict[str, Any]] = []
    merged_suspects: list[dict[str, Any]] = []
    page_boundaries: list[dict[str, Any]] = []
    seen_keys: set[tuple[int, str]] = set()

    for zidx, zone in enumerate(zones, 1):
        sp = int(zone.get("start_page") or zone.get("zone_start_page") or 1)
        ep = int(zone.get("end_page") or zone.get("zone_end_page") or sp)
        zone_records = [r for r in records if int(r.get("zone_id") or zidx) == int(zone.get("zone_id") or zidx)]
        dominant_start_margin, dominant_start_support = _dominant_record_start_margin(zone_records)
        start_margin_modes, start_margin_modes_support = _record_start_margin_modes(zone_records)
        try:
            if start_margin_modes:
                # Generic ingestion can coalesce same-baseline text from opposite
                # columns. For a proven multimodal start geometry use raw PDF
                # lines only inside the audit layer; extraction is unchanged.
                from biblioref.ingestion.backend_context import pymupdf
                from biblioref.extraction.column_reflow import _raw_page_lines
                lines = []
                with pymupdf.open(str(pdf_path)) as doc:
                    for page_number in range(sp, min(ep, doc.page_count) + 1):
                        lines.extend(
                            line for line in _raw_page_lines(doc[page_number - 1], page_number)
                            if _line_in_section(line, zone)
                        )
                lines.sort(key=lambda line: (int(line.page), float(line.y0), float(line.x0)))
            else:
                lines = [l for l in extract_layout_lines_range(pdf_path, sp, ep) if _line_in_section(l, zone)]
            lines, _removed_decorations = filter_repeated_page_decorations(lines)
        except Exception:
            lines = []
        by_page: dict[int, list[Any]] = {}
        for line in lines:
            by_page.setdefault(int(line.page), []).append(line)
        for page in by_page:
            by_page[page].sort(key=lambda l: (l.y0, l.x0))

        ref_texts = [str(r.get("reference_text") or r.get("text") or "") for r in zone_records]
        ref_norms = [_norm(text)[:220] for text in ref_texts]
        token_index: dict[str, list[int]] = {}
        for ref_index, normalized in enumerate(ref_norms):
            token = normalized.split(" ", 1)[0] if normalized else ""
            if token:
                token_index.setdefault(token, []).append(ref_index)
        for i, line in enumerate(lines):
            text, plausible = _candidate_text(lines, i)
            if not plausible:
                continue
            if dominant_start_margin is not None and abs(float(line.x0) - dominant_start_margin) > 7.0:
                continue
            if (
                dominant_start_margin is None
                and start_margin_modes
                and min(abs(float(line.x0) - margin) for margin in start_margin_modes) > 7.0
            ):
                continue
            best = _best_existing_match(text, ref_norms, token_index, str(line.text or ""))
            if best >= 0.62:
                continue
            key = (int(line.page), _norm(line.text)[:70])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            possible_missing.append({
                "id": f"missing_z{zidx}_p{line.page}_{len(possible_missing)+1}",
                "zone_id": zone.get("zone_id", zidx),
                "page": int(line.page),
                "y": round(float(line.y0), 2),
                "text": text[:700],
                "first_line": str(line.text or "").strip(),
                "best_existing_match": round(best, 3),
                "reason": "plausible_reference_start_not_represented",
                "status": "review",
            })

        pages = sorted(by_page)
        for a, b in zip(pages, pages[1:]):
            if b != a + 1:
                continue
            prev = by_page[a][-3:]
            nxt = by_page[b][:3]
            ev = evaluate_page_boundary(prev, nxt)
            try:
                w1, h1 = page_dimensions(pdf_path, a)
                w2, h2 = page_dimensions(pdf_path, b)
            except Exception:
                w1 = w2 = h1 = h2 = None
            page_boundaries.append({
                "id": f"boundary_z{zidx}_{a}_{b}",
                "zone_id": zone.get("zone_id", zidx),
                "page_before": a,
                "page_after": b,
                "verdict": ev["verdict"],
                "split_support": ev["split_support"],
                "continue_support": ev["continue_support"],
                "evidence": ev["evidence"],
                "previous_tail": ev["previous_tail"],
                "next_head": ev["next_head"],
                "previous_page_width": w1,
                "previous_page_height": h1,
                "next_page_width": w2,
                "next_page_height": h2,
            })

        from biblioref.audit.merged import looks_merged
        for r in zone_records:
            text = str(r.get("reference_text") or r.get("text") or "")
            if looks_merged(text):
                merged_suspects.append({"record_index": r.get("ref_in_zone"), "page": r.get("reference_start_page"), "reason": "multiple_reference_signatures_inside_record", "text": text[:700]})

    n_review_boundaries = sum(1 for x in page_boundaries if x["verdict"] == "review")
    return {
        "version": "0.9.10-coverage2",
        "status": "review" if possible_missing or n_review_boundaries or merged_suspects else "looks_consistent",
        "possible_missing": possible_missing,
        "merged_suspects": merged_suspects,
        "page_boundaries": page_boundaries,
        "summary": {
            "n_possible_missing": len(possible_missing),
            "n_merged_suspects": len(merged_suspects),
            "n_page_boundaries": len(page_boundaries),
            "n_page_boundaries_review": n_review_boundaries,
        },
    }
