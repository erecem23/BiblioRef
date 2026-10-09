#!/usr/bin/env python3
"""Smoke-test BiblioRef surfaces in an environment where PyMuPDF is absent.

The checks run in independent subprocesses so one import failure does not hide
the state of the remaining surfaces.  This tool is diagnostic only: it never
patches imports or substitutes a fake ``pymupdf``/``fitz`` module.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict


CASES: Dict[str, str] = {
    "pure_non_pdf_services": r"""
from pathlib import Path
from tempfile import TemporaryDirectory

from biblioref.exporters.files import write_result_files
from biblioref.parsing import parse_reference
from biblioref.projects import project_tree, relative_path

assert relative_path("Universidad/Tesis.pdf") == "Universidad/Tesis.pdf"
tree = project_tree(
    {"group_loose_by_university": True},
    [{
        "id": "doc_1",
        "filename": "Tesis.pdf",
        "title": "Tesis de prueba",
        "status": "uploaded",
        "metadata": {"university": "Universidad de prueba"},
        "metadata_detection": {
            "suggestions": {"university": "Universidad de prueba"}
        },
        "ingestion": {},
    }],
)
assert tree and tree[0]["kind"] == "folder"
parsed = parse_reference(
    "García, A. (2020). Un artículo de prueba. Revista de Prueba, "
    "4(2), 10-20. https://doi.org/10.1234/prueba"
)
assert isinstance(parsed, dict) and parsed
with TemporaryDirectory() as tmp:
    written = write_result_files(
        {
            "records": [{"reference_text": "Referencia"}],
            "zones": [{"zone_id": 1}],
        },
        json_out=Path(tmp) / "result.json",
        csv_out=Path(tmp) / "records.csv",
        zones_out=Path(tmp) / "zones.csv",
    )
    assert all(path and path.exists() for path in written.values())
print("parser, project tree and exporters available")
""",
    "metadata_cover_pdfium": r"""
from pathlib import Path

from biblioref.ingestion.backend_context import active_pdf_backend
from biblioref.metadata import detect_cover_metadata

fixture = Path("fixtures/document_grammar_stress.pdf")
result = detect_cover_metadata(fixture, fixture.name)
assert isinstance(result, dict)
assert result.get("version")
assert active_pdf_backend() == "pdfium"
assert result.get("title") == "Neural Systems and Document Analysis", result
assert result.get("title_source") == "cover_layout", result
assert (result.get("metadata") or {}).get("year") == "2023", result
assert (result.get("metadata") or {}).get("degree_level") == "doctorado", result
print({
    "backend": active_pdf_backend(),
    "title": result.get("title"),
    "title_source": result.get("title_source"),
    "metadata_fields": sorted((result.get("metadata") or {}).keys()),
    "confidence": result.get("confidence"),
})
""",
    "backend_dependent_import_surface": r"""
import importlib
import json

from biblioref.ingestion.backend_context import active_pdf_backend

modules = [
    "biblioref.ingestion",
    "biblioref.extraction.numeric_rescue",
    "biblioref.extraction.column_reflow",
    "biblioref.extraction.structural_repairs_v067",
    "biblioref.audit.coverage",
    "biblioref.adaptive.two_pass",
]
failures = {}
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failures[name] = f"{type(exc).__name__}: {exc}"
print(json.dumps(failures, ensure_ascii=False, sort_keys=True))
assert not failures, failures
assert active_pdf_backend() == "pdfium"
""",
    "ingestion_preflight": r"""
from pathlib import Path

from biblioref.ingestion import pdf_preflight

result = pdf_preflight(Path("fixtures/document_grammar_stress.pdf"))
assert result["page_count"] > 0
print(result)
""",
    "ingestion_layout_range": r"""
from pathlib import Path

from biblioref.ingestion import extract_layout_lines_range

lines = extract_layout_lines_range(
    Path("fixtures/document_grammar_stress.pdf"), 1, 1
)
assert lines
print({"lines": len(lines)})
""",
    "ingestion_render_png": r"""
from pathlib import Path

from biblioref.ingestion import render_page_png

png = render_page_png(Path("fixtures/document_grammar_stress.pdf"), 1, 1.0)
assert png.startswith(b"\x89PNG\r\n\x1a\n")
print({"png_bytes": len(png)})
""",
    "pipeline_import": r"""
from biblioref.pipeline import process_pdf

assert callable(process_pdf)
print("pipeline import available")
""",
    "pipeline_process_fixture": r"""
from pathlib import Path

from biblioref.pipeline import process_pdf

result = process_pdf(
    Path("fixtures/document_grammar_stress.pdf"),
    scope="all_reference_sections",
    adaptive_mode="shadow",
)
assert isinstance(result, dict)
assert result.get("algorithm_version") == "0.6.8"
assert isinstance(result.get("records"), list)
assert isinstance(result.get("zones"), list)
print({
    "records": len(result["records"]),
    "zones": len(result["zones"]),
    "algorithm_version": result["algorithm_version"],
})
""",
    "api_import": r"""
