# Core First-Reference Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `biblioref.pipeline.process_pdf()` the single authority for the narrow Alonso/RIEA first-reference recovery currently performed only by `app.py`, while preserving existing behavior and all validated PDFium/SEDICI gates.

**Architecture:** Move the existing heading-anchored first-reference repair into a focused backend-neutral core module. Apply it after the v0.6.7 structural reconciliation stack has produced the effective all-zones records, rebuild duplicate/count metadata centrally, then let normal scope selection, audit and coverage consume the repaired result. Remove the app-level mutation only after direct-core and app/core parity tests pass.

**Tech Stack:** Python 3, pytest, FastAPI app integration, BiblioRef modular extraction pipeline, `tests_support.pdf_factory`, PDFium default backend with optional PyMuPDF compatibility lane.

**Spec:** `docs/superpowers/specs/2026-09-11-core-first-reference-repair-design.md`

## Global Constraints

- Preserve the current `_first_reference_guard()` decision gates; do not broaden bibliography-heading detection or author/year heuristics.
- Never invent a first reference in a headingless region.
- Do not modify `biblioref/ingestion/pdfium_backend.py`, `pdfium_primitives.py`, `backend_context.py`, or frozen SEDICI benchmark CSVs to make this feature pass.
- Run the repair on effective all-zones core output before public rescoping, post-extraction audit and coverage.
- App and direct-core callers must receive identical automatic reference text, order and counts for identical inputs/options.
- Recompute duplicate and count metadata with core utilities; never approximate `n_unique_references` manually.
- Preserve repair evidence as `first_reference_repairs`; remove app-specific `app_repairs` after parity is proven.
- Layout acquisition failure in this optional repair means abstention, not fatal extraction failure.
- Keep structural layer provenance `v0.6.7` intact where it names the existing structural stack; the combined public algorithm becomes `0.6.8` only after integration.
- Final acceptance requires repository, PDFium-only, PyMuPDF legacy, Metadata Resolver and frozen SEDICI-10 gates green at one exact HEAD.

---

## File Structure

**Create**
- `biblioref/extraction/first_reference_repair.py` — core-only first-reference decision and layout acquisition.
- `tests_core/test_first_reference_repair.py` — public-core regressions, pure repair tests, abstention, counts and scope.

**Modify**
- `biblioref/pipeline.py` — integrate repair after structural reconciliation; rebuild derived metadata; expose combined algorithm 0.6.8.
- `app.py` — remove app extraction mutation; bump extraction revision.
- `test_app_v252.py` — replace private guard tests with app/core parity tests.
- `biblioref/core/config.py` — `ALGORITHM_VERSION = "0.6.8"` and explanatory provenance.
- `CURRENT_FIELD_TEST_STATE.json`, `test_current_field_test_state.py` and current-version assertions — keep current candidate provenance consistent.
- `PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md` — append final migration evidence.

**Preserve as historical/structural identifiers**
- `biblioref/extraction/structural_repairs_v067.py`
- `INTEGRATED_ALGORITHM_VERSION = "0.6.7"` inside that structural module, if present, because it names that layer rather than the new combined public pipeline.

---

### Task 1: Lock the public-core behavior with RED regressions

**Files:**
- Create: `tests_core/test_first_reference_repair.py`
- Read: `test_app_v252.py`
- Read: `tests_support/pdf_factory.py`

**Interfaces:**
- Consumes: `biblioref.pipeline.process_pdf()`.
- Produces: two failing public-core tests for the existing app-only Alonso/RIEA recovery.

- [ ] **Step 1: Create a synthetic Alonso PDF helper**

```python
from tests_support import pdf_factory as fitz


def write_alonso_fixture(tmp_path, name="alonso.pdf"):
    pdf = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((70, 70), "Bibliografía", fontsize=14)
    page.insert_text(
        (70, 105),
        "Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 116),
        "G. (2002): Propuestas alternativas a la agricultura industrializada.",
        fontsize=9.5,
    )
    page.insert_text((70, 138), "Altieri, M. A. (1985). Segunda referencia.", fontsize=9.5)
    doc.save(pdf)
    doc.close()
    return pdf
```

- [ ] **Step 2: Create a deterministic pre-repair report helper**

