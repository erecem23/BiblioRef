"""Access to development datasets that are not distributed with BiblioRef.

The parser gold sets and holdouts under ``parser_baseline/`` contain reference
strings extracted from real theses. They stay on the maintainer's machine and
are excluded from the public repository, so tests that read them skip when the
file is absent instead of failing.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def private_data(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"private development dataset not available: {path.name}")
    return path
