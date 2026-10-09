import difflib
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v09 import PARSER_STATUS, PARSER_VERSION, parse_reference
from biblioref.parsing.v08 import parse_reference as parse_v08

ROOT = Path(__file__).resolve().parents[1]


def _norm(value):
    s = str(value or "").casefold().replace("&", " and ")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fuzzy(a, b):
    a, b = _norm(a), _norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def test_version_and_status():
    assert PARSER_VERSION == "biblioref-parser-v0.9"
    assert PARSER_STATUS == "development_candidate"


# --------------------------------------------------------------------------
# Author block
# --------------------------------------------------------------------------

def test_multi_initial_given_part_does_not_truncate_the_author_block():
    p = parse_reference(
        "ALMEIDA, R. S.; BOURLIATAUX-LAJOINIE, S.; MARTINS, M. Satisfaction measurement "
        "instruments for healthcare service users: a systematic review. Cad. Saúde Pública, "
        "Rio de Janeiro, 31(1):11-25, jan, 2015."
    )
    assert _norm(p["author"]) == _norm("ALMEIDA, R. S.")
    assert p["authors"].count("|") == 2
    assert p["title"] == (
        "Satisfaction measurement instruments for healthcare service users: a systematic review"
    )
    assert p["journal"] == "Cad. Saúde Pública"


def test_semicolon_without_final_dot_keeps_the_second_initial():
    p = parse_reference(
        "ALBINO, R. M; RIGGENBACH, V. Medicina de urgência – passado, presente, futuro. "
        "Arq Catarinense de Medicina. Santa Catarina, v. 33, n. 3, p. 15-17, 2004."
    )
    assert _norm(p["author"]) == _norm("ALBINO, R. M")
    assert p["title"] == "Medicina de urgência – passado, presente, futuro"
    assert p["journal"] == "Arq Catarinense de Medicina"


def test_et_al_is_a_truncation_marker_not_a_name():
    p = parse_reference(
        "SILVEIRA, T. et al. Controle de inércia não monotônico de otimização por enxame de "
        "partículas. Interdisciplinary Studies in Computer Science, v. 20, n. 2, p. 69–82, 2009."
    )
    assert _norm(p["author"]) == _norm("SILVEIRA, T.")
    assert p["authors"].endswith("et al.")
    assert p["title"] == (
        "Controle de inércia não monotônico de otimização por enxame de partículas"
    )
    assert p["journal"] == "Interdisciplinary Studies in Computer Science"


def test_surname_with_initials_and_no_comma_is_a_personal_author():
    p = parse_reference(
        "DONABEDIAN A. Evaluating the quality of medical care. Milbank Memorial Fund "
        "Quarterly, 1966, 44: 166–206."
    )
    assert _norm(p["author"]) == _norm("DONABEDIAN A.")
    assert p["title"] == "Evaluating the quality of medical care"
    assert p["journal"] == "Milbank Memorial Fund Quarterly"
    assert p["publication_type"] == "articulo_revista"


def test_punctuation_loss_between_authors_keeps_the_first_author_only():
    p = parse_reference(
        "ALBUQUERQUE, Else de F. MENEZES Marilda. O valor material e simbólico da renda "
        "renascença. Estudos Feministas, Florianópolis, 15(2): 240, maio-agosto/2007."
    )
    assert _norm(p["author"]) == _norm("ALBUQUERQUE, Else de F.")
    assert "MENEZES" in p["authors"]
    assert p["title"] == "O valor material e simbólico da renda renascença"
    assert p["journal"] == "Estudos Feministas"


def test_given_name_after_an_initial_stays_in_the_author_when_a_separator_follows():
    p = parse_reference(
        "BICUDO, Maria A. Viggiani; JUNIOR, Celestino A. da Silva. (Orgs.) Formação do "
        "educador e avaliação educacional. São Paulo: Editora Unesp, 1999."
    )
    assert _norm(p["author"]) == _norm("BICUDO, Maria A. Viggiani")


def test_word_after_an_initial_is_the_title_when_no_separator_follows():
    p = parse_reference(
        "ALBUQUERQUE, P. P. Autogestão. In: CATTANI, A. D. (Org.). A outra economia. "
        "Porto Alegre: Veraz Editores, 2003."
    )
    assert _norm(p["author"]) == _norm("ALBUQUERQUE, P. P.")
    assert p["title"] == "Autogestão"
    assert p["publication_type"] == "capitulo_libro"


def test_ampersand_surnames_remain_one_collective_author():
    p = parse_reference(
        "BOGDAN & BIKLEN. Investigação qualitativa em educação. Porto Editora, LTDA, 1994."
    )
    assert _norm(p["author"]) == _norm("BOGDAN & BIKLEN")


