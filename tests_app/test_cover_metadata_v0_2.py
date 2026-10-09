from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.metadata import COVER_METADATA_VERSION, detect_cover_metadata
from biblioref.metadata.integration import _apply_cover_metadata


def _make_pdf(path: Path, lines, *, metadata_title: str = "") -> None:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for y, size, text in lines:
        page.insert_text((72, y), text, fontsize=size)
    if metadata_title:
        doc.set_metadata({"title": metadata_title})
    doc.save(path)
    doc.close()


def _master_cover(path: Path) -> None:
    _make_pdf(path, [
        (90, 14, "UNIVERSIDAD NACIONAL DEL CENTRO"),
        (115, 14, "FACULTAD DE CIENCIAS SOCIALES"),
        (220, 14, "TESIS DE MAESTRÍA"),
        (260, 14, "Redes comunitarias y bienestar:"),
        (285, 14, "un estudio longitudinal en barrios urbanos"),
        (350, 12, "Para obtener el título de"),
        (375, 14, "Magister en Psicología Comunitaria"),
        (460, 12, "Presenta:"),
        (485, 14, "Lic. Julia Pérez"),
        (525, 12, "Directora"),
        (550, 14, "Dra. Marta López"),
        (680, 12, "Buenos Aires."),
        (705, 12, "Mayo 2018."),
    ])


def test_master_cover_anchor_excludes_degree_statement(tmp_path):
    path = tmp_path / "master.pdf"
    _master_cover(path)
    result = detect_cover_metadata(path)
    assert result["version"] == COVER_METADATA_VERSION == "cover-metadata-v0.5.2"
    assert result["title"] == "Redes comunitarias y bienestar: un estudio longitudinal en barrios urbanos"
    assert "Para obtener" not in result["title"]
    assert result["title_source"] == "cover_anchor"
    assert result["metadata"]["author"] == "Julia Pérez"
    assert result["metadata"]["year"] == "2018"
    assert result["metadata"]["university"] == "Universidad Nacional del Centro"
    assert result["metadata"]["faculty"] == "Facultad de Ciencias Sociales"
    assert result["metadata"]["program"] == "Magister en Psicología Comunitaria"
    assert result["metadata"]["degree_level"] == "maestria"
    assert result["needs_review"] is False


def test_generic_cover_does_not_treat_advisor_as_author(tmp_path):
    path = tmp_path / "doctorado.pdf"
    _make_pdf(path, [
        (250, 14, "Procesos de aprendizaje y memoria en adultos"),
        (400, 14, "Carlos Méndez"),
        (510, 12, "Profesor guía"),
        (535, 14, "Dr. Pablo Ruiz"),
        (680, 12, "Santiago, octubre de 2022"),
    ])
    result = detect_cover_metadata(path)
    assert result["title"] == "Procesos de aprendizaje y memoria en adultos"
    assert result["metadata"]["author"] == "Carlos Méndez"
    assert result["metadata"]["year"] == "2022"
    assert "university" not in result["metadata"]


def test_plural_advisor_label_is_a_boundary(tmp_path):
    path = tmp_path / "plural.pdf"
    _make_pdf(path, [
        (220, 14, "Narrativas juveniles y salud comunitaria"),
        (390, 14, "Lucía Pérez Gómez"),
        (500, 12, "Profesoras Guías"),
        (525, 14, "Dra. Paula Ruiz"),
        (690, 12, "Octubre 2024"),
    ])
    result = detect_cover_metadata(path)
    assert result["metadata"]["author"] == "Lucía Pérez Gómez"
    assert result["needs_review"] is False


def test_pdf_metadata_garbage_is_not_used_as_title(tmp_path):
    path = tmp_path / "tesis_final.pdf"
    _make_pdf(path, [(700, 12, "Mayo 2020")], metadata_title="Microsoft Word - tesis_final.docx")
    result = detect_cover_metadata(path)
    assert result["title_source"] == "filename"
    assert "Microsoft Word" not in result["title"]


def test_degree_statement_can_never_be_title(tmp_path):
    path = tmp_path / "degree.pdf"
    _make_pdf(path, [
        (200, 14, "TESIS DE MAESTRÍA"),
        (280, 14, "Ciudadanía digital y prácticas educativas"),
        (360, 14, "Para obtener el título de Magister en Educación"),
        (470, 12, "Presenta:"),
        (495, 14, "Ana Torres"),
        (700, 12, "Junio 2020"),
    ])
    result = detect_cover_metadata(path)
    assert result["title"] == "Ciudadanía digital y prácticas educativas"


def test_prior_auto_values_refresh_on_revision(tmp_path):
    path = tmp_path / "migration.pdf"
    _master_cover(path)
    doc = {
        "path": str(path),
        "filename": path.name,
        "title": "Para obtener el título de Magister en Educación",
        "title_source": "cover_layout",
        "title_confirmed": False,
        "metadata": {"author": "Autora automática vieja", "year": "2017"},
        "metadata_detection": {
            "version": "cover-metadata-v0.1",
            "suggestions": {"author": "Autora automática vieja", "year": "2017"},
        },
    }
    assert _apply_cover_metadata(None, doc) is True
    assert doc["title"] == "Redes comunitarias y bienestar: un estudio longitudinal en barrios urbanos"
    assert doc["metadata"]["author"] == "Julia Pérez"
    assert doc["metadata"]["year"] == "2018"
    assert doc["metadata"]["degree_level"] == "maestria"
    assert doc["cover_metadata_revision"] == COVER_METADATA_VERSION


def test_human_values_are_preserved_during_revision(tmp_path):
    path = tmp_path / "human.pdf"
    _master_cover(path)
    doc = {
        "path": str(path),
        "filename": path.name,
        "title": "Título confirmado por usuario",
        "title_source": "human",
        "title_confirmed": True,
        "metadata": {"author": "Autora verificada", "year": "2014"},
        "metadata_detection": {
            "version": "cover-metadata-v0.1",
            "suggestions": {"author": "Autora automática vieja", "year": "2017"},
        },
    }
    _apply_cover_metadata(None, doc)
    assert doc["title"] == "Título confirmado por usuario"
    assert doc["metadata"]["author"] == "Autora verificada"
    assert doc["metadata"]["year"] == "2014"
    assert doc["metadata"]["university"] == "Universidad Nacional del Centro"
    assert doc["metadata_detection"]["needs_review"] is False
