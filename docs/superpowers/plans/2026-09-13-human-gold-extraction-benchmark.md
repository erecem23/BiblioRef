# Human-Gold Extraction Benchmark v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the independent human-gold extraction benchmark infrastructure, freeze a new source sample, and prepare a visual-first annotation package without modifying BiblioRef extraction heuristics.

**Architecture:** Keep benchmark code under `tools/human_gold`, benchmark data under `benchmarks/human_gold_v0_1`, and tests under `tests_benchmarks`. Sampling and gold validation are independent of BiblioRef output; the evaluator calls only the public `biblioref.pipeline.process_pdf()` interface after a candidate is frozen. Human annotations remain the authority and the primary set is not scored until source selection, schema, matching rules and candidate provenance are frozen.

**Tech Stack:** Python 3.11, pytest, FastAPI/uvicorn already present in `requirements-app.txt`, pypdfium2 for page rendering only, stdlib JSON/CSV/hashlib/random/statistics, optional numpy only if already installed by current test requirements; otherwise implement metrics with stdlib.

**Spec:** `docs/superpowers/specs/2026-09-13-human-gold-extraction-benchmark-design.md`

## Global Constraints

- Base the work on the current `dev` lineage whose pre-design baseline is `f185f96fc850084b8da785e06a83df99e452e59a`.
- Do not modify extraction heuristics, bibliography-heading vocabularies, structural repair rules, first-reference repair, PDF adapters, parser, resolver or StyleProfiler.
- Do not use BiblioRef output to select primary or stress documents.
- Do not include SEDICI-10 or any known development/challenge document in the primary benchmark.
- Human labels come from rendered PDF pages; BiblioRef output never pre-populates zone or reference boundaries.
- Deterministic selection seed is `20260913`.
- Primary set is 32 theses; stress set is 8; pilot is 6.
- No repository contributes more than 25% of the primary set.
- Headline uncertainty uses document-cluster bootstrap with seed `20260913` and at least 10,000 resamples.
- Initial record-start y tolerance is `0.015` page height and must be frozen after pilot/tool validation but before primary scoring.
- Normal CI tests only synthetic benchmark fixtures. Full human-gold scoring is manual and SHA-pinned.
- Work must stop before inventing or auto-generating primary human labels.

---

## File Structure

**Create**
- `tools/human_gold/__init__.py` — benchmark-tool package marker.
- `tools/human_gold/schema.py` — typed validation and JSONL I/O.
- `tools/human_gold/build_exclusion_registry.py` — collect known development identities.
- `tools/human_gold/sample_sources.py` — deterministic metadata-only sampling.
- `tools/human_gold/annotation_app.py` — local FastAPI visual annotation application.
- `tools/human_gold/metrics.py` — matching, metrics and bootstrap.
- `tools/human_gold/evaluate.py` — public-pipeline benchmark runner.
- `tools/human_gold/validate_gold.py` — CLI validation entry point.
- `tests_benchmarks/test_human_gold_schema.py`.
- `tests_benchmarks/test_human_gold_sampling.py`.
- `tests_benchmarks/test_human_gold_annotation_app.py`.
- `tests_benchmarks/test_human_gold_matching.py`.
- `tests_benchmarks/test_human_gold_metrics.py`.
- `tests_benchmarks/test_human_gold_no_production_mutation.py`.
- `benchmarks/human_gold_v0_1/README.md`.
- `benchmarks/human_gold_v0_1/selection_config.json`.
- `benchmarks/human_gold_v0_1/exclusion_registry.jsonl`.
- `benchmarks/human_gold_v0_1/source_manifest.jsonl` after source freeze.
- `benchmarks/human_gold_v0_1/SHA256SUMS.txt` after source freeze.
- `.github/workflows/human-gold-v0-1.yml` — manual scoring workflow, disabled until gold exists.

**Modify**
- `.gitignore` — ignore local benchmark PDF cache and annotation autosave scratch files.

**Must remain production-semantically unchanged in this phase**
- `biblioref/**`.
- `app.py`.

---

### Task 1: Define benchmark schemas and fail-closed validation

