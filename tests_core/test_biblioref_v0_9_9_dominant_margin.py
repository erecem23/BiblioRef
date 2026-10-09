import unittest
from types import SimpleNamespace

from biblioref.extraction.dominant_margin_reconciliation import build_dominant_margin_repair
from biblioref.legacy.engine import LayoutLine


def line(page, y, x, text, h=800.0):
    return LayoutLine(
        page=page, page_height=h, text=text, x0=x, y0=y,
        x1=x + 340, y1=y + 12, median_font_size=11.0, fragment_count=1,
    )


def synthetic_case(with_swap=True):
    heading = line(1, 60, 99, "Bibliografía")
    physical = [heading]
    true_texts = []
    y = 100.0
    page = 1
    for i in range(1, 51):
        if y > 710:
            page += 1
            y = 90.0
        start = f"Autor{i}, A. (20{(i % 20):02d}). Título de referencia {i}."
        physical.append(line(page, y, 128, start)); y += 18
        if i == 5:
            physical.append(line(page, y, 99, "Disponible en:")); y += 18
            physical.append(line(page, y, 99, "https://example.org/recurso/2005.pdf")); y += 18
            true_texts.append(start + " Disponible en: https://example.org/recurso/2005.pdf")
        elif i == 17:
            physical.append(line(page, y, 99, "51. Buenos Aires: Editorial Ejemplo.")); y += 18
            true_texts.append(start + " 51. Buenos Aires: Editorial Ejemplo.")
        else:
            physical.append(line(page, y, 99, f"Revista de Prueba, {i}(1), 1-9.")); y += 18
            true_texts.append(start + f" Revista de Prueba, {i}(1), 1-9.")
        y += 8

    zone = SimpleNamespace(
        heading=heading,
        lines=physical,
        start_page=1,
        end_page=page,
        style=SimpleNamespace(style="author_year_comma"),
        layout=SimpleNamespace(start_margin=128.0, continuation_margin=None,
                               start_margin_tolerance=12.0, hanging_indent_detected=False),
    )

    if not with_swap:
        base = [
            {"reference_text": text, "reference_start_x": 128.0}
            for text in true_texts
        ]
        return physical, zone, base

    base = []
    i = 0
    while i < len(true_texts):
        # Merge true records 30 and 31: one missing dominant-margin start.
        if i == 29:
            base.append({
                "reference_text": true_texts[i] + " " + true_texts[i + 1],
                "reference_start_x": 128.0,
            })
            i += 2
            continue
        base.append({"reference_text": true_texts[i], "reference_start_x": 128.0})
        i += 1

    # Simulate an evidence-based segmenter that stopped at ``Disponible en:``
    # and lost the following URL-only continuation line.
    base[4]["reference_text"] = base[4]["reference_text"].replace(
        " https://example.org/recurso/2005.pdf", ""
    )

    # Split an ordinary continuation at the continuation margin. The false
    # boundary compensates numerically for the missed true start above.
    base.insert(17, {
        "reference_text": "51. Buenos Aires: Editorial Ejemplo.",
        "reference_start_x": 99.0,
    })
    base[16]["reference_text"] = base[16]["reference_text"].replace(
        " 51. Buenos Aires: Editorial Ejemplo.", ""
    )
    assert len(base) == 50
    return physical, zone, base


class DominantMarginReconciliationTests(unittest.TestCase):
    def test_same_count_topology_swap_and_url_continuation_are_recovered(self):
        document_lines, zone, base = synthetic_case(with_swap=True)
        result = build_dominant_margin_repair(document_lines, zone, base)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["reason"], "dominant_margin_same_count_topology_reconciled")
        self.assertEqual(result["n_base_segments"], 50)
        self.assertEqual(result["n_reconciled_segments"], 50)
        self.assertEqual(result["delta"], 0)
        self.assertEqual(result["n_removed_start_signatures"], 1)
        self.assertEqual(result["n_added_start_signatures"], 1)
        self.assertGreaterEqual(result["dominant_start_margin_support"], 0.98)
        texts = [x["reference_text"] for x in result["segments"]]
        self.assertFalse(any(t.startswith("51. Buenos Aires") for t in texts))
        self.assertTrue(any(t.startswith("Autor31, A.") for t in texts))
        self.assertTrue(any("Disponible en: https://example.org/recurso/2005.pdf" in t for t in texts))

    def test_identical_topology_abstains(self):
        document_lines, zone, base = synthetic_case(with_swap=False)
        result = build_dominant_margin_repair(document_lines, zone, base)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["delta"], 0)
        self.assertEqual(result["n_removed_start_signatures"], 0)
        self.assertEqual(result["n_added_start_signatures"], 0)

    def test_low_dominant_margin_support_abstains(self):
        document_lines, zone, base = synthetic_case(with_swap=True)
        for idx in (2, 7, 12, 22):
            base[idx]["reference_start_x"] = 99.0
        result = build_dominant_margin_repair(document_lines, zone, base)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "baseline_start_margin_not_dominant")


if __name__ == "__main__":
    unittest.main()
