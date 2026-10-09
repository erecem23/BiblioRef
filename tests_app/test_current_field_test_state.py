import json
from pathlib import Path

from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION, STABLE_ENGINE_VERSION
from biblioref.parsing import PARSER_STATUS, PARSER_VERSION
from biblioref.styleprofiler import STYLE_PROFILER_STATUS, STYLE_PROFILER_VERSION


STATE_PATH = Path(__file__).resolve().parents[1] / "CURRENT_FIELD_TEST_STATE.json"


def _state():
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def test_current_field_test_state_tracks_effective_versions():
    state = _state()

    assert SOFTWARE_VERSION == "0.9.10-rc2"
    assert ALGORITHM_VERSION == "0.6.20"
    assert STABLE_ENGINE_VERSION == "0.4.5"

    assert state["software_version"] == SOFTWARE_VERSION
    assert state["algorithm_version"] == ALGORITHM_VERSION
    assert state["stable_engine_version"] == STABLE_ENGINE_VERSION
    assert state["parser_version"] == PARSER_VERSION
    assert state["styleprofiler_version"] == STYLE_PROFILER_VERSION


def test_current_field_test_state_tracks_effective_component_statuses():
    state = _state()

    assert state["parser_state"] == PARSER_STATUS
    assert state["styleprofiler_state"] == STYLE_PROFILER_STATUS
