import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests_support import pdf_factory as pymupdf

from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION
from biblioref.extraction.structural_repairs_v067 import (
    _column_hanging_indent_segments,
    _page_column_hanging_indent_segments,
    build_long_segment_raw_hanging_indent_repair,
)
from biblioref.legacy.engine import LayoutLine


def line(page, y, x, text, x1=None, h=800.0):
    return LayoutLine(
        page=page,
        page_height=h,
        text=text,
        x0=x,
        y0=y,
        x1=(x1 if x1 is not None else x + 250),
        y1=y + 11,
        median_font_size=10.5,
        fragment_count=1,
    )


class V0910RC2IntegrationTests(unittest.TestCase):
    def test_candidate_version_axes_are_unambiguous(self):
        self.assertEqual(SOFTWARE_VERSION, "0.9.10-rc2")
        self.assertEqual(ALGORITHM_VERSION, "0.6.20")

    def test_reflow_hanging_indent_recovers_tight_author_year_boundaries(self):
        lines = []
        y = 90
        for i in range(10):
            lines.append(line(1 if i < 5 else 2, y, 72, f"Apellido{chr(65+i)}, A. (20{10+i:02d}). Título {i}.", x1=500))
            lines.append(line(1 if i < 5 else 2, y + 12, 108, "Revista de Prueba, 4(2), 10-20.", x1=500))
            y += 25
            if i == 4:
                y = 90
        segments, diag = _column_hanging_indent_segments(lines)
        self.assertTrue(diag["eligible"])
        self.assertEqual(len(segments), 10)
        self.assertGreaterEqual(diag["margin_separation"], 14)
        self.assertTrue(all("hanging_indent_start_margin" in s["boundary_evidence"] for s in segments))

    def test_reflow_hanging_indent_abstains_without_distinct_continuation_margin(self):
        lines = []
        y = 90
        for i in range(10):
            lines.append(line(1, y, 72, f"Apellido{chr(65+i)}, A. (20{10+i:02d}). Título {i}.", x1=500))
            lines.append(line(1, y + 12, 72, "Revista de Prueba, 4(2), 10-20.", x1=500))
            y += 25
        segments, diag = _column_hanging_indent_segments(lines)
        self.assertFalse(diag["eligible"])
        self.assertEqual(segments, [])

    def test_page_column_hanging_indent_recovers_mirrored_top_lines_and_drops_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "mirrored_columns.pdf"
            doc = pymupdf.open()
            for page_number, (left_start, right_start) in enumerate(((70, 350), (105, 385)), start=1):
                page = doc.new_page(width=620, height=800)
                if page_number == 1:
                    page.insert_text((left_start, 30), "1. Sources", fontsize=9)
                    page.insert_text((left_start, 43), "primary", fontsize=9)
                    left_y = 70
                else:
                    left_y = 30
                for side_start, y0, prefix in ((left_start, left_y, "L"), (right_start, 30, "R")):
                    for i in range(5):
                        year = 2010 + i + (page_number - 1) * 5
                        y = y0 + i * 54
                        page.insert_text((side_start, y), f"{prefix}{page_number}{i}, A. ({year}). Reference title {i}.", fontsize=9)
                        page.insert_text((side_start + 12, y + 13), "Journal Test 4(2), 10-20.", fontsize=9)
                page.insert_text((left_start, 785), str(page_number), fontsize=9)
            doc.save(pdf)
            doc.close()

            zone = SimpleNamespace(start_page=1, end_page=2)
            segments, diag = _page_column_hanging_indent_segments(pdf, zone)
            texts = [item["reference_text"] for item in segments]
            self.assertTrue(diag["eligible"])
            self.assertEqual(diag["n_profiled_columns"], 4)
            self.assertEqual(diag["profiled_column_ratio"], 1.0)
            self.assertGreaterEqual(diag["median_pair_support_ratio"], 0.90)
            self.assertGreater(diag["top_margin_lines_recovered"], 0)
            self.assertEqual(diag["n_numbered_heading_chunks_excluded"], 2)
            self.assertEqual(len(segments), 20)
            self.assertFalse(any(text in {"1", "2"} for text in texts))
            self.assertFalse(any("Sources" in text or text == "primary" for text in texts))
            self.assertTrue(any(text.startswith("R10, A. (2010)") for text in texts))
            self.assertTrue(any(text.startswith("L20, A. (2015)") for text in texts))

    def test_page_column_hanging_indent_abstains_on_single_column_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "single_column.pdf"
            doc = pymupdf.open()
            for page_number in (1, 2):
                page = doc.new_page(width=620, height=800)
                y = 70
                for i in range(8):
                    page.insert_text((72, y), f"Author{i}, A. ({2010+i}). Reference title.", fontsize=9)
                    page.insert_text((84, y + 13), "Journal Test 4(2), 10-20.", fontsize=9)
                    y += 55
            doc.save(pdf)
            doc.close()
            segments, diag = _page_column_hanging_indent_segments(pdf, SimpleNamespace(start_page=1, end_page=2))
            self.assertFalse(diag["eligible"])
            self.assertEqual(segments, [])

    def test_raw_hanging_indent_repairs_moderate_long_undersegmentation(self):
        heading = line(1, 60, 72, "BIBLIOGRAFÍA")
        lines = [heading]
        y = 90
        for i in range(30):
            lines.append(line(1, y, 72, f"Autor{i}, A. Título de referencia académica {i}.", x1=500))
            lines.append(line(1, y + 12, 108, f"Revista de Prueba, 4(2), 10-20, {1990+i}.", x1=500))
            y += 25
        zone = SimpleNamespace(
            heading=heading,
            lines=lines,
            style=SimpleNamespace(style="author_year_bare"),
            layout=SimpleNamespace(start_margin=72.0),
        )
        huge = " ".join(["merged"] * 200)
        base = [{"reference_text": huge, "reference_start_x": 72.0} for _ in range(10)]
        result = build_long_segment_raw_hanging_indent_repair(zone, base)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["n_reconciled_segments"], 30)
        self.assertEqual(result["n_base_segments_ge_180"], 10)
        self.assertLess(result["candidate_max_words"], 180)

    def test_raw_hanging_indent_abstains_without_two_long_segments(self):
        heading = line(1, 60, 72, "BIBLIOGRAFÍA")
        zone = SimpleNamespace(
            heading=heading,
            lines=[heading, line(1, 90, 72, "Autor, A. (2020). Título.")],
            style=SimpleNamespace(style="author_year_bare"),
            layout=SimpleNamespace(start_margin=72.0),
        )
        base = [{"reference_text": " ".join(["merged"] * 200)}]
        result = build_long_segment_raw_hanging_indent_repair(zone, base)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "fewer_than_two_moderately_long_base_segments")


if __name__ == "__main__":
    unittest.main()
