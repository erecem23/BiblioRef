import tempfile
from pathlib import Path

from tests_support import pdf_factory as fitz

from biblioref.document_title import detect_thesis_title


def _pdf(lines, metadata_title=None):
    return _pdf_pages([lines], metadata_title)


def _pdf_pages(pages, metadata_title=None):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page(width=595, height=842)
        for text, x, y, size in lines:
            page.insert_text((x, y), text, fontsize=size)
    if metadata_title is not None:
        meta = doc.metadata
        meta["title"] = metadata_title
        doc.set_metadata(meta)
    data = doc.tobytes()
    doc.close()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


def test_multiline_title_reconstructs_even_when_individual_lines_are_short():
    path = _pdf([
        ("UNIVERSIDAD NACIONAL DE EJEMPLO", 110, 90, 18),
        ("Psicología y", 190, 260, 20),
        ("ciencia abierta", 175, 290, 20),
        ("en Argentina", 190, 320, 20),
        ("Tesis doctoral", 230, 390, 12),
    ])
    try:
        assert detect_thesis_title(path, "archivo_123.pdf") == (
            "Psicología y ciencia abierta en Argentina", "cover_layout"
        )
    finally:
        path.unlink(missing_ok=True)


def test_large_university_header_does_not_beat_smaller_real_title():
    path = _pdf([
        ("UNIVERSIDAD NACIONAL DE CÓRDOBA", 95, 80, 24),
        ("FACULTAD DE PSICOLOGÍA", 145, 115, 19),
        ("Trayectorias doctorales y circulación del conocimiento", 70, 290, 17),
        ("Una aproximación bibliométrica", 145, 320, 17),
        ("Presentada por Chris Moreno", 180, 420, 12),
    ])
    try:
        assert detect_thesis_title(path, "tesis.pdf") == (
            "Trayectorias doctorales y circulación del conocimiento Una aproximación bibliométrica",
            "cover_layout",
        )
    finally:
        path.unlink(missing_ok=True)


def test_garbage_pdf_metadata_is_rejected_in_favour_of_cover():
    path = _pdf([
        ("Bibliografías doctorales y culturas de citación", 85, 270, 19),
        ("en psicología argentina", 165, 300, 19),
    ], metadata_title="Microsoft Word - tesis_final_2026.docx")
    try:
        assert detect_thesis_title(path, "tesis_final.pdf") == (
            "Bibliografías doctorales y culturas de citación en psicología argentina",
            "cover_layout",
        )
    finally:
        path.unlink(missing_ok=True)


def test_good_metadata_can_win_when_cover_has_no_text_title():
    path = _pdf([
        ("Tesis doctoral", 220, 300, 12),
        ("Universidad Nacional de Ejemplo", 170, 350, 12),
    ], metadata_title="Redes de colaboración científica en la formación doctoral")
    try:
        assert detect_thesis_title(path, "scan_0042.pdf") == (
            "Redes de colaboración científica en la formación doctoral", "pdf_metadata"
        )
    finally:
        path.unlink(missing_ok=True)


def test_filename_is_last_resort_for_administrative_cover_and_bad_metadata():
    path = _pdf([
        ("UNIVERSIDAD NACIONAL DE EJEMPLO", 100, 100, 18),
        ("TESIS DOCTORAL", 210, 260, 16),
        ("Presentada por Juan Pérez", 180, 350, 12),
    ], metadata_title="Untitled Document")
    try:
        assert detect_thesis_title(path, "mi_tesis_2026.pdf") == ("mi tesis 2026", "filename")
    finally:
        path.unlink(missing_ok=True)


def test_institutional_word_inside_real_title_is_not_treated_as_header():
    path = _pdf([
        ("Procesos de institucionalización y memoria colectiva", 80, 270, 18),
        ("en comunidades universitarias", 145, 300, 18),
        ("Tesis doctoral", 230, 390, 12),
    ])
    try:
        assert detect_thesis_title(path, "documento.pdf") == (
            "Procesos de institucionalización y memoria colectiva en comunidades universitarias",
            "cover_layout",
        )
    finally:
        path.unlink(missing_ok=True)


def test_clean_metadata_wins_when_fragmented_historical_cover_corroborates_it():
    path = _pdf([
        ("SIGNIFICACION", 130, 100, 34),
        ("ANTROPOLOGICA", 105, 165, 36),
        ("SILENCIO", 240, 225, 34),
        ("del", 205, 225, 25),
        ("MARIA ANTONIA SELL SALUDES", 160, 310, 12),
        ("Tesis de Doctorado", 220, 430, 11),
    ], metadata_title="Significación antropológica del silencio")
    try:
        assert detect_thesis_title(path, "scan_historico.pdf") == (
            "Significación antropológica del silencio", "pdf_metadata"
        )
    finally:
        path.unlink(missing_ok=True)


def test_repository_coversheet_is_skipped_before_actual_title_page():
    path = _pdf_pages([
        [
            ("A Thesis Submitted for the Degree of PhD at the University of Example", 80, 180, 12),
            ("Permanent WRAP URL:", 80, 220, 12),
            ("http://repository.example/item/123", 80, 245, 12),
            ("Copyright and reuse:", 80, 330, 12),
            ("Please scroll down to view the document itself.", 80, 370, 12),
            ("Please refer to the repository record for this item for information to help you to cite it.", 50, 410, 10),
        ],
        [
            ("Experiences of Domestic Violence and Body Dissatisfaction: Women from the", 55, 190, 15),
            ("South Asian Diaspora", 205, 220, 15),
            ("Pria Sandhu", 245, 330, 12),
            ("A thesis submitted in partial fulfilment of the requirements for the degree of", 70, 430, 11),
            ("Doctor of Clinical Psychology", 190, 455, 11),
        ],
    ], metadata_title="WRAP_Coversheet_Theses_new")
    try:
        assert detect_thesis_title(path, "repository_download.pdf") == (
            "Experiences of Domestic Violence and Body Dissatisfaction: Women from the South Asian Diaspora",
            "cover_layout",
        )
    finally:
        path.unlink(missing_ok=True)
