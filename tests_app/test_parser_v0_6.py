import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v05 import parse_reference as parse_v05
from biblioref.parsing.v06 import PARSER_STATUS, PARSER_VERSION, parse_reference
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "parser_baseline" / "holdout_v05" / "PARSER_V05_ABNT_EXTERNAL_GOLD_FROZEN.csv"


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


def test_version_and_status():
    assert PARSER_VERSION == "biblioref-parser-v0.6"
    assert PARSER_STATUS == "development_candidate"


def test_full_given_name_abnt_book():
    p = parse_reference("ADICHIE, Chimamanda Ngozi. Sejamos Todos Feministas. Tradução: Christina Baum. 1a ed. São Paulo, Companhia das Letras, 2015")
    assert p["parse_style"] == "abnt_fullname_year_end"
    assert p["author"] == "ADICHIE, Chimamanda Ngozi"
    assert p["title"] == "Sejamos Todos Feministas"
    assert p["year"] == "2015"
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "Companhia das Letras"


def test_mixed_initials_particle_author():
    p = parse_reference("ALMEIDA, S. L. de. Racismo Estrutural. São Paulo: Editora Jandaíra, 2020.")
    assert p["author"] == "ALMEIDA, S. L. de"
    assert p["title"] == "Racismo Estrutural"
    assert p["publisher"] == "Editora Jandaíra"


def test_in_journal_is_article_not_chapter():
    p = parse_reference("CARRANO, P. Jovens, Escolas e Cidades: desafios à autonomia e à convivência. In: Revista Teias, v.12, n.26, p.7-22, set/dez 2011.")
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Revista Teias"


def test_in_book_container_remains_chapter():
    p = parse_reference("DE FINA, A. Group identity, narrative and self-representations. In: DE FINA, A., SCHIFFRIN, D. e BAMBERG, M. Discourse and Identity. Cambridge: CUP, 2006.")
    assert p["publication_type"] == "capitulo_libro"
    assert p["publisher"] == "CUP"


def test_tese_and_dissertacao_are_theses():
    a = parse_reference("COUTINHO, L.G. Ilusão e errância:adolescência e laço social contemporâneo na interface entre a psicanálise e as ciências sociais. Tese de doutorado em Psicologia. Rio de Janeiro: PUC, 2002.")
    b = parse_reference("BRANCO, R. M. “Lá onde há poder, há resistência”– A resistência no pensamento de Michel Foucault no período de 1975-1976. Dissertação (Mestrado em Filosofia) - Pontifícia Universidade Católica de São Paulo, São Paulo, 2013.")
    assert a["publication_type"] == "tesis"
    assert b["publication_type"] == "tesis"


def test_article_without_strict_volume_issue_triple():
    p = parse_reference("ANZALDÚA, Glória. Falando em línguas: uma carta para as mulheres escritoras do terceiro mundo. Estudos Feministas, Florianópolis: 229-235, 2000.")
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Estudos Feministas"


def test_v05_external_holdout_is_v06_development_regression():
    rows = list(csv.DictReader(private_data(DEV).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 30
    hits = {"author": 0, "year": 0, "title": 0, "type": 0, "journal": 0, "publisher": 0, "publisher_observed": 0}
    jn = pn = pon = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        hits["author"] += _norm(p.get("author")) == _norm(row["gold_author"])
        hits["year"] += str(p.get("year") or "") == row["gold_year"]
        hits["title"] += _fuzzy(p.get("title"), row["gold_title"]) >= .90
        hits["type"] += p.get("publication_type") == row["gold_publication_type"]
        if row["gold_journal"]:
            jn += 1; hits["journal"] += _fuzzy(p.get("journal"), row["gold_journal"]) >= .90
        if row["gold_publisher"]:
            pn += 1; hits["publisher"] += _norm(p.get("publisher")) == _norm(row["gold_publisher"])
        if row["gold_publisher_observed"]:
            pon += 1; hits["publisher_observed"] += _norm(p.get("publisher_observed")) == _norm(row["gold_publisher_observed"])
    assert hits["author"] >= 29
    assert hits["year"] == 30
    assert hits["title"] >= 28
    assert hits["type"] >= 28
    assert jn and hits["journal"] >= jn - 1
    assert pn and hits["publisher"] >= pn - 1
    assert pon and hits["publisher_observed"] >= pon - 1


def test_apa_route_remains_field_identical_to_v05():
    raws = [
        "Smith, J. A. (2020). A conventional article. Journal of Testing, 10(2), 1-9. https://doi.org/10.1234/test",
        "Brown, T. (2019). A book title. London: Example Press.",
    ]
    fields = ["parse_style", "author", "authors", "year", "publication_type", "title", "journal", "publisher", "publisher_observed", "source_publisher", "doi"]
    for raw in raws:
        old, new = parse_v05(raw), parse_reference(raw)
        for f in fields:
            assert new.get(f) == old.get(f), (f, old.get(f), new.get(f))
