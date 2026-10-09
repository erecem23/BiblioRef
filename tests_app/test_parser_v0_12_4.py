# -*- coding: utf-8 -*-
"""Synthetic regression fixtures for parser v0.12.4 author handling.

These cases reproduce structural author patterns only; no real thesis
bibliography is stored in the repository.
"""
from biblioref.parsing.v12_4 import PARSER_VERSION, parse_reference


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.4"


def test_hyphenated_surname_linebreak_space_is_normalized():
    p = parse_reference(
        "López, A., Esteller- Carceller, M., & Duran- Aniotz, C. (2021). "
        "Título de prueba. Revista de Ejemplo, 4(2), 10-20."
    )
    assert "Esteller-Carceller, M." in p["authors"]
    assert "Duran-Aniotz, C." in p["authors"]
    assert "Esteller- Carceller" not in p["authors"]


def test_two_corporate_authors_joined_by_y_are_split():
    p = parse_reference(
        "Consejo Internacional de Ciencias Médicas y Organización Regional de la Salud. "
        "(2017). Pautas éticas internacionales. Ginebra: Consejo Internacional."
    )
    assert p["authors"] == (
        "Consejo Internacional de Ciencias Médicas | Organización Regional de la Salud"
    )
    assert p["author_list_status"] == "complete"


def test_internal_y_in_ministry_name_is_not_split():
    p = parse_reference(
        "Ministerio de Economía, Fomento y Turismo. (2020). Estrategia nacional. "
        "https://example.org/estrategia.pdf"
    )
    assert p["authors"] == "Ministerio de Economía, Fomento y Turismo"


def test_surname_particle_and_lowercase_initial_survive():
    p = parse_reference(
        "González, F., del Carmen Calle-Dávila, M., & Paramo, M. d. (2011). "
        "Título de prueba. Revista de Ejemplo, 2(1), 1-8."
    )
    assert "del Carmen Calle-Dávila, M." in p["authors"]
    assert "Paramo, M. d." in p["authors"]


def test_spanish_y_between_personal_authors_is_supported():
    p = parse_reference(
        "Rossi, U., Martínez, L. y Buckley, M. (2020). Título. Revista, 3(1), 1-5."
    )
    assert p["authors"] == "Rossi, U. | Martínez, L. | Buckley, M."


def test_explicit_apa_ellipsis_is_not_presented_as_complete_author_list():
    p = parse_reference(
        "Escobar, M., Panesso, C., Chalco, E., Cardemil, A., Grez, A., Del Río, P., "
        "... & Duran-Aniotz, C. (2023). Título. Revista, 2(1), 1-9."
    )
    assert p["author_list_status"] == "explicit_ellipsis"
    assert p["needs_review"] is True
    assert "author_list_truncated" in p["review_reasons"]
    assert p["authors"].endswith("Duran-Aniotz, C.")


def test_et_al_is_audited_as_source_truncation():
    p = parse_reference(
        "García, M., et al. (2022). Título de ejemplo. Revista, 5(2), 20-30."
    )
    assert p["author_list_status"] == "et_al"
    assert p["needs_review"] is True
    assert "author_list_truncated" in p["review_reasons"]


def test_person_plus_corporate_coauthor_keeps_both_when_explicit():
    p = parse_reference(
        "García, M., & Organización Mundial de Ejemplo. (2022). Informe breve. "
        "Ginebra: Organización Mundial de Ejemplo."
    )
    assert p["authors"] == "García, M. | Organización Mundial de Ejemplo"


def test_corporate_subdivision_with_comma_remains_one_author():
    p = parse_reference(
        "Ministerio de Educación, Centro de Estudios. (2021). Evidencias educativas. "
        "https://example.org/evidencias.pdf"
    )
    assert p["authors"] == "Ministerio de Educación, Centro de Estudios"


def test_complete_single_author_is_not_sent_to_review():
    p = parse_reference("Vasilachis de Gialdino, I. (2006). Estrategias cualitativas. Editorial Ejemplo.")
    assert p["author"] == "Vasilachis de Gialdino, I."
    assert p["author_list_status"] == "complete"
    assert "author_list_truncated" not in p["review_reasons"]
