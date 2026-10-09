import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v08 import PARSER_STATUS, PARSER_VERSION, parse_reference
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "parser_baseline" / "holdout_v07" / "PARSER_V07_EXTERNAL_GOLD_FROZEN.csv"


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
    assert PARSER_VERSION == "biblioref-parser-v0.8"
    assert PARSER_STATUS == "development_candidate"


def test_editor_prefix_does_not_consume_educacao():
    p = parse_reference("ADORNO, Theodor. Educação e emancipação. Rio de Janeiro: Paz e Terra, 1995.")
    assert p["title"] == "Educação e emancipação"
    assert _norm(p["author"]) == _norm("ADORNO, Theodor")


def test_degree_descriptors_are_not_part_of_thesis_title():
    p = parse_reference(
        "AMÂNCIO, Nivânia. O novo ensino médio e a BNCC. "
        "Tese (Doutorado em Educação) – Programa de Pós-Graduação em Educação, "
        "Universidade Federal do Ceará, Fortaleza, 2022."
    )
    assert p["publication_type"] == "tesis"
    assert p["title"] == "O novo ensino médio e a BNCC"
    assert p["publisher"] == "Universidade Federal do Ceará"


def test_question_mark_before_in_is_chapter_boundary():
    p = parse_reference(
        "AGAMBEN, Giorgio. O que é um dispositivo? In: AGAMBEN, Giorgio. "
        "O que é o contemporâneo? E outros ensaios. Chapecó: Argos, 2009."
    )
    assert p["publication_type"] == "capitulo_libro"
    assert p["title"] == "O que é um dispositivo?"
    assert p["publisher"] == "Argos"


def test_journal_cleanup_removes_city_placeholder_and_platform_annotation():
    a = parse_reference(
        "ALEXANDRE, Ana; MARTINS, Marialda. A vivência do pai em relação ao trabalho de parto e parto. "
        "Cogitare Enfermagem, Curitiba, v.14, n.2, 2009."
    )
    b = parse_reference(
        "ALVES, Yamê; COUTO, Leila. A amamentação sob a égide de redes de apoio. "
        "Escola Anna Nery, [S.l.], v. 24, n.1, 2020."
    )
    c = parse_reference(
        "ARAÚJO, Júnior; Maciel Filho. Developing an operational framework for health policy analysis. "
        "Rev. bras. Saúde matern. infant [Scielo-Scientific Electronic Library Online]. V.1(3):203-21, 2001."
    )
    assert a["journal"] == "Cogitare Enfermagem"
    assert b["journal"] == "Escola Anna Nery"
    assert c["journal"] == "Rev. bras. Saúde matern. infant"


def test_portuguese_e_author_separator_and_allcaps_given_names():
    a = parse_reference(
        "ARRAIS, Ana L. e VIEIRA-SANTOS, Salomé. Envolvimento paterno em pais de crianças em idade escolar. "
        "Psic.: Teor. e Pesq., Brasília, vol. 37. 2021."
    )
    b = parse_reference(
        "BATISTA, PAULO CESAR. A onda conservadora, uma ameaça à democracia? "
        "Sociedade e Estado, 35 (03) 997-1003, 2020. Recuperado de <https://periodicos.unb.br/x>"
    )
    assert _norm(a["author"]) == _norm("ARRAIS, Ana L.")
    assert "VIEIRA-SANTOS" in (a["authors"] or "")
    assert a["journal"] == "Psic.: Teor. e Pesq"
    assert _norm(b["author"]) == _norm("BATISTA, PAULO CESAR")
    assert b["title"] == "A onda conservadora, uma ameaça à democracia?"
    assert b["journal"] == "Sociedade e Estado"


def test_repeated_year_in_interview_title_does_not_win_publication_year():
    p = parse_reference(
        "ARANTES, Apollo. Paternidades trans em diálogo [maio de 2023]. Entrevistador Benedito Medrado. "
        "Recife: Núcleo Feminista de Pesquisas em Gênero e Masculinidades, 2023. "
        "Disponível em: https://www.youtube.com/watch?v=x"
    )
    assert p["year"] == "2023"
    assert p["title"] == "Paternidades trans em diálogo"
    assert p["publication_type"] == "recurso_web"
    assert p["publisher"] == "Núcleo Feminista de Pesquisas em Gênero e Masculinidades"


def test_publisher_cleanup_handles_edition_state_and_comma_place():
    a = parse_reference("ÁVILA, Fernando Bastos de. Solidarismo. Rio de Janeiro: Agir, 3ª ed, 1965.")
    b = parse_reference("BERGER, Peter. O Dossel Sagrado. 4. ed. São Paulo, Paulus, 2003.")
    c = parse_reference(
        "BOFF, Leonardo. Jesus Cristo libertador. Ensaio de cristologia crítica para o nosso tempo. "
        "3ª ed. Petrópolis: RJ. Vozes, 1972."
    )
    assert a["publisher"] == "Agir"
    assert b["publisher"] == "Paulus"
    assert c["publisher"] == "Vozes"


def test_conservative_institutional_web_no_year():
    p = parse_reference(
        "ASSOCIAÇÃO DO VOLUNTARIADO E DA SOLIDARIEDADE. Quem somos. "
        "http://www.avesol.org.br/quem-somo."
    )
    assert p["parse_style"] == "institutional_web_no_year"
    assert p["author"] == "ASSOCIAÇÃO DO VOLUNTARIADO E DA SOLIDARIEDADE"
    assert p["title"] == "Quem somos"
    assert p["publication_type"] == "recurso_web"


def test_v07_external_holdout_is_v08_development_regression():
    rows = list(csv.DictReader(private_data(DEV).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 30
    hits = {"author": 0, "year": 0, "title": 0, "type": 0, "journal": 0, "publisher": 0}
    jn = pn = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        hits["author"] += _norm(p.get("author")) == _norm(row["gold_author"])
        hits["year"] += str(p.get("year") or "") == row["gold_year"]
        hits["title"] += _fuzzy(p.get("title"), row["gold_title"]) >= .90
        hits["type"] += p.get("publication_type") == row["gold_publication_type"]
        if row["gold_journal"]:
            jn += 1
            hits["journal"] += _fuzzy(p.get("journal"), row["gold_journal"]) >= .90
        if row["gold_publisher"]:
            pn += 1
            hits["publisher"] += _norm(p.get("publisher")) == _norm(row["gold_publisher"])
    assert hits["author"] == 30
    assert hits["year"] == 30
    assert hits["title"] == 30
    assert hits["type"] == 30
    assert hits["journal"] == jn
    assert hits["publisher"] == pn