```python

def base_report(records):
    return {
        "scope": "all_reference_sections",
        "scope_definition": "all reference sections",
        "records": records,
        "zones": [{
            "zone_id": 1,
            "heading": "Bibliografía",
            "start_page": 1,
            "end_page": 1,
            "zone_role": "primary_references",
            "start_confidence_score": 1.0,
            "start_confidence_label": "high",
            "end_confidence_score": 1.0,
            "end_confidence_label": "high",
            "zone_completeness": "complete",
            "termination_reason": "fixture",
            "adaptive_limit_exceeded": False,
        }],
        "duplicate_groups": [],
        "n_occurrences_all_zones": len(records),
        "n_unique_references": len(records),
        "n_duplicate_groups": 0,
        "n_occurrences_in_duplicate_groups": 0,
        "n_repeated_occurrences_beyond_first": 0,
        "n_records_selected": len(records),
        "detection_decision": {"method": "fixture", "requires_confirmation": False},
    }
```

Every fixture record contains `zone_id`, `ref_in_zone`, `reference_text`, start/end page, start x, `boundary_evidence`, and `audit_flags`.

- [ ] **Step 3: Add RED test for a complete omitted first entry**

Monkeypatch only `biblioref.pipeline._ORIGINAL_EFFECTIVE` to return one Altieri record, then call public `pipeline.process_pdf(pdf, rescue_audit=False)`.

```python
assert len(result["records"]) == 2
assert result["records"][0]["reference_text"].startswith("Alonso Mielgo")
assert result["records"][1]["reference_text"].startswith("Altieri")
assert result["first_reference_repairs"][0]["kind"] == "insert_omitted_first_reference"
assert "app252" not in result["records"][0]["boundary_evidence"]
```

- [ ] **Step 4: Add RED test for deferred author recovery**

Stub effective records as `G. (2002)...` followed by Altieri and call public `process_pdf()`.

```python
assert len(result["records"]) == 2
assert result["records"][0]["reference_text"].startswith("Alonso Mielgo")
assert "(2002)" in result["records"][0]["reference_text"]
assert result["first_reference_repairs"][0]["kind"] == "prepend_deferred_author"
```

- [ ] **Step 5: Verify RED**

```bash
pytest -q \
  tests_core/test_first_reference_repair.py::test_process_pdf_inserts_omitted_first_reference \
  tests_core/test_first_reference_repair.py::test_process_pdf_prepends_deferred_author
```

Expected: both fail because core still returns the pre-repair records and has no `first_reference_repairs`.

- [ ] **Step 6: Commit**

```bash
git add tests_core/test_first_reference_repair.py
git commit -m "test: define core first-reference recovery contract"
```

---

### Task 2: Implement the focused repair and abstention contract

**Files:**
- Create: `biblioref/extraction/first_reference_repair.py`
- Modify: `tests_core/test_first_reference_repair.py`

**Interfaces:**
- Consumes: `pdf_path: str | Path`, `zones: Sequence[dict]`, `records: Sequence[dict]`.
- Produces: `apply_first_reference_repair(pdf_path, zones, records) -> tuple[list[dict], list[dict]]`.

- [ ] **Step 1: Port the guard's extraction semantics into core-private helpers**

Implement `_norm`, `_compact_ocr_word`, `_looks_like_bibliography_heading`, `_candidate_key`, `_line_opens_record`, and the author-opening evidence calculation with semantics copied from the current app guard. Do not import `app.py`.

Heading vocabulary remains exactly:

```python
{
    "bibliografia", "bibliografía", "bibliography", "references", "reference",
    "referencias", "referencies", "referenciasbibliograficas",
    "listofreferences", "referencelist",
}
```

- [ ] **Step 2: Implement the public core helper**

```python

def apply_first_reference_repair(
    pdf_path: str | Path,
    zones: Sequence[dict],
    records: Sequence[dict],
) -> tuple[list[dict], list[dict]]:
    ...
```

Exact behavior:

```text
1. deep-copy incoming records;
2. inspect only the first returned record of each zone;
3. load only that record's physical start page through extract_layout_lines_range();
4. match the physical opening line conservatively;
5. search backward for an explicit bibliography heading;
6. collect non-empty lines between heading and first record;
7. require current author-opening evidence threshold;
8. undated prefix + deferred-year current record => prepend prefix;
9. dated prefix => insert omitted first record;
10. otherwise abstain.
```

On layout acquisition error, abstain for that zone. Do not catch programming errors from pure helper logic.

