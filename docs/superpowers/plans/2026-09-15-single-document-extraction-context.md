# Single-Document Extraction Context v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce single-thesis end-to-end processing time by reusing exact PDF information inside one `process_pdf()` execution without changing extraction, repair, audit, coverage, ordering, or public-result semantics.

**Architecture:** Add one execution-scoped `ExtractionContext` backed by `ContextVar`. Land instrumentation first, then enable only fail-closed reuse: identical historical range requests, exact page-dimension results, and full-layout slicing only for backend/tolerance combinations proven byte-for-byte equivalent at the `LayoutLine` level. Normal public results never contain profiler state.

**Tech Stack:** Python 3.11, stdlib `contextvars`, `dataclasses`, `collections.Counter`, `time.perf_counter`, pytest/unittest, existing PyMuPDF/PDFium abstraction, existing SEDICI-10 migration gate.

**Spec:** `docs/superpowers/specs/2026-09-15-single-document-extraction-context-design.md`

## Global Constraints

- Base: `dev` at `addc40c19a89877e9e36677941e477371c47fe20`.
- Branch: `feat/single-document-extraction-context-v0-1`.
- Do not change bibliography heuristics, regexes, thresholds, confidence gates, repair rules, parser, resolver, StyleProfiler, record ordering, or zone semantics.
- Keep `shadow`, rescue audit, and coverage active in the normal route.
- Human-gold remains frozen and out of scope. Do not run primary human-gold scoring or use its labels for tuning.
- Exact output equivalence has priority over speed. Any change in `records`, `zones`, duplicate metadata, `detection_decision`, repair reports, `post_extraction_audit`, `coverage_report`, or selected scope fails the gate.
- Context state lives for one thesis only and must reset after the outer call.
- Reuse only exact data. If equivalence is not proven, execute the historical operation.
- Do not keep one native PDF handle globally shared across components.
- Do not modify raw-geometry behavior in `numeric_rescue.py` or `column_reflow.py` in v0.1.
- Do not add wall-clock thresholds to CI. Performance evidence uses fresh processes and medians on one fixed machine.
- The >=15% end-to-end reduction is a target after baseline measurement, not a correctness gate.

## File Structure

**Create**
- `biblioref/ingestion/extraction_context.py` — context identity, caches, counters, timings, activation.
- `tests_core/test_extraction_context.py` — lifecycle, isolation, cache and fallback tests.
- `tools/profile_single_pdf.py` — one-run profiler with reuse on/off.
- `tests_core/test_single_pdf_context_equivalence.py` — exact public-pipeline equivalence.
- `SINGLE_DOCUMENT_EXTRACTION_CONTEXT_V0_1_REPORT.md` — final gate/performance evidence.

**Modify**
- `biblioref/ingestion/pdf.py` — instrumentation, exact range memoization, exact dimension cache, evidence-gated full-layout slicing.
- `biblioref/pipeline.py` — outer context ownership and stage timings.
- `biblioref/pipeline_v065.py` — rescue-audit, coverage and two-pass timings only.
- `tests_core/test_biblioref_v0_8_11_performance.py` — preserve existing performance contracts and add no-profiler-output checks.
- `tests_core/test_pdfium_dual_backend.py` — exact full/range probes per backend.

**Must remain semantically unchanged**
- `biblioref/extraction/first_reference_repair.py`.
- `biblioref/audit/coverage.py`.
- `biblioref/extraction/numeric_rescue.py`.
- `biblioref/extraction/column_reflow.py`.
- `app.py`, parser, resolver, StyleProfiler and human-gold files/workflow.

---

### Task 1: Add the execution-scoped monitor-only context

**Files:**
- Create: `biblioref/ingestion/extraction_context.py`
- Create: `tests_core/test_extraction_context.py`

**Interfaces:**
- Produces `ExtractionContext.for_pdf(pdf_path, backend, reuse_enabled=True)`.
- Produces `current_extraction_context()`.
- Produces `use_extraction_context(context)`.
- Produces `timed_extraction_stage(name)`.
- Produces full-layout, range and dimension cache methods used by later tasks.

- [ ] **Step 1: Write RED lifecycle tests**

Start `tests_core/test_extraction_context.py` with an explicit PDF helper:

