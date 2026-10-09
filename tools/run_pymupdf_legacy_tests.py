#!/usr/bin/env python3
"""Run BiblioRef tests whose subject explicitly requires PyMuPDF."""
from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests_support" / "pdf_backend_manifest.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _prove_pymupdf_available() -> None:
    try:
        installed = version("PyMuPDF")
    except PackageNotFoundError as exc:
        raise SystemExit("PyMuPDF is required for the legacy compatibility lane") from exc
    if find_spec("pymupdf") is None and find_spec("fitz") is None:
        raise SystemExit("PyMuPDF is installed but neither pymupdf nor fitz is importable")
    print(f"Legacy PyMuPDF lane using PyMuPDF {installed}", flush=True)


def main() -> int:
    _prove_pymupdf_available()
    manifest = _manifest()
    targets = list(manifest["legacy_pymupdf_tests"])
    targets.extend(manifest.get("legacy_pymupdf_nodeids", []))
    if not targets:
        raise SystemExit("Legacy PyMuPDF manifest is empty")
    args = [sys.executable, "-m", "pytest", "-q", *targets]
    print("Running legacy PyMuPDF lane:", " ".join(args), flush=True)
    return subprocess.call(args, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
