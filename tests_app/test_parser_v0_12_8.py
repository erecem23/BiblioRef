"""Parser v0.12.8: tipo documental separado del medio de acceso.

Control estable con extracción correcta (lista APA con sangría francesa). Se
mide exactitud del tipo: una señal secundaria (URL, «Boletín», fecha con día)
no desplaza a una señal documental más fuerte (norma, capítulo, informe).
"""
import os

import pytest

from biblioref.parsing import v12_8

MOD = __import__(os.environ.get("PARSER_UNDER_TEST", "biblioref.parsing.v12_8"), fromlist=["parse_reference"])


def _type(text):
    return MOD.parse_reference(text)["publication_type"]


def test_version():
    assert v12_8.PARSER_VERSION == "biblioref-parser-v0.12.8"


@pytest.mark.parametrize("text", [
    "Decreto 297/2020. (2020, 13 de marzo). Aislamiento Social, Preventivo y Obligatorio. Boletín Oficial de la República Argentina.",
    "Decreto 520/2020. (2020, 7 de junio). Distanciamiento Social, Preventivo y Obligatorio. Boletín Oficial de la República Argentina.",
    "Ley N° 26.206 (2006). Ley de Educación Nacional. Boletín Oficial, 28 de diciembre de 2006.",
])
def test_decree_or_law_published_in_the_official_gazette_is_legal(text):
    assert _type(text) == "documento_legal"


@pytest.mark.parametrize("text", [
    "Dirección General de Cultura y Educación. (1995, 28 de diciembre). Resolución n.º 1956.",
    "Dirección General de Cultura y Educación. (2009, 1 de diciembre). Resolución n.º 3828,",
    "Ministerio de Educación (2012). Resolución CFE N° 188/12. Buenos Aires.",
])
def test_resolution_is_legal(text):
    assert _type(text) == "documento_legal"


def test_regulation_reached_through_a_url_is_legal():
    assert _type("Centro Nacional de Documentación e Información Educativa. (1908). Reglamento para las Escuelas Profesionales de Artes y Oficios de Mujeres. http://www.bnm.me.gov.ar/giga1/documentos/EL003812.pdf") == "documento_legal"


@pytest.mark.parametrize("text", [
    "Bleichmar, S. (2005). Estatuto de lo histórico en psicoanálisis. La subjetividad en riesgo . Buenos Aires: Topía.",
    "Rivero, N. (2018). Constitución de subjetividades en grupos autogestionados. Una lectura desde la Psicología Institucional. Buenos Aires: Eudeba.",
    "Herrera, M., Caramelo, G. y Picasso, S. (2015). Código Civil y Comercial de la Nación comentado (Tomo I) (1ª Ed.). Editorial Ministerio de Justicia.",
])
def test_a_book_whose_title_opens_with_a_norm_word_is_not_legal(text):
    assert _type(text) != "documento_legal"


def test_a_code_issued_by_a_body_is_legal():
    assert _type("Colegio de Psicólogos de la Provincia de Buenos Aires. (1989). Código de ética. La Plata: Colegio de la Provincia de Buenos Aires.") == "documento_legal"


def test_an_article_about_a_law_stays_an_article():
    assert _type("Pérez, J. (2010). La Ley de Educación Nacional y sus críticos. Revista Argentina de Educación, 12 (3), 45-60.") == "articulo_revista"
    assert _type("Gómez, A. (2015). Ley 26.206: balance de una década. Propuesta Educativa, 24 (2), 10-22.") == "articulo_revista"


@pytest.mark.parametrize("text", [
    "Chernobilsky, L. (2009). El uso de la computadora como auxiliar en el análisis de datos cualitativos En I. Vasilachis de Giardino (Coord.). Estrategias de investigación cualitativa (pp. 239-271). Gedisa editorial.",
    "De la Garza Toledo, E., Gayosso Ramírez, J. L. y Moreno, S. H. (2010). La querella de las identidades: ¿pasado sistemático, presente fragmentario? En E. De la Garza Toledo y J. C. Neffa (Coords.), Trabajo, identidad y acción colectiva (pp. 9-42). Plaza y Valdés Editores.",
    "Dessors, G. B. (1998). El enfoque psicodinámico de las repercusiones de la precariedad sobre la salud En D. Dessors y M. P. Guiho Bailly (Comps.), Organización del trabajo y salud. De la psicopatología a la psicodinámica del trabajo . (pp. 24-79). Lumen-Humanitas.",
])
def test_chapter_container_after_question_mark_or_missing_period(text):
    assert _type(text) == "capitulo_libro"


def test_chapter_with_explicit_editor_still_works():
    assert _type("Davezies, P. (1998). Elementos de psicodinámica del trabajo. En D. Dessors y M.P. Guiho-Bailly (Comps.), Organización del trabajo y salud (pp. 179-192). Lumen-Humanitas.") == "capitulo_libro"


def test_en_inside_a_book_title_is_not_a_chapter():
    assert _type("Arfuch, L. (2002). Identidades, sujetos y subjetividades En la trama de la cultura . Prometeo.") != "capitulo_libro"


def test_article_with_volume_number_pages_stays_an_article():
    assert _type("Breilh, J. (2010). La epidemiología crítica: una nueva forma de mirar la salud en el espacio urbano. Salud Colectiva, 6 (1), 83-101.") == "articulo_revista"
    assert _type("Clot, Y. (2013). Suicides au travail : un drame de la conscience professionnelle ? Activités, 10(2), 39–53. https://doi.org/10.4000/activites.716") == "articulo_revista"


def test_public_body_data_report_is_a_report():
    assert _type("Dirección General de Cultura y Educación (2019). El estado de la escuela. Datos e indicadores . Buenos Aires Provincia.") == "informe_documento"


def test_public_body_book_without_report_cue_is_not_forced():
    assert _type("Ministerio de Educación (2007). Historias de la escuela argentina . Buenos Aires: Eudeba.") != "informe_documento"


def test_dated_news_piece_online_is_web_material():
    assert _type("Barrios, H. (2020, 12 de noviembre). Las particularidades de la educación técnica en la pandemia. Agencia de Noticias de Ciencias de la Comunicación UBA. http://anccom.sociales.uba.ar/2020/11/12/las-particularidades-de-la-educacion-tecnica-en-pandemia/") == "material_web"
    assert _type("Camiolo, M. (2018, 30 de julio de 2018). Las escuelas técnicas no se tocan. La izquierda diario. https://www.laizquierdadiario.com/Las-escuelas-tecnicas-no-se-tocan") == "material_web"


def test_book_with_url_stays_a_book():
    assert _type("Arfuch, L. (2002). Identidades, sujetos y subjetividades . Prometeo. https://www.prometeoeditorial.com/libro/identidades") == "libro"


def test_dated_conference_paper_is_not_web():
    assert _type("Abalo, M. y Srnec, C. (2009, 6 de agosto). Trabajo e identidad, el pasaje de asalariado a asociado. [Ponencia] 9no Congreso Nacional de Estudios del Trabajo, Buenos Aires. https://www.aset.org.ar/2009/ponencias.pdf") == "conference_paper"


def test_url_is_recorded_apart_from_the_type():
    parsed = MOD.parse_reference("Decreto 297/2020. (2020, 13 de marzo). Aislamiento Social. Boletín Oficial. https://www.boletinoficial.gob.ar/detalleAviso/primera/227042/20200320")
    assert parsed["publication_type"] == "documento_legal"
    assert parsed.get("has_url") is True
