import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v06 import parse_reference as parse_v06
from biblioref.parsing.v07 import PARSER_STATUS, PARSER_VERSION, parse_reference
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "parser_baseline" / "holdout_v06" / "PARSER_V06_ABNT_EXTERNAL_GOLD_FROZEN.csv"


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
    assert PARSER_VERSION == "biblioref-parser-v0.7"
    assert PARSER_STATUS == "development_candidate"


def test_first_author_contract_is_restored_for_multi_author_abnt():
    p = parse_reference(
        "ALTET, Marguerite; PAGUAY, Léopold & PERRENOUD, Phelippe. (Orgs.). "
        "A profissionalização dos formadores de professores. Porto Alegre: ARTMED Editora, 2003."
    )
    assert _norm(p["author"]) == _norm("ALTET, Marguerite")
    assert "PAGUAY" in (p["authors"] or "") and "PERRENOUD" in (p["authors"] or "")


def test_disponivel_without_em_cannot_supply_url_path_year():
    p = parse_reference(
        "CARDOSO, Edna Aniceto de Magalhães. Festival Folclórico de Parintins: percepções dos fatores de sucesso. "
        "2019. 284 f. Tese (doutorado em Administração) – Universidade Federal de Minas Gerais. "
        "Disponível: https://repositorio.ufmg.br/bitstream/1843/32454/1/tese.pdf. Acesso em: 31 jan. 2021."
    )
    assert p["year"] == "2019"
    assert p["publication_type"] == "tesis"
    assert p["publisher"] == "Universidade Federal de Minas Gerais"


def test_parenthesized_in_journal_is_clean_article():
    p = parse_reference(
        "BALL, Stephen J. Diretrizes políticas globais e relações políticas locais em educação. "
        "(in) Currículo Sem Fronteiras, v1, nº 2. pp. 99-116, 2001."
    )
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Currículo Sem Fronteiras"


def test_textual_volume_metadata_is_removed_from_journal():
    p = parse_reference(
        "CAZARIN, Ercília Ana. A Análise do Discurso nos estudos da linguagem e sua dimensão política. "
        "Revista da Abralin, v. Eletrônico, n. Especial, p. 33-46, 2011."
    )
    assert p["journal"] == "Revista da Abralin"


def test_compact_initials_and_no_comma_author_variants():
    a = parse_reference("BIANCHETTI, R.G.. Modelo neoliberal e políticas educacionais. 3ª Ed. São Paulo: Cortez, 2000.")
    b = parse_reference("ARISTÓTELES. A Política. São Paulo: Editora Escala, 2008.")
    c = parse_reference("ARENDT. Hannah. Entre o passado e o futuro. São Paulo: Perspectiva, 2009.")
    assert _norm(a["author"]) == _norm("BIANCHETTI, R.G.")
    assert a["title"] == "Modelo neoliberal e políticas educacionais"
    assert _norm(b["author"]) == _norm("ARISTÓTELES") and b["title"] == "A Política"
    assert _norm(c["author"]) == _norm("ARENDT. Hannah") and c["title"] == "Entre o passado e o futuro"


def test_in_book_container_is_chapter_not_article():
    p = parse_reference(
        "ARAGÓN, Virgilio Alvarez; ROCHA, Maria Zélia Borba. A educação superior latino-americana em uma encruzilhada. "
        "(in) SCHMIDT, Benício Viero; OLIVERIA, Renato; ARAGÓN, Virgilio Alvarez. "
        "Entre escombros e alternativas: ensino superior na America Latina. Brasília: Editora da Universidade de Brasília, 2000."
    )
    assert _norm(p["author"]) == _norm("ARAGÓN, Virgilio Alvarez")
    assert p["publication_type"] == "capitulo_libro"
    assert p["title"] == "A educação superior latino-americana em uma encruzilhada"


def test_institutional_acronym_preserves_v06_fallback():
    raw = "CONADEP. Nunca más. Informe de la Comisión Nacional sobre la desaparición de personas. Buenos Aires: Eudeba, 1984."
    old, new = parse_v06(raw), parse_reference(raw)
    for field in ["parse_style", "author", "authors", "year", "publication_type", "title", "journal", "publisher", "publisher_observed", "source_publisher", "doi"]:
        assert new.get(field) == old.get(field)


def test_v06_external_holdout_is_v07_development_regression():
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
    assert hits["author"] == 30
    assert hits["year"] == 30
    assert hits["title"] == 30
    assert hits["type"] == 30
    assert hits["journal"] == jn
    assert hits["publisher"] == pn
    assert hits["publisher_observed"] == pon