```python
from pathlib import Path

from tests_support import pdf_factory
from biblioref.ingestion.backend_context import active_pdf_backend
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    current_extraction_context,
    timed_extraction_stage,
    use_extraction_context,
)

ROOT = Path(__file__).resolve().parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"


def write_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = pdf_factory.open()
    for text in page_texts:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_context_is_none_outside_activation():
    assert current_extraction_context() is None


def test_context_activates_and_resets(tmp_path):
    pdf = write_pdf(tmp_path / "a.pdf", ["alpha"])
    ctx = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=False)
    with use_extraction_context(ctx):
        assert current_extraction_context() is ctx
    assert current_extraction_context() is None


def test_context_rejects_other_document(tmp_path):
    first = write_pdf(tmp_path / "a.pdf", ["alpha"])
    second = write_pdf(tmp_path / "b.pdf", ["beta"])
    ctx = ExtractionContext.for_pdf(first, active_pdf_backend())
    assert ctx.matches(first, active_pdf_backend())
    assert not ctx.matches(second, active_pdf_backend())
```

Do not add ReportLab.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests_core/test_extraction_context.py
```

Expected: collection fails because `biblioref.ingestion.extraction_context` does not exist.

- [ ] **Step 3: Implement the context module**

Create `biblioref/ingestion/extraction_context.py`:

```python
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

_ACTIVE_CONTEXT: ContextVar["ExtractionContext | None"] = ContextVar(
    "biblioref_extraction_context", default=None
)


@dataclass
class ExtractionContext:
    resolved_path: str
    backend: str
    size_bytes: int
    mtime_ns: int
    reuse_enabled: bool = True
    full_layout: tuple[Any, ...] | None = None
    full_layout_y_tolerance: float | None = None
    full_layout_slice_safe: bool = False
    lines_by_page: dict[int, tuple[Any, ...]] = field(default_factory=dict)
    range_layout_cache: dict[tuple[int, int, float], tuple[Any, ...]] = field(default_factory=dict)
    page_dimensions_cache: dict[int, tuple[float, float]] = field(default_factory=dict)
    counters: Counter = field(default_factory=Counter)
    timings: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    @classmethod
    def for_pdf(cls, pdf_path, backend: str, reuse_enabled: bool = True):
        path = Path(pdf_path).expanduser().resolve()
        stat = path.stat()
        return cls(
            resolved_path=str(path),
            backend=str(backend),
            size_bytes=int(stat.st_size),
            mtime_ns=int(stat.st_mtime_ns),
            reuse_enabled=bool(reuse_enabled),
        )

    def matches(self, pdf_path, backend: str) -> bool:
        return (
            str(Path(pdf_path).expanduser().resolve()) == self.resolved_path
            and str(backend) == self.backend
        )

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[str(name)] += int(value)

    def register_full_layout(self, lines, *, y_tolerance: float, slice_safe: bool) -> None:
        frozen = tuple(lines)
        grouped: dict[int, list[Any]] = defaultdict(list)
        for line in frozen:
            grouped[int(line.page)].append(line)
        self.full_layout = frozen
        self.full_layout_y_tolerance = float(y_tolerance)
        self.full_layout_slice_safe = bool(slice_safe)
        self.lines_by_page = {
            page: tuple(page_lines) for page, page_lines in grouped.items()
        }

    def get_cached_range(self, start_page: int, end_page: int, y_tolerance: float):
        return self.range_layout_cache.get(
            (int(start_page), int(end_page), float(y_tolerance))
        )

    def store_cached_range(self, start_page: int, end_page: int, y_tolerance: float, lines) -> None:
        self.range_layout_cache[
            (int(start_page), int(end_page), float(y_tolerance))
        ] = tuple(lines)

    def get_cached_dimensions(self, page_number: int):
        return self.page_dimensions_cache.get(int(page_number))

    def store_cached_dimensions(self, page_number: int, dimensions) -> None:
        width, height = dimensions
        self.page_dimensions_cache[int(page_number)] = (float(width), float(height))

    def get_full_layout_range(self, start_page: int, end_page: int, y_tolerance: float):
        if not self.reuse_enabled or not self.full_layout_slice_safe:
            return None
        if self.full_layout_y_tolerance != float(y_tolerance):
            return None
        if start_page <= 0 or end_page < start_page or not self.lines_by_page:
            return None
        return tuple(
            line
            for page in range(int(start_page), int(end_page) + 1)
            for line in self.lines_by_page.get(page, ())
        )

    def snapshot(self) -> dict:
        return {
            "backend": self.backend,
            "reuse_enabled": self.reuse_enabled,
            "counters": dict(self.counters),
            "timings": dict(self.timings),
        }


def current_extraction_context():
    return _ACTIVE_CONTEXT.get()


@contextmanager
def use_extraction_context(context: ExtractionContext) -> Iterator[ExtractionContext]:
    token = _ACTIVE_CONTEXT.set(context)
    try:
        yield context
    finally:
        _ACTIVE_CONTEXT.reset(token)