**Files:**
- Create: `tools/human_gold/schema.py`
- Create: `tests_benchmarks/test_human_gold_schema.py`

**Interfaces:**
- Produces `load_jsonl(path: Path) -> list[dict]`.
- Produces `validate_manifest(rows: list[dict]) -> None`.
- Produces `validate_gold(manifest_rows: list[dict], gold_rows: list[dict]) -> None`.
- Raises `ValueError` with deterministic messages on integrity violations.

- [ ] **Step 1: Write RED tests for manifest integrity**

Create tests covering duplicate `document_id`, invalid SHA-256, invalid partition, duplicate SHA, and missing `selected_before_biblioref_run=true`.

```python
from tools.human_gold.schema import validate_manifest


def test_manifest_rejects_duplicate_document_id():
    rows = [
        {"document_id": "d1", "partition": "primary", "sha256": "a" * 64,
         "selected_before_biblioref_run": True},
        {"document_id": "d1", "partition": "primary", "sha256": "b" * 64,
         "selected_before_biblioref_run": True},
    ]
    with pytest.raises(ValueError, match="duplicate document_id: d1"):
        validate_manifest(rows)
```

- [ ] **Step 2: Write RED tests for gold integrity**

Gold tests must reject:

```text
duplicate gold_zone_id
duplicate gold_ref_id
ordinal sequence not 1..N within zone
reference start outside zone pages
y ratio outside 0..1
manifest SHA mismatch
missing annotation_complete=true
missing required full-text sample
```

- [ ] **Step 3: Run RED**

Run:

```bash
pytest -q tests_benchmarks/test_human_gold_schema.py
```

Expected: collection/import failure because `tools.human_gold.schema` does not exist.

- [ ] **Step 4: Implement minimal schema validation**

Use stdlib only. Keep records as JSON-compatible dictionaries; do not introduce pydantic into production requirements.

Required top-level gold object shape:

```python
{
    "document_id": str,
    "document_sha256": str,
    "annotator_id": str,
    "annotation_complete": bool,
    "document_has_target_bibliography": bool,
    "zones": list[dict],
    "full_text_sample_ids": list[str],
}
```

Each zone contains `gold_zone_id`, `role`, `start_page`, `end_page`, `start_y_ratio`, `end_y_ratio`, `heading_present`, `heading_text`, and `references`.

Each reference contains `gold_ref_id`, `ordinal`, `start_page`, `start_y_ratio`, `start_anchor`, `flags`, and optional `visible_text_gold`.

- [ ] **Step 5: Run GREEN**

```bash
pytest -q tests_benchmarks/test_human_gold_schema.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/human_gold/schema.py tools/human_gold/__init__.py tests_benchmarks/test_human_gold_schema.py
git commit -m "test: define human-gold benchmark schema"
```

---

### Task 2: Build the development-exclusion registry and deterministic sampler

**Files:**
- Create: `tools/human_gold/build_exclusion_registry.py`
- Create: `tools/human_gold/sample_sources.py`
- Create: `tests_benchmarks/test_human_gold_sampling.py`
- Create: `benchmarks/human_gold_v0_1/selection_config.json`

**Interfaces:**
- Produces `normalize_identity(row: dict) -> set[str]`.
- Produces `is_excluded(candidate: dict, exclusion_rows: list[dict]) -> bool`.
- Produces `sample_candidates(candidates: list[dict], config: dict) -> list[dict]`.
- CLI sampler never imports `biblioref`.

- [ ] **Step 1: Write RED identity/leakage tests**

Test exact SHA, normalized stable URL, stable identifier, and normalized `title|institution|year` fallback matching.

```python
def test_exact_sha_is_excluded():
    candidate = {"sha256": "a" * 64}
    exclusions = [{"sha256": "a" * 64, "reason": "SEDICI-10"}]
    assert is_excluded(candidate, exclusions)
```

- [ ] **Step 2: Write RED deterministic-sampling tests**

Create 80 synthetic candidates across 10 repositories and verify:

