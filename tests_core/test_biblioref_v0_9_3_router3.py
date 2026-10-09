import tempfile
import unittest
from pathlib import Path

import fitz

from biblioref.core.config import SOFTWARE_VERSION, RESCUE_ROUTER_VERSION
from biblioref.extraction.numeric_rescue import numeric_filter_candidate, build_numeric_layout_resegmentation
from biblioref.extraction.structural_reconciliation import _strong_section_heading
from biblioref.ingestion import extract_layout_lines
from biblioref.legacy.engine import detect_adaptive_layout_zones
from biblioref.rescue import RESCUE_PROFILES


def rec(text, i=1):
    return {
        "reference_text": text,
        "zone_id": 1,
        "ref_in_zone": i,
        "reference_start_page": 1,
        "reference_end_page": 1,
        "audit_flags": "",
    }


class TestV093Router3(unittest.TestCase):
    def test_version_and_profiles(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.9.4-selective-router3-plausibility", RESCUE_ROUTER_VERSION)
        for profile in (
            "numeric_filter",
            "numeric_layout_resegmentation",
            "multi_column_reflow_v2",
            "structural_zone_reconciliation",
        ):
            self.assertIn(profile, RESCUE_PROFILES)
        self.assertEqual("stable", RESCUE_PROFILES[0])

    def test_numeric_filter_only_removes_safe_extras_from_complete_backbone(self):
        rows = []
        vals = [1, 2, 3, 110, 4, 5, 6, 7, 8, 473, 9, 10]
        for i, value in enumerate(vals, 1):
            if value in {110, 473}:
                rows.append(rec(f"{value}. [ layout navigation ]", i))
            else:
                rows.append(rec(f"{value}. Author, A. (2020). Reference {value}. Journal.", i))
        candidate = numeric_filter_candidate(rows)
        self.assertTrue(candidate["accepted"])
        self.assertEqual(10, candidate["n_enhanced_segments"])
        self.assertEqual([110, 473], [x["value"] for x in candidate["extras"]])

    def test_numeric_filter_abstains_when_true_sequence_has_gap(self):
        rows = [rec(f"{v}. Author, A. (2020). Reference.", i) for i, v in enumerate([1,2,3,5,6,7,8,9],1)]
        self.assertFalse(numeric_filter_candidate(rows)["accepted"])

    def test_structural_boundary_requires_the_boundary_line_itself_to_be_strong(self):
        self.assertTrue(_strong_section_heading("Chapter 2: Empirical Paper"))
        self.assertTrue(_strong_section_heading("5. Experimental"))
        self.assertFalse(_strong_section_heading("1.5 References 45"))
        self.assertFalse(_strong_section_heading("110 B. Former publication that does not form part of the thesis"))
        self.assertFalse(_strong_section_heading("must be removed to keep emissions in-channel"))

    def test_detached_marker_layout_can_be_resegmented_from_raw_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "detached.pdf"
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 72), "REFERENCES", fontsize=14)
            y = 110
            for value in range(1, 11):
                # Deliberately place the marker in a narrow, detached column.
                page.insert_text((72, y), str(value), fontsize=10)
                page.insert_text((112, y), f"Author{value}, A. (2020). Reference title {value}. Journal {value}.", fontsize=10)
                y += 55
            doc.save(pdf)
            doc.close()

            lines = extract_layout_lines(pdf)
            zones = detect_adaptive_layout_zones(lines)
            self.assertEqual(1, len(zones))
            deliberately_bad_base = [rec("Author merged (2020). Reference block.", i) for i in range(1, 4)]
            attempt = build_numeric_layout_resegmentation(pdf, zones[0], deliberately_bad_base)
            self.assertTrue(attempt["accepted"], attempt)
            self.assertEqual(10, attempt["n_enhanced_segments"])
            self.assertEqual(10, len(attempt["segments"]))


if __name__ == "__main__":
    unittest.main()
