from copy import deepcopy

from biblioref.parsing.v11 import parse_reference
from biblioref.styleprofiler import STYLE_PROFILER_STATUS, STYLE_PROFILER_VERSION, profile_document, profile_references


def _row(text, i=1, zone=1):
    return {"id": f"r{i}", "order": i, "zone_id": zone, "text": text, "parsed": parse_reference(text)}


def test_version_and_shadow_contract():
    p = profile_references([_row("Smith, J. (2020). Example. Journal, 1(2), 3-4."), _row("Jones, A. (2021). Example 2. Journal, 2(1), 4-5.", 2), _row("Brown, C. (2022). Example 3. Journal, 3(1), 5-6.", 3)])
    assert STYLE_PROFILER_VERSION == "biblioref-styleprofiler-v0.1-shadow"
    assert STYLE_PROFILER_STATUS == "shadow"
    assert p["confidence"] is None
    assert p["context"]["used_in_decision"] is False


def test_profiler_never_mutates_records_or_parsed_fields():
    rows = [_row("Ábalos, María Gabriela, \"El proceso de mejora\", en línea http://example.org; última visita: 10 de Febrero de 2012")]
    before = deepcopy(rows)
    profile_document(rows)
    assert rows == before


def test_apa_like_zone():
    rows = [
        _row("Smith, J. (2020). Example title. Journal of Examples, 12(3), 20-31.", 1),
        _row("Brown, A. (2021). Another title. Journal of Examples, 13(2), 10-19.", 2),
        _row("White, C. (2022). Third title. Journal of Examples, 14(1), 1-9.", 3),
    ]
    p = profile_references(rows)
    assert p["family"] == "author_year"
    assert p["likely_style"] == "apa_like"


def test_legacy_year_final_is_variant_not_forced_normative_style():
    rows = [
        _row("Agulla, Juan Carlos, La Promesa de la Sociología, Editorial de Belgrano, Buenos Aires, 1982", 1),
        _row("Bauman, Zygmunt, Modernidad líquida, Fondo de Cultura Económica, México, 2000", 2),
        _row("Weber, Max, Economía y Sociedad, Fondo de Cultura Económica, México, 1997", 3),
    ]
    p = profile_references(rows)
    assert p["variant"] == "legacy_year_final"
    assert p["likely_style"] == "unknown"
    assert p["family"] == "author_year"
    assert p["consistency"] >= 0.95


def test_context_is_preserved_but_not_used():
    rows = [_row("Smith, J. (2020). A. Journal, 1(1), 1-2."), _row("Brown, A. (2021). B. Journal, 1(1), 2-3.", 2), _row("White, C. (2022). C. Journal, 1(1), 3-4.", 3)]
    a = profile_references(rows, context={"country": "BR", "discipline": "psychology"})
    b = profile_references(rows, context={"country": "US", "discipline": "engineering"})
    assert a["family"] == b["family"]
    assert a["likely_style"] == b["likely_style"]
    assert a["context"]["used_in_decision"] is False
    assert b["context"]["used_in_decision"] is False
