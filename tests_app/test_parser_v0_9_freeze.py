import hashlib
import json
from pathlib import Path

from biblioref.parsing.v09 import PARSER_SCHEMA_VERSION, PARSER_VERSION

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "biblioref/parsing/v09.py"
PARSER_V08 = ROOT / "biblioref/parsing/v08.py"
DEV_EVAL = ROOT / "reports" / "parser" / "PARSER_V0_9_DEVELOPMENT_EVALUATION.json"
SWEEP = ROOT / "reports" / "parser" / "PARSER_V0_9_HISTORICAL_SWEEP.json"
CORE = ROOT / "EXTRACTION_CORE_NONREGRESSION_V09_SHA256.json"
PIPELINE = ROOT / "biblioref/pipeline.py"
HARNESS = ROOT / "tools" / "parser_history" / "evaluate_parser_v09_external_holdout.py"

PARSER_SHA = "4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320"
PARSER_V08_SHA = "b10079270b5df316ebbab4ad667df774280ab09f899f5b472f1e09f372bd885b"


def test_v09_frozen_version_metadata():
    assert PARSER_VERSION == "biblioref-parser-v0.9"
    assert PARSER_SCHEMA_VERSION == 9


def test_v09_source_freeze_sha256():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == PARSER_SHA


def test_v08_source_is_still_byte_identical():
    assert hashlib.sha256(PARSER_V08.read_bytes()).hexdigest() == PARSER_V08_SHA


def test_development_evaluation_matches_the_frozen_source():
    d = json.loads(DEV_EVAL.read_text(encoding="utf-8"))
    assert d["parser_v09_sha256"] == PARSER_SHA
    assert d["parser_v08_sha256"] == PARSER_V08_SHA
    assert d["n"] == 190


def test_development_evaluation_has_no_regression_in_any_field():
    d = json.loads(DEV_EVAL.read_text(encoding="utf-8"))
    for field, counts in d["paired"].items():
        assert counts["regressed"] == 0, field
    assert d["paired"]["author"]["improved"] == 13
    assert d["paired"]["authors"]["improved"] == 10
    assert d["paired"]["title_fuzzy90"]["improved"] == 11
    assert d["paired"]["journal_fuzzy90"]["improved"] == 15


def test_stress_set_journal_moves_from_zero_to_full_on_development_material():
    d = json.loads(DEV_EVAL.read_text(encoding="utf-8"))
    stress = d["by_set"]["v08_stress"]
    assert stress["v08"]["journal_fuzzy90"]["pct"] == 0.0
    assert stress["v09"]["journal_fuzzy90"]["pct"] == 100.0
    assert stress["v08"]["author"]["pct"] == 65.0
    assert stress["v09"]["author"]["pct"] == 100.0


def test_historical_sweep_never_removes_or_rewrites_an_existing_journal():
    d = json.loads(SWEEP.read_text(encoding="utf-8"))
    assert d["parser_v09_sha256"] == PARSER_SHA
    assert d["n_rows"] == 29027
    assert d["journal_delta"]["removed"] == 0
    assert d["journal_delta"]["modified"] == 0
    assert d["journal_delta"]["added"] == 360
    assert d["labelled_journal_moves"]["worse"] == 0
    assert d["pct_rows_changed"] < 2.0


def test_extraction_core_is_byte_identical_to_the_v08_release():
    d = json.loads(CORE.read_text(encoding="utf-8"))
    assert d["all_identical"] is True
    assert all(f["identical"] for f in d["files"])


def test_parser_remains_downstream_of_extraction_pipeline():
    assert "biblioref.parsing" not in PIPELINE.read_text(encoding="utf-8")


def test_external_holdout_harness_is_shipped():
    assert HARNESS.exists()
    text = HARNESS.read_text(encoding="utf-8")
    assert "gold_sha256" in text and "parser_v09_sha256" in text
