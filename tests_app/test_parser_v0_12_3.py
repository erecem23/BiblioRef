# -*- coding: utf-8 -*-
"""Synthetic regression fixtures for parser v0.12.3.

The records reproduce generic bibliography shapes exposed during field
validation.  No real thesis reference is stored here.
"""
from biblioref.parsing.v12_3 import PARSER_SCHEMA_VERSION, PARSER_VERSION, parse_reference


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.3"
    assert PARSER_SCHEMA_VERSION == 12


def test_article_volume_issue_without_pages_keeps_full_title_and_journal():
    p = parse_reference(
        "Rojas, A. (2023). Trauma y bienestar después de una crisis. "
        "Una experiencia de intervención escolar. Journal of Example Education, 4(1)."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["title"] == "Trauma y bienestar después de una crisis. Una experiencia de intervención escolar"
    assert p["journal"] == "Journal of Example Education"


def test_book_multisentence_title_before_place_country_imprint_is_preserved():
    p = parse_reference(
        "Chávez, P., & Vera, A. (2017). Ser joven en el país de hoy. "
        "La perspectiva de sus protagonistas y sus familias. Santiago, Chile: Ceibo."
    )
    assert p["publication_type"] == "libro"
    assert p["title"] == "Ser joven en el país de hoy. La perspectiva de sus protagonistas y sus familias"
    assert p["publisher"] == "Ceibo"


def test_book_multisentence_title_before_simple_place_imprint_is_preserved():
    p = parse_reference(
        "Hinton, D., & Good, B. (2015). Culture and distress. "
        "Trauma in global and historical perspective. Pennsylvania: University Example Press."
    )
    assert p["publication_type"] == "libro"
    assert p["title"] == "Culture and distress. Trauma in global and historical perspective"


def test_institutional_pdf_report_beats_generic_web_access_type():
    p = parse_reference(
        "Ministerio de Educación. (2021). Evidencias sobre aprendizaje en pandemia. "
        "Disponible en https://example.gov/files/evidencias_2021.pdf"
    )
    assert p["publication_type"] == "informe_documento"
    assert "material_web" in p["type_candidates"]
    assert "informe_documento" in p["type_candidates"]


def test_guideline_pdf_beats_generic_web_access_type():
    p = parse_reference(
        "Consejo Internacional de Salud. (2017). Pautas éticas internacionales para investigación. "
        "Retrieved Julio 2022, from Consejo Internacional de Salud: https://example.org/pautas.pdf"
    )
    assert p["publication_type"] == "documento_guia_manual"


def test_repository_url_is_thesis_candidate_not_forced_reclassification():
    p = parse_reference(
        "Pérez, A. (2013). Autoestima y salud mental en estudiantes. Retrieved Junio 2022, "
        "from Universidad Ejemplo: https://repositorio.example.edu/handle/20.500/1234"
    )
    assert p["publication_type"] == "material_web"
    assert "tesis" in p["type_candidates"]
    assert p["needs_review"] is True
    assert "possible_repository_thesis" in p["review_reasons"]


def test_extraido_de_form_recovers_title_when_source_repeats_author():
    p = parse_reference(
        "Datos Chile. (2004). Datos Chile. Extraído de Nivel socioeconómico de los hogares, "
        "Datos Chile: http://example.org/mapa.pdf"
    )
    assert p["publication_type"] == "material_web"
    assert p["title"] == "Nivel socioeconómico de los hogares"
    assert "Datos Chile" in p["title_candidates"]


def test_conference_locator_number_is_removed_from_title():
    p = parse_reference(
        "Torres, F., & Herrera, V. (2017). IX Congreso Internacional de Psicología. "
        "Profesionales de salud mental y representaciones sobre su práctica, 267. Buenos Aires."
    )
    assert p["publication_type"] == "conference_paper"
    assert p["title"].endswith("representaciones sobre su práctica")
    assert not p["title"].endswith("267")


def test_web_source_equal_to_author_is_not_kept_as_publisher():
    p = parse_reference(
        "UNICEF. (2020). UNICEF. Retrieved Julio 2022, from ¿Qué es la adolescencia?: "
        "https://example.org/que-es-la-adolescencia"
    )
    assert p["publication_type"] == "material_web"
    assert p["title"] == "¿Qué es la adolescencia?"
    assert p["publisher"] is None


def test_report_trailing_institution_expands_weak_publisher_fragment():
    p = parse_reference(
        "Báez, A., & Costa, C. (2020). Salud y economía para el desarrollo sostenible. "
        "CEPAL, OPS. Comisión Económica para América Latina (CEPAL), "
        "Organización Panamericana de la Salud (OPS)."
    )
    assert p["publication_type"] == "informe_documento"
    assert "Organización Panamericana de la Salud" in (p["publisher"] or "")


def test_manual_like_serial_container_is_flagged_instead_of_silently_retyped():
    p = parse_reference(
        "Pérez, S., & Soto, M. (2002). El concepto de adolescencia. "
        "Manual de prácticas clínicas para la atención integral, 2(3), 15-23."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["needs_review"] is True
    assert "serial_container_monograph_like" in p["review_reasons"]
    assert "capitulo_libro/documento_guia_manual" in p["type_candidates"]


def test_normal_article_is_not_sent_to_review_by_new_field_rules():
    p = parse_reference(
        "Ramos, I., & Méndez, L. (2014). Prácticas de salud mental comunitaria. "
        "Revista de Terapia Psicológica, 32(2), 133-142."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Revista de Terapia Psicológica"
    assert "serial_container_monograph_like" not in p["review_reasons"]
