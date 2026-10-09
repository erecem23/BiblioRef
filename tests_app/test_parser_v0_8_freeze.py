import hashlib
import json
from pathlib import Path

from biblioref.parsing.v08 import PARSER_SCHEMA_VERSION, PARSER_VERSION
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "biblioref/parsing/v08.py"
GOLD_GENERAL = ROOT / "parser_baseline/holdout_v08/PARSER_V08_EXTERNAL_GOLD_FROZEN.csv"
GOLD_STRESS = ROOT / "parser_baseline/holdout_v08/PARSER_V08_STRESS_GOLD_FROZEN.csv"
EVAL_GENERAL = ROOT / "reports" / "parser" / "PARSER_V0_8_EXTERNAL_HOLDOUT_EVALUATION.json"
EVAL_STRESS = ROOT / "reports" / "parser" / "PARSER_V0_8_STRESS_HOLDOUT_EVALUATION.json"
PIPELINE = ROOT / "biblioref/pipeline.py"

PARSER_SHA = "b10079270b5df316ebbab4ad667df774280ab09f899f5b472f1e09f372bd885b"
GENERAL_SHA = "47f90f7a0f4fddec0b5d07b71be2032682df6bb3574b7f17300a2520e5dac794"
STRESS_SHA = "102221579f2ed46842c4c8b532fc1eade016a93fd86f0ab7769a30bae54dac89"



def test_v08_frozen_version_metadata():
    assert PARSER_VERSION == "biblioref-parser-v0.8"
    assert PARSER_SCHEMA_VERSION == 8

def test_v08_source_freeze_sha256():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == PARSER_SHA


def test_v08_general_gold_freeze_sha256():
    assert hashlib.sha256(private_data(GOLD_GENERAL).read_bytes()).hexdigest() == GENERAL_SHA


def test_v08_stress_gold_freeze_sha256():
    assert hashlib.sha256(private_data(GOLD_STRESS).read_bytes()).hexdigest() == STRESS_SHA


def test_v08_general_holdout_is_no_regression_not_claimed_improvement():
    d = json.loads(EVAL_GENERAL.read_text(encoding="utf-8"))
    assert d["parser_v08_sha256"] == PARSER_SHA
    assert d["gold_sha256"] == GENERAL_SHA
    for field in ["author", "authors", "year", "title_fuzzy90", "type", "journal_fuzzy90", "publisher", "publisher_observed", "doi"]:
        assert d["paired"][field]["improved"] == 0
        assert d["paired"][field]["regressed"] == 0
    assert d["v08"]["year"]["pct"] == 100.0
    assert d["v08"]["doi"]["pct"] == 100.0


def test_v08_targeted_stress_improves_title_without_regression():
    d = json.loads(EVAL_STRESS.read_text(encoding="utf-8"))
    assert d["parser_v08_sha256"] == PARSER_SHA
    assert d["gold_sha256"] == STRESS_SHA
    assert d["v07"]["title_fuzzy90"]["pct"] == 35.0
    assert d["v08"]["title_fuzzy90"]["pct"] == 55.0
    assert d["paired"]["title_fuzzy90"]["improved"] == 4
    assert d["paired"]["title_fuzzy90"]["regressed"] == 0
    # Transparent limit: journal coverage is high but normalization remains wrong here.
    assert d["v08"]["journal_coverage"]["pct"] == 87.5
    assert d["v08"]["journal_fuzzy90"]["pct"] == 0.0
    assert d["v08"]["year"]["pct"] == 100.0
    assert d["v08"]["doi"]["pct"] == 100.0


def test_parser_remains_downstream_of_extraction_pipeline():
    assert "biblioref.parsing" not in PIPELINE.read_text(encoding="utf-8")
