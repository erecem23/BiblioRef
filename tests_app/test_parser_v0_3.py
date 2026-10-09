import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v03 import PARSER_STATUS, PARSER_VERSION, parse_reference
from biblioref.parsing.v02 import parse_reference as parse_v02
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
BURNED = ROOT / "parser_baseline" / "external_v02_burned_50_v03_development.csv"
SEED = ROOT / "parser_baseline" / "gold_seed_120_parser_legacy_v0_1.csv"


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


def _high_type(value):
    return {
        "articulo_revista": "articulo", "articulo_revista_probable": "articulo",
        "libro": "monografia", "capitulo_libro": "monografia", "capitulo": "monografia",
        "material_web": "web", "recurso_web": "web", "tesis": "tesis",
        "conference_paper": "conferencia", "conferencia": "conferencia",
        "documento_guia_manual": "otro", "informe_documento": "otro",
        "documento_legal": "otro", "documento_institucional": "otro",
        "no_referencia_fragmento": "otro", "sin_clasificar": "otro", "otro": "otro",
    }.get(str(value or ""), "otro")


def test_version_and_status():
    assert PARSER_VERSION == "biblioref-parser-v0.3"
    assert PARSER_STATUS == "development_candidate"


def test_bare_year_harvard_style():
    raw = "Bercier, M.L. and Maynard, B.R. 2015. Interventions for secondary traumatic stress with mental health workers: A systematic review. Research on Social Work Practice, 25(1), pp.81-89."
    p = parse_reference(raw)
    assert p["parse_style"] == "bare_year"
    assert _norm(p["author"]) == _norm("Bercier, M.L.")
    assert p["year"] == "2015"
    assert p["title"] == "Interventions for secondary traumatic stress with mental health workers: A systematic review"
    assert p["journal"] == "Research on Social Work Practice"
    assert p["publication_type"] == "articulo_revista"


def test_bare_year_colon_journal_is_preserved_whole():
    raw = "Bourke, M.L., and Craun, S.W. 2014a. Coping with secondary traumatic stress: Differences between U.K. and U.S. child exploitation personnel, Traumatology: An International Journal, 20(1), 57–64."
    p = parse_reference(raw)
    assert p["year"] == "2014"
    assert p["journal"] == "Traumatology: An International Journal"
    assert p["title"].startswith("Coping with secondary traumatic stress")


def test_vancouverish_style():
    raw = "Barker TH, Habibi N, Aromataris E, Stone JC, Leonardi-Bee J, Sears K, et al. The revised JBI critcal appraisal tool for the assessment of risk of bias quasi-experimental studies. JBI Evid Synth. 2024;22(3):378-88."
    p = parse_reference(raw)
    assert p["parse_style"] == "vancouverish"
    assert p["author"] == "Barker TH"
    assert p["year"] == "2024"
    assert p["title"].startswith("The revised JBI critcal appraisal tool")
    assert p["journal"] == "JBI Evid Synth"
    assert p["publication_type"] == "articulo_revista"


def test_parenthetical_colon_journal_does_not_collapse_to_generic_tail():
    raw = "Ackerman, S. J., & Hilsenroth, M. J. (2001). A review of therapist characteristics and techniques negatively impacting the therapeutic alliance. Psychotherapy: Theory, research, practice, training, 38(2), 171."
    p = parse_reference(raw)
    assert p["journal"] == "Psychotherapy: Theory, research, practice, training"


def test_article_number_and_single_page_metadata():
    a = parse_reference("Baier, A. L., Kline, A. C., & Feeny, N. C. (2020). Therapeutic alliance as a mediator of change: A systematic review and evaluation of research. Clinical psychology review, 82, 101921.")
    b = parse_reference("Ballespí, S., Vives, J., Sharp, C., Chanes, L., & Barrantes-Vidal, N. (2021). Self and other mentalizing polarities and dimensions of mental health: association with types of symptoms, functioning and well-being. Frontiers in Psychology, 12, 566254.")
    assert a["journal"] == "Clinical psychology review"
    assert b["journal"] == "Frontiers in Psychology"
    assert a["publication_type"] == b["publication_type"] == "articulo_revista"


