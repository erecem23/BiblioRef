# -*- coding: utf-8 -*-
"""Synthetic regression fixtures for parser v0.12.2 year-role auditing."""
from biblioref.parsing.v12_2 import PARSER_SCHEMA_VERSION, PARSER_VERSION, parse_reference


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.2"
    assert PARSER_SCHEMA_VERSION == 12


def test_plain_word_acceso_in_title_does_not_create_access_years():
    p = parse_reference(
        "Barrera, M. (2011). IX Jornadas de Sociología. Servicios públicos de salud mental: "
        "representaciones sobre el abordaje y el acceso a la salud. Ciudad de Buenos Aires "
        "(2005-2010). Buenos Aires."
    )
    assert p["year"] == "2011"
    assert "2011 [publication]" in p["year_candidates"]
    assert "2005 [context]" in p["year_candidates"]
    assert "2010 [context]" in p["year_candidates"]
    assert "multiple_year_mentions" not in p["review_reasons"]


def test_year_range_inside_title_is_evidence_not_automatic_review():
    p = parse_reference(
        "Gálvez, A., Pérez, B., & Ríos, C. (2021, November). Estado de la salud mental "
        "durante la pandemia y en el inicio del curso escolar 2020-2021. "
        "In Anales de Pediatría (Vol. 95, No. 5, pp. 354-363). Elsevier Example."
    )
    assert p["year"] == "2021"
    assert "2021 [publication / title]" in p["year_candidates"]
    assert "2020 [title]" in p["year_candidates"]
    assert "multiple_year_mentions" not in p["review_reasons"]


def test_structured_retrieval_year_remains_reviewable():
    p = parse_reference(
        "Rivas, C. (2021, Mayo 06). Portal Universitario. Retrieved Mayo 2022, "
        "from Nota interdisciplinaria: https://example.org/archivo.pdf"
    )
    assert p["year"] == "2021"
    assert "2021 [publication]" in p["year_candidates"]
    assert "2022 [access]" in p["year_candidates"]
    assert p["needs_review"] is True
    assert "multiple_year_mentions" in p["review_reasons"]


def test_url_year_has_lower_priority_but_is_preserved_for_review():
    p = parse_reference(
        "Pan Example Health Organization. (2012, Octubre 8). Declaración histórica. "
        "Retrieved Abril 2022, from Pan Example Health Organization: "
        "https://example.org/dmdocuments/2012/declaracion-1978.pdf"
    )
    assert p["year"] == "2012"
    assert "2012 [publication / url]" in p["year_candidates"]
    assert "2022 [access]" in p["year_candidates"]
    assert "1978 [url]" in p["year_candidates"]
    assert p["needs_review"] is True


def test_extraido_el_date_is_access_not_title_context():
    p = parse_reference(
        "Ministerio de Ejemplo. (2020). Estrategia gradual. Extraído el 19-10-2024 "
        "desde https://example.org/2020/estrategia.pdf"
    )
    assert p["year"] == "2020"
    assert "2024 [access]" in p["year_candidates"]
    assert p["needs_review"] is True


def test_core_fields_match_v121_when_only_year_audit_changes():
    raw = (
        "Acevedo, R., Miranda, G., & Jiménez, A. (2012). Experiencias del desasosiego. "
        "Salud mental y malestar en Chile. Revista Anales, 7(3), s.p."
    )
    from biblioref.parsing.v12_1 import parse_reference as parse_v121
    a, b = parse_v121(raw), parse_reference(raw)
    for field in ("author", "authors", "year", "publication_type", "title", "journal", "publisher"):
        assert a.get(field) == b.get(field)
