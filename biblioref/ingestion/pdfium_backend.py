"""Experimental PDFium backend used only for differential validation.

PyMuPDF remains BiblioRef's stable PDF authority.  This adapter reconstructs
BiblioRef's ``LayoutLine`` contract from PDFium text objects while keeping
backend-specific geometry visible for audit.
"""
from __future__ import annotations

import ctypes
import math
import re
import statistics
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

import pypdfium2 as pdfium
from pypdfium2 import raw

from biblioref.legacy.engine import LayoutLine


_MARKER_OBJECT_RX = re.compile(r"^[•·*▪◦●○◆♦‣⁃■]+$")
_DENSE_DETACHED_MARKER_THRESHOLD = 8
_BASELINE_TOLERANCE = 0.35
_ROTATED_BASELINE_TOLERANCE = 0.18
_SIZE_TOLERANCE = 0.005
_NATIVE_GAP_FACTOR = 0.80
_WORD_JOIN_FACTOR = 0.075


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _effective_font_size(text_obj, matrix) -> float:
    """Return a size comparable to MuPDF spans across transformed PDFs."""
    try:
        base = float(text_obj.get_font_size())
    except Exception:
        return 0.0
    if matrix is None:
        return base
    try:
        determinant = abs(
            float(matrix.a) * float(matrix.d)
            - float(matrix.b) * float(matrix.c)
        )
        return base * math.sqrt(determinant) if determinant > 0 else base
    except Exception:
        return base


def _font_name(text_obj) -> str:
    try:
        return str(text_obj.get_font().get_base_name() or "")
    except Exception:
        return ""


def _font_vertical_bbox(text_obj, matrix, page_height: float, fallback_bbox):
    """Reconstruct MuPDF-like vertical span bounds from font metrics.

    MuPDF preserves font ascender/descender metrics when their total em height
    is at least one.  Some legacy embedded fonts report an undersized metric
    box (``ascent - descent < 1``); MuPDF effectively expands that box to one
    em.  Applying the same lower-bound normalization to PDFium's font metrics,
    using the transformed/effective font size, reproduces both ordinary Word
    fonts (e.g. Times New Roman 1.007/-0.307) and the compressed legacy fonts
    seen in SEDICI (e.g. 0.693/-0.215).
    """
    if matrix is None:
        return float(fallback_bbox[1]), float(fallback_bbox[3])
    try:
        font = text_obj.get_font()
        ascent = ctypes.c_float()
        descent = ctypes.c_float()
        ok_a = raw.FPDFFont_GetAscent(font.raw, 1.0, ctypes.byref(ascent))
        ok_d = raw.FPDFFont_GetDescent(font.raw, 1.0, ctypes.byref(descent))
        metric_height = float(ascent.value - descent.value)
        if not ok_a or not ok_d or metric_height <= 1e-9:
            raise ValueError
        size = _effective_font_size(text_obj, matrix)
        if size <= 1e-9:
            raise ValueError
        # Do not shrink valid font metric boxes > 1 em.  Only repair legacy
        # undersized boxes, matching MuPDF's observed physical span geometry.
        metric_denominator = min(metric_height, 1.0)
        baseline = float(page_height - float(matrix.f))
        return (
            baseline - size * float(ascent.value) / metric_denominator,
            baseline - size * float(descent.value) / metric_denominator,
        )
    except Exception:
        return float(fallback_bbox[1]), float(fallback_bbox[3])


def _normalize_pdfium_object_text(text: str, matrix) -> str:
    """Map legacy Word/PDF discretionary-hyphen controls to soft hyphens."""
    value = str(text)
    controls = ("\x02", "\ufffe")
    if not any(control in value for control in controls):
        return value
    if value not in controls:
        try:
            identityish = bool(
                matrix is not None
                and abs(float(matrix.a) - 1.0) < 0.002
                and abs(float(matrix.d) - 1.0) < 0.002
                and abs(float(matrix.b)) < 0.002
                and abs(float(matrix.c)) < 0.002
            )
        except Exception:
            identityish = False
        replacement = "\xad" if identityish else " \xad"
    else:
        replacement = "\xad"
    for control in controls:
        value = value.replace(control, replacement)
    return value