Use these core evidence labels:

```python
"core_first_reference_repair_v0_6_8+prepend_deferred_author"
"core_first_reference_repair_v0_6_8+insert_omitted_first_reference"
```

For inserted records, clone the old first record as a schema template, clear duplicate fingerprint/group fields, set `ref_in_zone = 1`, and increment later integer `ref_in_zone` values for that zone.

- [ ] **Step 3: Add direct helper tests**

Call `apply_first_reference_repair()` directly for both Alonso/RIEA modes. Assert repaired text, order, repair kind and core evidence labels.

Run:

```bash
pytest -q tests_core/test_first_reference_repair.py -k "repair_function"
```

Expected: PASS while Task 1 public `process_pdf()` tests remain RED.

- [ ] **Step 4: Add five explicit abstention cases**

Test separately:

```text
no explicit heading
no physical prefix
weak author evidence
undated prefix + non-deferred first record
first returned record not physically matchable
```

Every case asserts:

```python
assert repairs == []
assert repaired == original_records
```

- [ ] **Step 5: Run focused helper tests**

```bash
pytest -q tests_core/test_first_reference_repair.py -k "repair_function or abstain"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add biblioref/extraction/first_reference_repair.py tests_core/test_first_reference_repair.py
git commit -m "feat: add core first-reference repair"
```

---

### Task 3: Integrate the repair and rebuild derived metadata centrally

**Files:**
- Modify: `biblioref/pipeline.py`
- Modify: `tests_core/test_first_reference_repair.py`

**Interfaces:**
- Consumes: `apply_first_reference_repair(...)` from Task 2.
- Produces: `_apply_first_reference_reconciliation(pdf_path, base_all) -> dict` and repaired all-zones output before public rescope/audit/coverage.

- [ ] **Step 1: Add `_apply_first_reference_reconciliation()`**

```python
from biblioref.extraction.first_reference_repair import apply_first_reference_repair


def _apply_first_reference_reconciliation(pdf_path: str | Path, base_all: Dict) -> Dict:
    result = dict(base_all)
    zones = [dict(z) for z in result.get("zones", [])]
    before = list(result.get("records", []))
    after, repairs = apply_first_reference_repair(pdf_path, zones, before)
    if not repairs:
        return result

    rebuilt = _rebuild_with_replacements(
        result,
        zones,
        _records_by_zone(before),
        _records_by_zone(after),
    )
    rebuilt["first_reference_repairs"] = repairs
    decision = dict(rebuilt.get("detection_decision", {}))
    decision["first_reference_repaired_zone_ids"] = sorted({int(x["zone_id"]) for x in repairs})
    decision["stable_output_preserved"] = False
    rebuilt["detection_decision"] = decision
    return rebuilt
```

If `_rebuild_with_replacements()` expects a replacement map rather than a full final map, pass all final zone record lists as replacements so no unchanged zone disappears. Do not write counts manually.

- [ ] **Step 2: Invoke it after existing structural repairs**

In `_process_pdf_effective()`:

```python
repaired = _apply_long_segment_reconciliation(pdf_path, base, lines, adaptive_mode)
repaired = _apply_dominant_margin_reconciliation(pdf_path, repaired, lines, adaptive_mode)
repaired = _apply_first_reference_reconciliation(pdf_path, repaired)
```

This must happen before returning to `pipeline_v065.process_pdf()`, which performs public scope selection, audit and coverage.

- [ ] **Step 3: Mark effective output changes correctly**

In public `biblioref.pipeline.process_pdf()` add:

```python
or result.get("first_reference_repairs")
```

to `default_effective_output_changed`.

- [ ] **Step 4: Add derived-metadata assertions**

For omitted-entry insertion:

```python
assert result["n_occurrences_all_zones"] == 2
assert result["n_unique_references"] == 2
assert result["n_records_selected"] == 2
assert result["n_duplicate_groups"] == 0
```

Add a fixture where recovered text duplicates a later occurrence and assert `_annotate_duplicates()` determines the unique/duplicate counts.

- [ ] **Step 5: Add a public-scope regression**

Call:

```python
pipeline.process_pdf(pdf, scope="unique_references", rescue_audit=False)
```

with a duplicate fixture. Assert scope is selected from the repaired all-zones report, not repaired after scope selection.

- [ ] **Step 6: Verify core GREEN**