```python
sample_a = sample_candidates(candidates, config)
sample_b = sample_candidates(list(reversed(candidates)), config)
assert [r["document_id"] for r in sample_a] == [r["document_id"] for r in sample_b]
assert len([r for r in sample_a if r["partition"] == "primary"]) == 32
assert max(Counter(r["repository"] for r in sample_a if r["partition"] == "primary").values()) <= 8
```

The sampler must sort candidates by a stable key before seeded selection so input ordering cannot alter the result.

- [ ] **Step 3: Run RED**

```bash
pytest -q tests_benchmarks/test_human_gold_sampling.py
```

Expected: FAIL because sampling module does not exist.

- [ ] **Step 4: Implement the exclusion registry builder**

The builder must collect machine-readable identities where available from:

```text
benchmarks/*.jsonl
benchmarks/*.csv
benchmarks/evidence/**
CURRENT_FIELD_TEST_STATE.json
known repository challenge/development manifests present in the repo
```

Also support a checked-in manual supplement list for documented development PDFs that exist only in reports. Each registry row records `identity_type`, `identity`, `source_file`, and `reason`.

Do not infer exclusion from BiblioRef success/failure.

- [ ] **Step 5: Implement `selection_config.json`**

Freeze:

```json
{
  "benchmark_version": "human_gold_v0_1",
  "seed": 20260913,
  "pilot_n": 6,
  "primary_n": 32,
  "stress_n": 8,
  "max_primary_share_per_repository": 0.25,
  "min_primary_repositories": 8,
  "min_countries": 4,
  "min_languages": 3,
  "time_bands": [
    {"name": "pre_2015", "max_year": 2014, "min_n": 8},
    {"name": "2015_2020", "min_year": 2015, "max_year": 2020, "min_n": 8},
    {"name": "2021_2026", "min_year": 2021, "max_year": 2026, "min_n": 8}
  ]
}
```

- [ ] **Step 6: Implement sampler**

Primary selection uses metadata only. Stress selection accepts a separate human-curated pre-output candidate list containing visual difficulty labels; it must not call BiblioRef.

Sampler output rows include `selection_rank`, `selection_seed`, and `selected_before_biblioref_run=true`.

- [ ] **Step 7: Run GREEN**

```bash
pytest -q tests_benchmarks/test_human_gold_sampling.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/human_gold/build_exclusion_registry.py tools/human_gold/sample_sources.py tests_benchmarks/test_human_gold_sampling.py benchmarks/human_gold_v0_1/selection_config.json
git commit -m "feat: add leakage-safe human-gold sampling"
```

---

### Task 3: Build the visual-first local annotation app

**Files:**
- Create: `tools/human_gold/annotation_app.py`
- Create: `tests_benchmarks/test_human_gold_annotation_app.py`
- Modify: `.gitignore`

**Interfaces:**
- CLI: `python -m tools.human_gold.annotation_app --manifest PATH --pdf-cache PATH --output PATH --annotator ID`.
- HTTP GET `/api/document/{document_id}/page/{page}` returns rendered PNG.
- HTTP GET `/api/document/{document_id}/annotation` returns current annotation draft only.
- HTTP POST `/api/document/{document_id}/annotation` persists user-supplied labels.
- No endpoint calls `biblioref.pipeline.process_pdf()`.

- [ ] **Step 1: Write RED import-separation test**

Patch `builtins.__import__` and fail if `biblioref` is imported while loading `tools.human_gold.annotation_app`.

- [ ] **Step 2: Write RED API tests**

Using `fastapi.testclient.TestClient`, verify a one-page synthetic PDF can be rendered and a posted annotation round-trips exactly.

```python
response = client.post("/api/document/d1/annotation", json=annotation)
assert response.status_code == 200
assert client.get("/api/document/d1/annotation").json() == annotation
```

- [ ] **Step 3: Run RED**

```bash
pytest -q tests_benchmarks/test_human_gold_annotation_app.py
```

Expected: FAIL because app does not exist.

- [ ] **Step 4: Implement PDF rendering**

Use `pypdfium2.PdfDocument` directly. Render one page on demand to PNG bytes. Annotation coordinates are browser/image ratios in `[0,1]`; do not expose PDFium text lines to define click targets.

