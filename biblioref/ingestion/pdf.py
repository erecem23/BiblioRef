"""PDF ingestion helpers with memory-safe utilities for large documents."""

from __future__ import annotations

import hashlib
import re
import statistics
from pathlib import Path
from typing import BinaryIO, Dict, List, Tuple

from biblioref.ingestion.backend_context import active_pdf_backend, pymupdf
from biblioref.ingestion.extraction_context import current_extraction_context

from biblioref.legacy.engine import (
    LayoutLine,
    clear_layout_line_cache as _clear_layout_line_cache,
    extract_layout_lines as _extract_layout_lines,
)


# Frozen only after exact equality probes on the grammar fixture plus synthetic
# hanging-indent and same-baseline/two-column PDFs. Unsupported tolerances and
# unrepresented pages always fall back to the historical range extractor.
_FULL_LAYOUT_SLICE_SAFE: dict[str, frozenset[float]] = {
    "pdfium": frozenset({0.9}),
    "pymupdf": frozenset({0.9}),
}


def extract_layout_lines(pdf_path: str | Path):
    backend = active_pdf_backend()
    context = current_extraction_context()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("full_layout_requests")
        context.increment("full_layout_backend_calls")

    if backend == "pdfium":
        from biblioref.ingestion.pdfium_backend import extract_layout_lines_pdfium

        result = extract_layout_lines_pdfium(pdf_path)
    else:
        result = _extract_layout_lines(pdf_path)

    if matches:
        context.register_full_layout(
            result,
            y_tolerance=0.9,
            slice_safe=0.9 in _FULL_LAYOUT_SLICE_SAFE.get(backend, frozenset()),
        )
    return result


def clear_layout_line_cache() -> None:
    """Release layout snapshots maintained by both installed backends."""
    _clear_layout_line_cache()
    try:
        from biblioref.ingestion.pdfium_backend import clear_pdfium_layout_line_cache

        clear_pdfium_layout_line_cache()
    except ModuleNotFoundError:
        pass


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _extract_layout_lines_range_historical(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
    y_tolerance: float = 0.9,
) -> List[LayoutLine]:
    """Historical range extractor kept byte-for-byte in decision semantics."""
    output: List[LayoutLine] = []
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= start_page <= end_page <= doc.page_count:
            raise ValueError("Rango de páginas fuera de límite.")
        for page_number in range(start_page, end_page + 1):
            page = doc[page_number - 1]
            fragments: List[dict] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = [s for s in line.get("spans", []) if str(s.get("text", "")).strip()]
                    if not spans:
                        continue
                    text = _clean_text(" ".join(str(s.get("text", "")) for s in spans))
                    if not text:
                        continue
                    fragments.append({
                        "text": text,
                        "x0": min(float(s["bbox"][0]) for s in spans),
                        "y0": min(float(s["bbox"][1]) for s in spans),
                        "x1": max(float(s["bbox"][2]) for s in spans),
                        "y1": max(float(s["bbox"][3]) for s in spans),
                        "sizes": [float(s.get("size", 0.0)) for s in spans],
                    })
            fragments.sort(key=lambda item: (item["y0"], item["x0"]))
            groups: List[List[dict]] = []
            for fragment in fragments:
                if groups:
                    baseline = statistics.median(x["y0"] for x in groups[-1])
                    if abs(fragment["y0"] - baseline) <= y_tolerance:
                        groups[-1].append(fragment)
                        continue
                groups.append([fragment])
            for group in groups:
                group.sort(key=lambda item: item["x0"])
                sizes = [size for item in group for size in item["sizes"]]
                output.append(LayoutLine(
                    page=page_number,
                    page_height=float(page.rect.height),
                    text=_clean_text(" ".join(item["text"] for item in group)),
                    x0=min(item["x0"] for item in group),
                    y0=min(item["y0"] for item in group),
                    x1=max(item["x1"] for item in group),
                    y1=max(item["y1"] for item in group),
                    median_font_size=statistics.median(sizes),
                    fragment_count=len(group),
                ))
    return output


def extract_layout_lines_range(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
    y_tolerance: float = 0.9,
) -> List[LayoutLine]:
    """Extract an inclusive 1-based range with exact execution-scoped reuse."""
    backend = active_pdf_backend()
    context = current_extraction_context()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("range_layout_requests")
        if context.reuse_enabled:
            full_slice = context.get_full_layout_range(
                start_page,
                end_page,
                y_tolerance,
            )
            if full_slice is not None:
                context.increment("range_layout_full_slice_hits")
                return list(full_slice)
            cached = context.get_cached_range(start_page, end_page, y_tolerance)
            if cached is not None:
                context.increment("range_layout_cache_hits")
                return list(cached)

    result = _extract_layout_lines_range_historical(
        pdf_path,
        start_page,
        end_page,
        y_tolerance,
    )
    if matches:
        context.increment("range_layout_backend_calls")
        context.store_cached_range(start_page, end_page, y_tolerance, result)
    return result


