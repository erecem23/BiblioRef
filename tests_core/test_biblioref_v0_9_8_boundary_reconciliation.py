import unittest
from types import SimpleNamespace

from biblioref.extraction.boundary_reconciliation import build_hanging_indent_boundary_repair
from biblioref.legacy.engine import LayoutLine


def line(page, y, x, text, h=800.0):
    return LayoutLine(page=page, page_height=h, text=text, x0=x, y0=y, x1=x+300, y1=y+12, median_font_size=11.0)


def zone(lines, hanging=True, sep=36.0):
    heading = line(1, 60, 72, "BIBLIOGRAFÍA")
    return SimpleNamespace(
        heading=heading,
        lines=[heading] + lines,
        style=SimpleNamespace(style="author_year_comma"),
        layout=SimpleNamespace(
            start_margin=72.0,
            continuation_margin=72.0 + sep,
            start_margin_tolerance=10.0,
            hanging_indent_detected=hanging,
        ),
    )


def base_records(n):
    return [
        {"reference_text": f"Autor{i}, A. (20{i:02d}). Título.", "reference_start_x": 72.0}
        for i in range(1, n + 1)
    ]


class BoundaryReconciliationV098Tests(unittest.TestCase):
    def test_recovers_digit_leading_first_reference_and_wrapped_author(self):
        lines = [
            line(2, 100, 72, "5G Américas. (2016). Informe regional."),
            line(2, 118, 108, "Disponible en: https://example.org/5g"),
            line(2, 145, 72, "Acevedo, J. (2009). Título uno."),
            line(2, 163, 108, "Revista X, 1, 1-10."),
            line(2, 190, 72, "Aguerre, C., Benítez-Larghi, S., Calamari, M.,"),
            line(2, 208, 108, "Fontecoba, A., y Winocur, R. (2009). Título dos."),
            line(2, 235, 72, "Asamblea Nacional. (2008). Constitución."),
            line(2, 262, 72, "Ministerio de Educación del Ecuador."),
            line(2, 280, 108, "(2016). Marco legal educativo."),
            line(2, 307, 72, "Zamora, G. (2017). Cierre."),
        ]
        z = zone(lines)
        # Baseline imitates three missed physical boundaries: no 5G, Aguerre,
        # or Ministerio as separate records.
        base = base_records(5)
        result = build_hanging_indent_boundary_repair(z, base)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["first_reference_recovered"])
        self.assertEqual(result["n_reconciled_segments"], 6)
        texts = [s["reference_text"] for s in result["segments"]]
        self.assertTrue(texts[0].startswith("5G Américas"))
        self.assertTrue(any(t.startswith("Aguerre, C.") and "(2009)" in t for t in texts))
        self.assertTrue(any(t.startswith("Ministerio de Educación") and "(2016)" in t for t in texts))

    def test_abstains_without_hanging_indent(self):
        z = zone([line(2, 100, 72, "Autor, A. (2010). Título.")], hanging=False)
        result = build_hanging_indent_boundary_repair(z, base_records(5))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "no_hanging_indent_geometry")

    def test_abstains_when_margin_clusters_are_too_close(self):
        z = zone([line(2, 100, 72, "Autor, A. (2010). Título.")], sep=8.0)
        result = build_hanging_indent_boundary_repair(z, base_records(5))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "start_continuation_margin_not_well_separated")

    def test_rejects_left_margin_lines_without_local_bibliographic_evidence(self):
        lines = []
        y = 100
        # Five valid references, one prose-like left-margin line between them.
        for i in range(5):
            lines.append(line(2, y, 72, f"Autor{i}, A. (201{i}). Título {i}.")); y += 20
            lines.append(line(2, y, 108, "Revista de prueba, 1, 1-2.")); y += 25
        lines.insert(4, line(2, 160, 72, "NOTA GENERAL SOBRE LA SECCIÓN"))
        z = zone(lines)
        result = build_hanging_indent_boundary_repair(z, base_records(5))
        # No gain after local-evidence filtering: the layer must abstain rather
        # than invent a sixth reference from formatting alone.
        self.assertFalse(result["accepted"])
        self.assertEqual(result["delta"], 0)
        self.assertGreaterEqual(result["n_candidates_rejected_without_local_evidence"], 1)

    def test_gain_guard_blocks_implausible_oversegmentation(self):
        lines = []
        y = 100
        for i in range(25):
            lines.append(line(2 + i // 10, y, 72, f"Institución {i}. (20{i%20:02d}). Informe {i}."))
            y += 22
            if y > 680:
                y = 100
        z = zone(lines)
        result = build_hanging_indent_boundary_repair(z, base_records(5))
        self.assertFalse(result["accepted"])
        self.assertGreater(result["delta"], result["max_allowed_gain"])


if __name__ == "__main__":
    unittest.main()
