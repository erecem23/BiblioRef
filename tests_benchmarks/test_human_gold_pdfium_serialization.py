from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.human_gold.acquire_sources import make_serialized_validator


def test_serialized_validator_allows_only_one_native_validation_at_a_time():
    state = {"active": 0, "max_active": 0}
    state_lock = threading.Lock()

    def inner(_path: Path) -> bool:
        with state_lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.02)
        with state_lock:
            state["active"] -= 1
        return True

    validator = make_serialized_validator(inner)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(validator, [Path(f"d{i}.pdf") for i in range(12)]))

    assert all(results)
    assert state["max_active"] == 1
