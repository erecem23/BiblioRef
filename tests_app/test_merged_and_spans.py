from collections import namedtuple

from biblioref.audit.merged import backfill_merged_suspects, looks_merged

Line = namedtuple("Line", "text x0 y0 x1 y1")


def test_long_author_lists_and_year_letters_are_detected():
    navarro = ("Navarro-Carrillo, G., Alonso-Ferres, M., Moya, M., & Valor-Segura, I. (2020). Socioeconomic Status and "
               "Psychological Well-Being. Frontiers in Psychology, 11, 1303. https://doi.org/10.3389/fpsyg.2020.01303 "
               "Navarro-Carrillo, G., Méndez, L., Cakal, H., Páez, D., Pizarro, J. J., Zumeta, L., Gracia-Leiva, M., "
               "Da Costa, S., Basabe, N., Telletxea, S., Delfino, G., Techio, E., … Cueto, R. M. (2021). Clase social, "
               "bienestar y afectividad general durante la pandemia. Escritos de Psicología, 14(2), 84-95.")
    assert looks_merged(navarro)
    assert not looks_merged("Ward, T., Polaschek, D. L. L., & Beech, A. R. (2008a). Malamuth’s Confluence Model of "
                            "sexual aggression. In Theories of sexual offending (pp. 79–93). John Wiley & Sons Ltd.")
    assert not looks_merged("Pettigrew, T. F., & Tropp, L. R. (2006). A meta-analytic test of intergroup contact theory. "
                            "Journal of Personality and Social Psychology, 90(5), 751-783.")


def test_backfill_adds_missed_suspects_once():
    merged = "Moore, V. (1986). The relationships. Journal, 42, 187-198. Morales, M. I., Chávez, A. M. G. (2010). Otro título. Revista, 3, 1-9."
    doc = {"references": [{"id": "r1", "order": 5, "start_page": 30, "text": merged},
                          {"id": "r2", "order": 6, "start_page": 30, "text": "Solo, A. (2001). Una sola referencia. Revista, 1, 2-3."}],
           "analysis": {"coverage": {"merged_suspects": [], "summary": {"n_merged_suspects": 0}}}}
    assert backfill_merged_suspects(doc) is True
    suspects = doc["analysis"]["coverage"]["merged_suspects"]
    assert [s["record_index"] for s in suspects] == ["r5"] and doc["analysis"]["coverage"]["summary"]["n_merged_suspects"] == 1
    assert backfill_merged_suspects(doc) is False and len(doc["analysis"]["coverage"]["merged_suspects"]) == 1


def test_near_identical_references_get_their_own_boxes():
    import app
    lines = [
        (182, Line("Ward, T., Polaschek, D. L. L., & Beech, A. R. (2008a). Malamuth’s Confluence Model of sexual", 70, 485, 520, 500), 595, 842),
        (182, Line("aggression. In Theories of sexual offending (pp. 79–93). John Wiley & Sons Ltd.", 90, 500, 480, 515), 595, 842),
        (182, Line("Ward, T., Polaschek, D. L. L., & Beech, A. R. (2008b). Theories of sexual offending. John Wiley &", 70, 521, 520, 536), 595, 842),
        (182, Line("Sons Ltd. https://doi.org/10.1002/9780470713648", 90, 536, 400, 551), 595, 842),
    ]
    by_page = {182: ([l for _p, l, _w, _h in lines], 595, 842)}
    a = {"id": "a", "order": 1, "start_page": 182, "end_page": 182, "text": lines[0][1].text + " " + lines[1][1].text}
    b = {"id": "b", "order": 2, "start_page": 182, "end_page": 182, "text": lines[2][1].text + " " + lines[3][1].text}
    span_a = app._span_for_reference(a, by_page, 300)
    span_b = app._span_for_reference(b, by_page, 300, after=(span_a[0]["page"], span_a[0]["y0"]))
    assert span_a[0]["y0"] == 485 and span_b[0]["y0"] == 521
    # Even without reading order, the full opening line tells them apart.
    assert app._span_for_reference(b, by_page, 300)[0]["y0"] == 521
