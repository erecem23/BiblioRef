# -*- coding: utf-8 -*-
"""OCR as an explicit, later step for pages that have no text layer.

Reading a thesis never runs OCR. It only records which pages are images
without text (``scan_ocr_needs``). When OCR is requested, those pages are
recognised with Tesseract (built into PyMuPDF) and a copy of the PDF is written
with the recognised lines as invisible text, so metadata and bibliography
extraction read it like any other PDF.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pymupdf

OCR_SCAN_REVISION = "ocr-scan-v3"  # v3: also pages whose text layer is unreadable
# v2: lines on rotated pages are placed where they are seen (v1 laid them sideways).
OCR_PLACEMENT_REVISION = 2
OCR_LANGUAGES = "spa+eng"
OCR_DPI = 300
FRONTMATTER_PAGES = 8
# From this share of image-only pages on, the whole thesis is a scan.
SCANNED_DOCUMENT_SHARE = 0.8
# Fewer characters than this on a page with an image means the text is in the image.
MIN_TEXT_CHARS = 20
# A text layer this full of control characters was written without a way back to letters
# (fonts without ToUnicode, T0140): the page looks fine but reads as control characters.
UNREADABLE_CONTROL_SHARE = 0.10
# When most pages are like that the whole file was made so, and pages with fewer control
# characters are the same garbage shifted into printable codes: they go to OCR too.
UNREADABLE_DOCUMENT_SHARE = 0.5
UNREADABLE_WEAK_SHARE = 0.02
# Unreadable pages are replaced by their picture before OCR; this is the stored resolution.
RASTER_DPI = 200
# A photographed open book (T0137): a landscape page holding two pages side by side.
# Read as one page its lines interleave; split at the gutter, each half reads alone.
SPREAD_MIN_ASPECT = 1.15
SPREAD_MIN_LINES_PER_SIDE = 5
SPREAD_MAX_CROSSING_SHARE = 0.08
SPREAD_SEARCH = (0.35, 0.65)


def tessdata_dir() -> Optional[Path]:
    """First Tesseract data folder that has the Spanish model."""
    candidates = [
        os.environ.get("BIBLIOREF_TESSDATA"),
        str(Path.home() / ".biblioref" / "tessdata"),
        os.environ.get("TESSDATA_PREFIX"),
        r"C:\Program Files\Tesseract-OCR\tessdata",
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "spa.traineddata").exists():
            return Path(candidate)
    return None


def ocr_available() -> Dict[str, Any]:
    folder = tessdata_dir()
    if folder is None:
        return {"available": False, "reason": "No se encontró el modelo de español de Tesseract (spa.traineddata)."}
    languages = sorted(p.stem for p in folder.glob("*.traineddata"))
    return {"available": True, "tessdata": str(folder), "languages": languages}


def _ranges(pages: Iterable[int]) -> List[List[int]]:
    out: List[List[int]] = []
    for page in sorted(set(pages)):
        if out and page == out[-1][1] + 1:
            out[-1][1] = page
        else:
            out.append([page, page])
    return out


def _control_share(text: str) -> float:
    text = (text or "").strip()
    if len(text) < MIN_TEXT_CHARS:
        return 0.0
    control = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return control / len(text)


def _unreadable_text(text: str) -> bool:
    return _control_share(text) > UNREADABLE_CONTROL_SHARE


def _unreadable_pages(pdf) -> set:
    """1-based pages whose text layer cannot be read back as letters."""
    shares = [_control_share(page.get_text("text")) for page in pdf]
    strong = [n for n, share in enumerate(shares, 1) if share > UNREADABLE_CONTROL_SHARE]
    if shares and len(strong) >= UNREADABLE_DOCUMENT_SHARE * len(shares):
        return {n for n, share in enumerate(shares, 1) if share > UNREADABLE_WEAK_SHARE}
    return set(strong)


def _needs_ocr(page) -> bool:
    text = page.get_text("text")
    if _unreadable_text(text):
        return True
    return len(text.strip()) < MIN_TEXT_CHARS and bool(page.get_images(full=False))


def _as_picture(pdf, index: int):
    """Replace a page by its picture, so the unreadable text under it is gone for good."""
    page = pdf[index]
    pix = page.get_pixmap(dpi=RASTER_DPI)
    image = pix.tobytes("jpeg", jpg_quality=80)
    width, height = page.rect.width, page.rect.height
    pdf.delete_page(index)
    fresh = pdf.new_page(pno=index, width=width, height=height)
    fresh.insert_image(fresh.rect, stream=image)
    return fresh


def scan_ocr_needs(path: str | Path) -> Dict[str, Any]:
    """1-based pages that are images without a text layer."""
    pages: List[int] = []
    with pymupdf.open(path) as pdf:
        page_count = pdf.page_count
        unreadable = sorted(_unreadable_pages(pdf))
        for index in range(page_count):
            if index + 1 in unreadable or _needs_ocr(pdf[index]):
                pages.append(index + 1)
    return {
        "revision": OCR_SCAN_REVISION,
        "page_count": page_count,
        "pages": pages,
        "ranges": _ranges(pages),
        "frontmatter_pages": [p for p in pages if p <= FRONTMATTER_PAGES],
        "unreadable_pages": unreadable,
        "scanned_document": bool(page_count) and (
            len(pages) >= SCANNED_DOCUMENT_SHARE * page_count
            or len(unreadable) >= UNREADABLE_DOCUMENT_SHARE * page_count
        ),
    }


def _recognised_lines(page, tessdata: str, language: str, dpi: int) -> List[Dict[str, Any]]:
    textpage = page.get_textpage_ocr(language=language, dpi=dpi, full=True, tessdata=tessdata)
    lines = []
    for block in page.get_text("dict", textpage=textpage).get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = " ".join(str(s.get("text") or "").strip() for s in line.get("spans", [])).strip()
            if text:
                lines.append({"text": text, "bbox": tuple(line["bbox"])})
    return lines


def _write_invisible_line(page, text: str, bbox) -> None:
    # OCR boxes come in unrotated page space; on a page with /Rotate the text runs
    # sideways there. Measure the line as it is seen, then write it back unrotated.
    seen = pymupdf.Rect(bbox) * page.rotation_matrix
    height = max(1.0, seen.height)
    unit = pymupdf.get_text_length(text, fontname="helv", fontsize=1) or 1.0
    # Match the recognised width so selections and highlights land on the image text.
    size = max(1.0, min(height * 0.9, seen.width / unit))
    origin = pymupdf.Point(seen.x0, seen.y1 - height * 0.2) * page.derotation_matrix
    page.insert_text(origin, text, fontsize=size, fontname="helv", render_mode=3, rotate=page.rotation)


def _spread_split(page, lines: List[Dict[str, Any]]) -> Optional[float]:
    """Where to cut a two-page photograph, in page units, or None when it is one page."""
    rect = page.rect
    if rect.width < SPREAD_MIN_ASPECT * rect.height or len(lines) < 2 * SPREAD_MIN_LINES_PER_SIDE:
        return None
    seen = [pymupdf.Rect(line["bbox"]) * page.rotation_matrix for line in lines]
    options = []
    lo, hi = SPREAD_SEARCH
    for step in range(61):
        x = rect.width * (lo + (hi - lo) * step / 60)
        crossing = sum(1 for r in seen if r.x0 < x and r.x1 > x)
        left = sum(1 for r in seen if r.x1 <= x)
        right = sum(1 for r in seen if r.x0 >= x)
        if min(left, right) >= SPREAD_MIN_LINES_PER_SIDE:
            options.append((crossing, x))
    # One page of the book left blank (a chapter ending): all the text sits in one half.
    middle = rect.width / 2
    if all(r.x0 >= middle - 20 for r in seen):
        return min(middle, min(r.x0 for r in seen) - 6)
    if all(r.x1 <= middle + 20 for r in seen):
        return max(middle, max(r.x1 for r in seen) + 6)
    if not options:
        return None
    fewest = min(crossing for crossing, _ in options)
    if fewest > SPREAD_MAX_CROSSING_SHARE * len(seen):
        return None
    # The middle of the gutter, not its first free point: a cut at the edge clips letters.
    gutter = [x for crossing, x in options if crossing == fewest]
    return gutter[len(gutter) // 2]


def _split_spread(pdf, index: int, x: float) -> List[Any]:
    """Replace a two-page photograph by its left and right halves, as pictures."""
    page = pdf[index]
    rect = page.rect
    halves = [pymupdf.Rect(0, 0, x, rect.height), pymupdf.Rect(x, 0, rect.width, rect.height)]
    images = [page.get_pixmap(dpi=OCR_DPI, clip=half).tobytes("jpeg", jpg_quality=80) for half in halves]
    pdf.delete_page(index)
    for offset, (half, image) in enumerate(zip(halves, images)):
        fresh = pdf.new_page(pno=index + offset, width=half.width, height=half.height)
        fresh.insert_image(fresh.rect, stream=image)
    # Page objects go stale when another page is inserted: hand back fresh ones.
    return [pdf[index], pdf[index + 1]]


def ocr_pdf_pages(
    source: str | Path,
    target: str | Path,
    pages: Optional[Iterable[int]] = None,
    *,
    language: str = OCR_LANGUAGES,
    dpi: int = OCR_DPI,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """Write ``target``: ``source`` with invisible OCR text on image-only pages.

    ``pages`` (1-based) limits the run; pages that already have text are left alone.
    """
    folder = tessdata_dir()
    if folder is None:
        raise RuntimeError(ocr_available()["reason"])
    target = Path(target)
    done: List[int] = []
    split: List[int] = []
    with pymupdf.open(source) as pdf:
        wanted = sorted({p for p in (pages or range(1, pdf.page_count + 1)) if 1 <= p <= pdf.page_count})
        unreadable = _unreadable_pages(pdf)
        shift = 0  # pages added before this one by splitting two-page photographs
        for position, number in enumerate(wanted, start=1):
            index = number - 1 + shift
            page = pdf[index]
            if number in unreadable:
                page = _as_picture(pdf, index)
            if _needs_ocr(page):
                lines = _recognised_lines(page, str(folder), language, dpi)
                cut = _spread_split(page, lines)
                if cut is not None:
                    halves = _split_spread(pdf, index, cut)
                    shift += 1
                    split.append(number)
                    written = 0
                    for half in halves:
                        for line in _recognised_lines(half, str(folder), language, dpi):
                            _write_invisible_line(half, line["text"], line["bbox"])
                            written += 1
                    lines = written
                else:
                    for line in lines:
                        _write_invisible_line(page, line["text"], line["bbox"])
                if lines:
                    done.append(number)
            if progress:
                progress(position, len(wanted))
        tmp = target.with_name(target.name + ".tmp")
        pdf.save(tmp, garbage=1, deflate=True)
    os.replace(tmp, target)
    # ``pages`` and ``split`` are numbered as in ``source``; each split page became two.
    return {"pages": done, "ranges": _ranges(done), "language": language, "dpi": dpi, "split_spreads": split}


def ocr_target_path(path: str | Path) -> Path:
    path = Path(path)
    stem = path.stem[:-4] if path.stem.endswith(".ocr") else path.stem
    return path.with_name(f"{stem}.ocr.pdf")


__all__ = [
    "FRONTMATTER_PAGES", "OCR_SCAN_REVISION", "ocr_available", "ocr_pdf_pages",
    "ocr_target_path", "scan_ocr_needs", "tessdata_dir",
]
