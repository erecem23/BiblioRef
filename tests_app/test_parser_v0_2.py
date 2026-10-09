import csv
import difflib
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v02 import PARSER_STATUS, PARSER_VERSION, parse_reference
from biblioref.parsing.legacy import parse_reference as parse_v01
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "parser_baseline" / "gold_seed_120_parser_legacy_v0_1.csv"


def _norm(value):
    if value is None:
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
    assert PARSER_VERSION == "biblioref-parser-v0.2"
    assert PARSER_STATUS == "development_candidate"


def test_article_journal_and_author():
    raw = "Massol, S., Vantaggio, S., & Chainay, H. (2020). Emotional modulation of episodic memory in school-age children and adults. Journal of Experimental Psychology: General, 149(9), 1684–1703. https://doi.org/10.1037/xge0000744"
    p = parse_reference(raw)
    assert p["author"] == "Massol, S."
    assert p["publication_type"] == "articulo_revista"
    assert p["journal"] == "Journal of Experimental Psychology: General"
    assert p["publisher"] is None
    assert p["doi"] == "10.1037/xge0000744"


def test_chapter_beats_article_like_volume_and_extracts_publisher():
    raw = "Eisenberg, N., Hofer, C., & Vaughan, J. (2007). Effortful control and its socioemotional consequences. In J. J. Gross (Ed.), Handbook of emotion regulation (pp. 287–306). New York: Guilford Press."
    p = parse_reference(raw)
    assert p["publication_type"] == "capitulo_libro"
    assert p["journal"] is None
    assert p["publisher"] == "Guilford Press"


def test_book_publisher_isolated():
    raw = "Turaine, A. (2005). Un nuevo paradigma. Para comprender el mundo de hoy. Barcelona: Paidós."
    p = parse_reference(raw)
    assert p["publication_type"] == "libro"
    assert p["publisher"] == "Paidós"
    assert p["source_publisher"] == "Paidós"


def test_compact_initials_first_author():
    raw = "Brusco, LI, López, MF & Comesaña, A. (2009). Procesos de deterioro en la memoria en la demencia. En J. Vivas (Comp.) Evaluación de redes semánticas. Instrumentos y Aplicaciones. Mar del Plata: Eudem."
    p = parse_reference(raw)
    assert p["author"] == "Brusco, L. I."


def test_conference_venue_is_not_promoted_to_publisher():
    raw = 'P. & Rodriguez, R. (2009). Exploración del capital psíquico. Un estudio con adultos mayores. Trabajo presentado en el 2° Congreso Internacional de Investigación de la Facultad de Psicología de la Universidad de La Plata, La Plata.'
    p = parse_reference(raw)
    assert p["publication_type"] == "conference_paper"
    assert p["publisher"] is None


def test_year_title_doi_are_v01_invariants_examples():
    cases = [
        "Escrivá, V., Mestre, M., Frías, M. & Samper P. (2004) La medida de la empatía: análisis del Interpersonal Reactivity Index. Psicothema, 16(2), 255-260.",
        "Holmes, J., Gathercole, S. E., & Dunning, D. L. (2009). Adaptive training leads to sustained enhancement of poor working memory in children. Developmental Science, 12(4), F9–F15. doi:10.1111/j.1467-7687.2009.00848.x",
        "Lacan, Jacques: El Seminario, Libro 11: Los cuatro conceptos fundamentales del psicoanálisis, Ediciones Paidós, Buenos Aires, 1973.",
    ]
    for raw in cases:
        old, new = parse_v01(raw), parse_reference(raw)
        assert new["year"] == old["year"]
        assert new["title"] == old["title"]
        assert new["doi"] == old["doi"]


def test_development_seed_nonregression_and_minimum_gains():
    # This seed is explicitly NOT external gold. It is a frozen development
    # fixture used only to prevent parser regressions while human audit is pending.
    rows = list(csv.DictReader(private_data(SEED).open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 120
    j_gold = j_hit = j_cov = 0
    type_hit = 0
    publisher_gold = publisher_hit = publisher_cov = 0
    for row in rows:
        old = parse_v01(row["raw_citation"])
        new = parse_reference(row["raw_citation"])
        assert new["year"] == old["year"]
        assert new["title"] == old["title"]
        assert new["doi"] == old["doi"]
        if row.get("gold_journal"):
            j_gold += 1
            if new.get("journal"):
                j_cov += 1
            if _fuzzy(new.get("journal"), row["gold_journal"]) >= 0.90:
                j_hit += 1
        if _high_type(new.get("publication_type")) == row.get("gold_type_high"):
            type_hit += 1
        if row.get("gold_publisher"):
            publisher_gold += 1
            if new.get("publisher"):
                publisher_cov += 1
            if _norm(new.get("publisher")) == _norm(row["gold_publisher"]):
                publisher_hit += 1
    assert j_gold == 30
    assert j_hit / j_gold >= 0.78
    assert j_cov / j_gold >= 0.80
    assert type_hit / len(rows) >= 0.78
    assert publisher_gold == 23
    # One seed row labels a conference venue (Facultad de Psicología) as a
    # publisher. v0.2 intentionally preserves the monograph-only publisher
    # invariant, so 22/23 is the correct conservative ceiling on this seed.
    assert publisher_cov >= 22
    assert publisher_hit >= 22
