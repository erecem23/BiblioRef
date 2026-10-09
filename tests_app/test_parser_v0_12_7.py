"""Parser v0.12.7: autor repetido y tipo documental con evidencia explícita.

Caso de desarrollo con sangría francesa y autores repetidos. Se mide
exactitud de tipo, no cobertura: una referencia sin evidencia suficiente sigue
``sin_clasificar``.
"""
from biblioref.parsing.v12_7 import PARSER_VERSION, parse_reference


def _type(text):
    return parse_reference(text)["publication_type"]


def test_version():
    assert PARSER_VERSION == "biblioref-parser-v0.12.7"


def test_journal_number_and_pages_is_an_article():
    for text in [
        "Kreszes, D. (1994) Algunas consideraciones sobre la “Verwerfung”, Redes de la Letra , 3. pp. 63-83.",
        "------------- (2006) Caballo arruga jirafa. Contexto en psicoanálisis . 11. pág. 35-54.",
        "------------- (1998). ¿Qué es un autor? Littoral: Revista de la Escuela Lacaniana de Psicoanálisis , 25/26. pp. 35-71.",
        "Sirota, N. (2016). Perspectivas en psicoanálisis, Lalengua , 24. pp. 13-14.",
        "Glasman, S. (1984) El número de oro. Conjetural: Revista psicoanalítica . 4. pp. 49- 68.",
        "Mordoh,E., Gurevicz, M. Thompson, S; Lombardi, G. (2005b). Efectos analíticos del psicoanálisis. En: Anuario de Investigaciones de la Facultad de Psicología, XIII, pp. 45-52.",
    ]:
        assert _type(text) == "articulo_revista", text


def test_city_and_publisher_is_a_book():
    for text in [
        "Clavreul, J. (1983). El orden médico . Barcelona, Argot.",
        "Farge, A. (1991). La atracción del archivo . Valencia, Institucio Alfons El Magnanim.",
        "------------- (2005). La dimensión clínica del psicoanálisis. Buenos Aires , Kliné.",
        "------------- (2016) Nada nos impide, nada nos obliga: De la contingencia en psicoanálisis . Rosario, Nube Negra.",
        "------------- (2014). La retórica conjetural o el nacimiento del sujeto . Rosario. Nube Negra.",
    ]:
        assert _type(text) == "libro", text


def test_unpublished_material():
    for text in [
        "------------- (1967-1968). El Acto Psicoanalítico: Seminario XV. Inédito. Traducción de Silvia García Espil para Discurso Freudiano.",
        "------------- (1972). El saber del psicoanalista (Charlas en Saint-Anne). Inédito. Traducción ENAPSI.",
        "Lacan, J. (1960-1961). La transferencia: Seminario VIII. Inédito. Versión crítica de Ricardo Rodríguez Ponte para la Escuela Freudiana de Buenos Aires.",
    ]:
        assert _type(text) == "material_inedito", text


def test_unpublished_does_not_override_stronger_types():
    assert _type("Colovini, M. Teresa (2004). Tesis de Doctorado: “Amor, locura y femineidad”. Facultad de Psicología. UNR. Inédita.") == "tesis"
    assert _type("Vetere, E. (2014). La posición del analista en la estructura. Coloquio Internacional de Convergencia 2014. Inédito.") == "conference_paper"


def test_an_online_article_in_a_named_serial_is_an_article():
    assert _type("------------- (2008) Algunas precisiones sobre el proceso diagnóstico en psicoanálisis. En Anuario de investigaciones , 14 Recuperado de: http://www.scielo.org.ar/scielo.php?pid=S1851-16862007000100007") == "articulo_revista"
    assert _type("Toro, C. (2013) Las paradojas del diagnóstico . Recuperado de: http://www.imagoagenda.com/articulo.asp?idarticulo=2028") == "material_web"
    assert _type("Bialo, A. (19 de marzo de 2023). Así fue el primer día en la revista El Gráfico hace 60 años. Infobae. https://www.infobae.com/deportes/2023/03/19/asi-fue/") != "articulo_revista"


def test_an_article_with_a_url_stays_an_article():
    assert _type("Pérez, J. (2015). La clínica. Revista de Psicología, 12(2), 45-60. Recuperado de http://www.x.org/a.pdf") == "articulo_revista"


def test_controls_that_already_worked():
    assert _type("Braunstein, N. (1994). La clínica del goce. México: Siglo XXI.") == "libro"
    assert _type("Pérez, J. (2010). Un capítulo. En A. Gómez (Comp.), Una obra (pp. 10-20). Buenos Aires: Paidós.") == "capitulo_libro"


def test_theses_and_meetings_before_city_and_publisher():
    assert _type("Barbosa Goncalves, C. A. (2012). A contratransfêrencia na clínica contemporânea. Dissertação de mestrado não publicada. Instituto de Psicologia. Universidade de São Paulo.") == "tesis"
    assert _type("---. (2011). Andarilhos do bem: Os caminos do acompanhamento terapêutico. Tese de doutorado. Instituto de Psicologia da Universidade de São Paulo. São Paulo, Brasil.") == "tesis"
    assert _type("Martín, A., Gómez, A. y Minervino, R. (2015). The role of instruments and locations in evaluating the quality of analogies . Trabajo presentado en la XV Reunión Nacional de Psicología. Rosario.") == "conference_paper"


def test_edition_notes_and_places_are_not_misread():
    assert _type("Una Epistemología del Sur. La reinvención del conocimiento y la emancipación social . Buenos Aires: Siglo XXI Editores, CLACSO, 2009. pp. 160-209.") != "articulo_revista"
    assert _type("Muñoz, E. (2018). Aportaciones del envejecimiento activo al bienestar de los adultos mayores: el caso del Centro de Día Ferrusola. Sevilla, España.") != "libro"
    assert _type("Asamblea Nacional (2014). Código orgánico integral penal. Registro Oficial 180 . Quito, Ecuador.") != "libro"
    assert _type("Mitelman, M. (2015). Secrets de l’énonciation, Révue Ironik Nº9, Paris, France.") != "libro"
    assert _type("Moya, M., Expósito, F. & Casado, P. (1999). Women's reactions to sexist situations . 22 nd General Meeting of the European Association of Experimental Social Psychology, Oxford, Inglaterra.") == "conference_paper"


def test_in_container_before_city_and_publisher_is_a_chapter():
    assert _type("Carrozzo, N. (1997). Apresentacao. En Crise e cidade: acompanhamento terapêutico. Equipo de acompanhantes Terapêuticos do Instituto A Casa . São Paulo. Educ.") == "capitulo_libro"


def test_a_personal_communication_is_not_a_conference_paper():
    assert _type("Sauvagnat, F. (2016). Comunicación personal, en el marco de una reunión de doctorantes Paris, 22/06/16.") != "conference_paper"


def test_library_of_congress_is_not_a_congress():
    assert _type("S. Freud (2004), “Jenseits des Lustprinzips”, Holograph manuscript, bound, Manuscript Division, Library of Congress, Washington.") != "conference_paper"
