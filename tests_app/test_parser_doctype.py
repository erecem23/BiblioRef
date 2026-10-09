"""Decisión de tipo documental en un solo lugar (biblioref/parsing/doctype.py).

El refactor no cambia comportamiento: el parser vivo da la misma salida que
v0.12.8 campo por campo (en el corpus: 40.453 de 40.481 idénticas y 28 que
solo cambian el orden de ``parser_notes``). Acá se fija eso sobre todos los
textos de los tests de 0.12.6-0.12.8, se fija la tabla declarada y se protege
el resultado de la muestra gold de 300 contra retrocesos.
"""
import ast
from pathlib import Path

import pytest

from biblioref.parsing import PARSER_VERSION, parse_reference, v12_8
from biblioref.parsing.doctype import TYPE_PASSES, decide_type, rule_table

ROOT = Path(__file__).resolve().parents[1]


def _fixture_texts():
    texts = []
    for name in ("test_parser_v0_12_6.py", "test_parser_v0_12_7.py", "test_parser_v0_12_8.py"):
        tree = ast.parse((ROOT / "tests_app" / name).read_text(encoding="utf-8"))
        texts += [n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) > 40 and "(" in n.value]
    return sorted(set(texts))


def _same(a, b):
    a, b = dict(a), dict(b)
    notes = lambda d: sorted(str(d.pop("parser_notes", "") or "").split(";"))
    return notes(a) == notes(b) and a == b


def test_version_is_unchanged():
    assert PARSER_VERSION == v12_8.PARSER_VERSION


@pytest.mark.parametrize("text", _fixture_texts())
def test_live_parser_equals_v0_12_8(text):
    assert _same(v12_8.parse_reference(text), parse_reference(text))


def test_declared_order():
    assert [p.name for p in TYPE_PASSES] == [
        "palabra_tesis_en_titulo", "rotulo_ponencia", "contenedor", "evidencia_explicita", "norma_capitulo_informe_web"]
    assert [r["rule"] for r in rule_table() if r["pass"] == "norma_capitulo_informe_web"] == [
        "legal", "loose_chapter", "public_body_report", "dated_news_online"]


def test_a_rule_does_not_leave_its_source_types():
    # «En: Revista…» pasa un libro a artículo, pero no toca una tesis.
    out = {"publication_type": "tesis", "title": "Un estudio"}
    decide_type("Pérez, J. (2010). Un estudio. En: Revista de Psicología, 3, pp. 1-10.", out)
    assert out["publication_type"] == "tesis"


def test_first_rule_in_a_pass_wins_and_is_recorded():
    out = {"publication_type": "sin_clasificar", "title": "Seminario"}
    decide_type("Lacan, J. (1962). Seminario 9. Inédito. Coloquio de la EFBA.", out)
    assert out["publication_type"] == "conference_paper"
    assert "v127_unpublished_event" in out["parser_notes"]
    assert out["type_candidates"]


def test_gold_sample_does_not_regress():
    pytest.importorskip("openpyxl")
    from tools.benchmark_tipos import DEFAULT_GOLD, load_gold, run

    if not DEFAULT_GOLD.exists():
        pytest.skip("muestra gold ausente")
    totals = run(load_gold(DEFAULT_GOLD), only_reviewed=False)["totales"]
    # Línea de base 0.12.8 contra gold v1 (299, una excluida): 278 correctas, 20 incorrectas, 1 sin clasificar.
    assert totals["correcta"] >= 278
    assert totals["incorrecta"] <= 20
