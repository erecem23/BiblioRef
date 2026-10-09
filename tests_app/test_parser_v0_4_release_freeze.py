from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
V04 = ROOT / "biblioref" / "parsing" / "v04.py"
GOLD = ROOT / "parser_baseline" / "holdout_v04" / "PARSER_V04_EXTERNAL_GOLD_FROZEN.csv"
EVAL = ROOT / "reports" / "parser" / "PARSER_V0_4_EXTERNAL_HOLDOUT_EVALUATION.json"
EXPECTED_V04 = "f12b43a4670615c9445112052b9714dd11c54f3f10c0889169c3083eb8f2d173"
EXPECTED_GOLD = "0db74739ad42c675fda7bc4d9afddc07faec83643a342a39875920b6cd86292d"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_v04_source_is_frozen_after_external_holdout():
    assert sha(V04) == EXPECTED_V04

def test_v04_external_gold_is_frozen_and_has_30_rows():
    assert sha(private_data(GOLD)) == EXPECTED_GOLD
    rows = list(csv.DictReader(private_data(GOLD).open(encoding="utf-8")))
    assert len(rows) == 30
    assert len({r["thesis_id"] for r in rows}) == 3

def test_v04_external_evaluation_matches_frozen_artifacts():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    assert data["frozen_gold_sha256"] == EXPECTED_GOLD
    assert data["parser_v04_pre_holdout_sha256"] == EXPECTED_V04
    assert data["parser_v04_post_holdout_sha256"] == EXPECTED_V04
    assert data["parser_source_unchanged_after_holdout"] is True

def test_v04_external_holdout_has_no_paired_regressions():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    for metric in data["paired"].values():
        assert metric["regressed_v03_right_v04_wrong"] == 0
    assert data["paired"]["title_fuzzy90"]["improved_v03_wrong_v04_right"] >= 2
    assert data["paired"]["publisher_observed_exact"]["improved_v03_wrong_v04_right"] >= 3

def test_v04_documents_abnt_limit_without_silent_patch():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    usp = data["by_thesis"]["USP_PIZZIMENTI_2024"]["v04"]
    assert usp["year_exact"]["pct"] == 100.0
    assert usp["title_fuzzy90"]["pct"] == 0.0
    assert usp["type_exact"]["pct"] == 20.0
