# PDFium / Legacy Test Harness Split Design

## Goal

Allow the current BiblioRef runtime and its current tests to execute in an environment where PyMuPDF/fitz is not installed, while preserving the historical PyMuPDF-based regression suite as an explicit legacy-compatibility lane.

## Constraints

- Do not modify the validated PDFium adapter, its primitives, or algorithm 0.6.7 behavior.
- Do not weaken or silently skip historical regression coverage.
- Keep legacy engines reproducible with PyMuPDF where the test subject is genuinely historical PyMuPDF behavior.
- Prefer backend-neutral fixture creation for current tests that use fitz/pymupdf only as a convenient PDF generator.
- The current runtime lane must prove PyMuPDF and fitz are not importable.
- Packaging remains unchanged until the PDFium-only current lane is green.
- Existing SEDICI-10 migration equivalence remains authoritative for backend semantic compatibility.

## Architecture

The repository test harness is split conceptually into two lanes.

### 1. Current PDFium-only lane

This lane validates current BiblioRef behavior: current ingestion, app/project flows, current metadata/title extraction, parser, StyleProfiler, resolver and other active components. It installs the application without PyMuPDF and fails if `pymupdf` or `fitz` is importable.

Tests in this lane must not import PyMuPDF directly. If a test currently imports `fitz` only to create a synthetic PDF, the test will use a small backend-neutral fixture helper instead. The helper will generate the minimum PDF structures needed by tests and will not participate in production extraction.

### 2. Legacy PyMuPDF compatibility lane

This lane preserves historical engine regressions and old module snapshots whose implementation or expected semantics are explicitly tied to PyMuPDF. It installs PyMuPDF and executes a maintained manifest of legacy tests/modules.

A test belongs here only when PyMuPDF is part of the behavior under test, not merely a fixture convenience.

## Classification rule

Each direct `fitz`/`pymupdf` import in the test suite is classified as one of:

- `fixture_only`: used to write/create a PDF for testing current behavior. Migrate to backend-neutral fixtures.
- `legacy_subject`: validates a historical engine/module whose implementation contract includes PyMuPDF. Keep in the legacy lane.
- `mixed`: combines current behavior with historical PyMuPDF setup. Split the test so current assertions run PDFium-only and the historical assertion stays legacy.

The classification must be documented in a machine-readable manifest so future imports cannot drift back unnoticed.

## Test fixtures

Create `tests_support/pdf_factory.py` as test-only infrastructure. Its public surface should be intentionally small:

- `make_text_pdf(path, pages)` for simple text pages.
- `make_rotated_text_pdf(path, pages, rotation)` only if an existing current test requires rotation.

Implementation may use pypdfium2 if it can author the required structure; if PDFium cannot author PDFs reliably, use another permissively licensed test-only writer already acceptable to the project. Do not route fixture generation through production extraction code.

## CI

Add a current PDFium-only repository gate that:

1. installs requirements with PyMuPDF removed,
2. proves `pymupdf` and `fitz` are absent,
3. runs all current-lane tests,
4. fails on any new direct import outside the legacy manifest.

Keep the existing full repository gate with PyMuPDF during migration. Add a dedicated legacy gate once the manifest is complete.

## Packaging transition

Only after the current PDFium-only lane is green and the legacy lane is explicit:

- remove PyMuPDF from default application requirements,
- add an opt-in legacy/compatibility requirements file,
- run the full current lane, legacy lane, PyMuPDF-free smoke, metadata gate and SEDICI-10 migration gate.

## Success criteria

- Current PDFium-only lane passes with `pymupdf` and `fitz` unimportable.
- Legacy PyMuPDF lane passes with no historical tests deleted.
- Full existing repository suite remains green during the transition.
- No production extraction code changes are required for the test-harness split.
- Default packaging is changed only after both lanes are independently green.