def _space_object_extent(text_obj, matrix, tight_bbox) -> float:
    """Infer the horizontal extent represented by an empty PDF text object."""
    if matrix is None:
        return float(tight_bbox[2])
    try:
        font = text_obj.get_font()
        width = ctypes.c_float()
        font_size = float(text_obj.get_font_size())
        ok = raw.FPDFFont_GetGlyphWidth(font.raw, ord(" "), font_size, ctypes.byref(width))
        if ok:
            return float(matrix.e) + abs(float(matrix.a)) * float(width.value)
    except Exception:
        pass
    return float(tight_bbox[2])


def _ptr_value(raw_handle) -> int | None:
    try:
        return ctypes.cast(raw_handle, ctypes.c_void_p).value
    except Exception:
        return None


def _rotated_loose_boxes(textpage) -> dict[int, tuple[float, float, float, float]]:
    """Return unioned loose char boxes keyed by PDF text-object pointer.

    Used only on pages containing rotated text.  Character-level geometry is
    expensive, so horizontal pages remain on the fast object-level path.
    """
    by_obj: dict[int, list[tuple[float, float, float, float]]] = {}
    try:
        count = int(textpage.count_chars())
    except Exception:
        return {}
    for index in range(count):
        try:
            text_obj = textpage.get_textobj(index)
            if text_obj is None:
                continue
            key = _ptr_value(text_obj.raw)
            if key is None:
                continue
            box = tuple(map(float, textpage.get_charbox(index, loose=True)))
        except Exception:
            continue
        by_obj.setdefault(key, []).append(box)
    out = {}
    for key, boxes in by_obj.items():
        out[key] = (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
    return out


def _is_rotated(matrix) -> bool:
    if matrix is None:
        return False
    try:
        return abs(float(matrix.b)) > abs(float(matrix.a))
    except Exception:
        return False


def _needs_space_between(prev: dict, cur: dict, gap: float, local_size: float) -> bool:
    """Decide whether two visible objects in one native line need a space."""
    prev_text = prev.get("raw", "")
    cur_text = cur.get("raw", "")
    if not prev_text or not cur_text:
        return False

    # MuPDF emits a span boundary whenever font identity/effective size changes;
    # BiblioRef's stable extractor joins such spans with exactly one space.
    if (
        prev.get("font") != cur.get("font")
        or abs(float(prev.get("size", 0.0)) - float(cur.get("size", 0.0))) > _SIZE_TOLERANCE
    ):
        return True

    # A real PDF-space object between the two fragments is authoritative.
    if cur.get("space_before"):
        return True

    # Detached punctuation is attached only when geometry supports continuity.
    if re.fullmatch(r"[.,;:!?%)\]}]+", _clean_text(cur_text)):
        return gap > max(0.8, local_size * 0.12)
    # A hyphen glyph split into its own object is commonly part of an ISBN,
    # ISSN or compound token. Attach it when the geometry is tight; an
    # explicit PDF-space object still wins above and preserves true separators.
    if re.fullmatch(r"-+", _clean_text(cur_text)):
        return gap > max(0.8, local_size * 0.12)
    if re.fullmatch(r"[(\[{¿¡]+", _clean_text(prev_text)):
        return False

    # Preserve em/en-dash and bullet marker spacing as a native span boundary.
    if re.fullmatch(r"[—–]+", _clean_text(prev_text)):
        return True

    # Very small gaps are PDFium object fragmentation inside a word.  Numeric
    # tokens and words can be split into adjacent text objects without an
    # explicit space object (e.g. ``(1`` + ``991)``).  A slightly wider
    # alphanumeric-only continuity gate is safe because true word spaces in
    # these PDFs are either embedded in the object text or represented by an
    # empty PDF text object, which was handled above.
    if gap <= max(0.8, local_size * _WORD_JOIN_FACTOR):
        return False
    if (
        re.search(r"[0-9A-Za-zÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇáéíóúàèìòùâêîôûäëïöüñç]$", prev_text)
        and re.match(r"^[0-9A-Za-zÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇáéíóúàèìòùâêîôûäëïöüñç]", cur_text)
        and gap <= max(1.5, local_size * 0.14)
    ):
        return False
    return True


def _native_line_text(items: list[dict]) -> str:
    visible = [x for x in items if x.get("visible")]
    if not visible:
        return ""
    pieces = [str(visible[0]["raw"])]
    for prev, cur in zip(visible, visible[1:]):
        gap = max(0.0, float(cur["geom_start"] - prev["geom_end"]))
        local_sizes = [s for s in (prev.get("size", 0.0), cur.get("size", 0.0)) if s > 0]
        local_size = statistics.median(local_sizes) if local_sizes else 10.0
        pieces.append(" " if _needs_space_between(prev, cur, gap, local_size) else "")
        pieces.append(str(cur["raw"]))
    return _clean_text("".join(pieces))


def _page_fragments(page, textpage, page_height: float, y_tolerance: float = 0.9) -> list[dict]:
    raw_objects = list(page.get_objects(filter=[raw.FPDF_PAGEOBJ_TEXT], textpage=textpage))
    page_has_rotated = False
    for obj in raw_objects:
        try:
            if _is_rotated(obj.get_matrix()):
                page_has_rotated = True
                break
        except Exception:
            continue
    loose_by_obj = _rotated_loose_boxes(textpage) if page_has_rotated else {}

    objects: list[dict] = []
    for object_index, text_obj in enumerate(raw_objects):
        try:
            extracted = text_obj.extract()
        except Exception:
            extracted = ""
        try:
            left, bottom, right, top = map(float, text_obj.get_bounds())
        except Exception:
            continue
        tight_bbox = (left, float(page_height - top), right, float(page_height - bottom))
        try:
            matrix = text_obj.get_matrix()
        except Exception:
            matrix = None
        raw_text = _normalize_pdfium_object_text(str(extracted or ""), matrix)
        visible_text = bool(str(raw_text).strip())
        size = _effective_font_size(text_obj, matrix)
        rotated = _is_rotated(matrix)

        if rotated:
            # For rotated text MuPDF's longitudinal box follows font advances,
            # including trailing spaces. PDFium loose char boxes reproduce that
            # behaviour closely and prevent adjacent table cells from merging.
            loose = loose_by_obj.get(_ptr_value(text_obj.raw))
            if loose:
                l, b, r, t = loose
                bbox = (l, float(page_height - t), r, float(page_height - b))
            else:
                bbox = tight_bbox
            # Vertical text runs upward in these historical tables. matrix.e is
            # the perpendicular/native-line coordinate. Keep longitudinal
            # continuity in PDF coordinates (bottom -> top), where matrix.f is
            # the text origin; top-left coordinates are used only for LayoutLine.
            line_coord = float(matrix.e) if matrix is not None else (bbox[0] + bbox[2]) / 2
            if visible_text and loose:
                geom_start = float(loose[1])
                geom_end = float(loose[3])
            elif matrix is not None:
                geom_start = float(matrix.f)
                geom_end = geom_start
                try:
                    font = text_obj.get_font()
                    width = ctypes.c_float()
                    font_size = float(text_obj.get_font_size())
                    if raw.FPDFFont_GetGlyphWidth(font.raw, ord(" "), font_size, ctypes.byref(width)):
                        geom_end = geom_start + abs(float(matrix.b)) * float(width.value)
                except Exception:
                    pass
            else:
                geom_start = float(bottom)
                geom_end = float(top)
        else:
            y0, y1 = _font_vertical_bbox(text_obj, matrix, page_height, tight_bbox)
            x0 = float(matrix.e) if matrix is not None else left
            if visible_text:
                x1 = right
            else:
                x1 = _space_object_extent(text_obj, matrix, tight_bbox)
            bbox = (x0, y0, max(x0, x1), y1)
            line_coord = float(page_height - float(matrix.f)) if matrix is not None else (y0 + y1) / 2
            geom_start = bbox[0]
            geom_end = bbox[2]

        objects.append({
            "object_index": object_index,
            "raw": raw_text,
            "visible": visible_text,
            "bbox": bbox,
            "line_coord": line_coord,
            "geom_start": geom_start,
            "geom_end": geom_end,
            "size": size,
            "font": _font_name(text_obj),
            "rotated": rotated,
        })

    marker_object_count = sum(
        bool(_MARKER_OBJECT_RX.fullmatch(_clean_text(item["raw"])))
        for item in objects if item["visible"]
    )
    preserve_detached_markers = marker_object_count >= _DENSE_DETACHED_MARKER_THRESHOLD

    # Build native-line buckets by baseline/perpendicular coordinate.  Keep PDF
    # source order inside a bucket: backward jumps are meaningful native-line
    # boundaries in old Word-generated PDFs.
    orient_groups: list[list[dict]] = []
    for rotated in (False, True):
        subset = [x for x in objects if x["rotated"] == rotated]
        subset.sort(key=lambda x: (x["line_coord"], x["object_index"]))
        tol = _ROTATED_BASELINE_TOLERANCE if rotated else _BASELINE_TOLERANCE
        groups: list[list[dict]] = []
        for item in subset:
            if groups:
                baseline = statistics.median(x["line_coord"] for x in groups[-1])
                if abs(item["line_coord"] - baseline) <= tol:
                    groups[-1].append(item)
                    continue
            groups.append([item])
        orient_groups.extend(groups)

    fragments: list[dict] = []
    for group in orient_groups:
        group.sort(key=lambda x: x["object_index"])
        native_runs: list[list[dict]] = []
        current: list[dict] = []
        previous: dict | None = None
        pending_space = False
        for item in group:
            if not item["visible"]:
                # Empty Word/PDF text objects can be real spaces. They carry
                # topology but are never emitted as text.
                if current:
                    pending_space = True
                    current.append(item)
                continue

            if previous is None:
                item["space_before"] = False
                current = [item]
                previous = item
                pending_space = False
                continue

            # Distance after all topology objects already retained in current.
            last_geom_end = max(x["geom_end"] for x in current)
            gap = float(item["geom_start"] - last_geom_end)
            sizes = [x["size"] for x in current if x.get("size", 0) > 0]
            if item.get("size", 0) > 0:
                sizes.append(item["size"])
            local_size = statistics.median(sizes) if sizes else 10.0
            gap_tolerance = max(3.0, local_size * _NATIVE_GAP_FACTOR)

            backward_jump = item["geom_start"] + 0.5 < previous["geom_start"]
            large_unbridged_gap = gap > gap_tolerance

            # Source-order topology matters when a small-font punctuation/span
            # sits between two objects that otherwise share a baseline.  MuPDF
            # keeps that interleaved object as a separate native fragment and
            # only the second-stage y-band merge puts the visual line back
            # together.  Without this barrier PDFium can jump over the object
            # and reorder punctuation (e.g. ``alumnos . En`` -> ``alumnos En .``).
            interleaved_visual_object = False
            if not item["rotated"] and item["object_index"] > previous["object_index"] + 1:
                left_edge = min(float(previous["geom_end"]), float(item["geom_start"])) - 0.5
                right_edge = max(float(previous["geom_end"]), float(item["geom_start"])) + 0.5
                for between in objects[previous["object_index"] + 1:item["object_index"]]:
                    if not between.get("visible") or between.get("rotated"):
                        continue
                    bx0 = float(between["bbox"][0])
                    by0 = float(between["bbox"][1])
                    if (
                        left_edge <= bx0 <= right_edge
                        and abs(by0 - float(previous["bbox"][1])) <= float(y_tolerance)
                        and abs(by0 - float(item["bbox"][1])) <= float(y_tolerance)
                    ):
                        interleaved_visual_object = True
                        break

            if backward_jump or large_unbridged_gap or interleaved_visual_object:
                if current:
                    native_runs.append(current)
                current = [item]
                item["space_before"] = False
            else:
                item["space_before"] = bool(pending_space)
                current.append(item)
            previous = item
            pending_space = False
        if current:
            native_runs.append(current)

        for run in native_runs:
            visible = [x for x in run if x["visible"]]
            if not visible:
                continue
            text = _native_line_text(run)
            if not text:
                continue
            fragments.append({
                "text": text,
                "x0": min(x["bbox"][0] for x in visible),
                "y0": min(x["bbox"][1] for x in visible),
                "x1": max(x["bbox"][2] for x in visible),
                "y1": max(x["bbox"][3] for x in visible),
                "sizes": [x["size"] for x in visible if x["size"] > 0],
            })

        if preserve_detached_markers and group:
            visible_group = [x for x in group if x["visible"]]
            if visible_group:
                leftmost = min(visible_group, key=lambda x: x["bbox"][0])
                for item in visible_group:
                    marker = _clean_text(item["raw"])
                    if item is leftmost or not _MARKER_OBJECT_RX.fullmatch(marker):
                        continue
                    x0, y0, x1, y1 = item["bbox"]
                    fragments.append({
                        "text": marker,
                        "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                        "sizes": [item["size"]] if item["size"] > 0 else [],
                    })

    return fragments


def _extract_layout_lines_pdfium_uncached(
    pdf_path: str,
    start_page: int,
    end_page: int | None,
    y_tolerance: float,
) -> tuple[LayoutLine, ...]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page_count = len(pdf)
        if end_page is None:
            end_page = page_count
        if not 1 <= start_page <= end_page <= page_count:
            raise ValueError("Rango de páginas fuera de límite.")
        output: list[LayoutLine] = []
        for page_number in range(start_page, end_page + 1):
            page = pdf[page_number - 1]
            try:
                _width, page_height = page.get_size()
                textpage = page.get_textpage()
                try:
                    fragments = _page_fragments(page, textpage, float(page_height), float(y_tolerance))
                finally:
                    textpage.close()

                fragments.sort(key=lambda item: (item["y0"], item["x0"]))
                groups: list[list[dict]] = []
                for fragment in fragments:
                    if groups:
                        baseline = statistics.median(x["y0"] for x in groups[-1])
                        if abs(fragment["y0"] - baseline) <= float(y_tolerance):
                            groups[-1].append(fragment)
                            continue
                    groups.append([fragment])

                for group in groups:
                    group.sort(key=lambda item: item["x0"])
                    text = _clean_text(" ".join(item["text"] for item in group))
                    sizes = [s for item in group for s in item["sizes"] if s > 0]
                    if not text:
                        continue
                    output.append(LayoutLine(
                        page=page_number,
                        page_height=float(page_height),
                        text=text,
                        x0=min(item["x0"] for item in group),
                        y0=min(item["y0"] for item in group),
                        x1=max(item["x1"] for item in group),
                        y1=max(item["y1"] for item in group),
                        median_font_size=statistics.median(sizes) if sizes else 0.0,
                        fragment_count=max(1, len(group)),
                    ))
            finally:
                page.close()
        output.sort(key=lambda line: (line.page, line.y0, line.x0))
        return tuple(output)
    finally:
        pdf.close()


@lru_cache(maxsize=4)
def _extract_layout_lines_pdfium_cached(
    resolved_path: str,
    start_page: int,
    end_page: int | None,
    y_tolerance: float,
    size_bytes: int,
    mtime_ns: int,
) -> tuple[LayoutLine, ...]:
    del size_bytes, mtime_ns
    return _extract_layout_lines_pdfium_uncached(
        resolved_path, start_page, end_page, y_tolerance
    )


def extract_layout_lines_pdfium(
    pdf_path: str | Path,
    start_page: int = 1,
    end_page: int | None = None,
    y_tolerance: float = 0.9,
) -> List[LayoutLine]:
    """Extract MuPDF-compatible ``LayoutLine`` values with PDFium."""
    path = Path(pdf_path).expanduser().resolve()
    stat = path.stat()
    return list(_extract_layout_lines_pdfium_cached(
        str(path), int(start_page), int(end_page) if end_page is not None else None,
        float(y_tolerance), int(stat.st_size), int(stat.st_mtime_ns)
    ))


def clear_pdfium_layout_line_cache() -> None:
    _extract_layout_lines_pdfium_cached.cache_clear()


def pdf_page_count_pdfium(pdf_path: str | Path) -> int:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def page_dimensions_pdfium(pdf_path: str | Path, page_number: int) -> Tuple[float, float]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if not 1 <= page_number <= len(pdf):
            raise ValueError("Página fuera de rango.")
        page = pdf[page_number - 1]
        try:
            width, height = page.get_size()
            return float(width), float(height)
        finally:
            page.close()
    finally:
        pdf.close()