def test_institutional_author_is_left_to_the_previous_route():
    p = parse_reference(
        "MINISTÉRIO DA SAÚDE. Política nacional de atenção básica. Brasília: MS, 2012."
    )
    assert not str(p["parse_style"] or "").startswith("abnt_v09")


# --------------------------------------------------------------------------
# Journal candidate
# --------------------------------------------------------------------------

def test_corporate_publishing_entity_is_removed_from_the_journal_name():
    p = parse_reference(
        "YACAMINI, R.; ABU-NSSAER, A. Numerical calculation of inrush current in single-phase "
        "transformers. IEE Proceedings B - Electric Power Applications, Institute of Electrical "
        "and Electronics Engineers (IEEE), v. 128, n. 5, p. 327–334, 1981."
    )
    assert p["journal"] == "IEE Proceedings B - Electric Power Applications"


def test_journal_like_final_segment_is_not_mistaken_for_a_place():
    p = parse_reference(
        "DELGADO, P. G. Reforma psiquiátrica: estratégias para resistir ao desmonte. "
        "Trabalho, Educação e Saúde, v. 17, n. 2, 2022."
    )
    assert p["journal"] == "Trabalho, Educação e Saúde"


def test_compact_volume_issue_pages_cut_the_journal_candidate():
    p = parse_reference(
        "CICONET, R. M.; MARQUES, G. Q.; LIMA, M. A. D. S. Educação em serviço para "
        "profissionais de saúde. Interface (Botucatu), v. 12, n. 26, set. 2008."
    )
    assert p["journal"] == "Interface (Botucatu)"


# --------------------------------------------------------------------------
# APA journal rescue
# --------------------------------------------------------------------------

def test_apa_journal_rescue_handles_non_numeric_issue_designator():
    p = parse_reference(
        "Blustein, D. L., Olle, C., Connors-Kellgren, A., & Diamonti, A. J. (2016). "
        "Decent work: A psychological perspective. Frontiers in Psychology, 7(MAR), 1–10. "
        "https://doi.org/10.3389/fpsyg.2016.00407"
    )
    assert p["journal"] == "Frontiers in Psychology"
    assert p["publication_type"] == "articulo_revista"


def test_apa_journal_rescue_handles_elocator_and_online_marker():
    p = parse_reference(
        "Antloga, C. S., Monteiro, R. A., & Bentes, A. M. (2023). Percepção de danos no "
        "trabalho de ser mãe universitária. Psicologia: Ciência e Profissão, 43, e25314. "
        "https://doi.org/10.1590/1982-3703003253141"
    )
    assert p["journal"] == "Psicologia: Ciência e Profissão"
    p2 = parse_reference(
        "Andrade, A. L., Pires, F. M., & Martins, G. H. (2024). The psychology of working: "
        "First evidence with brazilian workers. International Journal for Educational and "
        "Vocational Guidance, (online). https://doi.org/10.1007/s10775-024-09650-1"
    )
    assert p2["journal"] == "International Journal for Educational and Vocational Guidance"


def test_apa_journal_rescue_abstains_on_books_and_chapters():
    book = parse_reference(
        "Amarante, P. (2007). Saúde mental e atenção psicossocial. Editora Fiocruz."
    )
    assert not book["journal"]
    chapter = parse_reference(
        "Ashworth, P. (2019). Fundamentos conceituais da psicologia qualitativa. "
        "In J. A. Smith (Ed.), Psicologia qualitativa (pp. 4-28). Artmed."
    )
    assert not chapter["journal"]


def test_apa_journal_rescue_never_overwrites_an_existing_journal():
    text = ("Alegría, J. (2006). Por un enfoque psicolingüístico del aprendizaje de la "
            "lectura. Infancia y Aprendizaje, 29(1), 93-111.")
    assert parse_reference(text)["journal"] == parse_v08(text)["journal"]


# --------------------------------------------------------------------------
# Contract
# --------------------------------------------------------------------------

def test_v09_falls_back_to_v08_when_no_route_applies():
    text = "Texto sin estructura bibliográfica reconocible."
    a, b = parse_v08(text), parse_reference(text)
    for field in ("author", "authors", "year", "title", "journal", "publisher", "doi"):
        assert a.get(field) == b.get(field)


def test_parser_remains_downstream_of_extraction_pipeline():
    source = (ROOT / "biblioref/pipeline.py").read_text(encoding="utf-8")
    assert "biblioref.parsing" not in source
    v09 = (ROOT / "biblioref/parsing/v09.py").read_text(encoding="utf-8")
    for forbidden in ("pymupdf", "fitz", "biblioref.pipeline", "biblioref.extraction",
                      "biblioref.detection", "biblioref.adaptive"):
        assert forbidden not in v09
