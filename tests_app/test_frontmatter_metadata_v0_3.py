from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.document_title_v22 import TITLE_READING_REVISION, detect_thesis_title
from biblioref.metadata.cover_v03 import COVER_METADATA_VERSION, detect_cover_metadata


def _frontmatter_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rows = [
        (85, 14, "UNIVERSIDAD NACIONAL DE CÓRDOBA"),
        (112, 13, "FACULTAD DE PSICOLOGÍA"),
        (235, 16, "Trayectorias académicas y circulación del conocimiento"),
        (264, 16, "en la formación doctoral argentina"),
        # Deliberately larger than the title: this was the observed false positive.
        (355, 20, "Tribunal evaluador: Elena Zárate"),
        (438, 12, "Director:"),
        (462, 13, "Dr. Hugo Klappenbach"),
        (490, 12, "Codirectora:"),
        (514, 13, "Dra. María Andrea Piñeda"),
        (690, 12, "Córdoba, septiembre 2026"),
    ]
    for y, size, text in rows:
        page.insert_text((70, y), text, fontsize=size)
    doc.save(path)
    doc.close()


def test_tribunal_evaluador_cannot_win_as_thesis_title(tmp_path):
    path = tmp_path / "tribunal-title.pdf"
    _frontmatter_pdf(path)
    title, source = detect_thesis_title(path, path.name)
    assert title == "Trayectorias académicas y circulación del conocimiento en la formación doctoral argentina"
    assert "tribunal" not in title.casefold()
    assert source == "cover_layout"
    assert TITLE_READING_REVISION == "document-title-v2.2"


def test_cover_metadata_captures_director_codirector_and_institution(tmp_path):
    path = tmp_path / "frontmatter.pdf"
    _frontmatter_pdf(path)
    detected = detect_cover_metadata(path, path.name)
    meta = detected["metadata"]
    assert detected["version"] == COVER_METADATA_VERSION == "cover-metadata-v0.3"
    assert meta["director"] == "Hugo Klappenbach"
    assert meta["codirector"] == "María Andrea Piñeda"
    assert meta["university"] == "Universidad Nacional de Córdoba"
    assert meta["institution"] == meta["university"]
    assert detected["confidence"]["director"] >= 0.95
    assert detected["confidence"]["codirector"] >= 0.95
