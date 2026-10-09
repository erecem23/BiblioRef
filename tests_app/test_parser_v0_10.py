# -*- coding: utf-8 -*-
"""v0.10: journal issue without a volume, and imprint after place and country."""
import hashlib
import json
from pathlib import Path

from biblioref.parsing.v10 import PARSER_SCHEMA_VERSION, PARSER_STATUS, PARSER_VERSION, parse_reference
from biblioref.parsing.v09 import parse_reference as parse_v09

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "biblioref/parsing/v10.py"
PARSER_V09 = ROOT / "biblioref/parsing/v09.py"
DEV = ROOT / "reports" / "parser" / "PARSER_V0_10_DEVELOPMENT_EVALUATION.json"
SWEEP = ROOT / "reports" / "parser" / "PARSER_V0_10_HISTORICAL_SWEEP.json"
TARGET = ROOT / "reports" / "parser" / "PARSER_V0_10_TARGET_EVALUATION.json"

PARSER_SHA = "56993eed5a0c032e9c52495eb721a2cc8ecde73ca3ad0cefd9d1fb0d152d17f2"
PARSER_V09_SHA = "4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320"


def test_version_and_status():
    assert PARSER_VERSION == "biblioref-parser-v0.10"
    assert PARSER_SCHEMA_VERSION == 10
    assert PARSER_STATUS == "development_candidate"


# --------------------------------------------------------------------------
# Journal issue without a volume
# --------------------------------------------------------------------------

def test_issue_without_volume_recovers_the_journal():
    p = parse_reference(
        "Aparici, R., y Silva, M. (2012). Pedagogía de la interactividad. "
        "Comunicar, (38), 51-58."
    )
    assert p["journal"] == "Comunicar"
    assert p["publication_type"] == "articulo_revista"


def test_internal_full_stop_in_the_journal_name_is_preserved():
    p = parse_reference(
        "Adell, J. (1997). Tendencias en educación en la sociedad de las tecnologías "
        "de la información. Edutec. Revista electrónica de tecnología educativa, (7), 1-21."
    )
    assert p["journal"] == "Edutec. Revista electrónica de tecnología educativa"


def test_volume_between_name_and_issue_is_trimmed():
    p = parse_reference(
        "Bermejo, V. (2005). Microgénesis y cambio cognitivo. Psicothema, 17, (1), 39-45."
    )
    assert p["journal"] == "Psicothema"


def test_journal_name_misread_as_publisher_is_corrected():
    p = parse_reference(
        "López-Cerezo, J. (1999). Los estudios de ciencia, tecnología y sociedad. "
        "Revista Iberoamericana de Educación, (20), 217-225."
    )
    assert p["journal"] == "Revista Iberoamericana de Educación"
    assert not p["publisher"]


def test_parenthesised_year_is_never_read_as_an_issue():
    text = ("Ministerio de Educación. (2016). Informe anual. Quito, Ecuador: "
            "Ministerio de Educación.")
    assert parse_reference(text)["journal"] is None


def test_issue_route_abstains_on_chapters_and_theses():
    chapter = parse_reference(
        "Acevedo, J. (2009). Cambiando la práctica docente. En M. Gordillo (Coord.), "
        "Educación, ciencia y sociedad (pp. 35-40), (9), 12-20. Madrid: OEI."
    )
    assert not chapter["journal"]
    thesis = parse_reference(
        "Muñoz, L. (2012). Las construcciones de autoridad en el aula "
        "[Tesis de maestría], (3), 10-20. Universidad Nacional de Colombia."
    )
    assert not thesis["journal"]


def test_existing_journals_are_never_rewritten():
    text = ("Alegría, J. (2006). Por un enfoque psicolingüístico del aprendizaje de la "
            "lectura. Infancia y Aprendizaje, 29(1), 93-111.")
    assert parse_reference(text)["journal"] == parse_v09(text)["journal"]


# --------------------------------------------------------------------------
# Imprint after place and country
# --------------------------------------------------------------------------

