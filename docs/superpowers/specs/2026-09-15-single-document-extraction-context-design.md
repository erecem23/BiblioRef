# Single-Document Extraction Context v0.1 Design

**Date:** 2026-09-15

**Repository:** `erecem23/BiblioRef`

**Base branch:** `dev`

**Base commit:** `addc40c19a89877e9e36677941e477371c47fe20`

**Feature branch:** `feat/single-document-extraction-context-v0-1`

## Goal

Reduce end-to-end processing time for a single thesis without changing extraction quality, output ordering, zone decisions, repair decisions, post-extraction audit, coverage behavior, or public `process_pdf()` semantics.

The first optimization phase will eliminate redundant PDF access by introducing one execution-scoped context that reuses already-materialized document information. The context is an infrastructure optimization only: it must not weaken, approximate, bypass, reorder, or otherwise alter any extraction, repair, audit, or coverage decision.

## Background

BiblioRef already parallelizes work across multiple theses in the application layer, but one thesis remains the effective unit of work. The current extraction stack obtains a full document layout and then several downstream stages may reopen the same PDF or re-read page ranges independently.

Examples in the current tree include:

- `biblioref.pipeline._process_pdf_effective()` capturing the full `extract_layout_lines()` result;
- `biblioref.extraction.first_reference_repair.apply_first_reference_repair()` calling `extract_layout_lines_range()` for the first physical page of a zone;
- `biblioref.audit.coverage.build_coverage_report()` re-reading zone ranges and repeatedly querying page dimensions;
- raw-layout paths in numeric and column reconciliation opening the PDF again when their stronger geometry is required.

The PDFium backend already contains an LRU around its own layout extractor, but not every downstream range/dimension/raw-page access is routed through one shared execution-scoped cache. Repeated requests can therefore still cause physical document access, duplicated page parsing, and repeated dimension reads.

The human-gold benchmark remains frozen and outside the critical path for this work. This optimization phase uses existing regression suites, SEDICI gates, backend differential tests, and exact before/after semantic equivalence. It does not use human-gold labels and does not run primary human-gold scoring.

## Non-goals

This phase does **not**:

- change bibliography detection heuristics;
- change regexes, thresholds, confidence gates, or repair rules;
- change record text, order, page boundaries, zone topology, duplicate metadata, or audit decisions;
- change parser behavior or StyleProfiler behavior;
- redesign the application UI;
- parallelize pages inside a single thesis;
- keep a native PDF document handle open globally across unrelated components;
- make persistent caches survive across theses;
- optimize raw PDF geometry until profiling proves it is necessary;
- promise a fixed speedup before a measured baseline exists.

## Design principles

1. **Quality before speed.** Any optimization that changes semantic output is rejected.
2. **Reuse only exact data.** Cached information may be reused only when it is equivalent to the historical operation being replaced.
3. **Fallback to the historical path.** If an exact cache hit cannot be proven, the caller executes the existing operation unchanged.
4. **One context per `process_pdf()` execution.** No document state leaks into another thesis.
5. **Materialized immutable data over shared native handles.** The context shares values such as `LayoutLine` lists and dimensions, not an indiscriminately shared `PdfDocument` instance.
6. **Measure before optimizing deeper layers.** Instrumentation lands before raw-page or native-handle optimization.
7. **Profiler data is not part of normal public semantic output.** Timings and counters are collected by an opt-in profiling path so ordinary result contracts remain stable.

## Proposed architecture

Create an internal module:

```text
biblioref/ingestion/extraction_context.py
```

It defines an execution-scoped `ExtractionContext` and a `ContextVar`-backed activation helper, following the existing `backend_context.py` pattern.

Conceptually:

```text
process_pdf()
    |
    +-- ExtractionContext
          |- pdf_path
          |- backend
          |- full_layout
          |- lines_by_page
          |- range_layout_cache
          |- page_dimensions_cache
          |- raw_page_lines_cache        # reserved for later phase
          |- counters
          `- timings
                 |
                 +-- stable extraction
                 +-- structural reconciliation
                 +-- first-reference repair
                 +-- rescue audit
                 `-- coverage
```

