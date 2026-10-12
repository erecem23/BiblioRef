from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

from biblioref import process_pdf
from biblioref.adaptive import context as context_module
from biblioref.core.config import ADAPTIVE_ANALYSIS_VERSION, ALGORITHM_VERSION, SOFTWARE_VERSION
from biblioref.ingestion import (
    clear_layout_line_cache,
    extract_layout_lines,
    extract_layout_lines_range,
    pdf_preflight,
    stream_file_to_disk,
)

ROOT = Path(__file__).resolve().parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"


class NoGetValueBytesIO(io.BytesIO):
    def getvalue(self):  # pragma: no cover - should never be called
        raise AssertionError("streaming path must not call getvalue()")


class TestV0811PerformanceInfrastructure(unittest.TestCase):
    def tearDown(self):
        clear_layout_line_cache()

    def test_version_keeps_v0810_diagnostics_and_effective_algorithm(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.6.21", ALGORITHM_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)

    def test_streaming_copy_does_not_require_getvalue(self):
        payload = b"%PDF-test" + b"x" * 100_000
        source = NoGetValueBytesIO(payload)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "uploaded.pdf"
            result = stream_file_to_disk(source, target, chunk_size=4096)
            self.assertEqual(len(payload), result["size_bytes"])
            self.assertEqual(payload, target.read_bytes())
            self.assertEqual(64, len(result["sha256"]))

    def test_range_layout_matches_full_layout_filter(self):
        full = extract_layout_lines(GRAMMAR_PDF)
        subset = extract_layout_lines_range(GRAMMAR_PDF, 4, 6)
        expected = [line for line in full if 4 <= int(line.page) <= 6]
        self.assertEqual(expected, subset)

    def test_preflight_page_threshold_enables_heavy_mode(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "many_pages.pdf"
            doc = pymupdf.open()
            for index in range(8):
                page = doc.new_page()
                page.insert_text((72, 72), f"Text page {index} with a usable text layer." * 3)
            doc.save(pdf)
            doc.close()
            info = pdf_preflight(pdf, heavy_pages=8, heavy_size_mb=9999)
            self.assertTrue(info["heavy_mode"])
            self.assertIn("many_pages", info["heavy_mode_reasons"])
            self.assertFalse(info["predominantly_scanned"])

    def test_pipeline_requests_full_layout_once(self):
        import biblioref.pipeline as pipeline
        original = pipeline.extract_layout_lines
        calls = []
        def counted(path):
            calls.append(str(path))
            return original(path)
        with patch.object(pipeline, "extract_layout_lines", side_effect=counted):
            process_pdf(GRAMMAR_PDF, adaptive_mode="shadow")
        self.assertEqual(1, len(calls))

    def test_document_page_roles_are_computed_once_in_shadow_pipeline(self):
        import biblioref.pipeline as pipeline
        original = pipeline.classify_document_pages
        calls = []
        def counted(lines):
            calls.append(len(lines))
            return original(lines)
        with patch.object(pipeline, "classify_document_pages", side_effect=counted):
            process_pdf(GRAMMAR_PDF, adaptive_mode="shadow")
        self.assertEqual(1, len(calls))

    def test_scope_selection_does_not_rerun_v06(self):
        import biblioref.pipeline as pipeline
        original = pipeline.process_pdf_v06
        calls = []
        def counted(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)
        with patch.object(pipeline, "process_pdf_v06", side_effect=counted):
            process_pdf(GRAMMAR_PDF, scope="unique_references", adaptive_mode="off")
        self.assertEqual(1, len(calls))

    def test_normal_result_does_not_expose_profiler_state(self):
        result = process_pdf(GRAMMAR_PDF, adaptive_mode="shadow")
        self.assertNotIn("performance", result)
        self.assertNotIn("timings", result)
        self.assertNotIn("counters", result)
        self.assertNotIn("extraction_context", result)

    def test_audit_app_has_no_full_pdf_bytes_session_copy(self):
        source = (ROOT / "biblioref_audit_app.py").read_text(encoding="utf-8")
        self.assertNotIn('"pdf_bytes"', source)
        self.assertNotIn("uploaded.getvalue()", source)
        self.assertIn("stream_file_to_disk", source)
        self.assertIn("extract_layout_lines_range", source)


if __name__ == "__main__":
    unittest.main()