def pdf_page_count(pdf_path: str | Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def pdf_preflight(
    pdf_path: str | Path,
    heavy_size_mb: float = 150.0,
    heavy_pages: int = 700,
) -> Dict:
    """Cheap document classification used only to choose infrastructure mode."""
    path = Path(pdf_path)
    size_bytes = path.stat().st_size
    with pymupdf.open(path) as doc:
        page_count = doc.page_count
        if page_count:
            candidates = {0, page_count - 1, page_count // 2, page_count // 4, (3 * page_count) // 4}
            sample_indices = sorted(i for i in candidates if 0 <= i < page_count)
        else:
            sample_indices = []
        text_pages = 0
        sample_chars = 0
        for index in sample_indices:
            text = doc[index].get_text("text").strip()
            sample_chars += len(text)
            if len(text) >= 40:
                text_pages += 1
    sample_count = len(sample_indices)
    text_page_ratio = text_pages / sample_count if sample_count else 0.0
    predominantly_scanned = bool(page_count >= 50 and sample_count and text_page_ratio <= 0.35)
    size_mb = size_bytes / (1024 * 1024)
    reasons = []
    if size_mb >= heavy_size_mb:
        reasons.append("large_file_size")
    if page_count >= heavy_pages:
        reasons.append("many_pages")
    if predominantly_scanned:
        reasons.append("predominantly_scanned_sample")
    return {
        "size_bytes": size_bytes,
        "size_mb": round(size_mb, 2),
        "page_count": page_count,
        "sampled_pages": [i + 1 for i in sample_indices],
        "sample_text_page_ratio": round(text_page_ratio, 3),
        "sample_text_characters": sample_chars,
        "predominantly_scanned": predominantly_scanned,
        "heavy_mode": bool(reasons),
        "heavy_mode_reasons": reasons,
        "heavy_size_threshold_mb": heavy_size_mb,
        "heavy_page_threshold": heavy_pages,
    }


def stream_file_to_disk(
    source: BinaryIO,
    target: str | Path,
    chunk_size: int = 4 * 1024 * 1024,
) -> Dict:
    """Copy an uploaded/file-like PDF to disk without materializing another full bytes object."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.seek(0)
    except Exception:
        pass
    digest = hashlib.sha256()
    total = 0
    with target.open("wb") as handle:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": total, "path": str(target)}


def render_page_png(pdf_path: str | Path, page_number: int, zoom: float = 1.6) -> bytes:
    """Render a 1-based PDF page as PNG."""
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError("Página fuera de rango.")
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def render_band_png(
    pdf_path: str | Path,
    page_number: int,
    top: float,
    bottom: float,
    zoom: float = 1.6,
    mark: Tuple[float, float] | None = None,
) -> bytes:
    """Render a horizontal strip of a 1-based page, with the reviewed paragraph boxed.

    The box is drawn on the rendered strip instead of being placed by the caller:
    clamping at the edges of a page would otherwise move the paragraph inside the
    strip without the browser knowing by how much.
    """
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError("Página fuera de rango.")
        page = doc[page_number - 1]
        rect = page.rect
        top = max(0.0, min(float(top), float(rect.height) - 2))
        bottom = max(top + 8.0, min(float(bottom), float(rect.height)))
        # The text column, so the strip is the bibliography and not the whole sheet.
        words = page.get_text("words")
        x0 = max(0.0, min((w[0] for w in words), default=rect.width * 0.1) - 6)
        x1 = min(float(rect.width), max((w[2] for w in words), default=rect.width * 0.9) + 6)
        if x1 - x0 < 40:
            x0, x1 = 0.0, float(rect.width)
        if mark:
            m0 = max(top, float(mark[0]))
            m1 = min(bottom, float(mark[1]))
            if m1 > m0:
                page.draw_rect(
                    pymupdf.Rect(x0 + 1.5, m0, x1 - 1.5, m1),
                    color=(0.706, 0.325, 0.035),  # --warn #b45309
                    fill=(0.706, 0.325, 0.035),
                    fill_opacity=0.08,
                    width=1.1,
                    dashes="[3 2] 0",
                )
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(x0, top, x1, bottom), alpha=False)
        return pix.tobytes("png")


def _page_dimensions_historical(
    pdf_path: str | Path,
    page_number: int,
) -> Tuple[float, float]:
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError("Página fuera de rango.")
        rect = doc[page_number - 1].rect
        return float(rect.width), float(rect.height)


def page_dimensions(pdf_path: str | Path, page_number: int) -> Tuple[float, float]:
    backend = active_pdf_backend()
    context = current_extraction_context()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("dimension_requests")
        if context.reuse_enabled:
            cached = context.get_cached_dimensions(page_number)
            if cached is not None:
                context.increment("dimension_cache_hits")
                return cached

    result = _page_dimensions_historical(pdf_path, page_number)
    if matches:
        context.increment("dimension_backend_calls")
        context.store_cached_dimensions(page_number, result)
    return result
