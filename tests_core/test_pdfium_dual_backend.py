from __future__ import annotations

import unittest
from pathlib import Path

from biblioref.ingestion import (
    extract_layout_lines_range,
    pdf_page_count,
    render_page_png,
)
from biblioref.ingestion.backend_context import active_pdf_backend, use_pdf_backend
from biblioref.ingestion.pdf_backend_compare import compare_pdf_backends
from biblioref.ingestion.pipeline_backend_compare import (
    _candidate_superset,
    _canonical_bibliographic_text,
    compare_pipeline_backends,
)
from biblioref.metadata import detect_cover_metadata


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "document_grammar_stress.pdf"


class TestPdfiumDualBackend(unittest.TestCase):
    def test_pdfium_context_routes_app_primitives_and_resets(self):
        previous = active_pdf_backend()
        with use_pdf_backend("pdfium"):
            self.assertEqual(active_pdf_backend(), "pdfium")
            self.assertEqual(pdf_page_count(FIXTURE), 9)
            self.assertEqual(len(extract_layout_lines_range(FIXTURE, 1, 1)), 2)
            png = render_page_png(FIXTURE, 1, 1.0)
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            metadata = detect_cover_metadata(FIXTURE, FIXTURE.name)
            self.assertEqual(metadata["title"], "Neural Systems and Document Analysis")
            self.assertEqual(metadata["title_source"], "cover_layout")
            # The cover carries no date; the years on page 2 belong to cited works.
            self.assertNotIn("year", metadata["metadata"])
        self.assertEqual(active_pdf_backend(), previous)

    def test_document_grammar_fixture_preserves_text_sequence(self):
        # PDFium returns glyph-tight vertical boxes whereas MuPDF span boxes
        # include different ascender/descender padding. Text sequence and font
        # size are the blocking invariants; raw vertical geometry is diagnostic.
        report = compare_pdf_backends(FIXTURE, geometry_tolerance=7.0)
        self.assertTrue(report["page_count"]["equal"])
        self.assertEqual(report["layout_lines"]["pymupdf"], 44)
        self.assertEqual(report["layout_lines"]["pdfium"], 44)
        self.assertTrue(report["layout_lines"]["exact_text_sequence"])
        self.assertTrue(report["candidate_ready_for_algorithm_diff"])
        self.assertFalse(report["stable_backend_changed"])
        self.assertEqual(report["geometry"]["max_font_size_delta_pt"], 0.0)
        self.assertLessEqual(report["geometry"]["max_abs_delta_pt"], 7.0)

    def test_pipeline_fixture_is_bibliographically_equivalent(self):
        report = compare_pipeline_backends(FIXTURE)
        self.assertTrue(report["summary"]["equal"])
        self.assertTrue(report["zones"]["semantic_exact"])
        self.assertTrue(report["records"]["bibliographic_equivalence"]["equivalent"])
        self.assertTrue(report["migration_gate"]["passes"])
        self.assertFalse(report["stable_backend_changed"])

    def test_equivalence_ignores_whitespace_but_preserves_characters(self):
        self.assertEqual(
            _canonical_bibliographic_text("Los Raros , Buenos Aires"),
            _canonical_bibliographic_text("Los Raros, Buenos Aires"),
        )
        self.assertEqual(
            _canonical_bibliographic_text("Bue \xad nos Aires"),
            _canonical_bibliographic_text("Bue-nos Aires"),
        )
        self.assertNotEqual(
            _canonical_bibliographic_text("New York-London"),
            _canonical_bibliographic_text("New York London"),
        )

    def test_candidate_superset_accepts_insertions_only(self):
        evidence = _candidate_superset(
            "http://example/revista-de- Consultado",
            "http://example/revista-de-occidente/1243 Consultado",
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["relation"], "possible_content_superset")
        self.assertIsNone(_candidate_superset("abcdef", "abXdef"))
        self.assertIsNone(_candidate_superset("abcdef", "abdef"))


if __name__ == "__main__":
    unittest.main()
