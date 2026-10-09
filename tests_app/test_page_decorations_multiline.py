from collections import namedtuple

from biblioref_page_decorations import filter_repeated_page_decorations

L = namedtuple("L", "page text x0 y0 y1 page_height")


def test_two_line_running_header_is_removed_on_every_page():
    lines = []
    for page in (111, 112, 113):
        lines += [
            L(page, "Aplicación Móvil para el Entrenamiento de Estrategias Cognitivas de Regulación", 70, 36.4, 48, 842),
            L(page, "Emocional", 70, 50.2, 62, 842),
            L(page, f"Referencia que empieza en la página {page}. Revista, 3, 1-9.", 70, 90, 102, 842),
            L(page, str(page), 300, 780, 792, 842),
        ]
    kept, removed = filter_repeated_page_decorations(lines)
    assert {r["text"] for r in removed} == {
        "Aplicación Móvil para el Entrenamiento de Estrategias Cognitivas de Regulación", "Emocional"}
    assert all("Referencia" in k.text or k.text.isdigit() for k in kept)


def test_a_line_in_the_band_that_does_not_repeat_is_kept():
    lines = [L(1, "Encabezado de la tesis", 70, 30, 40, 842), L(1, "Smith, J. (2001). Única.", 70, 45, 55, 842),
             L(2, "Encabezado de la tesis", 70, 30, 40, 842), L(2, "Pérez, A. (1999). Otra distinta.", 70, 45, 55, 842)]
    kept, removed = filter_repeated_page_decorations(lines)
    assert [r["text"] for r in removed] == ["Encabezado de la tesis", "Encabezado de la tesis"]
    assert len(kept) == 2
