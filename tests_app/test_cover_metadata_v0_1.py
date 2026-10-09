from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.metadata import COVER_METADATA_VERSION, detect_cover_metadata


def _write_cover(path: Path, lines):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for y, text, size in lines:
        page.insert_text((70, y), text, fontsize=size)
    doc.save(path)
    doc.close()


def test_master_cover_keeps_real_title_separate_from_degree_statement(tmp_path):
    path = tmp_path / "master.pdf"
    _write_cover(path, [
        (100, "UNIVERSIDAD NACIONAL DEL SUR", 14),
        (125, "FACULTAD DE CIENCIAS SOCIALES", 14),
        (275, "TESIS DE MAESTRÍA", 14),
        (305, "Prácticas colectivas, educación y subjetividad:", 14),
        (330, "una experiencia comunitaria en organizaciones sociales", 14),
        (415, "Para obtener el título de", 12),
        (438, "Magister en Psicología Comunitaria", 14),
        (520, "Presenta:", 12),
        (544, "Lic. Camila Cabrera", 14),
        (570, "Directora", 12),
        (594, "Dra. Ana Fernández", 14),
        (715, "Mayo 2015", 12),
    ])
    got = detect_cover_metadata(path, path.name)
    assert got["version"] == COVER_METADATA_VERSION
    assert got["title"] == "Prácticas colectivas, educación y subjetividad: una experiencia comunitaria en organizaciones sociales"
    assert "Para obtener" not in got["title"]
    assert got["metadata"]["author"] == "Camila Cabrera"
    assert got["metadata"]["year"] == "2015"
    assert got["metadata"]["university"] == "Universidad Nacional del Sur"
    assert got["metadata"]["faculty"] == "Facultad de Ciencias Sociales"
    assert got["metadata"]["program"] == "Magister en Psicología Comunitaria"


def test_minimal_cover_recovers_unlabelled_author_and_month_year(tmp_path):
    path = tmp_path / "minimal.pdf"
    _write_cover(path, [
        (300, "Aportes críticos al estudio de la salud mental:", 12),
        (328, "experiencias juveniles durante una crisis social", 12),
        (435, "Maximiliano Andrés Pérez Lorenzo", 12),
        (545, "Profesora guía Dra. María Sol Gómez", 12),
        (680, "Santiago, octubre de 2024", 12),
    ])
    got = detect_cover_metadata(path, path.name)
    assert got["title"] == "Aportes críticos al estudio de la salud mental: experiencias juveniles durante una crisis social"
    assert got["metadata"]["author"] == "Maximiliano Andrés Pérez Lorenzo"
    assert got["metadata"]["year"] == "2024"
    assert "university" not in got["metadata"]


def test_degree_phrase_alone_is_never_title(tmp_path):
    path = tmp_path / "roles.pdf"
    _write_cover(path, [
        (300, "Para obtener el título de", 14),
        (330, "Magister en Psicología Social", 16),
        (500, "Presenta:", 12),
        (525, "Lucía Martínez", 14),
        (700, "Junio 2020", 12),
    ])
    got = detect_cover_metadata(path, path.name)
    assert got["title_source"] == "filename"
    assert got["title"] == "roles"
    assert got["metadata"]["author"] == "Lucía Martínez"
    assert got["metadata"]["year"] == "2020"


def test_advisor_is_not_mistaken_for_author_when_explicit_author_label_exists(tmp_path):
    path = tmp_path / "advisor.pdf"
    _write_cover(path, [
        (250, "Memoria, trabajo y participación comunitaria", 14),
        (480, "Autora:", 12),
        (505, "Lic. Julia Torres", 14),
        (535, "Directora", 12),
        (560, "Dra. Laura Sánchez", 14),
        (700, "Marzo 2019", 12),
    ])
    got = detect_cover_metadata(path, path.name)
    assert got["metadata"]["author"] == "Julia Torres"


def test_pdf_metadata_is_only_fallback_when_cover_has_no_title_candidate(tmp_path):
    path = tmp_path / "meta.pdf"
    doc = fitz.open()
    doc.set_metadata({"title": "Dinámicas sociales y participación en contextos educativos"})
    page = doc.new_page()
    page.insert_text((70, 700), "Abril 2018", fontsize=10)
    doc.save(path)
    doc.close()
    got = detect_cover_metadata(path, path.name)
    assert got["title"] == "Dinámicas sociales y participación en contextos educativos"
    assert got["title_source"] == "pdf_metadata"
