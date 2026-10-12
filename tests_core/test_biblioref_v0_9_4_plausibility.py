"""Tests for the v0.9.4 (P1) output-plausibility gate of the audit router.

The gate exists because every issue detector in ``rescue.py`` iterates over
detected zones or records: when the stable route abstains there are no zones,
no detector can fire, and the status used to collapse to ``looks_consistent``
no matter how bad the outcome was.  On the frozen TDX-40 holdout that happened
for 10 of 40 theses, with a sensitivity of 0.00 against severe failures.

These tests are behavioural, not corpus-specific: no assertion mentions an
author, a university, a repository or a page number.
"""
import unittest

from biblioref.core.config import ALGORITHM_VERSION, RESCUE_ROUTER_VERSION, SOFTWARE_VERSION
from biblioref.rescue import (
    IMPLAUSIBLE_YIELD_PER_100_PAGES,
    MIN_PAGES_FOR_YIELD_CHECK,
    UNUSABLE_TEXT_LAYER_RATIO,
    _output_plausibility,
)


class FakeLine:
    """Minimal stand-in for a LayoutLine (only .page and .text are read here)."""

    def __init__(self, page, text):
        self.page = page
        self.text = text


def clean_lines(n_pages=100, per_page=6, text="Smith, J. (2020). A perfectly ordinary title."):
    return [FakeLine(p, text) for p in range(1, n_pages + 1) for _ in range(per_page)]


def corrupted_lines(n_pages=100, per_page=6):
    return [FakeLine(p, "\x03\x14\x06 \x1d\x17\x08 \x12\x05\x08 \x1f\x08")
            for p in range(1, n_pages + 1) for _ in range(per_page)]


NO_COVERAGE = {"n_toc_reference_candidates": 0, "possible_incomplete_coverage": False}
TOC_COVERAGE = {"n_toc_reference_candidates": 3, "possible_incomplete_coverage": True}


class TestOutputPlausibility(unittest.TestCase):

    def test_versions_keep_effective_algorithm(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.6.21", ALGORITHM_VERSION)
        self.assertEqual("0.9.4-selective-router3-plausibility", RESCUE_ROUTER_VERSION)

    def test_zero_records_is_always_implausible(self):
        p = _output_plausibility(clean_lines(), {}, NO_COVERAGE, {"n_records": 0})
        self.assertTrue(p["implausible"])
        self.assertIn("zero_records", [r["signal"] for r in p["reasons"]])

    def test_healthy_extraction_is_not_flagged(self):
        p = _output_plausibility(clean_lines(), {}, NO_COVERAGE, {"n_records": 180})
        self.assertFalse(p["implausible"])
        self.assertEqual([], p["reasons"])

    def test_incomplete_coverage_is_flagged(self):
        p = _output_plausibility(clean_lines(), {}, TOC_COVERAGE, {"n_records": 0})
        signals = [r["signal"] for r in p["reasons"]]
        self.assertIn("possible_incomplete_coverage", signals)

    def test_implausible_yield_needs_a_bibliographic_hint(self):
        """A low count alone must not fire: there has to be evidence of a bibliography."""
        bland = [FakeLine(p, "ordinary body text with no section vocabulary")
                 for p in range(1, 201) for _ in range(6)]
        p = _output_plausibility(bland, {}, NO_COVERAGE, {"n_records": 4})
        self.assertNotIn("implausible_reference_yield", [r["signal"] for r in p["reasons"]])

    def test_implausible_yield_fires_with_hint(self):
        lines = clean_lines(n_pages=200) + [FakeLine(150, "References")]
        p = _output_plausibility(lines, {}, NO_COVERAGE, {"n_records": 4})
        self.assertIn("implausible_reference_yield", [r["signal"] for r in p["reasons"]])

    def test_short_documents_are_exempt_from_the_yield_check(self):
        short = clean_lines(n_pages=MIN_PAGES_FOR_YIELD_CHECK - 1)
        p = _output_plausibility(short, {}, NO_COVERAGE, {"n_records": 1})
        self.assertNotIn("implausible_reference_yield", [r["signal"] for r in p["reasons"]])

    def test_unusable_text_layer_is_flagged_when_output_is_empty(self):
        p = _output_plausibility(corrupted_lines(), {}, NO_COVERAGE, {"n_records": 0})
        signals = [r["signal"] for r in p["reasons"]]
        self.assertIn("unusable_text_layer", signals)
        reason = next(r for r in p["reasons"] if r["signal"] == "unusable_text_layer")
        self.assertFalse(reason["rescue_applicable"])

    def test_corruption_heuristic_alone_never_flags_a_full_bibliography(self):
        """Regression guard.

        Gene/protein nomenclature (rem1, cig2, Cdc2) trips the corrupted-token
        heuristic, which pushed a healthy molecular-biology thesis just over the
        threshold while it had extracted a complete bibliography.  A text layer
        that produced a full bibliography is usable by demonstration, so the
        signal must require corroboration from the output.
        """
        genes = [FakeLine(p, "deletion of rem1 and cig2 in a pat1-114 mei4 background Cdc2 ade6")
                 for p in range(1, 141) for _ in range(20)]
        from biblioref.adaptive.stable_conflicts import _corrupted_token_ratio
        self.assertGreaterEqual(_corrupted_token_ratio(genes), UNUSABLE_TEXT_LAYER_RATIO)
        p = _output_plausibility(genes, {}, NO_COVERAGE, {"n_records": 162})
        self.assertNotIn("unusable_text_layer", [r["signal"] for r in p["reasons"]])
        self.assertFalse(p["implausible"])

    def test_gate_is_diagnostic_only(self):
        p = _output_plausibility(corrupted_lines(), {}, TOC_COVERAGE, {"n_records": 0})
        self.assertTrue(p["diagnostic_only"])
        self.assertFalse(p["effective_output_changed"])

    def test_thresholds_are_module_level_and_conservative(self):
        self.assertEqual(0.08, UNUSABLE_TEXT_LAYER_RATIO)
        self.assertLessEqual(IMPLAUSIBLE_YIELD_PER_100_PAGES, 10.0)
        self.assertGreaterEqual(MIN_PAGES_FOR_YIELD_CHECK, 20)


if __name__ == "__main__":
    unittest.main()
