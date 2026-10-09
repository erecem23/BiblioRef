import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v04 import parse_reference as parse_v04
from biblioref.parsing.v05 import PARSER_STATUS, PARSER_VERSION, parse_reference
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_V04 = ROOT / "parser_baseline" / "holdout_v04" / "PARSER_V04_EXTERNAL_GOLD_FROZEN.csv"


def _norm(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).casefold().replace("&", " and ")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fuzzy(a, b):
    a, b = _norm(a), _norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _abnt_rows():
    rows = list(csv.DictReader(private_data(HOLDOUT_V04).open(encoding="utf-8-sig", newline="")))
    return [r for r in rows if r["thesis_id"] == "USP_PIZZIMENTI_2024"]


def test_version_and_status():
    assert PARSER_VERSION == "biblioref-parser-v0.5"
    assert PARSER_STATUS == "development_candidate"


def test_abnt_book_place_publisher_year():
    p = parse_reference("ALBERTI, S. Crepúsculo da alma. Rio de Janeiro: Contra Capa Livraria, 2003.")
    assert p["parse_style"] == "abnt_author_title_year_end"
    assert p["author"] == "ALBERTI, S."
    assert p["year"] == "2003"
    assert p["title"] == "Crepúsculo da alma"
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "Contra Capa Livraria"


def test_abnt_article_with_city_volume_issue():
    p = parse_reference("ASKOFARÉ, S. Da subjetividade contemporânea. A Peste: Revista de Psicanálise e Sociedade e Filosofia, São Paulo, v. 1, n. 1, jan.-jun. 2009.")
    assert p["title"] == "Da subjetividade contemporânea"
    assert p["journal"] == "A Peste: Revista de Psicanálise e Sociedade e Filosofia"
    assert p["publication_type"] == "articulo_revista"


def test_abnt_chapter_in_container_and_publisher():
    p = parse_reference("ASSOUN, P. L. O sujeito da Psicanálise. In. A Lei, as leis. (Org. Sonia Altoé). Rio de Janeiro: Revinter, 1990.")
    assert p["author"] == "ASSOUN, P. L."
    assert p["title"] == "O sujeito da Psicanálise"
    assert p["publication_type"] == "capitulo_libro"
    assert p["publisher"] == "Revinter"


def test_abnt_access_year_does_not_replace_publication_year():
    p = parse_reference("DELGADO, P. G. Reforma psiquiátrica: estratégias para resistir ao desmonte. Trabalho, Educação e Saúde, v. 17, n. 2, 2022. Disponível em: https://www.tes.epsjv.fiocruz.br/index.php/tes/article/view/856. Acesso em: 26 jan. 2023.")
    assert p["year"] == "2022"
    assert p["title"] == "Reforma psiquiátrica: estratégias para resistir ao desmonte"
    assert p["journal"] == "Trabalho, Educação e Saúde"
    assert p["publication_type"] == "articulo_revista"


def test_abnt_observed_and_canonical_publisher_are_distinct():
    p = parse_reference("CABAS, A. O sujeito da Psicanálise de Freud a Lacan: da questão do sujeito ao sujeito em questão. Rio de Janeiro: Jorge Zahar Ed., 2010")
    assert p["publisher"] == "Jorge Zahar"
    assert p["publisher_observed"] == "Jorge Zahar Ed."


def test_v04_abnt_rows_are_v05_development_regression():
    rows = _abnt_rows()
    assert len(rows) == 10
    hits = {"author": 0, "year": 0, "title": 0, "type": 0, "journal": 0, "publisher": 0, "publisher_observed": 0}
    jn = pn = pon = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        hits["author"] += _norm(p.get("author")) == _norm(row["gold_author"])
        hits["year"] += str(p.get("year") or "") == row["gold_year"]
        hits["title"] += _fuzzy(p.get("title"), row["gold_title"]) >= .98
        hits["type"] += p.get("publication_type") == row["gold_publication_type"]
        if row["gold_journal"]:
            jn += 1
            hits["journal"] += _fuzzy(p.get("journal"), row["gold_journal"]) >= .98
        if row["gold_publisher"]:
            pn += 1
            hits["publisher"] += _norm(p.get("publisher")) == _norm(row["gold_publisher"])
        if row["gold_publisher_observed"]:
            pon += 1
            hits["publisher_observed"] += _norm(p.get("publisher_observed")) == _norm(row["gold_publisher_observed"])
    assert hits["author"] == 10
    assert hits["year"] == 10
    assert hits["title"] == 10
    assert hits["type"] == 10
    assert jn == 2 and hits["journal"] == 2
    assert pn == 8 and hits["publisher"] == 8
    assert pon == 8 and hits["publisher_observed"] == 8


def test_non_abnt_v04_holdout_rows_are_field_identical_except_version_metadata():
    rows = list(csv.DictReader(private_data(HOLDOUT_V04).open(encoding="utf-8-sig", newline="")))[:20]
    fields = ["parse_style", "author", "authors", "year", "publication_type", "title", "journal", "publisher", "publisher_observed", "source_publisher", "doi"]
    for row in rows:
        old, new = parse_v04(row["raw_citation"]), parse_reference(row["raw_citation"])
        for field in fields:
            assert new.get(field) == old.get(field), (field, row["raw_citation"], old.get(field), new.get(field))


def test_uppercase_author_with_parenthesized_year_stays_v04_route():
    raw = "SMITH, J. (2020). A conventional parenthetical reference. Journal of Testing, 10(2), 1-9."
    old, new = parse_v04(raw), parse_reference(raw)
    assert new["parse_style"] == old["parse_style"]
    assert new["title"] == old["title"]
