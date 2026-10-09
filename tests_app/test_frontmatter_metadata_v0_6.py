"""Año de la tesis: la portada manda sobre una fecha narrada en una nota al pie.

Caso externo: la portada dice «Año 2025» y una página de dedicatoria trae la
nota «1 Violeta Parra … nacida el 4 de octubre de 1917». La nota sumaba el
bono de mes y el de pie de página y le ganaba a la portada. Una etiqueta
explícita («Año», «Fecha», «Year») es la señal más fuerte; una nota al pie
(numeral inicial, cuerpo menor que el de la página) nunca fecha la tesis.
"""
from pathlib import Path

from biblioref.metadata.cover_v05 import detect_cover_metadata
from tests_support.pdf_factory import write_pdf


def _pdf(path: Path, pages) -> None:
    write_pdf(path, [[(text, x, y, size) for x, y, size, text in rows] for rows in pages])


COVER = [
    (70, 90, 13, "UNIVERSIDAD NACIONAL DE LA PLATA"),
    (70, 110, 13, "FACULTAD DE PSICOLOGÍA"),
    (70, 260, 16, "Transiciones en la clínica: diálogos conceptuales"),
    (70, 400, 12, "Tesis de Doctorado en Psicología"),
    (70, 460, 12, "Doctoranda: Lic. Ana Pérez"),
]

DEDICATION_WITH_FOOTNOTE = [
    (200, 300, 12, "A mi familia, y a la memoria de quien cantaba1"),
    (200, 330, 12, "gracias a la vida que me ha dado tanto"),
    (70, 760, 10, "1 Una cantante y compositora chilena nacida el 4 de octubre de 1917 en San Carlos, Ñuble."),
]


def test_labelled_cover_year_beats_a_dated_footnote(tmp_path):
    path = tmp_path / "cover.pdf"
    _pdf(path, [COVER + [(70, 700, 12, "Año 2025")], DEDICATION_WITH_FOOTNOTE])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2025"


def test_an_unlabelled_bare_cover_year_still_beats_the_footnote(tmp_path):
    path = tmp_path / "bare.pdf"
    _pdf(path, [COVER + [(70, 700, 12, "La Plata, 2025")], DEDICATION_WITH_FOOTNOTE])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2025"


def test_cover_date_with_month_is_still_read(tmp_path):
    path = tmp_path / "month.pdf"
    _pdf(path, [COVER + [(70, 700, 12, "La Plata, marzo de 2019")]])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2019"


def test_a_cover_date_that_opens_with_the_day_is_not_a_footnote(tmp_path):
    path = tmp_path / "day.pdf"
    _pdf(path, [[
        (70, 90, 16, "UNIVERSIDAD NACIONAL DE LA PLATA"),
        (70, 260, 18, "Transiciones en la clínica"),
        (70, 400, 16, "Tesis de Doctorado en Psicología"),
        (70, 680, 14, "10 DE NOVIEMBRE DE 2014"),
    ]])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2014"


def test_the_word_year_inside_a_title_is_not_a_label(tmp_path):
    path = tmp_path / "title.pdf"
    _pdf(path, [[
        (70, 90, 13, "UNIVERSIDAD NACIONAL DE CÓRDOBA"),
        (70, 300, 18, "El suicidio en la ciudad conforme a los"),
        (70, 322, 18, "registros del año 2007 al 2012: aplicación del modelo a"),
        (70, 344, 18, "los casos de la justicia provincial"),
        (70, 740, 11, "Córdoba, 2017"),
    ]])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2017"