The first implementation phase uses only the safe subset:

- `pdf_path`;
- active backend identity;
- `full_layout` once materialized;
- `lines_by_page` derived from that full layout;
- exact range-layout cache;
- page-dimensions cache;
- request/hit counters and timing buckets.

`raw_page_lines_cache` is part of the architecture but remains unused until a later profiling-backed phase because raw geometry can contain information not present in generic `LayoutLine` output.

## Context lifecycle

The public `biblioref.pipeline.process_pdf()` contract remains unchanged.

A context is created at the outer extraction call and activated only for that execution:

```python
context = ExtractionContext(pdf_path=pdf_path, backend=active_pdf_backend())
with use_extraction_context(context):
    result = _existing_process_pdf_flow(...)
```

Nested helpers can consult the active context without adding a `context=` argument throughout the codebase.

The context is discarded after the call returns or raises. No cache survives into a later thesis.

Nested or test calls without an active context continue to use the historical code path.

## Full-layout reuse

The current effective pipeline already captures the full `extract_layout_lines()` result. Once that result exists, the active context may receive it and build a deterministic page index:

```text
page 1 -> tuple[LayoutLine, ...]
page 2 -> tuple[LayoutLine, ...]
...
```

However, **full-layout slicing is not assumed to be equivalent to `extract_layout_lines_range()` merely because both return `LayoutLine` objects**. Before enabling that optimization for a backend, focused differential tests must prove that the historical range operation and the corresponding slice of the historical full-layout operation are exactly equal for representative fixtures and the same tolerance/semantics.

An `extract_layout_lines_range(path, start, end, ...)` request may be satisfied from `full_layout` only when all of the following are true:

- the requested path resolves to the same physical PDF;
- the backend matches the context backend;
- focused tests have established exact backend-specific equivalence between the historical full-layout slice and historical range operation for those semantics;
- the requested tolerance/semantics match the proven-equivalent contract;
- the requested range is wholly represented in `full_layout`;
- no caller requires raw/native geometry that generic layout does not preserve.

If any condition is not met, the existing range extractor runs unchanged. Its exact result may still be memoized under a key that includes document identity, backend, page range, tolerance, and any other semantic parameter, so later identical requests in the same execution can reuse the historical result without approximation.

This fail-closed behavior is critical: the context is allowed to miss optimization opportunities, but it is not allowed to approximate results.

## Page-dimension reuse

`page_dimensions(pdf_path, page_number)` becomes context-aware.

For the active document it first checks `page_dimensions_cache`. When dimensions are already available from an exact source, they are reused. Otherwise the historical backend-specific dimension call runs and the returned `(width, height)` pair is cached for the remainder of the extraction.

The cache key includes the resolved document identity, active backend, and physical page number. Invalid page requests retain the existing exception behavior.

## Initial consumers

### 1. First-reference repair

`biblioref/extraction/first_reference_repair.py` keeps the same function signatures and decision logic.

Its call to `extract_layout_lines_range(pdf_path, page, page)` becomes cheaper automatically only when the ingestion layer has an exact cache hit or a proven-equivalent full-layout slice. No heading vocabulary, author-opening score, year logic, or repair evidence changes.

### 2. Coverage audit

`biblioref/audit/coverage.py` remains semantically unchanged.

The ordinary range-layout path may reuse a proven-equivalent full-layout slice or an exact memoized historical range result. Repeated calls to `page_dimensions()` should hit the dimension cache.

The special multimodal-margin branch that intentionally uses raw page lines is not converted to generic cached layout in this phase. It remains on the historical raw geometry path.

### 3. Numeric and column paths

`numeric_rescue.py` and `column_reflow.py` are **not** optimized in the first implementation pass unless the profiler demonstrates that they dominate runtime after safe layout/dimension reuse.