@contextmanager
def timed_extraction_stage(name: str):
    context = current_extraction_context()
    if context is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        context.timings[str(name)] += perf_counter() - started
```

- [ ] **Step 4: Add GREEN behavior tests**

Add tests for nested context restoration, two counter increments, a nonnegative timing bucket and page-index order after `register_full_layout()`:

```python
ctx.increment("range_layout_requests")
ctx.increment("range_layout_requests")
assert ctx.snapshot()["counters"]["range_layout_requests"] == 2

ctx.register_full_layout(lines, y_tolerance=0.9, slice_safe=False)
assert list(ctx.lines_by_page[2]) == [line for line in lines if int(line.page) == 2]
assert not ctx.full_layout_slice_safe
```

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest -q tests_core/test_extraction_context.py
git add biblioref/ingestion/extraction_context.py tests_core/test_extraction_context.py
git commit -m "feat: add extraction execution context"
```

---

### Task 2: Instrument the historical route and create the profiler

**Files:**
- Modify: `biblioref/ingestion/pdf.py`
- Modify: `biblioref/pipeline.py`
- Modify: `biblioref/pipeline_v065.py`
- Modify: `tests_core/test_extraction_context.py`
- Modify: `tests_core/test_biblioref_v0_8_11_performance.py`
- Create: `tools/profile_single_pdf.py`

**Interfaces:**
- Consumes Task 1 context helpers.
- Produces private historical helpers `_extract_layout_lines_range_historical()` and `_page_dimensions_historical()`.
- Produces outer public-pipeline context ownership.
- Produces a one-run profiler with reuse explicitly on/off.
- This task is instrumentation-only: no cache value is returned yet.

- [ ] **Step 1: Write RED context-ownership tests**

Add:

```python
def test_public_process_pdf_owns_one_context(monkeypatch):
    import biblioref.pipeline as pipeline
    original = ExtractionContext.for_pdf.__func__
    created = []

    def counted(cls, pdf_path, backend, reuse_enabled=True):
        ctx = original(cls, pdf_path, backend, reuse_enabled)
        created.append(ctx)
        return ctx

    monkeypatch.setattr(ExtractionContext, "for_pdf", classmethod(counted))
    pipeline.process_pdf(GRAMMAR_PDF, rescue_audit=False, adaptive_mode="off")
    assert len(created) == 1
    assert current_extraction_context() is None
```

Also add a test that manually activates a `reuse_enabled=False` context, patches `ExtractionContext.for_pdf` to raise if called, invokes `pipeline.process_pdf()`, and succeeds.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests_core/test_extraction_context.py -k "public_process_pdf"
```

Expected: FAIL because the public wrapper does not yet own a context.

- [ ] **Step 3: Extract the historical range helper with its exact current body**

In `biblioref/ingestion/pdf.py`, replace the current public range implementation with this private helper plus a thin public wrapper. The helper body is the current implementation copied without semantic edits:

```python
def _extract_layout_lines_range_historical(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
    y_tolerance: float = 0.9,
) -> List[LayoutLine]:
    output: List[LayoutLine] = []
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= start_page <= end_page <= doc.page_count:
            raise ValueError("Rango de páginas fuera de límite.")
        for page_number in range(start_page, end_page + 1):
            page = doc[page_number - 1]
            fragments: List[dict] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = [
                        s for s in line.get("spans", [])
                        if str(s.get("text", "")).strip()
                    ]
                    if not spans:
                        continue
                    text = _clean_text(
                        " ".join(str(s.get("text", "")) for s in spans)
                    )
                    if not text:
                        continue
                    fragments.append({
                        "text": text,
                        "x0": min(float(s["bbox"][0]) for s in spans),
                        "y0": min(float(s["bbox"][1]) for s in spans),
                        "x1": max(float(s["bbox"][2]) for s in spans),
                        "y1": max(float(s["bbox"][3]) for s in spans),
                        "sizes": [float(s.get("size", 0.0)) for s in spans],
                    })
            fragments.sort(key=lambda item: (item["y0"], item["x0"]))
            groups: List[List[dict]] = []
            for fragment in fragments:
                if groups:
                    baseline = statistics.median(x["y0"] for x in groups[-1])
                    if abs(fragment["y0"] - baseline) <= y_tolerance:
                        groups[-1].append(fragment)
                        continue
                groups.append([fragment])
            for group in groups:
                group.sort(key=lambda item: item["x0"])
                sizes = [size for item in group for size in item["sizes"]]
                output.append(LayoutLine(
                    page=page_number,
                    page_height=float(page.rect.height),
                    text=_clean_text(" ".join(item["text"] for item in group)),
                    x0=min(item["x0"] for item in group),
                    y0=min(item["y0"] for item in group),
                    x1=max(item["x1"] for item in group),
                    y1=max(item["y1"] for item in group),
                    median_font_size=statistics.median(sizes),
                    fragment_count=len(group),
                ))
    return output
