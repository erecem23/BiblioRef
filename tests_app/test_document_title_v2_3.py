from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.document_title_v23 import (
    TITLE_READING_REVISION,
    detect_thesis_title,
    title_conflicts_with_people,
)


def _pdf(path: Path, rows):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for y, size, text in rows:
        page.insert_text((70, y), text, fontsize=size)
    doc.save(path)
    doc.close()


def test_known_author_name_is_removed_before_title_ranking(tmp_path):
    path = tmp_path / "person-vs-title.pdf"
    _pdf(path, [
        (85, 13, "UNIVERSIDAD NACIONAL DE EJEMPLO"),
        # Large isolated personal name: deliberately stronger typographically.
        (205, 27, "María Elena Zárate"),
        (315, 16, "Circulación del conocimiento y trayectorias doctorales"),
        (346, 16, "en psicología argentina"),
        (430, 12, "Tesis doctoral"),
    ])

    title, source = detect_thesis_title(
        path, path.name, excluded_people=["Zárate, María Elena"]
    )

    assert title == "Circulación del conocimiento y trayectorias doctorales en psicología argentina"
    assert source == "cover_layout"
    assert TITLE_READING_REVISION == "document-title-v2.3"


def test_separate_jury_label_and_name_are_negative_title_evidence(tmp_path):
    path = tmp_path / "jury-name.pdf"
    _pdf(path, [
        (80, 13, "UNIVERSIDAD NACIONAL DE EJEMPLO"),
        (190, 12, "Jurado evaluador"),
        (220, 26, "Elena Zárate"),
        (330, 16, "Memoria colectiva y formación doctoral"),
        (360, 16, "en universidades públicas"),
        (440, 12, "Tesis de doctorado"),
    ])

    title, source = detect_thesis_title(path, path.name)

    assert title == "Memoria colectiva y formación doctoral en universidades públicas"
    assert title != "Elena Zárate"
    assert source == "cover_layout"


def test_name_comparison_is_exactish_not_substring_based():
    assert title_conflicts_with_people("Dra. María Andrea Piñeda", ["Piñeda, María Andrea"])
    assert title_conflicts_with_people("Juan Pérez", ["Pérez, Juan"])
    assert not title_conflicts_with_people(
        "La recepción de Sigmund Freud en la psicología argentina",
        ["Sigmund Freud"],
    )
