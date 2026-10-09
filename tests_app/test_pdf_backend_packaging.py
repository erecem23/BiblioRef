from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_REQUIREMENTS = ROOT / "requirements-app.txt"
PYMUPDF_COMPAT_REQUIREMENTS = ROOT / "requirements-pymupdf-compat.txt"


def _active_requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_default_app_requirements_are_pdfium_first_without_pymupdf():
    lines = [line.lower() for line in _active_requirement_lines(BASE_REQUIREMENTS)]
    assert any(line.startswith("pypdfium2") for line in lines)
    assert not any(line.startswith("pymupdf") for line in lines)


def test_pymupdf_compatibility_requirements_are_explicit_opt_in():
    assert PYMUPDF_COMPAT_REQUIREMENTS.exists()
    lines = [line.lower() for line in _active_requirement_lines(PYMUPDF_COMPAT_REQUIREMENTS)]
    assert "-r requirements-app.txt" in lines
    assert any(line.startswith("pymupdf") for line in lines)
