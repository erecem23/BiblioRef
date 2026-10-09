import hashlib
from pathlib import Path
from biblioref.parsing.v05 import PARSER_SCHEMA_VERSION, PARSER_VERSION
from tests_support.private_data import private_data
ROOT=Path(__file__).resolve().parents[1]
PARSER=ROOT/'biblioref/parsing/v05.py'
GOLD=ROOT/'parser_baseline/holdout_v05/PARSER_V05_ABNT_EXTERNAL_GOLD_FROZEN.csv'

def test_v05_frozen_version_metadata():
    assert PARSER_VERSION == 'biblioref-parser-v0.5'
    assert PARSER_SCHEMA_VERSION == 5

def test_v05_source_freeze_sha256():
    assert hashlib.sha256(PARSER.read_bytes()).hexdigest() == '5be695aeb585e02b4eb1b20b96904fb513be87e36950c98487f2572feb8be1d8'

def test_v05_external_gold_freeze_sha256():
    assert hashlib.sha256(private_data(GOLD).read_bytes()).hexdigest() == '5773422499c42fbd866b69d457cbaf849310a498f7e2c8ecf6e129960fc3d70c'