def test_monograph_publisher_blocks_false_volume_only_journal():
    raw = "Escohotado, A. (1998) Aprendiendo de las drogas. Usos y abusos. Prejuicios y desafíos. Anagrama, Barcelona, 1998, p. 25"
    p = parse_reference(raw)
    assert p["journal"] is None
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "Anagrama"


def test_instrument_vs_dsm_taxonomy():
    dsm = parse_reference("American Psychiatric Association. (2013). Diagnostic and statistical manual of mental disorders (5th ed.). https://doi.org/10.1176/appi.books.9780890425596")
    scale = parse_reference("Bandelow, B. (1999). Panic and Agoraphobia Scale (PAS). Hogrefe & Huber Publishers. https://psycnet.apa.org/record/1999-04218-000")
    assert dsm["publication_type"] == "libro"
    assert scale["publication_type"] == "documento_guia_manual"


def test_burned_external_50_is_now_v03_development_regression():
    rows = list(csv.DictReader(private_data(BURNED).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 50
    author_hit = title90 = type_hit = 0
    jgold = jhit = jcov = 0
    pgold = phit = pcov = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        author_hit += _norm(p.get("author")) == _norm(row.get("gold_author"))
        title90 += _fuzzy(p.get("title"), row.get("gold_title")) >= 0.90
        type_hit += p.get("publication_type") == row.get("gold_publication_type")
        if row.get("gold_journal"):
            jgold += 1
            jcov += bool(_norm(p.get("journal")))
            jhit += _fuzzy(p.get("journal"), row.get("gold_journal")) >= 0.90
        if row.get("gold_publisher"):
            pgold += 1
            pcov += bool(_norm(p.get("publisher")))
            phit += _norm(p.get("publisher")) == _norm(row.get("gold_publisher"))
    # This set is development now; thresholds prevent reintroducing the exact
    # failure families that motivated v0.3 without claiming external accuracy.
    assert author_hit >= 49
    assert title90 >= 49
    assert type_hit >= 49
    assert jgold == 39 and jcov == 39 and jhit >= 38
    assert pgold == 10 and pcov == 10 and phit >= 6


def test_seed120_does_not_regress_materially_from_v02():
    rows = list(csv.DictReader(private_data(SEED).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 120
    jgold = jhit = jcov = type_hit = 0
    pgold = phit = pcov = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        if row.get("gold_journal"):
            jgold += 1
            jcov += bool(_norm(p.get("journal")))
            jhit += _fuzzy(p.get("journal"), row.get("gold_journal")) >= .90
        type_hit += _high_type(p.get("publication_type")) == row.get("gold_type_high")
        if row.get("gold_publisher"):
            pgold += 1
            pcov += bool(_norm(p.get("publisher")))
            phit += _norm(p.get("publisher")) == _norm(row.get("gold_publisher"))
    assert jgold == 30 and jhit >= 24 and jcov >= 25
    assert type_hit >= 94
    assert pgold == 23 and phit >= 22 and pcov >= 22


def test_parenthetical_v02_year_and_doi_still_match_examples():
    cases = [
        "Holmes, J., Gathercole, S. E., & Dunning, D. L. (2009). Adaptive training leads to sustained enhancement of poor working memory in children. Developmental Science, 12(4), F9–F15. doi:10.1111/j.1467-7687.2009.00848.x",
        "Massol, S., Vantaggio, S., & Chainay, H. (2020). Emotional modulation of episodic memory in school-age children and adults. Journal of Experimental Psychology: General, 149(9), 1684–1703. https://doi.org/10.1037/xge0000744",
    ]
    for raw in cases:
        old, new = parse_v02(raw), parse_reference(raw)
        assert new["year"] == old["year"]
        assert new["doi"] == old["doi"]