- [ ] **Step 5: Implement minimal browser UI**

Serve one HTML page with vanilla JavaScript that can:

```text
navigate pages
mark zone start/end by clicking page image
add ordered reference-start clicks
edit start_anchor text manually
mark reference flags
show deterministic full-text transcription tasks
save draft
mark document annotation_complete
```

Do not display BiblioRef predicted zones, counts or records.

- [ ] **Step 6: Add autosave safety**

Write draft atomically via temporary file + `os.replace`. Keep an append-only `.history.jsonl` containing timestamp and SHA-256 of each submitted document annotation.

Add to `.gitignore`:

```text
benchmarks/human_gold_v0_1/pdf_cache/
benchmarks/human_gold_v0_1/annotation_work/
*.annotation.tmp
```

- [ ] **Step 7: Run GREEN**

```bash
pytest -q tests_benchmarks/test_human_gold_annotation_app.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/human_gold/annotation_app.py tests_benchmarks/test_human_gold_annotation_app.py .gitignore
git commit -m "feat: add visual human-gold annotation app"
```

---

### Task 4: Implement frozen matching and metrics on synthetic gold

**Files:**
- Create: `tools/human_gold/metrics.py`
- Create: `tests_benchmarks/test_human_gold_matching.py`
- Create: `tests_benchmarks/test_human_gold_metrics.py`

**Interfaces:**
- `match_zones(gold_zones, predicted_zones, iou_threshold=0.50) -> dict`.
- `align_boundaries(gold_refs, predicted_refs, y_tolerance=0.015) -> dict`.
- `text_fidelity(gold_text: str, predicted_text: str) -> dict`.
- `summarize_documents(document_results, bootstrap_seed=20260913, bootstrap_n=10000) -> dict`.

- [ ] **Step 1: Write RED zone-matching tests**

Cover exact match, partial overlap, missed zone, extra zone and deterministic one-to-one tie-breaking.

- [ ] **Step 2: Write RED boundary tests**

Synthetic cases must explicitly cover:

```text
exact boundaries
missed first reference
one merged pair
one split reference
spurious predicted start
same count but shifted boundaries
page mismatch
missing predicted physical y with anchor fallback
```

Assert that equal counts do not imply perfect F1.

- [ ] **Step 3: Write RED text-fidelity tests**

Canonicalization may only normalize whitespace and discretionary soft hyphen. Verify punctuation deletion lowers similarity.

- [ ] **Step 4: Write RED bootstrap determinism test**

```python
s1 = summarize_documents(results, bootstrap_seed=20260913, bootstrap_n=1000)
s2 = summarize_documents(results, bootstrap_seed=20260913, bootstrap_n=1000)
assert s1["macro_boundary_f1_ci95"] == s2["macro_boundary_f1_ci95"]
```

Use 1000 resamples in unit tests for speed; production default remains 10000.

- [ ] **Step 5: Run RED**

```bash
pytest -q tests_benchmarks/test_human_gold_matching.py tests_benchmarks/test_human_gold_metrics.py
```

Expected: FAIL because metrics module does not exist.

- [ ] **Step 6: Implement matching**

Zone IoU uses inclusive page intervals. Boundary alignment is monotonic and never reorders predictions. When both y coordinates exist, page equality + absolute y difference `<= 0.015` determines the start match. When predicted y is unresolved, use conservative normalized prefix matching against `start_anchor`; unresolved cases remain separately counted.

- [ ] **Step 7: Implement metrics**

Return explicit integer numerators/denominators alongside ratios. Include:

```text
zone page P/R/F1
zone IoU>=0.50 P/R/F1
boundary P/R/F1
macro boundary F1
count MAE/median AE/exact-count rate
first-reference miss rate
last-reference miss rate
split/merge counts
CER/WER/normalized Levenshtein/exact canonical rate
review-vs-no-review error summaries
```

- [ ] **Step 8: Implement document-cluster bootstrap**

Resample documents with replacement, recompute requested headline metrics, and return percentile 2.5/97.5 bounds. Do not resample references independently.

- [ ] **Step 9: Run GREEN**

