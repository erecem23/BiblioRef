# -*- coding: utf-8 -*-
"""Algoritmo 0.6.16: el extractor PyMuPDF lee una página con /Rotate como se ve.

Prueba el backend PyMuPDF junto con el escritor del OCR (biblioref.ocr), por eso
importa pymupdf directamente y figura en tests_support/pdf_backend_manifest.json.
"""
import unittest


class RotatedPageLines(unittest.TestCase):
    """Una página escaneada con /Rotate 90 guarda el texto en vertical.

    ``get_text`` da las cajas en el espacio sin rotar: el extractor agrupaba por
    «renglones» que en la página vista son columnas, y la bibliografía del OCR
    salía en palabras sueltas y desordenadas. Las cajas se llevan al espacio
    visible con ``page.rotation_matrix``, como hace el escritor del OCR.
    """

    def test_lines_of_a_rotated_page_come_out_whole_and_in_order(self):
        import tempfile
        import pymupdf
        from biblioref.ocr import _write_invisible_line
        from biblioref_v0_3 import _extract_layout_lines_uncached

        texts = ["Referencias bibliográficas:",
                 "1.- ALLPORT, F.H. Social psychology. Boston: Houghton",
                 "Mifflin, 1924.",
                 "2.- BALLY, Ch. El lenguaje y la vida. Buenos Aires: Losada, 1941."]
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        page.set_rotation(90)
        for i, text in enumerate(texts):
            # Caja vista (vertical en la página sin rotar), como la devuelve Tesseract.
            seen = pymupdf.Rect(100, 120 + 24 * i, 100 + 7 * len(text), 136 + 24 * i)
            _write_invisible_line(page, text, seen * page.derotation_matrix)
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/rotated.pdf"
            doc.save(path)
            doc.close()
            lines = _extract_layout_lines_uncached(path, 0.9)
        self.assertEqual(texts, [line.text for line in lines])
        self.assertTrue(all(line.x1 - line.x0 > line.y1 - line.y0 for line in lines))


if __name__ == "__main__":
    unittest.main()
