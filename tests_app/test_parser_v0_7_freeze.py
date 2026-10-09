import hashlib
import json
from pathlib import Path

from biblioref.parsing.v07 import PARSER_SCHEMA_VERSION, PARSER_VERSION
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "biblioref/parsing/v07.py"
GOLD = ROOT / "parser_baseline/holdout_v07/PARSER_V07_EXTERNAL_GOLD_FROZEN.csv"
EVAL = ROOT / "reports" / "parser" / "PARSER_V0_7_EXTERNAL_HOLDOUT_EVALUATION.json"
INSTALLER = ROOT / "installer/BiblioRef.iss"
HANDOFF = ROOT / "docs/handoff/BIBLIOREF_MASTER_HANDOFF_V0_9_6_APP_V2_6_6_PARSER_V0_7.md"
PIPELINE = ROOT / "biblioref/pipeline.py"

PARSER_SHA = "099f62a1346c6055b8c17720676d643027070d62a1a0ab2f5448ed94a36a91b3"
GOLD_SHA = "863b1d3b03ff60ab9b4d9780d6d644fce52e665438d7e76c9a8f41bdf26099c8"


def test_v07_frozen_version_metadata():
    assert PARSER_VERSION == "biblioref-parser-v0.7"
    assert PARSER_SCHEMA_VERSION == 7


def test_v07_source_freeze_sha256():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == PARSER_SHA


def test_v07_external_gold_freeze_sha256():
    assert hashlib.sha256(private_data(GOLD).read_bytes()).hexdigest() == GOLD_SHA


def test_v07_external_evaluation_is_frozen_and_transparent():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    assert data["parser_v07_sha256"] == PARSER_SHA
    assert data["gold_sha256"] == GOLD_SHA
    assert data["v07"]["author"]["pct"] == 96.67
    assert data["v07"]["year"]["pct"] == 100.0
    assert data["v07"]["title_fuzzy90"]["pct"] == 76.67
    assert data["v07"]["type"]["pct"] == 86.67
    assert data["v07"]["publisher"]["pct"] == 72.22
    assert data["paired"]["author"]["improved"] == 9
    assert data["paired"]["author"]["regressed"] == 0
    assert data["paired"]["title_fuzzy90"]["improved"] == 6
    assert data["paired"]["title_fuzzy90"]["regressed"] == 2
    assert data["paired"]["type"]["regressed"] == 0
    assert data["paired"]["publisher"]["regressed"] == 0


def test_v07_historical_handoff_is_preserved():
    assert HANDOFF.exists()


def test_parser_remains_downstream_of_extraction_pipeline():
    source = PIPELINE.read_text(encoding="utf-8")
    assert "biblioref.parsing" not in source
