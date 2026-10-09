import unittest
from pathlib import Path

from biblioref.core.config import SOFTWARE_VERSION, RESCUE_ROUTER_VERSION, TWO_PASS_ANALYSIS_VERSION
from biblioref.pipeline import _process_pdf_effective, process_pdf
from biblioref.rescue import RESCUE_PROFILES, PROFILE_LABELS

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "document_grammar_stress.pdf"


class TestV091SelectiveRouter(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.9.4-selective-router3-plausibility", RESCUE_ROUTER_VERSION)
        self.assertEqual("0.9.0-two-pass-shadow1", TWO_PASS_ANALYSIS_VERSION)

    def test_stable_router_preserves_effective_records_and_zones(self):
        baseline = _process_pdf_effective(FIXTURE, scope="all_reference_sections", adaptive_mode="shadow")
        routed = process_pdf(FIXTURE, scope="all_reference_sections", adaptive_mode="shadow", rescue_profile="stable")
        self.assertEqual(baseline.get("records"), routed.get("records"))
        self.assertEqual(baseline.get("zones"), routed.get("zones"))
        self.assertFalse(routed.get("rescue_auto_apply"))
        self.assertFalse(routed.get("default_effective_output_changed"))

    def test_router_and_two_pass_coexist_without_auto_apply(self):
        result = process_pdf(FIXTURE, two_pass_shadow=True, rescue_profile="stable")
        self.assertIn("two_pass_shadow", result)
        self.assertFalse(result["two_pass_shadow"]["auto_apply"])
        self.assertIn("post_extraction_audit", result)
        self.assertFalse(result["post_extraction_audit"]["default_output_changed"])

    def test_rescue_menu_starts_with_stable(self):
        self.assertEqual("stable", RESCUE_PROFILES[0])
        self.assertIn("v0.9.0", PROFILE_LABELS["stable"])

    def test_invalid_rescue_profile_rejected(self):
        with self.assertRaises(ValueError):
            process_pdf(FIXTURE, rescue_profile="magic")


if __name__ == "__main__":
    unittest.main()