import app

assert app.app.title == "BiblioRef"
print({"app_version": app.APP_VERSION})
""",
    "api_read_endpoints": r"""
from fastapi.testclient import TestClient

import app

with TestClient(app.app) as client:
    health = client.get("/api/health")
    capabilities = client.get("/api/capabilities")
    index = client.get("/")
assert health.status_code == 200, health.text
assert health.json().get("ok") is True
assert capabilities.status_code == 200, capabilities.text
assert index.status_code == 200, index.text[:300]
print({
    "health": health.status_code,
    "capabilities": capabilities.status_code,
    "index": index.status_code,
})
""",
    "api_project_flow": r"""
from fastapi.testclient import TestClient

import app

with TestClient(app.app) as client:
    token = client.get("/api/health").json()["session_token"]
    headers = {"X-BiblioRef-Token": token}
    created = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "Smoke test",
            "description": "isolated",
            "group_loose_by_university": True,
        },
    )
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]
    listing = client.get("/api/projects")
    tree = client.get(f"/api/projects/{project_id}/tree")
assert listing.status_code == 200, listing.text
assert tree.status_code == 200, tree.text
print({"project_id": project_id})
""",
    "api_pdf_end_to_end": r"""
from pathlib import Path

from fastapi.testclient import TestClient

import app

fixture = Path("fixtures/document_grammar_stress.pdf")
with TestClient(app.app) as client:
    token = client.get("/api/health").json()["session_token"]
    headers = {"X-BiblioRef-Token": token}
    with fixture.open("rb") as handle:
        uploaded = client.post(
            "/api/documents",
            headers=headers,
            files={"files": (fixture.name, handle, "application/pdf")},
        )
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()["documents"][0]["id"]
    analyzed = client.post(
        f"/api/documents/{doc_id}/analyze",
        headers=headers,
        json={"rescue_profile": "stable", "worker": False},
    )
    assert analyzed.status_code == 200, analyzed.text
    lines = client.get(f"/api/documents/{doc_id}/page/1/lines")
    png = client.get(f"/api/documents/{doc_id}/page/1.png?zoom=1.0")
assert lines.status_code == 200, lines.text
assert lines.json().get("lines")
assert png.status_code == 200, png.text[:300]
assert png.headers.get("content-type", "").startswith("image/png")
print({
    "doc_id": doc_id,
    "records": analyzed.json().get("n_references"),
    "line_count": len(lines.json()["lines"]),
    "png_bytes": len(png.content),
})
""",
}


def _run_case(name: str, raw_code: str, root: Path, output_dir: Path) -> dict:
    case_workspace = output_dir / f"workspace-{name}"
    case_workspace.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["BIBLIOREF_WORKSPACE"] = str(case_workspace)
    env["PYTHONNOUSERSITE"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(raw_code)],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        passed = completed.returncode == 0
        return {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-12000:],
            "stderr": completed.stderr.strip()[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "FAIL",
            "returncode": None,
            "stdout": (
                exc.stdout.strip()[-12000:]
                if isinstance(exc.stdout, str)
                else ""
            ),
            "stderr": "Timeout after 180 seconds",
        }


def _markdown(payload: dict) -> str:
    lines = [
        "# BiblioRef PyMuPDF-free smoke matrix",
        "",
        f"- Python: {payload['python']}",
        "- PyMuPDF installed: no",
        f"- Result: {payload['passed']}/{payload['total']} passed",
        "",
        "| Surface | Result |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{item['name']}` | {item['status']} |"
        for item in payload["results"]
    )
    lines.extend(["", "## Diagnostics", ""])
    for item in payload["results"]:
        stdout = (item["stdout"] or "(empty)").replace("\n", "\n    ")
        stderr = (item["stderr"] or "(empty)").replace("\n", "\n    ")
        lines.extend([
            f"### {item['name']}: {item['status']}",
            "",
            "Standard output:",
            "",
            f"    {stdout}",
            "",
            "Standard error:",
            "",
            f"    {stderr}",
            "",
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    fixture = root / "fixtures" / "document_grammar_stress.pdf"
    if not fixture.is_file():
        parser.error(f"Missing fixture: {fixture}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name, raw_code in CASES.items():
        result = _run_case(name, raw_code, root, args.output_dir)
        results.append(result)
        print(f"{result['status']:4} {name}")

    payload = {
        "gate": "pymupdf-free-smoke-v1",
        "python": sys.version.split()[0],
        "pymupdf_installed": False,
        "fixture": str(fixture),
        "results": results,
        "passed": sum(item["status"] == "PASS" for item in results),
        "failed": sum(item["status"] == "FAIL" for item in results),
        "total": len(results),
    }
    (args.output_dir / "pymupdf-free-smoke-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = _markdown(payload)
    (args.output_dir / "pymupdf-free-smoke-report.md").write_text(
        markdown,
        encoding="utf-8",
    )

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        summary_lines = markdown.split("\n")[: 8 + len(results)]
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(summary_lines) + "\n")

    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
