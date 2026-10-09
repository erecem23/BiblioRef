from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import biblioref_v0_3
from biblioref.pipeline import process_pdf


ROOT = Path(__file__).resolve().parent


class TestV089PerformanceOnly(unittest.TestCase):
    def setUp(self):
        biblioref_v0_3.clear_layout_line_cache()

    def tearDown(self):
        biblioref_v0_3.clear_layout_line_cache()

    def test_repeated_layout_requests_open_pdf_once(self):
        pdf = ROOT / "fixtures" / "document_grammar_stress.pdf"
        original = biblioref_v0_3.pymupdf.open
        calls = []

        def counted(*args, **kwargs):
            calls.append(str(args[0]) if args else "")
            return original(*args, **kwargs)

        with patch.object(biblioref_v0_3.pymupdf, "open", side_effect=counted):
            a = biblioref_v0_3.extract_layout_lines(pdf)
            b = biblioref_v0_3.extract_layout_lines(pdf)
            c = biblioref_v0_3.extract_layout_lines(pdf)

        self.assertEqual(a, b)
        self.assertEqual(b, c)
        self.assertEqual(len(calls), 1)

    def test_full_shadow_pipeline_uses_one_physical_layout_parse(self):
        pdf = ROOT / "fixtures" / "document_grammar_stress.pdf"
        original = biblioref_v0_3.pymupdf.open
        calls = []

        def counted(*args, **kwargs):
            calls.append(str(args[0]) if args else "")
            return original(*args, **kwargs)

        with patch.object(biblioref_v0_3.pymupdf, "open", side_effect=counted):
            result = process_pdf(pdf, scope="all_reference_sections", adaptive_mode="shadow")

        self.assertEqual(result["algorithm_version"], "0.6.20")
        self.assertFalse(result["adaptive_shadow"]["auto_apply"])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
