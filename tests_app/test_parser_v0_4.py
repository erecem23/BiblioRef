import csv
import difflib
import math
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v04 import PARSER_STATUS, PARSER_VERSION, parse_reference
from biblioref.parsing.v03 import parse_reference as parse_v03
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
RESERVE_V03 = ROOT / "parser_baseline" / "reserve_v03" / "PARSER_V03_RESERVE_STRICT_GOLD_FROZEN.csv"


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
    assert PARSER_VERSION == "biblioref-parser-v0.4"
    assert PARSER_STATUS == "development_candidate"


def test_full_journal_expands_one_word_contained_alias():
    raw = "Crewe, B., Ievins, A., Larmour, S., Laursen, J., Mjaland, K. & Schliehe, A. (2023). Nordic Penal Exceptionalism: A Comparative, Empirical Analysis. The British Journal of Criminology, 63, 424–443. https://doi.org/10.1093/bjc/azac013"
    p = parse_reference(raw)
    assert p["journal"] == "The British Journal of Criminology"
    assert p["title"] == "Nordic Penal Exceptionalism: A Comparative, Empirical Analysis"


def test_chapter_one_word_publisher_after_pages():
    raw = "Haley, M. (2010). Attachment-based psychodynamic psychotherapy. In J. Harvey & K. Smedley (Eds.), Psychological Therapy in Prisons and Other Secure Settings (pp. 48-70). Willan."
    p = parse_reference(raw)
    assert p["publication_type"] == "capitulo_libro"
    assert p["publisher"] == "Willan"


def test_edition_is_not_part_of_title_and_explicit_publisher_form_is_preserved():
    raw = "Kirkwood, B. R., & Sterne, J. A. C. (2003). Essential Medical Statistics (2nd ed.). Blackwell Publishing."
    p = parse_reference(raw)
    assert p["title"] == "Essential Medical Statistics"
    assert p["publisher"] == "Blackwell"
    assert p["publisher_observed"] == "Blackwell Publishing"


def test_question_mark_does_not_truncate_article_title():
    raw = "Kounali, D., Button, K. S., Lewis, G., Gilbody, S., Kessler, D., Araya, R., Duffy, L., Lanham, P., Peters, T. J., Wiles, N., & Lewis, G. (2022). How much change is enough? Evidence from a longitudinal study on depression in UK primary care. Psychological Medicine, 52(10), 1875–1882. https://doi.org/10.1017/S0033291720003700"
    p = parse_reference(raw)
    assert p["title"] == "How much change is enough? Evidence from a longitudinal study on depression in UK primary care"
    assert p["journal"] == "Psychological Medicine"


def test_explicit_publisher_variant_preserved_when_same_alias_family():
    raw = "Beck, J. S. (2020). Cognitive behavior therapy: Basics and beyond. Guilford Publications."
    p = parse_reference(raw)
    assert p["publisher"] == "Guilford Press"
    assert p["publisher_observed"] == "Guilford Publications"


def test_v03_strict_reserve_is_now_v04_development_regression():
    rows = list(csv.DictReader(private_data(RESERVE_V03).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 20
    title_hit = type_hit = 0
    jgold = jhit = jcov = 0
    pgold = phit = pcov = pobserved_hit = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        title_hit += _fuzzy(p.get("title"), row.get("gold_title")) >= .90
        type_hit += p.get("publication_type") == row.get("gold_publication_type")
        if row.get("gold_journal"):
            jgold += 1
            jcov += bool(_norm(p.get("journal")))
            jhit += _fuzzy(p.get("journal"), row.get("gold_journal")) >= .90
        if row.get("gold_publisher"):
            pgold += 1
            pcov += bool(_norm(p.get("publisher")))
            phit += _norm(p.get("publisher")) == _norm(row.get("gold_publisher"))
            pobserved_hit += _norm(p.get("publisher_observed")) == _norm(row.get("gold_publisher"))
    assert title_hit == 20
    assert type_hit == 20
    assert jgold == 15 and jcov == 15 and jhit == 15
    assert pgold == 5 and pcov == 5 and phit >= 3 and pobserved_hit == 5


def test_year_author_doi_are_v03_invariants_on_residual_cases():
    rows = list(csv.DictReader(private_data(RESERVE_V03).open(encoding="utf-8-sig", newline="")))
    for row in rows:
        old, new = parse_v03(row["raw_citation"]), parse_reference(row["raw_citation"])
        assert new["author"] == old["author"]
        assert new["authors"] == old["authors"]
        assert new["year"] == old["year"]
        assert new["doi"] == old["doi"]
