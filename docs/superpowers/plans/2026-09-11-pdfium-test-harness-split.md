# PDFium / Legacy Test Harness Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current BiblioRef test lane fully runnable without PyMuPDF while preserving historical PyMuPDF regressions in an explicit legacy lane, then make default packaging PDFium-first.

**Architecture:** Introduce a test-only raw PDF factory and a machine-readable backend test manifest. Migrate current tests that use fitz only as a PDF writer to the neutral factory; keep tests of historical engines in the legacy lane. CI will then prove both a PyMuPDF-free current lane and a PyMuPDF-enabled legacy lane before default requirements change.

**Tech Stack:** Python 3.11, pytest, pypdfium2, GitHub Actions, existing BiblioRef backend context.

**Spec:** `docs/superpowers/specs/2026-09-11-pdfium-test-harness-split-design.md`

## Global Constraints

- Do not modify the validated PDFium adapter or algorithm 0.6.7 behavior.
- Do not delete or silently skip historical regression tests.
- Current-lane tests must run when `pymupdf` and `fitz` are not importable.
- Default requirements change only after current and legacy lanes are independently green.
- Preserve the existing SEDICI-10 migration evidence and PyMuPDF-free smoke gate.

---

### Task 1: Test backend manifest and neutral PDF factory

**Files:**
- Create: `tests_support/__init__.py`
- Create: `tests_support/pdf_factory.py`
- Create: `tests_support/pdf_backend_manifest.json`
- Create: `test_pdf_backend_test_contract.py`

**Interfaces:**
- Produces: `pdf_bytes(pages, *, width=595, height=842, metadata=None) -> bytes`
- Produces: `write_pdf(path, pages, *, width=595, height=842, metadata=None) -> Path`
- Manifest key `legacy_pymupdf_tests: list[str]` lists tests permitted to import fitz/pymupdf.

- [ ] **Step 1: Write the failing contract test**

The test scans `test*.py` and `tests_core/test*.py` for direct `fitz`/`pymupdf` imports and fails if the importing path is not in `legacy_pymupdf_tests`. It also creates a two-page PDF with accented text through `pdf_bytes()` and verifies pypdfium2 extracts both pages.

- [ ] **Step 2: Run the contract test and verify RED**

Run: `python -m pytest -q test_pdf_backend_test_contract.py`
Expected: FAIL because current top-level tests still import fitz directly and the neutral PDF factory does not yet exist.

- [ ] **Step 3: Implement the minimal raw PDF writer**

The factory writes a standards-compliant minimal PDF 1.4 with Helvetica/WinAnsi text streams, page MediaBox, optional `/Rotate`, and optional Info metadata (`Title`, `Author`). Input page items are tuples `(text, x, y_from_top, font_size)`; the writer converts top-origin coordinates to PDF bottom-origin coordinates.

- [ ] **Step 4: Add the initial legacy manifest**

Legacy list:
`tests_core/test_biblioref_audit.py`, `tests_core/test_biblioref_v0_6.py`, `tests_core/test_biblioref_v0_6_1.py`, `tests_core/test_biblioref_v0_7_0.py`, `tests_core/test_biblioref_v0_8_1.py`, `tests_core/test_biblioref_v0_8_10.py`, `tests_core/test_biblioref_v0_8_11_performance.py`, `tests_core/test_biblioref_v0_8_2.py`, `tests_core/test_biblioref_v0_8_3.py`, `tests_core/test_biblioref_v0_9_0_two_pass.py`, `tests_core/test_biblioref_v0_9_3_router3.py`, `tests_core/test_biblioref_v0_9_9_regimes.py`.

`tests_core/test_biblioref_v0_9_10_rc2_integration.py` is current and must be migrated, not listed as legacy.

- [ ] **Step 5: Run the contract test**

Expected: still FAIL until Task 2 removes current direct imports.

### Task 2: Migrate current synthetic-PDF tests

**Files:**
- Modify: `test_app_project_flow.py`
- Modify: `test_cover_metadata_app_integration_v0_1.py`
- Modify: `test_cover_metadata_v0_1.py`
- Modify: `test_cover_metadata_v0_2.py`
- Modify: `test_document_title_integration_v2_1.py`
- Modify: `test_document_title_v2_1.py`
- Modify: `test_document_title_v2_3.py`
- Modify: `test_frontmatter_metadata_v0_3.py`
- Modify: `test_frontmatter_metadata_v0_4.py`
- Modify: `test_parallel_import.py`
- Modify: `test_projects_explorer.py`
- Modify: `tests_core/test_biblioref_v0_9_10_rc2_integration.py`

**Interfaces:**
- Consumes `tests_support.pdf_factory.pdf_bytes` and `write_pdf`.
- Existing test assertions remain unchanged unless fixture construction requires equivalent page definitions.