Their direct/raw PDF reads remain untouched initially because raw geometry can differ from generic layout. A later phase may add an exact raw-page cache if measurement justifies it.

## Profiling tool

Create:

```text
tools/profile_single_pdf.py
```

The profiler runs the normal public pipeline and reports timing/counter information without modifying normal result semantics.

Example output:

```text
BiblioRef single-document profile

total                         24.83 s
full_layout                    8.11 s
effective_extraction           5.37 s
structural_reconciliation      2.03 s
first_reference_repair         0.28 s
rescue_audit                   3.74 s
coverage                       5.06 s

pdf_opens                         19
full_layout_extractions             1
range_layout_requests              11
range_layout_cache_hits             9
dimension_requests                 22
dimension_cache_hits               20
raw_page_reads                     17
```

The exact initial timing categories may be narrower if instrumenting a deeper category would require changing production semantics. Counters are more important than artificial timing granularity.

The profiler must clearly identify:

- repository/algorithm version;
- backend;
- PDF identity/hash or path plus size/mtime for reproducibility;
- whether caches were cold at process start;
- total wall-clock time;
- counters relevant to redundant access.

## Benchmark methodology

### Corpus

Use the existing SEDICI-10 regression corpus as the primary real-document performance/equivalence set because it already has known expected behavior and established gates.

Synthetic PDFs are permitted for unit tests of cache behavior but are not evidence of real-world speedup.

The frozen human-gold corpus is not used for optimization decisions in this phase.

### Execution discipline

For end-to-end timing comparisons:

- baseline and optimized builds run in fresh processes;
- use the same machine, Python version, dependency set, backend, and files;
- perform at least five measured runs per thesis per variant when practical;
- compare medians rather than single runs;
- do not rely on shared GitHub Actions runners as the authoritative speed benchmark.

CI validates correctness and reproducibility, not precise wall-clock performance.

## Semantic equivalence contract

Before and after optimization, the following must remain identical for the same input/options:

- `records` including full record dictionaries;
- record order;
- `zones`;
- duplicate metadata;
- `detection_decision`;
- repair reports;
- `post_extraction_audit`;
- `coverage_report`;
- selected scope output;
- public algorithm/software provenance except where a future release process intentionally updates a version field.

The preferred gate is direct equality wherever possible:

```python
before["records"] == after["records"]
```

For complete reports, use a semantic projection only to remove profiling-only metadata that is explicitly outside normal public output.

No normalization is allowed merely to make a changed result compare equal.

## Tests

Create focused tests under:

```text
tests_core/test_extraction_context.py
```

They should prove at minimum:

- no-context calls preserve historical behavior;
- a context is scoped to one document only;
- full-layout page indexing preserves order exactly;
- backend-specific full-layout slicing is used only after exact differential equivalence is established;
- identical historical range requests are memoized safely even when full-layout slicing is not eligible;
- non-equivalent tolerance/backend/path requests fall back;
- page dimensions are cached only for the active document/backend;
- exceptions and invalid ranges remain unchanged;
- context state is released after the outer call;
- nested/test usage does not contaminate another extraction.

Add an equivalence harness, likely under:

```text
tests_performance/test_single_pdf_equivalence.py
```

or an existing benchmark-test location if repository conventions make that more appropriate during implementation planning.

The harness should compare baseline and optimized semantic projections over existing regression documents without turning wall-clock thresholds into flaky CI assertions.

## Required gates

Each optimization increment must pass, in this order:

1. focused context/cache tests, including full-vs-range backend differential tests;
2. adjacent pipeline/audit tests;
3. complete repository test suite;
4. PDFium-only validation;
5. PyMuPDF compatibility lane where supported;
6. frozen SEDICI-10 regression/equivalence gate;
7. before/after semantic equality report;
8. reproducible local performance benchmark.

A performance improvement that changes one reference, its order, a zone, or an extraction/audit/coverage decision fails the gate regardless of speedup.

