"""Autor repetido: «------------- (2013)» hereda el autor explícito anterior.

La referencia sigue siendo independiente; el marcador original queda como
trazabilidad (``author_marker_raw``) y el autor resuelto se marca como heredado.
"""
from biblioref.parsing import parse_reference
from biblioref.parsing.inheritance import inherit_repeated_authors, repeated_author_marker


def _refs(texts, zone_id=1):
    return [{"id": f"r{i}", "order": i + 1, "zone_id": zone_id, "text": t, "parsed": parse_reference(t)}
            for i, t in enumerate(texts)]


def test_markers_are_recognised_and_never_become_an_author():
    for text in ["------------- (2013). Clasificar en psiquiatría. México: Siglo XXI.",
                 "---. (2015). Who is afraid of the ontological wolf? Cambridge journal, 33 (1), 2–17.",
                 "_______ (1998). Otra obra. Buenos Aires: Paidós.",
                 "—— (2001). Título. Madrid: Síntesis.",
                 "— (2001). Título. Madrid: Síntesis.",
                 "○ ------------- (2012). El problema del diagnóstico. Revista Borromeo , 3."]:
        parsed = parse_reference(text)
        assert repeated_author_marker(text), text
        assert not parsed.get("author"), (text, parsed.get("author"))
        assert parsed.get("author_marker_raw"), text
        assert parsed.get("year"), text


def test_a_bullet_or_a_dash_before_a_name_is_not_a_marker():
    for text in ["- Pérez, J. (2001). Título. Madrid: Síntesis.", "○ Pérez, J. (2001). Título.", "-Pérez, J. (2001). Título."]:
        assert not repeated_author_marker(text), text


def test_a_long_chain_inherits_the_explicit_author():
    texts = ["Freud, S. (1979a). Proyecto de psicología. Buenos Aires: Amorrortu."]
    texts += [f"------------- (1979{chr(98 + i)}). Obra {i}. Buenos Aires: Amorrortu." for i in range(10)]
    texts += ["Gerber, D. (2014). El psicoanálisis en el malestar. Buenos Aires: Letra Viva.",
              "------------- (2016). Otra obra. Buenos Aires: Letra Viva."]
    refs = inherit_repeated_authors(_refs(texts))
    assert all(r["parsed"]["author"] == "Freud, S." for r in refs[1:11])
    assert all(r["parsed"]["author_inherited"] and r["parsed"]["author_inherited_from"] == "r0" for r in refs[1:11])
    assert refs[12]["parsed"]["author"] == "Gerber, D."
    assert refs[12]["parsed"]["author_marker_raw"] == "-------------"
    assert not refs[11]["parsed"].get("author_inherited")


def test_inheritance_crosses_pages_but_not_zones():
    refs = _refs(["Lacan, J. (1961). El Seminario 8. Buenos Aires: Paidós."])
    refs += _refs(["------------- (1962). El Seminario 9. Inédito."], zone_id=1)
    refs[1]["id"] = "r1"
    refs += _refs(["------------- (1970). Otra zona."], zone_id=2)
    refs[2]["id"] = "r2"
    out = inherit_repeated_authors(refs)
    assert out[1]["parsed"]["author"] == "Lacan, J."
    assert not out[2]["parsed"].get("author")


def test_explicit_author_after_a_marker_is_kept():
    refs = inherit_repeated_authors(_refs([
        "Muñoz, P. (2009). La invención lacaniana. Buenos Aires: Manantial.",
        "------------- (2012). El problema del diagnóstico. Revista Borromeo , 3.",
        "Nava Murcia (2012). El mal de archivo. Historia y Grafía, 38. pp. 95-126.",
    ]))
    assert refs[1]["parsed"]["author"] == "Muñoz, P."
    assert refs[2]["parsed"]["author"].startswith("Nava Murcia")
    assert not refs[2]["parsed"].get("author_inherited")


def test_the_input_is_not_mutated():
    refs = _refs(["Braunstein, N. (1994). La clínica. México.", "------------- (2013). Clasificar. México."])
    inherit_repeated_authors(refs)
    assert not refs[1]["parsed"].get("author")
