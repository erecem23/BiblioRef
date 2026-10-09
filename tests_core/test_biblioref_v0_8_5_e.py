import unittest
from pathlib import Path

from biblioref.adaptive.reconciliation import analyze_reconciliation
from biblioref.audit.surveillance import analyze_surveillance
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.pipeline import process_pdf


def src(i, text, page=1):
    return {
        "line_index": i, "page": page, "page_height": 800.0,
        "x0": 72.0, "y0": 100.0 + i * 12, "x1": 500.0, "y1": 110.0 + i * 12,
        "median_font_size": 11.0, "fragment_count": 1, "text": text,
    }


def segment(lines, boundary_signals=None):
    pages=sorted({x.get('page',1) for x in lines})
    return {
        "reference_text": " ".join(x['text'] for x in lines),
        "reference_start_page": pages[0], "reference_end_page": pages[-1],
        "n_pages_spanned": len(pages), "n_source_lines": len(lines),
        "source_lines": lines, "shadow_boundary_signals": list(boundary_signals or []),
    }


class TestBiblioRefV085E(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, "0.9.10-rc2")
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, "0.8.10-shadow23")

    def test_false_split_generates_merge_safe_proposal_but_does_not_apply(self):
        segs = [
            segment([src(0, "Ribeirão Preto: Legis and")]),
            segment([src(1, "Summa, 2015.")], ["publisher_year_continuation"]),
            segment([src(2, "SILVA, JOAO. Titulo bibliografico suficientemente completo com editora local volume numero paginas cidade e outras informacoes. 2016.")]),
            segment([src(3, "SOUZA, MARIA. Outra referencia bibliografica suficientemente completa com editora revista volume paginas DOI e demais metadados. 2017.")]),
        ]
        surveillance = analyze_surveillance(segs, [])
        out = analyze_reconciliation(segs, [], surveillance=surveillance)
        merges = [p for p in out["proposals"] if p["operation"] == "MERGE"]
        self.assertTrue(merges)
        self.assertEqual(merges[0]["classification"], "SAFE_REPAIR")
        self.assertFalse(out["auto_apply"])
        self.assertFalse(out["effective_output_changed"])

    def test_order_conflict_split_is_review_not_safe(self):
        merged = segment([
            src(0, "Codazzi, Augustin. 2003. First reference."),
            src(1, "Balkaran, Stephen. 2014. Second reference."),
        ])
        candidates = [{
            "line_index": 1, "semantic_anchor": True, "score": 4.25, "label": "weak",
            "features": {"strong_alphabetical_inversion": True},
            "contributions": [
                {"signal": "author_bare_date", "weight": 3.5},
                {"signal": "strong_alphabetical_inversion", "weight": -4.0},
                {"signal": "nearby_bibliographic_evidence", "weight": 1.0},
            ],
            "text": "Balkaran, Stephen. 2014. Second reference.",
        }]
        surveillance = analyze_surveillance([merged], candidates)
        out = analyze_reconciliation([merged], candidates, surveillance=surveillance)
        splits = [p for p in out["proposals"] if p["operation"] == "SPLIT"]
        self.assertTrue(splits)
        self.assertEqual(splits[0]["classification"], "REVIEW_REPAIR")
        self.assertTrue(splits[0]["order_conflict"])

    def test_multiple_strong_internal_starts_can_generate_split_proposals(self):
        merged = segment([
            src(0, "Smith, J. (2020). First."),
            src(1, "Brown, P. (2021). Second."),
            src(2, "Jones, R. (2022). Third."),
        ])
        candidates = [
            {"line_index": 1, "semantic_anchor": True, "score": 5.0, "label": "strong", "features": {}, "contributions": [{"signal":"author_parenthetical_date","weight":3.5}]},
            {"line_index": 2, "semantic_anchor": True, "score": 5.0, "label": "strong", "features": {}, "contributions": [{"signal":"author_parenthetical_date","weight":3.5}]},
        ]
        surveillance = analyze_surveillance([merged], candidates)
        out = analyze_reconciliation([merged], candidates, surveillance=surveillance)
        splits = [p for p in out["proposals"] if p["operation"] == "SPLIT"]
        self.assertEqual(len(splits), 2)
        self.assertTrue(all(p["classification"] != "SAFE_REPAIR" for p in splits))

    def test_zone_end_truncation_generates_ambiguous_extend(self):
        segs=[segment([src(0, "Smith, J. (2020). Very long title and")])]
        surveillance=analyze_surveillance(segs, [])
        out=analyze_reconciliation(segs, [], surveillance=surveillance)
        extends=[p for p in out['proposals'] if p['operation']=='EXTEND']
        self.assertTrue(extends)
        self.assertEqual(extends[0]['classification'], 'AMBIGUOUS')
        self.assertTrue(extends[0]['requires_external_source_context'])

    def test_page_flow_continuation_can_generate_extend_hypothesis(self):
        segs=[
            segment([src(0,"Smith, J. (2020). Long title and",page=1)]),
            segment([src(1,"its continuation. Journal, 2, 3-9.",page=2)]),
            segment([src(2,"Brown, P. (2021). Next.",page=2)]),
        ]
        flows=[{"from_page":1,"to_page":2,"flow_state":"likely_continuation","continuation_support":5,"boundary_support":1,"signals":["previous_terminal_incomplete","next_starts_like_continuation","continuation_indent"]}]
        surveillance=analyze_surveillance(segs, [], flows)
        out=analyze_reconciliation(segs, [], surveillance=surveillance, page_flows=flows)
        self.assertTrue(any(p['operation']=='EXTEND' for p in out['proposals']))

    def test_clean_short_valid_reference_generates_no_repair_proposal(self):
        segs = [
            segment([src(0, "Smith, J. (2019). Ordinary complete bibliographic reference with journal metadata and pages.")]),
            segment([src(1, "WHO. (2020). Report.")]),
            segment([src(2, "Brown, P. (2021). Another ordinary complete bibliographic reference with journal metadata and pages.")]),
        ]
        surveillance = analyze_surveillance(segs, [])
        out = analyze_reconciliation(segs, [], surveillance=surveillance)
        self.assertEqual(out["n_proposals"], 0)
        self.assertEqual(out["classification_counts"]["SAFE_REPAIR"], 0)

    def test_moderate_realistic_page_flow_evidence_is_not_safe_repair(self):
        segs = [
            segment([src(0, "[43] A comparison of survival forests based on a simulation", page=91)]),
            segment([src(1, "study as well as on two applications with time-to-event data, BMC methodology, 2017.", page=92)]),
            segment([src(2, "[44] Next numbered reference, 2018.", page=92)]),
        ]
        flows = [{
            "from_page": 91, "to_page": 92, "flow_state": "likely_continuation",
            "continuation_support": 3, "boundary_support": 1,
            "signals": ["next_starts_like_continuation", "next_at_start_cluster", "next_not_active_boundary_candidate"],
        }]
        surveillance = analyze_surveillance(segs, [], flows)
        out = analyze_reconciliation(segs, [], surveillance=surveillance, page_flows=flows)
        props = [p for p in out["proposals"] if p["operation"] == "EXTEND"]
        self.assertTrue(props)
        self.assertNotEqual(props[0]["classification"], "SAFE_REPAIR")

    def test_pipeline_exposes_reconciliation_without_changing_validated_records(self):
        pdf = Path(__file__).with_name("fixtures") / "document_grammar_stress.pdf"
        off = process_pdf(pdf, adaptive_mode="off")
        shadow = process_pdf(pdf, adaptive_mode="shadow")
        self.assertEqual(off.get("records"), shadow.get("records"))
        zones = shadow.get("adaptive_shadow", {}).get("zones", [])
        self.assertTrue(zones)
        self.assertIn("reconciliation", zones[0])
        self.assertFalse(zones[0]["reconciliation"]["auto_apply"])


if __name__ == "__main__":
    unittest.main()