## Success criteria

The first success criterion is structural, not a guessed speed number:

- demonstrably fewer redundant physical/range/dimension PDF accesses;
- zero semantic differences on the required gates;
- no cross-document cache leakage;
- bounded memory growth per thesis;
- profiler identifies the next dominant cost after safe reuse.

After the baseline exists, the practical target for this first optimization iteration is at least a 15% median end-to-end reduction across the measured real-document corpus if redundant safe-to-remove reads are a meaningful portion of runtime.

This is a target, not a correctness gate. If semantic equivalence is exact and redundant accesses collapse substantially but end-to-end improvement is smaller, the result is still useful evidence for the next bottleneck. Conversely, a large speedup with semantic drift is unacceptable.

A stable regression above approximately 5% on an individual thesis must be investigated before integration.

## Implementation phases

### Phase 1 — instrumentation and baseline

- add execution counters/timing hooks;
- add `tools/profile_single_pdf.py`;
- capture reproducible SEDICI-10 baseline data;
- make no performance-changing optimization yet.

### Phase 2 — safe context reuse

- add `ExtractionContext` and `ContextVar` activation;
- capture the already-materialized full layout;
- build `lines_by_page`;
- add backend-specific differential tests for full-layout slice versus historical range extraction;
- enable full-layout range reuse only for contracts proven exactly equivalent;
- otherwise memoize only exact historical range results;
- cache `page_dimensions()`;
- leave decision logic unchanged.

### Phase 3 — remeasure

- rerun equivalence gates;
- rerun profiler and real-document timings;
- quantify reductions in range reads, dimension reads, and total wall time;
- identify the new dominant cost.

### Phase 4 — optional raw geometry optimization

Only if Phase 3 proves raw page access is now material:

- design an exact raw-page cache;
- preserve backend/raw geometry semantics;
- add independent tests before migrating numeric or column consumers;
- do not introduce internal page parallelism in the same change.

Phase 4 is not automatically part of v0.1 implementation; it requires profiling evidence and a separate design/approval if its scope becomes architectural.

## Expected file impact for v0.1

**Create**

- `biblioref/ingestion/extraction_context.py`
- `tools/profile_single_pdf.py`
- `tests_core/test_extraction_context.py`
- an equivalence/performance harness in the repository's appropriate test/benchmark location

**Likely modify**

- `biblioref/pipeline.py`
- `biblioref/ingestion/pdf.py`
- `biblioref/extraction/first_reference_repair.py` only if explicit context integration is needed beyond ingestion-level reuse
- `biblioref/audit/coverage.py` only where necessary for exact context reuse/profiling

**Preserve in the initial safe phase**

- extraction heuristics and pattern constants;
- `biblioref/extraction/numeric_rescue.py` raw geometry behavior;
- `biblioref/extraction/column_reflow.py` raw geometry behavior;
- parser/resolver/StyleProfiler behavior;
- human-gold benchmark source/gold/evaluation state.

## Failure handling

The context must fail closed.

If cache state is absent, mismatched, incomplete, or cannot prove equivalence, the historical operation runs. Cache failures must not convert an otherwise valid extraction into a fatal failure unless the historical operation itself would have failed.

Instrumentation must never swallow production exceptions or change fallback behavior.

## Rollback strategy

The optimization is designed so that disabling/removing context activation returns the system to the historical access pattern without changing extraction rules.

Because the first phase does not modify heuristics or raw geometry, rollback should consist primarily of removing the context-aware reuse path rather than reverting extraction logic.

## Decision summary

Approved direction: execution-scoped shared context, not ad-hoc global memoization and not internal page parallelism.

The context optimizes repeated access to already-known document information while retaining all current diagnostics (`shadow`, rescue audit, coverage) and exact extraction semantics.

The first implementation stops after profiling plus safe full-layout/range/dimension reuse and remeasurement. Deeper raw-geometry caching or internal parallelism requires evidence from that profile and is not assumed in advance.
