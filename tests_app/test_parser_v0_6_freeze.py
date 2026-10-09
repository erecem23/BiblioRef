import hashlib
import json
from pathlib import Path

from biblioref.parsing.v06 import PARSER_SCHEMA_VERSION, PARSER_VERSION
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "biblioref/parsing/v06.py"
GOLD = ROOT / "parser_baseline/holdout_v06/PARSER_V06_ABNT_EXTERNAL_GOLD_FROZEN.csv"
EVAL = ROOT / "reports" / "parser" / "PARSER_V0_6_ABNT_EXTERNAL_HOLDOUT_EVALUATION.json"
INSTALLER = ROOT / "installer/BiblioRef.iss"
HANDOFF = ROOT / "docs/handoff/BIBLIOREF_MASTER_HANDOFF_V0_9_6_APP_V2_6_5_PARSER_V0_6.md"


def test_v06_historical_version_is_frozen():
    assert PARSER_VERSION == "biblioref-parser-v0.6"
    assert PARSER_SCHEMA_VERSION == 6


def test_v06_source_freeze_sha256():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == "c09e87c6f76552d5b3e0f29f846e896224a81c353f2b60eeb4c0c34fb479c942"


def test_v06_external_gold_freeze_sha256():
    assert hashlib.sha256(private_data(GOLD).read_bytes()).hexdigest() == "23d575357fd38c0e54e2a497610d1339550fba31d70f2198e09d146d35f3bbb5"


def test_v06_external_evaluation_records_known_nonmonotonicity():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    assert data["paired"]["title_fuzzy90"]["improved"] == 21
    assert data["paired"]["title_fuzzy90"]["regressed"] == 0
    assert data["paired"]["type"]["improved"] == 20
    assert data["paired"]["type"]["regressed"] == 0
    assert data["paired"]["author"]["regressed"] == 3
    assert data["paired"]["year"]["improved"] == 1
    assert data["paired"]["year"]["regressed"] == 1


def test_v06_release_metadata_is_preserved():
    assert HANDOFF.exists()