```bash
pytest -q tests_benchmarks/test_human_gold_matching.py tests_benchmarks/test_human_gold_metrics.py
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add tools/human_gold/metrics.py tests_benchmarks/test_human_gold_matching.py tests_benchmarks/test_human_gold_metrics.py
git commit -m "feat: add frozen human-gold scoring rules"
```

---

### Task 5: Build the evaluator without creating a benchmark-specific extraction path

**Files:**
- Create: `tools/human_gold/evaluate.py`
- Create: `tools/human_gold/validate_gold.py`
- Create: `tests_benchmarks/test_human_gold_no_production_mutation.py`

**Interfaces:**
- CLI validator: `python -m tools.human_gold.validate_gold --manifest ... --gold ...`.
- CLI evaluator: `python -m tools.human_gold.evaluate --manifest ... --gold ... --pdf-cache ... --output-dir ...`.
- Evaluator calls `biblioref.pipeline.process_pdf(path, scope="all_reference_sections")` exactly once per document unless a fatal error is retried explicitly and recorded.

- [ ] **Step 1: Write RED public-interface test**

Monkeypatch only `biblioref.pipeline.process_pdf` and assert evaluator calls it with:

```python
scope="all_reference_sections"
```

and no benchmark-only arguments.

- [ ] **Step 2: Write RED production-import-direction test**

Scan `biblioref/**/*.py` and `app.py`; fail if any production file contains imports from `tools.human_gold` or paths under `benchmarks/human_gold_v0_1`.

- [ ] **Step 3: Write RED output-shape test**

Given synthetic gold + stub predictions, evaluator writes:

```text
results.json
per_document.jsonl
summary.md
bootstrap.json
environment.json
SHA256SUMS.txt
```

- [ ] **Step 4: Run RED**

```bash
pytest -q tests_benchmarks/test_human_gold_no_production_mutation.py
```

Expected: FAIL because evaluator is absent.

- [ ] **Step 5: Implement predicted-start localization adapter**

Use record metadata first. If physical y is not already exposed, locate the predicted opening on the recorded start page using the same public PDF layout access available to tools, but do not change the record. Store localization status:

```text
metadata
layout_match
anchor_only
unresolved
```

Unresolved is a scored diagnostic, not silently dropped.

- [ ] **Step 6: Implement evaluator output**

Every results bundle records:

```json
{
  "benchmark_version": "human_gold_v0_1",
  "candidate_git_sha": "...",
  "software_version": "...",
  "algorithm_version": "...",
  "manifest_sha256": "...",
  "gold_sha256": "...",
  "selection_seed": 20260913,
  "boundary_y_tolerance": 0.015,
  "bootstrap_seed": 20260913,
  "bootstrap_n": 10000
}
```

- [ ] **Step 7: Run GREEN**

```bash
pytest -q tests_benchmarks/test_human_gold_no_production_mutation.py
pytest -q tests_benchmarks
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/human_gold/evaluate.py tools/human_gold/validate_gold.py tests_benchmarks/test_human_gold_no_production_mutation.py
git commit -m "feat: add public-interface human-gold evaluator"
```

---

### Task 6: Run a six-document pilot to validate tooling only

**Files:**
- Create/update: `benchmarks/human_gold_v0_1/README.md`
- Create: `benchmarks/human_gold_v0_1/pilot/source_manifest.jsonl`
- Create: pilot raw annotations and pilot evaluator evidence as permitted.

**Interfaces:**
- Consumes Tasks 1-5.
- Produces a frozen annotation/scoring protocol; does not change extraction code.

- [ ] **Step 1: Acquire six pilot theses using the sampler**

Pilot sources may be inspected and scored because they are not headline test items. Verify all SHA-256 values.

- [ ] **Step 2: Exercise the annotation app manually**

For each pilot PDF, create complete zone + reference-start labels and required full-text samples. This step must be performed by a human. An agent may render and navigate pages but must not author final labels on the human's behalf.

If no human annotation is available in the current Work run, stop this task at the point where the annotation package is ready and report the exact command/URL to continue.

- [ ] **Step 3: Validate pilot gold**

