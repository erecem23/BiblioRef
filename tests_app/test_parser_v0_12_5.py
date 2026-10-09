from biblioref.parsing.v12_5 import PARSER_VERSION, parse_reference


def test_legacy_serial_number_is_article_and_recovers_journal():
    p = parse_reference(
        "Pérez, A. (2008). Un estudio comunitario. Revista de Estudios Sociales, N° 12, Universidad X."
    )
    assert p["parser_version"] == PARSER_VERSION == "biblioref-parser-v0.12.5"
    assert p["publication_type"] == "articulo_revista"
    assert p["title"] == "Un estudio comunitario"
    assert p["journal"] == "Revista de Estudios Sociales"


def test_legacy_serial_tomo_theme_does_not_put_theme_in_journal():
    p = parse_reference(
        "García, M. (2005). Subjetividad y trabajo. Revista de Psicología, “Debates contemporáneos”, Tomo XXVIII, N° 1."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Revista de Psicología"


def test_explicit_multiword_serial_name_is_preserved():
    p = parse_reference(
        "López, C. (2014). Implicaciones metodológicas. Sujeto, Subjetividad y Cultura, Número 8, Universidad X."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Sujeto, Subjetividad y Cultura"


def test_url_only_unresolved_item_becomes_web_not_book():
    p = parse_reference(
        "Ruiz, P. (2004). Documento de trabajo sin datos editoriales. Disponible en: http://example.org/doc.pdf"
    )
    assert p["publication_type"] == "material_web"
    assert "document_type_unresolved" not in str(p.get("review_reasons") or "")


def test_edition_plus_imprint_recovers_book():
    p = parse_reference(
        "Álvarez, J. (2010). Historia de una experiencia colectiva. (2ª ed.) Buenos Aires: Editorial Ejemplo."
    )
    assert p["publication_type"] == "libro"
    assert p["title"] == "Historia de una experiencia colectiva"
    assert p["publisher"] == "Editorial Ejemplo"


def test_hyphenated_same_year_suffix_is_parsed_and_author_status_is_complete():
    p = parse_reference(
        "Fernández, A. (2008-a). Experiencias educativas. Revista de Educación, Año 20, N° 209."
    )
    assert p["year"] == "2008"
    assert p["publication_type"] == "articulo_revista"
    assert p["author_list_status"] == "complete"


def test_chapter_with_cuadernos_in_book_title_is_not_stolen_without_serial_metadata():
    p = parse_reference(
        "Martínez, L. (2004). Educación popular. En Pérez, R. (Comp.). Cuadernos de educación popular. Buenos Aires: Editorial Sur."
    )
    assert p["publication_type"] != "articulo_revista"
