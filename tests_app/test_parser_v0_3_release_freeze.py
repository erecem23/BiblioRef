import csv
import hashlib
import re
import unicodedata
from pathlib import Path

from biblioref.parsing.v03 import parse_reference
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "parser_baseline" / "reserve_v03" / "PARSER_V03_RESERVE_STRICT_GOLD_FROZEN.csv"
V03 = ROOT / "biblioref" / "parsing" / "v03.py"
V03_SHA = "f0d62221105c4552c80ad1f6dff6014653070dcc22543fdf06c4239c2fde0b27"
GOLD_SHA = "7ff4c1c6d8b9ad8b09925ab5b629ad6a61d45842d740e5af7252b0474fcd2d79"


def _norm(value):
    s = str(value or "").casefold().replace("&", " and ")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def test_v03_source_is_the_pre_reserve_frozen_parser():
    assert hashlib.sha256(V03.read_bytes()).hexdigest() == V03_SHA


def test_strict_reserve_gold_is_frozen():
    assert hashlib.sha256(private_data(GOLD).read_bytes()).hexdigest() == GOLD_SHA


def test_strict_reserve_now_serves_as_release_regression_only():
    rows = list(csv.DictReader(private_data(GOLD).open(encoding="utf-8", newline="")))
    assert len(rows) == 20
    author = year = typ = doi = 0
    journal_gold = journal_ok = 0
    for row in rows:
        p = parse_reference(row["raw_citation"])
        author += _norm(p.get("author")) == _norm(row["gold_author"])
        year += _norm(p.get("year")) == _norm(row["gold_year"])
        typ += p.get("publication_type") == row["gold_publication_type"]
        if row["gold_doi"]:
            doi += _norm(p.get("doi")) == _norm(row["gold_doi"])
        if row["gold_journal"]:
            journal_gold += 1
            journal_ok += _norm(p.get("journal")) == _norm(row["gold_journal"])
    assert author == 20
    assert year == 20
    assert typ == 20
    assert doi == 14
    assert journal_gold == 15 and journal_ok >= 14