```bash
python -m tools.human_gold.validate_gold \
  --manifest benchmarks/human_gold_v0_1/pilot/source_manifest.jsonl \
  --gold benchmarks/human_gold_v0_1/pilot/gold.jsonl
```

Expected: PASS.

- [ ] **Step 4: Run pilot evaluator**

Pilot results are allowed solely to prove the scoring machinery works. Do not modify `biblioref/**` or `app.py` in response to pilot extraction errors.

- [ ] **Step 5: Freeze tolerance and schema**

If coordinate mechanics prove the `0.015` tolerance is technically invalid because of rendering-coordinate conversion, fix the evaluator mechanics now and document the final tolerance before primary annotation. Do not choose a tolerance based on which value improves BiblioRef accuracy.

- [ ] **Step 6: Commit pilot-tooling evidence**

```bash
git add benchmarks/human_gold_v0_1/README.md benchmarks/human_gold_v0_1/pilot
git commit -m "test: validate human-gold tooling on pilot corpus"
```

---

### Task 7: Freeze the primary/stress source manifest without running BiblioRef

**Files:**
- Create: `benchmarks/human_gold_v0_1/exclusion_registry.jsonl`
- Create: `benchmarks/human_gold_v0_1/source_manifest.jsonl`
- Create/update: `benchmarks/human_gold_v0_1/SHA256SUMS.txt`
- Create/update: `benchmarks/human_gold_v0_1/README.md`

**Interfaces:**
- Produces the exact 32 primary + 8 stress identities used by human annotation.

- [ ] **Step 1: Build exclusion registry**

```bash
python -m tools.human_gold.build_exclusion_registry \
  --repo-root . \
  --output benchmarks/human_gold_v0_1/exclusion_registry.jsonl
```

Inspect entries for SEDICI-10, previous challenge/dev PDFs and known manually diagnosed cases.

- [ ] **Step 2: Gather a candidate pool from public repositories**

Use repository metadata and access rules only. Do not run `process_pdf()` on candidate PDFs before selection. Download only to compute SHA-256 and confirm readable bitstreams; do not inspect BiblioRef output.

- [ ] **Step 3: Run deterministic selection**

```bash
python -m tools.human_gold.sample_sources \
  --candidates /tmp/hg_candidates.jsonl \
  --exclusions benchmarks/human_gold_v0_1/exclusion_registry.jsonl \
  --config benchmarks/human_gold_v0_1/selection_config.json \
  --output benchmarks/human_gold_v0_1/source_manifest.jsonl
```

- [ ] **Step 4: Verify composition before any extraction run**

Assert:

```text
primary = 32
stress = 8
primary max per repository <= 8
primary repositories >= 8 when feasible
countries >= 4
languages >= 3
all SHA unique
no excluded identity
selected_before_biblioref_run = true for all
```

If an availability constraint prevents a target, record it in README before continuing.

- [ ] **Step 5: Freeze hashes**

Write SHA-256 for selection config, exclusion registry, source manifest and every locally acquired PDF into `SHA256SUMS.txt`.

- [ ] **Step 6: Commit source freeze**

```bash
git add benchmarks/human_gold_v0_1/exclusion_registry.jsonl benchmarks/human_gold_v0_1/source_manifest.jsonl benchmarks/human_gold_v0_1/SHA256SUMS.txt benchmarks/human_gold_v0_1/README.md
git commit -m "data: freeze human-gold v0.1 source sample"
```

This commit becomes part of the benchmark provenance.

---

### Task 8: Add manual workflow and candidate-freeze guard

**Files:**
- Create: `.github/workflows/human-gold-v0-1.yml`
- Modify: `tests_benchmarks/test_human_gold_no_production_mutation.py`

**Interfaces:**
- Workflow runs only via `workflow_dispatch`.
- Inputs: gold artifact/path and explicit candidate SHA.
- Fails on any manifest/PDF SHA mismatch.

- [ ] **Step 1: Add RED test that workflow is manual-only**

Parse YAML text and assert it contains `workflow_dispatch` and no `push` or `pull_request` trigger.

- [ ] **Step 2: Add RED candidate provenance test**

