from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.metadata.cover_v04 import COVER_METADATA_VERSION, detect_cover_metadata


def _unc_like_pdf(path: Path) -> None:
    doc = fitz.open()
    # A sparse first page, like a repository/institutional cover.
    p0 = doc.new_page(width=595, height=842)
    p0.insert_text((70, 120), "FACULTAD DE PSICOLOGÍA", fontsize=14)
    p0.insert_text((70, 165), "Aportes a la explicación de la violencia sexual", fontsize=18)
    p0.insert_text((70, 195), "un contraste empírico del Modelo de Confluencia", fontsize=18)

    # Actual thesis title/front-matter page. Inline role labels are deliberate:
    # v0.3 only handled some label-only forms and page-1 affiliation/author.
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((70, 80), "Universidad Nacional de Córdoba", fontsize=15)
    p1.insert_text((70, 108), "Facultad de Psicología", fontsize=14)
    p1.insert_text((70, 250), "Doctorando: Lic. Jorge Ángel Bruera", fontsize=13)
    p1.insert_text((70, 286), "Directora: Dra. Karin Arbach", fontsize=13)
    p1.insert_text((70, 322), "Codirectora: Dra. Antonella Bobbio", fontsize=13)
    p1.insert_text((70, 390), "Doctorado en Psicología", fontsize=13)
    p1.insert_text((70, 710), "Córdoba, 2025", fontsize=12)
    doc.save(path)
    doc.close()


def test_v04_reads_inline_roles_and_later_title_page(tmp_path):
    path = tmp_path / "bruera-like.pdf"
    _unc_like_pdf(path)
    detected = detect_cover_metadata(path, path.name)
    meta = detected["metadata"]

    assert detected["version"] == COVER_METADATA_VERSION == "cover-metadata-v0.4"
    assert meta["author"] == "Jorge Ángel Bruera"
    assert meta["director"] == "Karin Arbach"
    assert meta["codirector"] == "Antonella Bobbio"
    assert meta["university"] == "Universidad Nacional de Córdoba"
    assert meta["faculty"] == "Facultad de Psicología"
    assert meta["institution"] == "Universidad Nacional de Córdoba"
    assert meta["year"] == "2025"
    assert meta["degree_level"] == "doctorado"


def test_v04_uses_pdf_author_only_as_fallback(tmp_path):
    path = tmp_path / "metadata-author.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((80, 250), "Una tesis con autor en metadatos PDF", fontsize=18)
    meta = doc.metadata
    meta["author"] = "Jorge Ángel Bruera"
    doc.set_metadata(meta)
    doc.save(path)
    doc.close()

    detected = detect_cover_metadata(path, path.name)
    assert detected["metadata"]["author"] == "Jorge Ángel Bruera"
    assert detected["sources"]["author"] == "pdf_metadata"
