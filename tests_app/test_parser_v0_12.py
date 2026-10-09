# -*- coding: utf-8 -*-
"""v0.12: robust APA-like parsing plus explicit ambiguity/audit metadata.

All fixtures are synthetic.  They reproduce field shapes observed during
external validation without storing thesis references or PDFs.
"""
from biblioref.parsing.v12 import (
    PARSER_SCHEMA_VERSION,
    PARSER_VERSION,
    flatten_parsed,
    parse_reference,
)


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12"
    assert PARSER_SCHEMA_VERSION == 12


def test_primary_parenthetical_year_beats_access_and_url_years_but_keeps_candidates():
    raw = (
        "Rivas, C. (2021, Mayo 06). Portal Universitario. Retrieved Mayo 2022, "
        "from Informe interdisciplinario sobre salud: "
        "https://example.org/noticias/2021/declaracion-1978.pdf"
    )
    p = parse_reference(raw)
    assert p["year"] == "2021"
    assert p["needs_review"] is True
    assert "multiple_year_mentions" in p["review_reasons"]
    assert "2021 [publication" in p["year_candidates"]
    assert "2022 [access]" in p["year_candidates"]
    assert "1978 [url]" in p["year_candidates"]


def test_complete_apa_author_block_is_recovered_before_title():
    raw = (
        "Torres, J., Pérez, L., & Soto, M. (2005, Octubre). "
        "Research update on adolescent wellbeing. "
        "Journal of Example Studies, 44 (10), 972-986."
    )
    p = parse_reference(raw)
    assert p["author"] == "Torres, J."
    assert p["authors"] == "Torres, J. | Pérez, L. | Soto, M."
    assert p["publication_type"] == "articulo_revista"
    assert p["title"] == "Research update on adolescent wellbeing"
    assert p["journal"] == "Journal of Example Studies"


def test_full_revista_de_prefix_stays_in_journal_not_title():
    raw = (
        "Ramos, I., Ramírez, C., & Méndez, L. (2014). "
        "Representaciones clínicas y prácticas de salud mental. "
        "Revista de Terapia Psicológica, 32 (2), 133-142."
    )
    p = parse_reference(raw)
    assert p["title"] == "Representaciones clínicas y prácticas de salud mental"
    assert p["journal"] == "Revista de Terapia Psicológica"
    assert p["publication_type"] == "articulo_revista"


def test_issue_only_journal_shape_recovers_article_and_removes_lexical_publisher():
    raw = (
        "Cardenal, M., & Marco, A. (2020). Los cuidados profesionales en los problemas "
        "de conducta adolescente. RECIEN: Revista Científica de Enfermería (19), 40-57."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "RECIEN: Revista Científica de Enfermería"
    assert p["publisher"] is None


def test_journal_name_cannot_be_reduced_to_publisher_token():
    raw = (
        "Molina, A., & Zeta, B. (2005). Plan nacional de salud mental: diez años de experiencia. "
        "Revista Panamericana de Salud Pública, 346-358."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Revista Panamericana de Salud Pública"
    assert p["publisher"] is None


def test_internal_title_periods_do_not_break_last_title_journal_boundary():
    raw = (
        "Ocampo, R. C. (2014). Psicologización de la vida. Lectura crítica del curso. "
        "Reading of a theoretical course. Logos: Anales del Seminario de Metafísica, 47, 55."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "articulo_revista"
    assert p["title"].endswith("Reading of a theoretical course")
    assert p["journal"] == "Logos: Anales del Seminario de Metafísica"


def test_book_chapter_with_in_and_pages_is_not_book():
    raw = (
        "Barrera, P. (1990). La juventud no es una sola palabra. "
        "In P. Barrera, Sociología y Cultura (pp. 119-127). México: Grijalbo."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "capitulo_libro"
    assert p["title"] == "La juventud no es una sola palabra"
    assert p["publisher"] == "Grijalbo"


def test_spanish_en_chapter_with_editorial_recovers_publisher():
    raw = (
        "Ocampo, A. (2021). Clínica y ciudadanía. Los desafíos de la interculturalidad crítica. "
        "En C. Rojas, A. Ocampo, & E. Núñez, Repensar la salud colectiva (pp. 81-107). "
        "Santiago: Editorial Contracorriente."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "capitulo_libro"
    assert p["title"] == "Clínica y ciudadanía. Los desafíos de la interculturalidad crítica"
    assert p["publisher"] == "Editorial Contracorriente"


def test_in_journal_vol_no_pp_shape_is_article_not_chapter():
    raw = (
        "Gálvez, A., Pérez, B., & Ríos, C. (2021, November). Salud juvenil durante la pandemia. "
        "In Anales de Pediatría (Vol. 95, No. 5, pp. 354-363). Elsevier Example."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Anales de Pediatría"
    assert p["title"] == "Salud juvenil durante la pandemia"


def test_short_uppercase_terminal_publisher_rescues_book():
    raw = (
        "Cerda, M. C. (2006). Metodologías de la investigación social. "
        "Introducción a los oficios. LOM."
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "LOM"
    assert p["title"] == "Metodologías de la investigación social. Introducción a los oficios"


def test_web_title_source_ambiguity_is_visible_to_human_review():
    raw = (
        "UNICEF. (2020). UNICEF. Retrieved Julio 2022, from ¿Qué es la adolescencia?: "
        "https://example.org/que-es-la-adolescencia"
    )
    p = parse_reference(raw)
    assert p["publication_type"] == "material_web"
    assert p["title"] == "¿Qué es la adolescencia?"
    assert p["needs_review"] is True
    assert "web_title_source_ambiguous" in p["review_reasons"]
    assert "UNICEF" in p["title_candidates"]
    assert "¿Qué es la adolescencia?" in p["title_candidates"]


def test_flatten_exposes_review_columns():
    p = parse_reference(
        "Rivas, C. (2021). Portal. Retrieved Mayo 2022, from Nota extensa para revisar: "
        "https://example.org/nota"
    )
    flat = flatten_parsed(p)
    for key in (
        "parsed_needs_review", "parsed_review_reasons", "parsed_parser_notes",
        "parsed_parser_confidence", "parsed_year_candidates", "parsed_author_candidates",
        "parsed_title_candidates", "parsed_journal_candidates", "parsed_type_candidates",
        "parsed_publisher_candidates",
    ):
        assert key in flat


def test_v11_legacy_year_final_core_fields_are_not_changed():
    raw = "Agulla, Juan Carlos, La Promesa de la Sociología, Editorial de Belgrano, Buenos Aires, 1982"
    from biblioref.parsing.v11 import parse_reference as p11
    a, b = p11(raw), parse_reference(raw)
    for field in ("author", "authors", "year", "publication_type", "title", "journal", "publisher"):
        assert a.get(field) == b.get(field)