- [ ] **Step 1: Replace fitz-based fixture writers with the neutral factory**

Use page item tuples preserving the same text, approximate positions, font sizes, page dimensions and metadata. `test_parallel_import.py` must construct its bibliography fixture directly as pages instead of opening an existing PDF and appending a page.

- [ ] **Step 2: Run the contract test**

Run: `python -m pytest -q test_pdf_backend_test_contract.py`
Expected: PASS; remaining direct imports are only manifest-listed legacy tests.

- [ ] **Step 3: Run all migrated tests with normal requirements**

Run the twelve migrated test modules explicitly.
Expected: all PASS.

### Task 3: Current PDFium-only lane

**Files:**
- Create: `tools/run_pdfium_current_tests.py`
- Modify: `.github/workflows/pymupdf-free-isolation.yml`

**Interfaces:**
- Runner reads `tests_support/pdf_backend_manifest.json` and invokes pytest with `--ignore` for each legacy path.

- [ ] **Step 1: Add a failing CI-oriented test/runner check**

Runner must refuse to start if PyMuPDF or fitz is importable when `BIBLIOREF_REQUIRE_PDFIUM_ONLY=1`.

- [ ] **Step 2: Implement runner**

Runner constructs `python -m pytest -q` plus manifest ignores and exits with pytest's return code.

- [ ] **Step 3: Extend isolation workflow**

Install pytest/pandas/httpx2 inside the PyMuPDF-free venv after the filtered application requirements, prove PyMuPDF absence, run the smoke matrix, then run `BIBLIOREF_REQUIRE_PDFIUM_ONLY=1 python tools/run_pdfium_current_tests.py`.

- [ ] **Step 4: Verify CI**

Expected: PyMuPDF-Free Isolation Gate succeeds with the current lane, not only the smoke matrix.

### Task 4: Explicit legacy lane

**Files:**
- Create: `tools/run_pymupdf_legacy_tests.py`
- Create: `.github/workflows/pymupdf-legacy-gate.yml`

**Interfaces:**
- Runner reads the same manifest and invokes pytest only on `legacy_pymupdf_tests`.

- [ ] **Step 1: Implement legacy runner**

Fail fast with a clear message if PyMuPDF is unavailable; otherwise run every listed legacy test.

- [ ] **Step 2: Add legacy workflow**

Install current `requirements-app.txt` plus pytest/pandas/httpx2 and execute the legacy runner on PRs targeting `dev` and by workflow dispatch.

- [ ] **Step 3: Verify legacy CI**

Expected: every manifest-listed historical regression passes.

### Task 5: PDFium-first default packaging

**Files:**
- Modify: `requirements-app.txt`
- Create: `requirements-pymupdf-compat.txt`
- Modify: `.github/workflows/repository-gate.yml`
- Modify: `.github/workflows/pymupdf-free-isolation.yml`
- Create or modify: `test_pdf_backend_packaging.py`

**Interfaces:**
- `requirements-app.txt` contains pypdfium2 and not PyMuPDF.
- `requirements-pymupdf-compat.txt` includes `-r requirements-app.txt` and `PyMuPDF>=1.23,<2.0`.

- [ ] **Step 1: Write RED packaging contract**

Assert default requirements contain pypdfium2 but no PyMuPDF, and compatibility requirements explicitly add PyMuPDF.

- [ ] **Step 2: Change packaging**

Move PyMuPDF from default requirements to compatibility requirements.

- [ ] **Step 3: Update repository full gate**

Install `requirements-pymupdf-compat.txt` for the complete mixed historical suite, preserving the existing full-suite signal during transition.

- [ ] **Step 4: Simplify PDFium-free installation**

The isolation workflow now installs `requirements-app.txt` directly; no filtered temporary requirements file is needed.

- [ ] **Step 5: Verify packaging contract and both lanes**

Expected: package contract PASS, current PDFium-only gate PASS, legacy gate PASS, full repository gate PASS.

### Task 6: Final verification and documentation

**Files:**
- Modify: `PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md`

- [ ] **Step 1: Run/inspect fresh CI at branch HEAD**

Required successful checks: Repository Test Gate, PyMuPDF-Free Isolation Gate, Metadata Resolver Gate, PyMuPDF Legacy Gate.

- [ ] **Step 2: Record final architecture**

Document that default installation is PDFium-first, legacy PyMuPDF remains opt-in for historical reproducibility, and no extraction adapter/algorithm changes were made.

- [ ] **Step 3: Confirm no regression claim exceeds evidence**

Do not claim precision/recall/F1 without independent human gold; report only engineering equivalence/gate results supported by CI and the frozen SEDICI-10 comparison.
