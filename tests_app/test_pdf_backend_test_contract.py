import importlib
import json
import re
from pathlib import Path

import pypdfium2 as pdfium


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests_support" / "pdf_backend_manifest.json"
DIRECT_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?:fitz|pymupdf)\b|from\s+(?:fitz|pymupdf)\b)",
    re.MULTILINE,
)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _test_files() -> list[Path]:
    files = list((ROOT / "tests_app").glob("test*.py"))
    files.extend((ROOT / "tests_core").glob("test*.py"))
    return sorted(files)


def test_direct_pymupdf_imports_are_confined_to_legacy_manifest():
    legacy = set(_manifest()["legacy_pymupdf_tests"])
    offenders = []
    for path in _test_files():
        rel = path.relative_to(ROOT).as_posix()
        if DIRECT_IMPORT_RE.search(path.read_text(encoding="utf-8")) and rel not in legacy:
            offenders.append(rel)
    assert offenders == []


def test_neutral_pdf_factory_is_readable_by_pdfium(tmp_path):
    pdf_factory = importlib.import_module("tests_support.pdf_factory")
    path = tmp_path / "neutral.pdf"
    pdf_factory.write_pdf(
        path,
        [
            [("Página uno con acento", 70, 100, 14)],
            [("Página dos", 70, 120, 12)],
        ],
        metadata={"title": "Título sintético", "author": "Autora de prueba"},
    )

    doc = pdfium.PdfDocument(str(path))
    try:
        assert len(doc) == 2
        text0 = doc[0].get_textpage().get_text_range()
        text1 = doc[1].get_textpage().get_text_range()
        assert "Página uno con acento" in text0
        assert "Página dos" in text1
    finally:
        doc.close()
