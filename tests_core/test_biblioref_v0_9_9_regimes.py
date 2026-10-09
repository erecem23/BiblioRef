import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from biblioref.extraction.marker_regime import build_hierarchical_marker_repair
from biblioref.extraction.numeric_rescue import numeric_filter_candidate, extend_numeric_candidate_end_page
from biblioref.extraction.column_reflow import _column_geometry
from biblioref.extraction.boundary_reconciliation import build_hanging_indent_boundary_repair
from biblioref.legacy.engine import LayoutLine


def line(page, y, x, text, x1=None, h=800.0):
    return LayoutLine(
        page=page, page_height=h, text=text, x0=x, y0=y,
        x1=(x1 if x1 is not None else x + 250), y1=y + 11,
        median_font_size=10.5, fragment_count=1,
    )


class V099RegimeTests(unittest.TestCase):
    def test_hierarchical_marker_sequence_recovers_local_bibliography(self):
        heading = line(53, 70, 70, "1.8 BIBLIOGRAFÍA")
        lines = [
            heading,
            line(53, 100, 72, "1.1. Schreiber, S. (2011). Organic synthesis. PNAS 108:1-9."),
            line(53, 118, 105, "Continuation text."),
            line(53, 145, 72, "1.2. Smith, J. (2012). Second paper. Nature 2:1-3."),
            line(53, 172, 72, "1.3. Doe, A. (2013). Third paper. Science 4:4-8."),
        ]
        zone = SimpleNamespace(lines=lines, heading=heading)
        result = build_hierarchical_marker_repair(zone, [{"reference_text": "merged"}])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["sequence_last"], 3)
        self.assertEqual(len(result["segments"]), 3)
        self.assertTrue(result["segments"][0]["reference_text"].startswith("1.1."))

    def test_hierarchical_section_numbers_without_bibliographic_evidence_abstain(self):
        heading = line(4, 60, 70, "CAPÍTULO 5")
        lines = [
            heading,
            line(4, 100, 72, "5.1. Introducción general al problema"),
            line(4, 130, 72, "5.2. Metodología y diseño del estudio"),
            line(4, 160, 72, "5.3. Resultados de la investigación"),
        ]
        zone = SimpleNamespace(lines=lines, heading=heading)
        result = build_hierarchical_marker_repair(zone, [{"reference_text": "one"}])
        self.assertFalse(result["accepted"])

    def test_numeric_filter_merges_short_doi_continuation_fragments(self):
        records = []
        for i in range(1, 9):
            records.append({"reference_text": f"{i}. Author {i}. (201{i}). Journal 1:1-2."})
            if i == 4:
                # False stable boundary whose leading number overlaps the true backbone.
                records.append({"reference_text": "37. doi:10.1016/j.math.2014.08.006"})
        result = numeric_filter_candidate(records)
        self.assertTrue(result["accepted"])
        self.assertEqual(len(result["segments"]), 8)
        self.assertIn("doi:10.1016", result["segments"][3]["reference_text"])

    def test_candidate_numeric_end_extends_only_by_exact_next_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "numeric_tail.pdf"
            doc = pymupdf.open()
            page1 = doc.new_page(width=595, height=842)
            y = 80
            for i in range(1, 9):
                page1.insert_text((72, y), f"{i} Author{i}, A. (20{10+i:02d}). Reference title {i}.", fontsize=10)
                y += 30
            page2 = doc.new_page(width=595, height=842)
            y = 80
            for i in range(9, 13):
                page2.insert_text((72, y), f"{i} Author{i}, A. (20{10+i:02d}). Reference title {i}.", fontsize=10)
                y += 30
            doc.save(pdf)
            doc.close()
            result = extend_numeric_candidate_end_page(pdf, 1, 1, max_forward_pages=2)
            self.assertTrue(result["extended"])
            self.assertEqual(result["end_page"], 2)
            self.assertEqual(result["continued_values"], [9, 10, 11, 12])

    def test_candidate_numeric_end_does_not_skip_missing_next_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "numeric_gap.pdf"
            doc = pymupdf.open()
            page1 = doc.new_page(width=595, height=842)
            y = 80
            for i in range(1, 9):
                page1.insert_text((72, y), f"{i} Author{i}, A. (20{10+i:02d}). Reference title {i}.", fontsize=10)
                y += 30
            page2 = doc.new_page(width=595, height=842)
            page2.insert_text((72, 80), "10 Author10, A. (2020). Missing marker nine.", fontsize=10)
            doc.save(pdf)
            doc.close()
            result = extend_numeric_candidate_end_page(pdf, 1, 1, max_forward_pages=2)
            self.assertFalse(result["extended"])
            self.assertEqual(result["end_page"], 1)


    def test_hanging_indent_reconciliation_removes_only_weak_off_margin_bare_year_starts(self):
        heading = line(1, 60, 72, "BIBLIOGRAFÍA")
        lines = [heading]
        y = 100
        for i in range(10):
            lines.append(line(2, y, 72, f"Autor{i}, A. (201{i}). Título {i}.")); y += 18
            if i == 2:
                lines.append(line(2, y, 108, "Argentina, 2005-2007. Revista X, 1, 1-2.")); y += 18
            else:
                lines.append(line(2, y, 108, "Revista X, 1, 1-2.")); y += 18
        z = SimpleNamespace(
            heading=heading, lines=lines, style=SimpleNamespace(style="author_year_comma"),
            layout=SimpleNamespace(start_margin=72.0, continuation_margin=108.0,
                                   start_margin_tolerance=10.0, hanging_indent_detected=True),
        )
        base = []
        for i in range(10):
            base.append({"reference_text": f"Autor{i}, A. (201{i}). Título {i}.",
                         "reference_start_x": 72.0,
                         "boundary_evidence": "author_or_institution+parenthetical_date+start_margin"})
        base.insert(3, {"reference_text": "Argentina, 2005-2007. Revista X, 1, 1-2.",
                        "reference_start_x": 108.0,
                        "boundary_evidence": "author+bare_year+local_geometry"})
        result = build_hanging_indent_boundary_repair(z, base)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["repair_direction"], "remove_weak_false_boundaries_and_reconcile")
        self.assertEqual(result["n_reconciled_segments"], 10)
        self.assertEqual(result["n_baseline_off_margin_weak_local_geometry"], 1)

    def test_hanging_indent_negative_delta_protects_repeated_author_year_only_entries(self):
        heading = line(1, 60, 72, "BIBLIOGRAFÍA")
        lines = [heading]
        y = 100
        for i in range(10):
            lines.append(line(2, y, 72, f"Autor{i}, A. (201{i}). Título {i}.")); y += 18
            lines.append(line(2, y, 108, "Revista X, 1, 1-2.")); y += 18
        z = SimpleNamespace(
            heading=heading, lines=lines, style=SimpleNamespace(style="author_year_comma"),
            layout=SimpleNamespace(start_margin=72.0, continuation_margin=108.0,
                                   start_margin_tolerance=10.0, hanging_indent_detected=True),
        )
        base = [{"reference_text": f"Autor{i}, A. (201{i}). Título {i}.",
                 "reference_start_x": 72.0,
                 "boundary_evidence": "author_or_institution+parenthetical_date+start_margin"}
                for i in range(10)]
        base.insert(3, {"reference_text": "(1995). Reflexiones sobre la enseñanza.",
                        "reference_start_x": 108.0,
                        "boundary_evidence": "repeated_author_inherited_year"})
        result = build_hanging_indent_boundary_repair(z, base)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["n_baseline_off_margin_protected_repeated_author"], 1)

    def test_gutter_geometry_accepts_realistic_31_percent_column_separation(self):
        # A two-column bibliography with a persistent empty corridor around x=280.
        lines = []
        for page in (1, 2):
            y = 100
            for i in range(8):
                lines.append(line(page, y, 90, f"Left Author {i}. (201{i}). Title.", x1=250))
                lines.append(line(page, y, 345, f"Right Author {i}. (201{i}). Title.", x1=510))
                y += 28
        geom = _column_geometry(lines, 595.0)
        self.assertTrue(geom["strong"])
        self.assertEqual(geom["method"], "persistent_vertical_gutter_v0_6_5")

    def test_gutter_geometry_abstains_on_single_column_hanging_indent(self):
        lines = []
        y = 100
        for i in range(12):
            lines.append(line(1, y, 90, f"Author {i}. (201{i}). Title.", x1=510)); y += 16
            lines.append(line(1, y, 125, "Continuation of the same reference.", x1=510)); y += 24
        geom = _column_geometry(lines, 595.0)
        self.assertFalse(geom["strong"])


if __name__ == "__main__":
    unittest.main()
