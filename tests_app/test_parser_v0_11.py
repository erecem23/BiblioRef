# -*- coding: utf-8 -*-
"""v0.11: legacy Ibero-American year-final bibliography regime."""
from biblioref.parsing.v11 import PARSER_SCHEMA_VERSION, PARSER_VERSION, parse_reference


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.11"
    assert PARSER_SCHEMA_VERSION == 11


def test_legacy_book_year_final():
    p = parse_reference(" Agulla, Juan Carlos, La Promesa de la Sociología, Editorial de Belgrano, Buenos Aires, 1982")
    assert p["author"] == "Agulla, Juan Carlos"
    assert p["year"] == "1982"
    assert p["title"] == "La Promesa de la Sociología"
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "Editorial de Belgrano"


def test_legacy_journal_year_final():
    p = parse_reference("Alvarez Gendín Blanco, S., El Estado de Derecho y el Poder Judicial Independiente, Revista de Administración Pública, Número 31, página 11, Madrid, España, 1960")
    assert p["author"] == "Alvarez Gendín Blanco, S."
    assert p["year"] == "1960"
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Revista de Administración Pública"


def test_url_is_access_mode_not_automatic_year():
    p = parse_reference("Ábalos, María Gabriela, “El proceso de mejora y autoevaluación en un juzgado de Mendoza”, en línea http://www.gestionjudicial.net/home1.htm; última visita: 10 de Febrero de 2012")
    assert p["author"] == "Ábalos, María Gabriela"
    assert p["title"] == "El proceso de mejora y autoevaluación en un juzgado de Mendoza"
    assert p["year"] is None
    assert p["publication_type"] == "material_web"


def test_tesis_false_positive_from_publisher_is_removed():
    p = parse_reference("Labrada, Pelayo Ariel, La Motivación en los Organismos Judiciales, Editorial Jurídica Nova Tesis, Buenos Aires, 2006")
    assert p["publication_type"] == "libro"


def test_explicit_thesis_remains_thesis():
    p = parse_reference("Palma, Luis María, Justicia y Desarrollo en América Latina, Tesis Doctoral de Ciencia Política, Universidad de Belgrano, Inédita, Buenos Aires, Junio de 2010")
    assert p["publication_type"] == "tesis"


def test_abnt_route_is_not_reinterpreted():
    raw = "ALBERTI, S. Crepúsculo da alma. Rio de Janeiro: Contra Capa Livraria, 2003."
    from biblioref.parsing.v10 import parse_reference as p10
    a, b = p10(raw), parse_reference(raw)
    for field in ("author", "authors", "year", "publication_type", "title", "journal", "publisher"):
        assert a.get(field) == b.get(field)
