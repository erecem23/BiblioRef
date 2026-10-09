"""Parser v0.12.6: tipo documental, autor sin fecha y apellidos con partícula.

Caso externo de desarrollo (tesis con bibliografía con viñetas): la palabra
«tesis» dentro del título hacía `tesis` a un libro; los capítulos con «, en
<Editor> (Comp.) … (pp. x-y)» quedaban como `libro`; el autor corporativo
absorbía «(s/f»; y «De Souza, L.» salía como «De, Souza».
"""
from biblioref.parsing.v12_6 import PARSER_VERSION, parse_reference


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.6"


# -- tesis ------------------------------------------------------------------
def test_the_word_thesis_inside_a_title_is_a_book():
    for text in [
        "Eco, U. (2014). Cómo se hace una tesis. Gedisa.",
        "Eco, U. (2006) Como se hace una tesis . Barcelona: Gedisa.",
        "Serrano, R. (1996) Tesis sobre Stanislavski , México: Edit. Gaceta, México, 1996.",
        "Benjamin, W. (1942). Tesis sobre la Historia y otros fragmentos. Bolívar Echeverría ediciones.",
    ]:
        assert parse_reference(text)["publication_type"] == "libro", text


def test_real_theses_stay_theses():
    for text in [
        "Tkach, C. E. (2006). Síntomas en la infancia: La neurosis infantil y las neurosis actuales . [Tesis de doctorado]. Universidad de Buenos Aires.",
        "Arditi Rocha, R. (1942). La educación psicológica del médico . Tesis del Profesorado. Facultad de Ciencias Médicas, Universidad de Buenos Aires, Buenos Aires.",
        "Muñoz, C. (2014). El meme como evolución de los medios de expresión social . Tesis de Ingeniería. Universidad de Chile. Santiago.",
        "Possani, T. (2010). A experiência de «sentir com» no acompanhamento terapêutico . Master´s Dissertation. Instituto de Psicologia, Universidade de São Paulo.",
        "Pérez, A. (2019). Las tesis de la escuela de Frankfurt (Tesis doctoral). Universidad Nacional de La Plata.",
    ]:
        assert parse_reference(text)["publication_type"] == "tesis", text


# -- capítulos --------------------------------------------------------------
def test_chapters_with_editor_or_page_range_are_chapters():
    for text in [
        "Barbarosch, A. (1996). Sobre la teoría del juego de Donald W. Winnicott, en Grego, B. (Comp.). (1996). Lecturas de Winnicott (pp. 69-80). Lugar Editorial.",
        "Abelleira, H. y Delucca, N. (2022). El valor de un legado, en N. Di Rienzo (Comp.) Teoría y Clínica en la obra de Isidoro Berenstein (pp. 115-130). Ricardo Vergara Editor.",
        "Freud, S. (1990). Más allá del principio del placer, en Obras Completas, tomo XVIII (pp. 1- 62). Amorrortu Editores.",
        "Winnicott, D. W. (2016). Why Children Play, en The Collected Works of D. W. Winnicott: Volume 2, 1939-1945 (pp.167-170). Oxford University Press.",
        "Tkach, C. (2022). Ferenczi y Winnicott frente a la ortodoxia: el analista en juego, en Isely, M. P. (Comp). Aportes de Donald W. Winnicott a la clínica. Letra Viva.",
    ]:
        assert parse_reference(text)["publication_type"] == "capitulo_libro", text


def test_en_inside_a_title_or_a_journal_is_not_a_chapter():
    book = parse_reference("Pérez, J. (2010). El juego en la infancia. Buenos Aires: Paidós.")
    assert book["publication_type"] == "libro"
    article = parse_reference(
        "Tkach, C. (2011). La consulta terapéutica en la práctica analítica. Actualidad psicológica, 402, 22-25.")
    assert article["publication_type"] == "articulo_revista"
    online = parse_reference(
        "Gómez, A. (2015). Crianza, en línea. Revista de Psicología, 12(2), 45-60.")
    assert online["publication_type"] == "articulo_revista"


# -- autor ------------------------------------------------------------------
def test_corporate_author_without_date_does_not_absorb_the_date():
    p = parse_reference(
        "Asociación Psicoanalítica Internacional (API), (s/f. Varias versiones). Diccionario Enciclopédico "
        "Interregional de Psicoanálisis. Disponible en: https://www.ipa.world/")
    assert p["author"] == "Asociación Psicoanalítica Internacional (API)"
    # Misma convención que «(s.f.)» en las versiones anteriores.
    assert p["year"] == "s.f."
    for text in ["Pérez, J. (s/f). Diccionario. Buenos Aires: Paidós.",
                 "Pérez, J. (sin fecha). Diccionario. Buenos Aires: Paidós."]:
        q = parse_reference(text)
        assert (q["author"], q["year"], q["title"]) == ("Pérez, J.", "s.f.", "Diccionario"), text


def test_surname_particles_are_kept():
    for text, author in [
        ("De Souza, L. (4 y 5 de noviembre de 2011). La creatividad en Winnicott . [Ponencia] XX Encuentro Latinoamericano, Montevideo.", "De Souza, L."),
        ("Van Dijk, T. (1999). Ideología. Barcelona: Gedisa.", "Van Dijk, T."),
        ("Da Silva, M. (2004). A clínica. São Paulo: Escuta.", "Da Silva, M."),
        ("Pérez Souza, L. (4 y 5 de noviembre de 2011). La creatividad . [Ponencia] XX Encuentro, Montevideo.", "Pérez Souza, L."),
    ]:
        assert parse_reference(text)["author"] == author, text


def test_a_day_and_month_date_is_read_as_the_year():
    p = parse_reference("De Souza, L. (4 y 5 de noviembre de 2011). La creatividad en Winnicott . [Ponencia] XX Encuentro Latinoamericano, Montevideo.")
    assert (p["year"], p["title"], p["publication_type"]) == ("2011", "La creatividad en Winnicott", "conference_paper")


def test_an_explicit_ponencia_label_is_a_conference_paper():
    p = parse_reference("Tkach, C. (2009). El concepto de trauma de Freud a Winnicott. Un recorrido hasta la actualidad. [Ponencia]. XII Jornada de Clínica de Niños y Adolescentes. Buenos Aires.")
    assert p["publication_type"] == "conference_paper"


def test_a_bullet_before_an_undated_corporate_author():
    p = parse_reference("○ Asociación Psicoanalítica Internacional (API), (s/f. Varias versiones). Diccionario Enciclopédico. Disponible en: https://www.ipa.world/")
    assert (p["author"], p["year"]) == ("Asociación Psicoanalítica Internacional (API)", "s.f.")


def test_a_container_that_opens_with_its_editors_is_a_chapter():
    p = parse_reference("Liberman, A. (2011). Verdadero y Falso Self, en A. Abello Blanco y A. Liberman, A. Una introducción a la obra de DW Winnicott: contribuciones al pensamiento relacional . Ágora Relacional.")
    assert p["publication_type"] == "capitulo_libro"


def test_title_and_publisher_alone_is_a_book():
    for text in ["Smalinsky, E. (2020). Devenir jugando. Dispositivos transicionales, experiencias y microanálisis . Brueghel.",
                 "Smalinsky, E. y Ripesi, D. (2010). Winnicott para principiantes . Era Naciente.",
                 "Rodríguez Sutil, C. (2010). Introducción a la obra de Ronald Fairbairn. Los orígenes del psicoanálisis relacional. Ágora relacional."]:
        assert parse_reference(text)["publication_type"] == "libro", text
