# -*- coding: utf-8 -*-
"""Query hygiene v0.1.

What is repaired here belongs to the PDF extraction, not to the reference: a
search API cannot see through a soft hyphen or a word split across a line break,
and a human reader can. The repair happens on the way out to a backend and never
touches the parsed record.
"""
from biblioref.resolver.models import ResolverQuery
from biblioref.resolver.normalize import clean_query_text, strip_reference_noise


def test_soft_hyphen_and_zero_width_characters_disappear():
    assert clean_query_text("neuro­protectin") == "neuroprotectin"
    assert clean_query_text("theory​ of‌ mind") == "theory of mind"


def test_typographic_dashes_become_plain_hyphens():
    assert clean_query_text("DHA‐derived") == "DHA-derived"
    assert clean_query_text("1990–2000") == "1990-2000"


def test_the_exotic_dash_that_broke_crossref_becomes_ascii():
    """The real failing case: an U+2010 HYPHEN the backend could not match."""
    got = clean_query_text(
        "Neuroprotectin D1 (NPD1): a DHA ‐ derived mediator that protects brain and retina"
    )
    assert "‐" not in got
    assert got.endswith("a DHA - derived mediator that protects brain and retina")


def test_a_dash_used_as_a_field_separator_keeps_its_spaces():
    """Gluing these would destroy the token boundaries a search needs."""
    got = clean_query_text(
        "Alvarez, Juan Luis – 2003 – Cómo hacer investigación cualitativa – Paidós"
    )
    assert got == "Alvarez, Juan Luis - 2003 - Cómo hacer investigación cualitativa - Paidós"


def test_a_word_split_at_a_line_break_is_rejoined():
    assert clean_query_text("more differen- tiated") == "more differentiated"
    assert clean_query_text("socio- sexual orientations") == "sociosexual orientations"


def test_a_real_compound_survives():
    assert clean_query_text("meta-analysis of self-report measures") == "meta-analysis of self-report measures"


def test_a_split_hyphenated_name_keeps_its_hyphen():
    """The continuation is capitalised, so the hyphen belongs to the name."""
    assert clean_query_text("Baron- Cohen, S.") == "Baron-Cohen, S."
    assert clean_query_text("Merleau- Ponty") == "Merleau-Ponty"


def test_curly_quotes_become_straight():
    got = clean_query_text("Is there a ‘‘language of the eyes’’?")
    assert got == "Is there a ''language of the eyes''?"
    assert clean_query_text("“Reading the Mind in the Eyes”") == '"Reading the Mind in the Eyes"'


def test_ligatures_are_expanded():
    assert clean_query_text("identiﬁcation of inﬂuence") == "identification of influence"


def test_access_trails_are_dropped_from_a_reference_query():
    raw = "Bedoya, J. (2022). Impacto Post Covid-19. Revista X, 4(2). Recuperado de https://ejemplo.org/a/b"
    got = strip_reference_noise(raw)
    assert got.endswith("Revista X, 4(2)")
    assert "http" not in got


def test_index_badges_are_dropped():
    raw = "Smith, J. (2019). A study. Journal of X, 12(3), 44-60. [ Links ]"
    assert strip_reference_noise(raw) == "Smith, J. (2019). A study. Journal of X, 12(3), 44-60"


def test_a_reference_without_noise_is_left_alone():
    raw = "Smith, J. (2019). A study. Journal of X, 12(3), 44-60"
    assert strip_reference_noise(raw) == raw


def test_acceso_inside_a_title_is_not_an_access_trail():
    """Real case: cutting at the bare word ate two thirds of the reference."""
    raw = ("Álvarez, Gladys Stella, La Mediación y el Acceso a Justicia, "
           "Rubinzal - Culzoni Editores, Santa Fe, Abril de 2003")
    assert strip_reference_noise(raw) == raw


def test_a_strip_that_would_eat_the_reference_is_refused():
    raw = "Disponible en el catálogo"
    assert strip_reference_noise(raw) == raw


def test_a_long_reference_still_loses_its_access_trail():
    raw = ("Bedoya, J. S. F., Zumba, B. L. G., & Preciado, A. M. S. (2022). Impacto Post Covid-19 "
           "en la Calidad de Vida del Adulto Mayor. Revista X, 4(2), 10-25. "
           "Disponible en https://ejemplo.org/articulo/12345")
    got = strip_reference_noise(raw)
    assert got.endswith("Revista X, 4(2), 10-25")
    assert "http" not in got


def test_hygiene_reaches_the_query_a_backend_receives():
    query = ResolverQuery.from_parser(
        "Bazan, N. G. (2005). Neuroprotectin D1 (NPD1): a DHA ‐ derived mediator. "
        "J Lipid Res. Recuperado de http://ejemplo.org",
        {
            "title": "Neuroprotectin D1 (NPD1): a DHA ‐ derived mediator",
            "authors": "Bazan, N. G.",
            "year": "2005",
            "journal": "Journal of Lipid ‐ Research",
        },
    )
    assert "‐" not in query.title
    assert "‐" not in query.raw_reference
    assert "http" not in query.raw_reference
    assert query.journal == "Journal of Lipid - Research"


def test_hygiene_does_not_rewrite_the_parsed_record():
    parsed = {"title": "a DHA ‐ derived mediator", "year": "2005"}
    before = dict(parsed)
    ResolverQuery.from_parser("cruda", parsed)
    assert parsed == before


def test_hygiene_is_idempotent():
    once = clean_query_text("more differen- tiated ‘quote’")
    assert clean_query_text(once) == once