def test_imprint_after_country_is_recovered_without_a_lexicon_hit():
    for text, imprint in (
        ("Arias, M. (2010). Radiografía del Chile Digital 2.0. Santiago de Chile, Chile: Divergente.", "Divergente"),
        ("Andréu, J. (2000). Las técnicas de análisis de contenido. Andalucía, España: Centro de Estudios Andaluces.", "Centro de Estudios Andaluces"),
        ("Álvarez, F. (2016). Universidad emblemática. Azogues, Ecuador: UNAE.", "UNAE"),
        ("Serra, C. (2014). Leyendo historietas. Buenos Aires, Argentina: Eterna Cadencia Editora.", "Eterna Cadencia Editora"),
    ):
        p = parse_reference(text)
        assert p["publisher_observed"] == imprint, text


def test_page_number_glued_at_the_end_does_not_block_the_imprint():
    """The running page number that the extractor leaves attached must not hide
    the imprint from the closing-country route."""
    text = ("Arias, M. (2010). Radiografía del Chile Digital 2.0. "
            "Santiago de Chile, Chile: Divergente. [273]")
    assert parse_reference(text)["publisher_observed"] == "Divergente"


def test_imprint_route_needs_a_country_not_just_a_place():
    """Without a country before the colon the route abstains and v0.9 stands."""
    text = "Autor, A. (2010). Un título cualquiera. Rosario: Imprenta Local."
    assert parse_reference(text)["publisher"] == parse_v09(text)["publisher"]


def test_existing_publishers_are_kept():
    for text in (
        "Acaso, M., y Manzanera, P. (2015). Esto no es una clase. Barcelona: Ariel.",
        "Area, M. (2004). Los medios y las tecnologías en la educación. Madrid, España: Pirámide.",
    ):
        assert parse_reference(text)["publisher"] == parse_v09(text)["publisher"]


def test_imprint_route_does_not_touch_journal_articles():
    text = ("Aguaded, J. (2013). El programa Media. Comunicar, 20(40), 127-135. "
            "Huelva, España: Grupo Comunicar.")
    p = parse_reference(text)
    assert p["publication_type"] == "articulo_revista"
    assert not p["publisher"]


# --------------------------------------------------------------------------
# Contract and frozen evidence
# --------------------------------------------------------------------------

def test_v10_falls_back_to_v09_when_no_route_applies():
    text = "Texto sin estructura bibliográfica reconocible."
    a, b = parse_v09(text), parse_reference(text)
    for field in ("author", "authors", "year", "title", "journal", "publisher", "doi"):
        assert a.get(field) == b.get(field)


def test_source_freeze():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == PARSER_SHA
    assert hashlib.sha256(PARSER_V09.read_bytes()).hexdigest() == PARSER_V09_SHA


def test_development_corpus_is_untouched():
    d = json.loads(DEV.read_text(encoding="utf-8"))
    assert d["n"] == 190
    assert d["parser_v10_sha256"] == PARSER_SHA
    for field, counts in d["paired"].items():
        assert counts["improved"] == 0, field
        assert counts["regressed"] == 0, field


def test_historical_sweep_only_adds_journals():
    d = json.loads(SWEEP.read_text(encoding="utf-8"))
    assert d["parser_v10_sha256"] == PARSER_SHA
    assert d["n_rows"] == 29027
    assert d["journal_delta"]["removed"] == 0
    assert d["journal_delta"]["modified"] == 0
    assert d["journal_delta"]["added"] == 165
    assert d["labelled_journal_moves"]["worse"] == 0
    assert d["pct_rows_changed"] < 1.0


def test_target_corpus_numbers():
    d = json.loads(TARGET.read_text(encoding="utf-8"))
    assert d["parser_v10_sha256"] == PARSER_SHA
    assert d["n"] == 310
    assert d["journal"]["v09"] == 103 and d["journal"]["v10"] == 142
    assert d["journal"]["rewritten"] == 0
    assert d["sin_clasificar"]["v09"] == 42 and d["sin_clasificar"]["v10"] == 8
    # every publisher rewrite must clear a journal-name fragment
    for row in d["publisher_rewrites"]:
        assert row["v10_publisher"] in (None, "")
        assert row["v10_journal"]


def test_parser_remains_downstream_of_extraction_pipeline():
    source = (ROOT / "biblioref/pipeline.py").read_text(encoding="utf-8")
    assert "biblioref.parsing" not in source
    v10 = PARSER.read_text(encoding="utf-8")
    for forbidden in ("pymupdf", "fitz", "biblioref.pipeline", "biblioref.extraction",
                      "biblioref.detection", "biblioref.adaptive"):
        assert forbidden not in v10