```bash
pytest -q tests_core/test_first_reference_repair.py
pytest -q tests_core/test_biblioref_v0_9_10_rc2_integration.py tests_core/test_pdfium_dual_backend.py
```

Expected: all new tests PASS and no new adjacent structural failures.

- [ ] **Step 7: Commit**

```bash
git add biblioref/pipeline.py tests_core/test_first_reference_repair.py
git commit -m "feat: integrate first-reference repair into core pipeline"
```

---

### Task 4: Remove the app's second extraction authority and prove parity

**Files:**
- Modify: `app.py`
- Modify: `test_app_v252.py`

**Interfaces:**
- Consumes: authoritative repaired `process_pdf()` result.
- Produces: `_analyze_document()` that converts/persists core output without mutating automatic records.

- [ ] **Step 1: Write app/core parity tests before cleanup**

For both omitted-entry and deferred-author fixtures, compare:

```python
core_texts = [r["reference_text"] for r in core_result["records"]]
app_texts = [r["text"] for r in doc["references"]]
assert app_texts == core_texts
assert doc["n_references"] == len(core_texts)
```

Also inspect the persisted result JSON and assert the final contract should contain `first_reference_repairs` and no `app_repairs`.

- [ ] **Step 2: Verify the existing app path fails the authority contract**

```bash
pytest -q test_app_v252.py -k "app_core_first_reference_parity"
```

Expected before cleanup: FAIL on the assertion that no app-level repair layer exists, even if content happens to match idempotently.

- [ ] **Step 3: Delete the post-core mutation**

Remove from `_analyze_document()`:

```python
app_repairs = _first_reference_guard(path, result)
if app_repairs:
    result["app_repairs"] = app_repairs
    try:
        result["coverage_report"] = build_coverage_report(path, result)
    except Exception:
        pass
```

Delete `_first_reference_guard()` itself. Delete only helpers now used exclusively by that guard; preserve click/snap helpers still referenced by UI/manual selection.

- [ ] **Step 4: Replace private-guard tests**

Remove:

```text
test_first_reference_guard_inserts_complete_omitted_entry
test_first_reference_guard_prepends_deferred_author_line
```

Keep their behavior covered by Task 1/2 core tests and add:

```text
test_app_core_first_reference_parity_for_omitted_entry
test_app_core_first_reference_parity_for_deferred_author
```

Neither may call a private app extraction-repair function.

- [ ] **Step 5: Bump persisted app extraction revision**

Set exactly:

```python
EXTRACTION_REVISION = "v096-core-first-reference-1"
```

Update the existing revision assertion in `test_app_v252.py`.

- [ ] **Step 6: Verify app GREEN**

```bash
pytest -q test_app_v252.py test_app_project_flow.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py test_app_v252.py
git commit -m "refactor: make app consume authoritative core extraction"
```

---

### Task 5: Update combined algorithm provenance to 0.6.8

**Files:**
- Modify: `biblioref/core/config.py`
- Modify: `biblioref/pipeline.py`
- Modify: `CURRENT_FIELD_TEST_STATE.json`
- Modify: `test_current_field_test_state.py`
- Modify current-version assertions found by repository search.

**Interfaces:**
- Consumes: working core/app migration from Tasks 1–4.
- Produces: one internally consistent combined public algorithm identity, while preserving v0.6.7 labels that name the historical structural layer.

- [ ] **Step 1: Bump the public algorithm constant**

In `biblioref/core/config.py`:

```python
ALGORITHM_VERSION = "0.6.8"
```

Update its docstring to state: algorithm 0.6.8 preserves the 0.6.7 structural stack and adds the narrow explicit-heading first-reference reconciliation formerly confined to the app.

Keep:

```python
STABLE_ENGINE_VERSION = "0.4.5"
```

- [ ] **Step 2: Update the combined pipeline identity, not historical layers**

In `biblioref/pipeline.py`:

- change the module-level description from public/current `0.6.7` wrapper to `0.6.8` combined pipeline;
- change:

```python
repaired["algorithm_integration"] = {
    "version": "0.6.8",
    "preserved_base": "0.6.5",
    "cabrera_dominant_margin": "0.6.6",
    "rc1_structural_origin": RC1_ORIGIN,
    "first_reference_repair": "0.6.8-core-first-reference-1",
}
```

