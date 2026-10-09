# -*- coding: utf-8 -*-
"""Synthetic regression fixtures for parser v0.12.1.

These records reproduce structural patterns found during field validation; no
real thesis bibliography is stored in the repository.
"""
from biblioref.parsing.v12_1 import (
    PARSER_SCHEMA_VERSION,
    PARSER_VERSION,
    flatten_parsed,
    parse_reference,
)


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.1"
    assert PARSER_SCHEMA_VERSION == 12


def test_multiple_years_keep_publication_year_and_audit_candidates():
    p = parse_reference(
        "Rivas, C. (2021, Mayo 06). Portal Universitario. Retrieved Mayo 2022, "
        "from Nota interdisciplinaria: https://example.org/archivo/1978.pdf"
    )
    assert p["year"] == "2021"
    assert p["needs_review"] is True
    assert "multiple_year_mentions" in p["review_reasons"]
    assert "2021 [publication]" in p["year_candidates"]
    assert "2022 [access]" in p["year_candidates"]
    assert "1978 [url]" in p["year_candidates"]


def test_lowercase_surname_particle_and_initial_are_preserved():
    p = parse_reference(
        "González, F., del Carmen Calle-Dávila, M., & Rubio, M. (2021). "
        "Respuesta con enfoque de derechos. Revista Panamericana de Salud Pública, 45."
    )
    assert "del Carmen Calle-Dávila, M." in p["authors"]

    q = parse_reference(
        "Paramo, M. d. (2011). Factores de riesgo y protección. "
        "Revista de Terapia Psicológica, 29(1), 85-95."
    )
    assert q["author"] == "Paramo, M. d."


def test_corporate_author_with_y_is_not_split_as_personal_authors():
    p = parse_reference(
        "Ministerio de Economía, Fomento y Turismo. (2020). Estrategia gradual Paso a Paso. "
        "Extraído el 19-10-2024 desde https://example.org/estrategia.pdf"
    )
    assert p["author"] == "Ministerio de Economía, Fomento y Turismo"


def test_article_sp_keeps_full_title_and_journal():
    p = parse_reference(
        "Acevedo, R., Miranda, G., & Jiménez, A. (2012). "
        "Experiencias del desasosiego. Salud mental y malestar en Chile. "
        "Revista Anales, 7(3), s.p."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["title"] == "Experiencias del desasosiego. Salud mental y malestar en Chile"
    assert p["journal"] == "Revista Anales"


def test_article_with_trailing_url_is_not_web_material():
    p = parse_reference(
        "Fernández, R., & Manrique, F. (2010). Rol de la enfermería en el apoyo social. "
        "Enfermería Global, 19. Pp. 1-9. https://example.org/articulo"
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Enfermería Global"


def test_colon_pages_article_and_journal_abbreviation():
    p = parse_reference(
        "González, Q., & Restrepo, C. (2010). Prevalencia de felicidad y redes de apoyo. "
        "Rev Salud Pública, 12(2): 228-238. https://example.org/rsap"
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Rev Salud Pública"


def test_in_serial_no_only_is_article_not_chapter():
    p = parse_reference(
        "Retamal, C. M. (2020, October). Salud mental en situación de confinamiento. "
        "In Anales de la Universidad de Chile (No. 17, pp. 303-318)."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Anales de la Universidad de Chile"


def test_thesis_type_survives_retrieved_url_pattern():
    p = parse_reference(
        "Castañeda, A. (2013). Autoestima, claridad de autoconcepto y salud mental. "
        "Tesis de Maestría. Retrieved Junio 2022, from Universidad Ejemplo: "
        "https://example.org/tesis"
    )
    assert p["publication_type"] == "tesis"


def test_psykhe_style_metadata_is_article():
    p = parse_reference(
        "Mendive, S. (2004). Entrevista al Dr. Juan Marconi, creador de la psiquiatría comunitaria. "
        "PSYKHE 2004, Vol. 13, N°2, 187-199."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "PSYKHE"


def test_conference_venue_is_not_used_as_contribution_title():
    p = parse_reference(
        "Bazzano, M. (2011). IX Jornadas de Sociología. Servicios públicos de salud mental: "
        "representaciones sobre el abordaje y el acceso. Buenos Aires."
    )
    assert p["publication_type"] == "conference_paper"
    assert p["title"].startswith("Servicios públicos de salud mental")


def test_institutional_report_is_report_not_book():
    p = parse_reference(
        "Organización Mundial de la Salud. (2020). Estadísticas Sanitarias Mundiales 2020. "
        "Monitoreando la salud para los ODS, objetivos de desarrollo sostenible. "
        "Organización Mundial de la Salud."
    )
    assert p["publication_type"] == "informe_documento"


def test_closing_full_organization_publisher_beats_lexical_fragment():
    p = parse_reference(
        "Organización Panamericana de la Salud. (2009). Epidemiología de los trastornos mentales. "
        "Washington, D.C: Organización Panamericana de la Salud."
    )
    assert p["publisher"] == "Organización Panamericana de la Salud"


def test_acronym_publisher_is_recovered():
    p = parse_reference(
        "García, A. (2024). El malestar emocional infanto-juvenil tras la pandemia. "
        "ACCI (Asociación Cultural y Científica Iberoamericana)."
    )
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "ACCI"


def test_flatten_keeps_legacy_csv_shape_without_audit_extras():
    p = parse_reference("Autor, A. (2020). Título. Revista de Ejemplo, 2(1), 1-5.")
    flat = flatten_parsed(p)
    assert "parsed_parser_version" in flat
    assert "parsed_needs_review" not in flat
    assert p["parser_version"] == "biblioref-parser-v0.12.1"