```

- [ ] **Step 4: Extract the historical dimension helper with its exact current body**

```python
def _page_dimensions_historical(
    pdf_path: str | Path,
    page_number: int,
) -> Tuple[float, float]:
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError("Página fuera de rango.")
        rect = doc[page_number - 1].rect
        return float(rect.width), float(rect.height)
```

- [ ] **Step 5: Add monitor-only public wrappers**

Import `active_pdf_backend` and `current_extraction_context`. Define the exact counter vocabulary:

```text
full_layout_requests
full_layout_backend_calls
range_layout_requests
range_layout_backend_calls
range_layout_cache_hits
range_layout_full_slice_hits
dimension_requests
dimension_backend_calls
dimension_cache_hits
```

The Task 2 range wrapper always calls the historical helper:

```python
def extract_layout_lines_range(pdf_path, start_page, end_page, y_tolerance=0.9):
    context = current_extraction_context()
    backend = active_pdf_backend()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("range_layout_requests")
        context.increment("range_layout_backend_calls")
    result = _extract_layout_lines_range_historical(
        pdf_path, start_page, end_page, y_tolerance
    )
    if matches:
        context.store_cached_range(start_page, end_page, y_tolerance, result)
    return result
```

The Task 2 dimension wrapper also always calls the historical helper:

```python
def page_dimensions(pdf_path, page_number):
    context = current_extraction_context()
    backend = active_pdf_backend()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("dimension_requests")
        context.increment("dimension_backend_calls")
    result = _page_dimensions_historical(pdf_path, page_number)
    if matches:
        context.store_cached_dimensions(page_number, result)
    return result
```

Instrument `extract_layout_lines()` with `full_layout_requests` and `full_layout_backend_calls`, still executing the existing backend code. After success, register the full result with `y_tolerance=0.9` and `slice_safe=False`.

- [ ] **Step 6: Wrap public `process_pdf()` in one context**

Refactor the current body into `_process_pdf_with_active_context(*args, **kwargs)` without changing its existing `_v065.process_pdf()` bridge, algorithm version assignment or `default_effective_output_changed` logic. Then:

```python
def process_pdf(*args, **kwargs):
    pdf_path = args[0] if args else kwargs["pdf_path"]
    if current_extraction_context() is not None:
        return _process_pdf_with_active_context(*args, **kwargs)

    context = ExtractionContext.for_pdf(
        pdf_path,
        backend=active_pdf_backend(),
        reuse_enabled=True,
    )
    with use_extraction_context(context):
        with timed_extraction_stage("process_pdf"):
            return _process_pdf_with_active_context(*args, **kwargs)
```

- [ ] **Step 7: Add timing wrappers around existing calls only**

In `biblioref/pipeline.py`, time these existing stages without changing arguments or return values:

```text
effective_base
long_segment_reconciliation
dominant_margin_reconciliation
first_reference_reconciliation
```

In `biblioref/pipeline_v065.py`, time:

```text
rescue_audit
coverage
two_pass_shadow
```

Do not alter exception handling.

- [ ] **Step 8: Add the public-output regression**

In `tests_core/test_biblioref_v0_8_11_performance.py`:

```python
def test_normal_result_does_not_expose_profiler_state(self):
    result = process_pdf(GRAMMAR_PDF, adaptive_mode="shadow")
    self.assertNotIn("performance", result)
    self.assertNotIn("timings", result)
    self.assertNotIn("counters", result)
    self.assertNotIn("extraction_context", result)
```

Keep the existing one-full-layout and no-rerun tests unchanged.

- [ ] **Step 9: Create `tools/profile_single_pdf.py`**

Required CLI:

```text
positional pdf
--backend pdfium|pymupdf
--reuse on|off
--adaptive-mode off|shadow
--rescue-audit / --no-rescue-audit
--json PATH_OR_DASH
```

One process performs exactly one pipeline run:

```python
clear_layout_line_cache()
ctx = ExtractionContext.for_pdf(
    pdf_path,
    backend=args.backend,
    reuse_enabled=args.reuse == "on",
)
with use_pdf_backend(args.backend), use_extraction_context(ctx):
    started = perf_counter()
    result = pipeline.process_pdf(
        pdf_path,
        adaptive_mode=args.adaptive_mode,
        rescue_audit=args.rescue_audit,
    )
    total_seconds = perf_counter() - started