Do **not** rename `structural_repairs_v067.py` or change its internal `INTEGRATED_ALGORITHM_VERSION = "0.6.7"` merely to match the new wrapper; that value documents the structural layer.

- [ ] **Step 3: Update current field-test state**

`CURRENT_FIELD_TEST_STATE.json` must report:

```json
{
  "algorithm_version": "0.6.8",
  "stable_engine_version": "0.4.5"
}
```

while preserving all unrelated current metadata.

- [ ] **Step 4: Classify all exact-version hits before editing**

```bash
rg -n '0\.6\.7|0\.9\.10-rc2|v096-app252-alonso-5' . \
  -g '!*.csv' -g '!*.zip' -g '!*.whl'
```

Update current-candidate assertions only. Preserve frozen historical reports/fixtures when `0.6.7` refers specifically to the prior structural integration.

- [ ] **Step 5: Decide software RC only from existing repository policy**

Default action: retain `SOFTWARE_VERSION = "0.9.10-rc2"` because this plan changes algorithm provenance independently. If an existing repository test or release-policy document explicitly requires a new software RC for every algorithm bump, change it consistently to `0.9.10-rc3`; do not infer such a policy from naming alone.

- [ ] **Step 6: Verify provenance**

```bash
pytest -q test_current_field_test_state.py tests_core/test_first_reference_repair.py test_app_v252.py
```

Expected: PASS with public algorithm 0.6.8 and stable engine 0.4.5.

- [ ] **Step 7: Commit**

```bash
git add biblioref/core/config.py biblioref/pipeline.py CURRENT_FIELD_TEST_STATE.json test_current_field_test_state.py
git commit -m "chore: version core first-reference reconciliation"
```

---

### Task 6: Full regression, SEDICI-10 verification and stacked draft PR

**Files:**
- Modify after evidence is known: `PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md`

**Interfaces:**
- Consumes: final implementation from Tasks 1–5.
- Produces: exact final verification evidence and a draft stacked PR; no merge.

- [ ] **Step 1: Run full repository suite with compatibility dependencies**

```bash
pytest -q
```

Expected: no regression relative to prior baseline `807 passed, 3 skipped, 16 subtests`, plus the newly added passing tests. Record exact new totals.

- [ ] **Step 2: Run PDFium-only lane**

```bash
python tools/run_pdfium_current_tests.py
```

Expected: PASS with PyMuPDF/`fitz` absent; only previously classified legacy comparator deselections remain.

- [ ] **Step 3: Run PyMuPDF legacy lane**

```bash
python tools/run_pymupdf_legacy_tests.py
```

Expected: PASS; historical compatibility coverage remains intact.

- [ ] **Step 4: Re-run frozen SEDICI-10 migration benchmark**

Use the existing repository differential tooling and unchanged corpus. Required counts:

```text
022=206
055=10
090=0
092=395
093=0
094=220
097=390
098=436
099=82
100=130
```

Expected: 10/10 migration gates PASS. Any unexpected count/semantic-zone change is a stop condition requiring investigation before documentation or PR creation.

- [ ] **Step 5: Update the differential report with observed evidence**

Append the exact final test totals and state:

```text
- app-level `_first_reference_guard` removed;
- recovery is core-owned under public algorithm 0.6.8;
- omitted-entry and deferred-author app/core parity fixtures pass;
- SEDICI-10 remains 10/10 with unchanged frozen counts;
- PDFium adapter unchanged;
- evidence remains an engineering migration validation, not human-gold precision/recall/F1.
```

- [ ] **Step 6: Commit the report**

```bash
git add PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md
git commit -m "docs: record core first-reference migration evidence"
```

- [ ] **Step 7: Push and verify all four GitHub Actions workflows on one exact HEAD**

Required successful workflows:

```text
Repository Test Gate
PyMuPDF-Free Isolation Gate
PyMuPDF Legacy Gate
Metadata Resolver Gate
```

Do not claim completion from stale or mixed commit SHAs.

- [ ] **Step 8: Open a stacked draft PR**

Head:

```text
feat/core-first-reference-repair
```

Base:

```text
feat/pdfium-test-harness-split
```

Title:

```text
refactor: move first-reference recovery into extraction core
```

PR body must state dependency on PR #34 and that it must not be merged independently into `dev` until the stack is resolved. Keep it draft; do not merge automatically.
