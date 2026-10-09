#!/usr/bin/env python3
"""Run the current BiblioRef test lane without historical PyMuPDF tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests_support" / "pdf_backend_manifest.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _prove_pdfium_only() -> None:
    if os.environ.get("BIBLIOREF_REQUIRE_PDFIUM_ONLY") != "1":
        return
    try:
        version("PyMuPDF")
    except PackageNotFoundError:
        pass
    else:
        raise SystemExit("PyMuPDF distribution is installed in the PDFium-only lane")
    if find_spec("pymupdf") is not None:
        raise SystemExit("pymupdf is importable in the PDFium-only lane")
    if find_spec("fitz") is not None:
        raise SystemExit("fitz is importable in the PDFium-only lane")


def main() -> int:
    _prove_pdfium_only()
    manifest = _manifest()
    args = [sys.executable, "-m", "pytest", "-q"]
    for path in manifest["legacy_pymupdf_tests"]:
        args.extend(["--ignore", path])
    for nodeid in manifest.get("legacy_pymupdf_nodeids", []):
        args.extend(["--deselect", nodeid])
    print("Running current PDFium lane:", " ".join(args), flush=True)
    return subprocess.call(args, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