```

Output must include resolved path, SHA-256, size, mtime, Python/platform, backend, reuse flag, total seconds, algorithm/software versions, records, zones, coverage status, counters and timings. `--json -` sends JSON only to stdout and human-readable text to stderr. Never mutate `result`.

- [ ] **Step 10: Run monitor-only verification and commit**

```bash
python -m pytest -q \
  tests_core/test_extraction_context.py \
  tests_core/test_biblioref_v0_8_11_performance.py \
  tests_core/test_first_reference_repair.py \
  tests_core/test_pdfium_dual_backend.py
python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
  --backend pdfium --reuse off --json -
git add biblioref/ingestion/pdf.py biblioref/pipeline.py biblioref/pipeline_v065.py \
  tests_core/test_extraction_context.py tests_core/test_biblioref_v0_8_11_performance.py \
  tools/profile_single_pdf.py
git commit -m "feat: profile single-document PDF access"
```

This commit is the instrumentation baseline. Tasks 3-5 must leave `reuse_enabled=False` behavior unchanged.

---

### Task 3: Memoize identical historical range requests

**Files:**
- Modify: `biblioref/ingestion/pdf.py`
- Modify: `tests_core/test_extraction_context.py`

**Interfaces:**
- Consumes Task 2 `_extract_layout_lines_range_historical()`.
- Produces exact per-context memoization keyed by `(start_page, end_page, y_tolerance)`.
- Does not slice full layout.

- [ ] **Step 1: Write RED memoization and safety tests**

```python
def test_identical_range_request_is_memoized(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module
    pdf = write_pdf(tmp_path / "memo.pdf", ["one", "two", "three"])
    ctx = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=True)
    calls = []
    original = pdf_module._extract_layout_lines_range_historical

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_extract_layout_lines_range_historical", counted)
    with use_extraction_context(ctx):
        first = pdf_module.extract_layout_lines_range(pdf, 1, 2)
        second = pdf_module.extract_layout_lines_range(pdf, 1, 2)

    assert first == second
    assert first is not second
    assert len(calls) == 1
    assert ctx.counters["range_layout_cache_hits"] == 1
```

Add separate tests proving no hit when start page, end page, tolerance, path or backend differs, and no hit when `reuse_enabled=False`.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests_core/test_extraction_context.py -k "range"
```

Expected: the identical-request test reports two historical calls.

- [ ] **Step 3: Implement exact memoization**

```python
def extract_layout_lines_range(pdf_path, start_page, end_page, y_tolerance=0.9):
    context = current_extraction_context()
    backend = active_pdf_backend()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("range_layout_requests")
        if context.reuse_enabled:
            cached = context.get_cached_range(start_page, end_page, y_tolerance)
            if cached is not None:
                context.increment("range_layout_cache_hits")
                return list(cached)

    result = _extract_layout_lines_range_historical(
        pdf_path, start_page, end_page, y_tolerance
    )
    if matches:
        context.increment("range_layout_backend_calls")
        context.store_cached_range(start_page, end_page, y_tolerance, result)
    return result
```

Failed historical calls are not cached. Return a fresh list on hits.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest -q tests_core/test_extraction_context.py \
  tests_core/test_first_reference_repair.py \
  tests_core/test_biblioref_v0_9_10_rc2_integration.py
