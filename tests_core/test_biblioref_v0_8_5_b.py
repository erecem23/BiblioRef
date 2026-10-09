import unittest
from types import SimpleNamespace

from biblioref.adaptive.page_flow import analyze_page_flows, terminal_completeness
from biblioref.core.config import SOFTWARE_VERSION, ADAPTIVE_ANALYSIS_VERSION
from biblioref.legacy.engine import LayoutLine


def line(page, text, x0=72, y0=100, y1=112, h=800):
    return LayoutLine(page=page, page_height=h, text=text, x0=x0, y0=y0, x1=500, y1=y1, median_font_size=10, fragment_count=1)


class TestBiblioRefV085B(unittest.TestCase):
    def test_version_metadata(self):
        self.assertEqual(SOFTWARE_VERSION, '0.9.10-rc2')
        self.assertEqual(ADAPTIVE_ANALYSIS_VERSION, '0.8.10-shadow23')

    def test_terminal_incomplete_connector(self):
        out = terminal_completeness('Smith, J. (2020). A very long title and', line(1, 'x', y0=760, y1=790))
        self.assertEqual(out['terminal_state'], 'likely_incomplete')
        self.assertIn('ends_with_linking_word', out['signals'])

    def test_cross_page_continuation(self):
        lines = [
            line(1, 'Smith, J. (2020). A very long title and', x0=72, y0=760, y1=790),
            line(2, 'its continuation. Journal, 4, 1-10.', x0=96, y0=70, y1=82),
            line(2, 'Brown, P. (2021). Next.', x0=72, y0=110, y1=122),
        ]
        flows = analyze_page_flows(lines, candidates=[])
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0]['flow_state'], 'likely_continuation')

    def test_running_reference_heading_is_skipped(self):
        lines = [
            line(1, 'Smith, J. (2020). A title and', x0=72, y0=760, y1=790),
            line(2, 'REFERENCES', x0=72, y0=40, y1=52),
            line(2, 'its continuation. Journal, 4, 1-10.', x0=96, y0=70, y1=82),
        ]
        flows = analyze_page_flows(lines, candidates=[])
        self.assertEqual(flows[0]['flow_state'], 'likely_continuation')
        self.assertEqual(flows[0]['next_text_preview'], 'its continuation. Journal, 4, 1-10.')
        self.assertIn('page_top_decoration_skipped', flows[0]['signals'])

    def test_complete_record_then_new_reference(self):
        lines = [
            line(1, 'Smith, J. (2020). Title. Journal, 2, 3-8.', x0=72, y0=760, y1=790),
            line(2, 'Brown, P. (2021). Next.', x0=72, y0=70, y1=82),
        ]
        candidates = [{"line_index": 1, "active_shadow_boundary": True}]
        flows = analyze_page_flows(lines, candidates=candidates)
        self.assertEqual(flows[0]['flow_state'], 'likely_new_reference')

    def test_page_break_itself_is_not_boundary_evidence(self):
        lines = [
            line(1, 'Neutral text without terminal cue', x0=72, y0=760, y1=790),
            line(2, 'Neutral next line', x0=72, y0=70, y1=82),
        ]
        flows = analyze_page_flows(lines, candidates=[])
        self.assertEqual(flows[0]['flow_state'], 'ambiguous')
        self.assertNotIn('page_break_is_boundary', flows[0]['signals'])

    def test_incomplete_page_range_plus_doi_continues(self):
        lines = [
            line(1, 'Smith, J. (2020). Journal, 12, 509-', x0=72, y0=760, y1=790),
            line(2, '521. doi:10.1234/abc', x0=96, y0=70, y1=82),
        ]
        flows = analyze_page_flows(lines, candidates=[])
        self.assertEqual(flows[0]['flow_state'], 'likely_continuation')
        self.assertIn('incomplete_page_range', flows[0]['previous_terminal_signals'])


if __name__ == '__main__':
    unittest.main()
