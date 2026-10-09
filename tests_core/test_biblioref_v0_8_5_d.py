import unittest
from pathlib import Path

from biblioref.adaptive.length_profile import build_length_profile
from biblioref.audit.surveillance import analyze_surveillance
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.pipeline import process_pdf


def src(i, text, page=1):
    return {
        "line_index": i, "page": page, "page_height": 800.0,
        "x0": 72.0, "y0": 100.0 + i * 12, "x1": 500.0, "y1": 110.0 + i * 12,
        "median_font_size": 11.0, "fragment_count": 1, "text": text,
    }


def seg(text, indices, boundary_signals=None, page=1):
    return {
        "reference_text": text,
        "reference_start_page": page,
        "reference_end_page": page,
        "n_pages_spanned": 1,
        "n_source_lines": len(indices),
        "source_lines": [src(i, text if len(indices) == 1 else f"line {i}", page=page) for i in indices],
        "shadow_boundary_signals": list(boundary_signals or []),
    }


class TestBiblioRefV085D(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, "0.9.10-rc2")
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, "0.8.10-shadow23")

    def test_length_profile_uses_robust_local_statistics(self):
        segments = [seg("word " * n, [i]) for i, n in enumerate([30, 32, 31, 29, 2, 33, 30])]
        profile = build_length_profile(segments)
        self.assertEqual(profile["median_words"], 30.0)
        self.assertIn("short_vs_zone_median", profile["records"][4]["length_flags"])
        self.assertFalse(profile["auto_apply"])

    def test_very_short_valid_reference_is_not_auto_split_or_merge(self):
        segments = [
            seg("Smith, J. (2019). A reasonably ordinary bibliographic reference with journal metadata and pages.", [0]),
            seg("WHO. (2020). Report.", [1]),
            seg("Brown, P. (2021). Another reasonably ordinary bibliographic reference with journal metadata and pages.", [2]),
        ]
        out = analyze_surveillance(segments, candidates=[])
        flags = out["records"][1]["surveillance_flags"]
        self.assertNotIn("SPLIT_WATCH", flags)
        self.assertNotIn("MERGE_WATCH", flags)
        self.assertFalse(out["auto_apply"])

    def test_false_split_pattern_gets_high_watch(self):
        segments = [
            seg("Ribeirão Preto: Legis and", [0]),
            seg("Summa, 2015.", [1], boundary_signals=["publisher_year_continuation"]),
            seg("SILVA, JOAO. Titulo bibliografico completo com editora local e outras informacoes. 2016.", [2]),
            seg("SOUZA, MARIA. Outra referencia bibliografica completa com varias palavras e metadados. 2017.", [3]),
        ]
        out = analyze_surveillance(segments, candidates=[])
        row = out["records"][1]
        self.assertIn("SPLIT_WATCH", row["surveillance_flags"])
        self.assertEqual(row["highest_severity"], "HIGH_WATCH")

    def test_multiple_internal_boundaries_raise_merge_watch(self):
        merged = {
            "reference_text": "Smith, J. (2020). First. Brown, P. (2021). Second. Jones, R. (2022). Third.",
            "reference_start_page": 1, "reference_end_page": 1, "n_pages_spanned": 1,
            "n_source_lines": 3,
            "source_lines": [src(0, "Smith, J. (2020). First."), src(1, "Brown, P. (2021). Second."), src(2, "Jones, R. (2022). Third.")],
            "shadow_boundary_signals": [],
        }
        candidates = [
            {"line_index": 1, "semantic_anchor": True, "score": 4.0, "features": {}},
            {"line_index": 2, "semantic_anchor": True, "score": 4.0, "features": {}},
        ]
        out = analyze_surveillance([merged], candidates)
        row = out["records"][0]
        self.assertIn("MERGE_WATCH", row["surveillance_flags"])
        self.assertGreaterEqual(row["internal_strong_boundaries"], 2)

    def test_order_conflict_inside_record_is_exposed_as_merge_watch(self):
        merged = {
            "reference_text": "Codazzi, Augustin. 2003. First. Balkaran, Stephen. 2014. Second.",
            "reference_start_page": 1, "reference_end_page": 1, "n_pages_spanned": 1,
            "n_source_lines": 2,
            "source_lines": [src(0, "Codazzi, Augustin. 2003. First."), src(1, "Balkaran, Stephen. 2014. Second.")],
            "shadow_boundary_signals": [],
        }
        candidates = [{
            "line_index": 1, "semantic_anchor": True, "score": 1.0,
            "features": {"strong_alphabetical_inversion": True},
        }]
        out = analyze_surveillance([merged], candidates)
        row = out["records"][0]
        self.assertIn("MERGE_WATCH", row["surveillance_flags"])
        self.assertEqual(row["internal_order_conflicts"], 1)
        self.assertIn("ORDER_CONFLICT_WATCH", row["alerts"][0]["evidence"])

    def test_zone_end_incomplete_record_gets_truncation_high_watch(self):
        segments = [seg("Smith, J. (2020). Very long title and", [0])]
        out = analyze_surveillance(segments, candidates=[])
        row = out["records"][0]
        self.assertIn("TRUNCATION_WATCH", row["surveillance_flags"])
        self.assertIn("ZONE_END_TRUNCATION_WATCH", row["surveillance_flags"])
        self.assertEqual(row["highest_severity"], "HIGH_WATCH")

    def test_page_flow_ambiguity_and_decoration_uncertainty_are_watched(self):
        flows = [{
            "from_page": 10, "to_page": 11, "flow_state": "ambiguous",
            "continuation_support": 2, "boundary_support": 2,
            "signals": ["page_flow_decoration_uncertain"],
        }]
        out = analyze_surveillance([], candidates=[], page_flows=flows)
        item = out["page_flow_watches"][0]
        self.assertIn("PAGE_FLOW_DECORATION_UNCERTAIN", item["flags"])
        self.assertIn("PAGE_FLOW_CONFLICT", item["flags"])
        self.assertEqual(item["severity"], "HIGH_WATCH")

    def test_surveillance_never_applies_repair(self):
        out = analyze_surveillance([seg("WHO. (2020). Report.", [0])], candidates=[])
        self.assertFalse(out["auto_apply"])
        self.assertEqual(out["repair_authority"], "none")

    def test_pipeline_exposes_surveillance_without_changing_validated_records(self):
        pdf = Path(__file__).with_name("fixtures") / "document_grammar_stress.pdf"
        off = process_pdf(pdf, adaptive_mode="off")
        shadow = process_pdf(pdf, adaptive_mode="shadow")
        self.assertEqual(off.get("records"), shadow.get("records"))
        zones = shadow.get("adaptive_shadow", {}).get("zones", [])
        self.assertTrue(zones)
        self.assertIn("surveillance", zones[0])
        self.assertFalse(zones[0]["surveillance"]["auto_apply"])


if __name__ == "__main__":
    unittest.main()