git add biblioref/ingestion/pdf.py tests_core/test_extraction_context.py
git commit -m "perf: reuse identical layout range requests"
```

---

### Task 4: Cache exact page dimensions per extraction

**Files:**
- Modify: `biblioref/ingestion/pdf.py`
- Modify: `tests_core/test_extraction_context.py`

**Interfaces:**
- Consumes Task 2 `_page_dimensions_historical()`.
- Produces one exact historical dimension read per page per matching context when reuse is enabled.

- [ ] **Step 1: Write RED dimension-cache tests**

```python
def test_page_dimensions_cached_per_page(tmp_path, monkeypatch):
    from biblioref.ingestion import pdf as pdf_module
    pdf = write_pdf(tmp_path / "dims.pdf", ["one", "two"])
    ctx = ExtractionContext.for_pdf(pdf, active_pdf_backend(), reuse_enabled=True)
    calls = []
    original = pdf_module._page_dimensions_historical

    def counted(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(pdf_module, "_page_dimensions_historical", counted)
    with use_extraction_context(ctx):
        first = pdf_module.page_dimensions(pdf, 1)
        second = pdf_module.page_dimensions(pdf, 1)
        pdf_module.page_dimensions(pdf, 2)

    assert first == second
    assert len(calls) == 2
    assert ctx.counters["dimension_cache_hits"] == 1
```

Add tests for page `0` retaining `ValueError`, another path/backend missing the cache, and `reuse_enabled=False` performing two historical reads.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests_core/test_extraction_context.py -k "dimension"
```

- [ ] **Step 3: Implement exact dimension reuse**

```python
def page_dimensions(pdf_path, page_number):
    context = current_extraction_context()
    backend = active_pdf_backend()
    matches = context is not None and context.matches(pdf_path, backend)
    if matches:
        context.increment("dimension_requests")
        if context.reuse_enabled:
            cached = context.get_cached_dimensions(page_number)
            if cached is not None:
                context.increment("dimension_cache_hits")
                return cached

    result = _page_dimensions_historical(pdf_path, page_number)
    if matches:
        context.increment("dimension_backend_calls")
        context.store_cached_dimensions(page_number, result)
    return result
```

Do not infer dimensions from generic layout. Cache only successful historical reads.

- [ ] **Step 4: Add public coverage equivalence evidence**

Build a four-page synthetic bibliography with an explicit `Bibliography` heading and author-year entries on consecutive pages. Run public `process_pdf()` with a monitor-only context and then reuse enabled, clearing global layout caches between runs. Require full result equality. If the fixture naturally repeats dimension requests, also require fewer optimized dimension backend calls; otherwise leave call-reduction proof to the direct cache test rather than patching coverage internals.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest -q tests_core/test_extraction_context.py \
  tests_core/test_biblioref_v0_8_11_performance.py \
  tests_core/test_biblioref_v0_9_10_rc2_integration.py
git add biblioref/ingestion/pdf.py tests_core/test_extraction_context.py
git commit -m "perf: cache page dimensions per extraction"
```

---

### Task 5: Admit full-layout slicing only after exact backend probes

**Files:**
- Modify: `biblioref/ingestion/pdf.py`
- Modify: `tests_core/test_extraction_context.py`
- Modify: `tests_core/test_biblioref_v0_8_11_performance.py`
- Modify: `tests_core/test_pdfium_dual_backend.py`

**Interfaces:**
- Consumes Task 1 registered full layout and Task 2 historical range helper.
- Produces `_FULL_LAYOUT_SLICE_SAFE: dict[str, frozenset[float]]` based only on exact probe evidence.
- An empty safe map is valid.

- [ ] **Step 1: Write exact probes before enabling any backend**

Test, for each installed backend, the existing grammar fixture plus two PDFs created with `tests_support.pdf_factory`: one multiline/hanging-indent and one two-column/same-baseline. For every tested range:

```python
with use_pdf_backend(backend):
    clear_layout_line_cache()
    full = extract_layout_lines(pdf)
    historical = pdf_module._extract_layout_lines_range_historical(
        pdf, start_page, end_page, 0.9
    )
    sliced = [
        line for line in full
        if start_page <= int(line.page) <= end_page
    ]
    assert historical == sliced
```

If a backend fails any probe, record that failure as evidence and do not admit it. Do not weaken equality to text-only or geometric tolerance.

- [ ] **Step 2: Run probes and freeze the safe set**

```bash
python -m pytest -q tests_core/test_biblioref_v0_8_11_performance.py \
  tests_core/test_pdfium_dual_backend.py \
  -k "range_layout or full_layout"
```

Then define in `biblioref/ingestion/pdf.py` only the passing backend/tolerance pairs:

```python
_FULL_LAYOUT_SLICE_SAFE: dict[str, frozenset[float]] = {}
```

Replace the empty mapping only with entries proven by all probes, such as `{"pymupdf": frozenset({0.9})}` only if PyMuPDF passed every exact probe.

- [ ] **Step 3: Register the evidence-backed safety flag**

After historical full extraction succeeds:

```python
backend = active_pdf_backend()
safe = 0.9 in _FULL_LAYOUT_SLICE_SAFE.get(backend, frozenset())
context.register_full_layout(
    result,
    y_tolerance=0.9,
    slice_safe=safe,
)
```

- [ ] **Step 4: Write RED positive and fallback tests**

For each admitted backend, call full extraction once, patch `_extract_layout_lines_range_historical` to raise, request a supported range and require exact filtered equality plus `range_layout_full_slice_hits == 1`.

For every non-admitted backend and for `y_tolerance=1.1` on all backends, require the historical helper to execute. If no backend qualifies, skip only the positive case with `pytest.skip("no backend proved exact full-layout slicing")`; fallback tests still run.

- [ ] **Step 5: Implement the fail-closed full-slice path**

Before identical-range memoization, ask the active matching context for `get_full_layout_range()`. Use it only when reuse is enabled, the backend/tolerance was admitted and the requested page range is valid. Increment `range_layout_full_slice_hits` and return a fresh list on success. If `end_page` can exceed the document, delegate to `_extract_layout_lines_range_historical()` so the historical exact `ValueError` remains authoritative.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest -q tests_core/test_extraction_context.py \
  tests_core/test_biblioref_v0_8_11_performance.py \
  tests_core/test_pdfium_dual_backend.py \
  tests_core/test_first_reference_repair.py \
  tests_core/test_biblioref_v0_9_10_rc2_integration.py
git add biblioref/ingestion/pdf.py tests_core/test_extraction_context.py \
  tests_core/test_biblioref_v0_8_11_performance.py tests_core/test_pdfium_dual_backend.py
git commit -m "perf: reuse proven-equivalent full layout ranges"
```

---

### Task 6: Prove exact public-pipeline equivalence and finalize profiling recipes

**Files:**
- Create: `tests_core/test_single_pdf_context_equivalence.py`
- Modify: `tools/profile_single_pdf.py`

**Interfaces:**
- Produces full dictionary equality between reuse-off and reuse-on public executions.
- Produces fresh-process Bash and PowerShell benchmark recipes.

- [ ] **Step 1: Create the equivalence harness**

```python
from pathlib import Path

import pytest

import biblioref.pipeline as pipeline
from biblioref.ingestion import clear_layout_line_cache
from biblioref.ingestion.backend_context import available_pdf_backends, use_pdf_backend
from biblioref.ingestion.extraction_context import ExtractionContext, use_extraction_context

ROOT = Path(__file__).resolve().parent
GRAMMAR_PDF = ROOT / "fixtures" / "document_grammar_stress.pdf"


def run_with_reuse(pdf, backend: str, reuse_enabled: bool, **kwargs):
    clear_layout_line_cache()
    ctx = ExtractionContext.for_pdf(pdf, backend, reuse_enabled=reuse_enabled)
    with use_pdf_backend(backend), use_extraction_context(ctx):
        result = pipeline.process_pdf(pdf, **kwargs)
    return result, ctx
```

- [ ] **Step 2: Compare complete reports across public modes**

Parametrize every installed backend over:

```python
CASES = [
    {"adaptive_mode": "shadow", "rescue_audit": True, "scope": "all_reference_sections"},
    {"adaptive_mode": "off", "rescue_audit": True, "scope": "unique_references"},
    {"adaptive_mode": "shadow", "rescue_audit": False, "scope": "final_reference_section"},
    {"adaptive_mode": "shadow", "rescue_audit": True, "two_pass_shadow": True},
]
```

For every case:

```python
baseline, baseline_ctx = run_with_reuse(GRAMMAR_PDF, backend, False, **options)
optimized, optimized_ctx = run_with_reuse(GRAMMAR_PDF, backend, True, **options)
assert baseline == optimized
```

Do not project away or normalize fields.

- [ ] **Step 3: Add one coverage-heavy synthetic equality case**

Use `tests_support.pdf_factory` to create a multi-page bibliography and assert the complete reuse-off/reuse-on result dictionaries are equal. Do not patch coverage decisions to manufacture hits.

- [ ] **Step 4: Finalize profiler JSON and help text**

`--json -` must emit only this machine-readable shape to stdout, with actual values:

```json
{
  "pdf_sha256": "64-hex-digest",
  "backend": "pdfium",
  "reuse_enabled": true,
  "total_seconds": 1.234,
  "algorithm_version": "0.6.8",
  "software_version": "0.9.10-rc2",
  "n_records_selected": 42,
  "n_zones": 1,
  "coverage_status": "looks_consistent",
  "counters": {},
  "timings": {}
}
```

Add fresh-process help examples.

Bash:

```bash
for i in 1 2 3 4 5; do
  python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
    --backend pdfium --reuse off --json - > "baseline-$i.json"
done
for i in 1 2 3 4 5; do
  python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
    --backend pdfium --reuse on --json - > "optimized-$i.json"
done
```

PowerShell:

```powershell
1..5 | ForEach-Object {
  python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf `
    --backend pdfium --reuse off --json - | Out-File "baseline-$_.json" -Encoding utf8
}
1..5 | ForEach-Object {
  python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf `
    --backend pdfium --reuse on --json - | Out-File "optimized-$_.json" -Encoding utf8
}
```

- [ ] **Step 5: Run GREEN/profile smoke and commit**

```bash
python -m pytest -q tests_core/test_single_pdf_context_equivalence.py
python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
  --backend pdfium --reuse off --json -
python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
  --backend pdfium --reuse on --json -
git add tests_core/test_single_pdf_context_equivalence.py tools/profile_single_pdf.py
git commit -m "test: prove extraction context equivalence"
```

---

### Task 7: Run the full gate matrix and freeze measured evidence

**Files:**
- Create: `SINGLE_DOCUMENT_EXTRACTION_CONTEXT_V0_1_REPORT.md`
- Modify implementation files from Tasks 1-6 only if a genuine regression is found.

**Interfaces:**
- Produces one exact candidate HEAD with repository, PDFium-free, PyMuPDF legacy, SEDICI-10, semantic-equivalence and performance evidence.

- [ ] **Step 1: Run focused tests**

```bash
python -m pytest -q tests_core/test_extraction_context.py \
  tests_core/test_single_pdf_context_equivalence.py \
  tests_core/test_biblioref_v0_8_11_performance.py \
  tests_core/test_first_reference_repair.py \
  tests_core/test_pdfium_dual_backend.py \
  tests_core/test_biblioref_v0_9_10_rc2_integration.py
```

Expected: all PASS.

- [ ] **Step 2: Run complete repository and legacy lanes**

```bash
python -m pytest -q
python tools/run_pymupdf_legacy_tests.py
```

Expected: repository PASS with only established skips/warnings, legacy lane PASS.

- [ ] **Step 3: Run a clean PyMuPDF-free lane**

Use a Python 3.11 venv with `requirements-app.txt`, `httpx>=0.27,<1.0`, `pytest`, `pandas`, `httpx2`; verify `pymupdf` and `fitz` are not importable.

Linux/macOS:

```bash
mkdir -p /tmp/biblioref-pymupdf-free
python tools/pymupdf_free_smoke.py --output-dir /tmp/biblioref-pymupdf-free
BIBLIOREF_REQUIRE_PDFIUM_ONLY=1 python tools/run_pdfium_current_tests.py
```

Windows PowerShell:

```powershell
$evidence = Join-Path $env:TEMP "biblioref-pymupdf-free"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
python tools/pymupdf_free_smoke.py --output-dir $evidence
$env:BIBLIOREF_REQUIRE_PDFIUM_ONLY = "1"
python tools/run_pdfium_current_tests.py
```

Expected: both required PDFium-only checks PASS.

- [ ] **Step 4: Run the existing SEDICI-10 workflow unchanged on the candidate HEAD**

Required frozen counts:

```text
022=206
055=10
090=0
092=395
093=0
094=220
097=390
098=436
099=83
100=130
```

Required result: `SEDICI-10: 10/10 PASS`, both backends report algorithm `0.6.8`, and migration gates pass. Do not run the human-gold workflow.

- [ ] **Step 5: Capture fresh-process performance evidence**

Use the SHA-verified local SEDICI-10 PDFs from the same acquisition recipe embedded in `.github/workflows/sedici10-migration-gate.yml`. On one fixed machine/backend, run at least five separate processes per document with `--reuse off` and five with `--reuse on`. Calculate medians outside the profiler process.

For every document record:

```text
backend
baseline median seconds
optimized median seconds
percent change
range requests/backend calls/cache hits/full-slice hits
dimension requests/backend calls/cache hits
records/zones equality
```

Do not use GitHub shared-runner wall time as the authoritative speed claim.

- [ ] **Step 6: Write the final report with observed values**

Create `SINGLE_DOCUMENT_EXTRACTION_CONTEXT_V0_1_REPORT.md` containing candidate SHA, base SHA, Python/OS/CPU, dependency/backend versions, exact commands, test/gate outcomes, SEDICI counts, exact equivalence status, per-document medians, aggregate median change, access-counter reductions, `_FULL_LAYOUT_SLICE_SAFE` contents and the remaining dominant profiler cost.

If the aggregate improvement is below 15%, state it plainly. Do not weaken semantics or broaden the safe map to chase the target.

- [ ] **Step 7: Check diff scope**

```bash
git diff --name-only addc40c19a89877e9e36677941e477371c47fe20...HEAD
```

Allowed implementation changes are limited to the spec/plan/report and files declared above. There must be no changes to `app.py`, parser/resolver/StyleProfiler, human-gold data/results, `numeric_rescue.py`, or `column_reflow.py` without a separately approved design.

- [ ] **Step 8: Commit evidence and verify final candidate**

```bash
git add SINGLE_DOCUMENT_EXTRACTION_CONTEXT_V0_1_REPORT.md
git commit -m "docs: record extraction context performance evidence"
python -m pytest -q tests_core/test_extraction_context.py \
  tests_core/test_single_pdf_context_equivalence.py
```

Record the exact final SHA. Only then open a PR to `dev` and let repository, PDFium-free, PyMuPDF legacy and SEDICI-10 workflows validate that exact candidate.