Evaluator must refuse to claim a frozen run if candidate SHA is missing or if recorded provenance cannot be resolved.

- [ ] **Step 3: Implement workflow**

Workflow steps:

```text
checkout requested candidate SHA
set up Python 3.11
install benchmark/runtime requirements
restore/download SHA-pinned PDF cache
verify every PDF SHA
obtain frozen gold supplied for the manual run
validate gold
run evaluator
upload evidence artifact
```

Do not put human-gold scoring into the ordinary repository gate.

- [ ] **Step 4: Run tests**

```bash
pytest -q tests_benchmarks
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/human-gold-v0-1.yml tests_benchmarks/test_human_gold_no_production_mutation.py
git commit -m "ci: add manual human-gold benchmark workflow"
```

---

### Task 9: Prove benchmark infrastructure did not alter extraction and stop for human annotation

**Files:**
- No production modifications allowed.
- Update: `benchmarks/human_gold_v0_1/README.md` with exact handoff state.

**Interfaces:**
- Produces the candidate commit to be annotated/scored later.

- [ ] **Step 1: Compare against implementation start**

Use git diff/compare to verify benchmark commits do not semantically modify:

```text
biblioref/**
app.py
```

If `dev` moved independently during implementation, rebase and separate upstream changes from benchmark changes before making this assertion.

- [ ] **Step 2: Run benchmark tests**

```bash
pytest -q tests_benchmarks
```

Expected: all PASS.

- [ ] **Step 3: Run repository regression gate**

Use the repository's documented full test command/workflow. Expected: no regression relative to current `dev` gates.

- [ ] **Step 4: Record candidate SHA**

Append to README:

```text
source_manifest_sha256 = ...
exclusion_registry_sha256 = ...
selection_config_sha256 = ...
candidate_git_sha = ...
algorithm_version = 0.6.8 (unless dev legitimately advanced before this work)
boundary_y_tolerance = 0.015 or the pilot-frozen mechanics value
primary_metrics_observed = false
```

- [ ] **Step 5: Prepare human annotation command**

Provide the user exactly:

```bash
python -m tools.human_gold.annotation_app \
  --manifest benchmarks/human_gold_v0_1/source_manifest.jsonl \
  --pdf-cache benchmarks/human_gold_v0_1/pdf_cache \
  --output benchmarks/human_gold_v0_1/annotation_work \
  --annotator <human-id>
```

- [ ] **Step 6: STOP**

Do not create `frozen_gold.jsonl` by model inference. Do not run headline primary scoring. Do not change heuristics based on unlabelled/previewed benchmark documents.

Report that infrastructure/source freeze is complete and the next required action is human annotation.

- [ ] **Step 7: Commit handoff state**

```bash
git add benchmarks/human_gold_v0_1/README.md
git commit -m "docs: freeze human-gold annotation handoff"
```

---

## Post-annotation continuation — execute only after human labels exist

This section is intentionally not part of the initial Work run unless the user supplies completed human annotations.

1. Validate raw annotations.
2. Perform/adjudicate the 25% quality-control subset.
3. Build `frozen_gold.jsonl` without consulting predictions.
4. Record its SHA-256.
5. Confirm candidate SHA was frozen before metrics.
6. Run exactly one primary evaluation.
7. Archive `results.json`, `per_document.jsonl`, `summary.md`, `bootstrap.json`, `environment.json` and hashes.
8. Do not alter extraction heuristics in the same evaluation PR.
9. Report primary and stress metrics separately.
10. Mark `human_gold_v0_1` as observed/blocked for future rule design.

## Self-review checklist for the executor

Before claiming this plan complete, verify all of the following:

- no benchmark selection code imports BiblioRef;
- annotation UI shows no predictions;
- source manifest was frozen before primary extraction output was observed;
- exclusion registry includes the known engineering/development corpora;
- matching/tolerance rules were frozen before primary scoring;
- benchmark tooling tests are green;
- ordinary repository tests remain green;
- `biblioref/**` and `app.py` were not changed by benchmark work;
- no primary human label was generated by an LLM/agent;
- no headline precision/recall/F1 was reported before human annotation and candidate freeze.
