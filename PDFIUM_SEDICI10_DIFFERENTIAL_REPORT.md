# BiblioRef — PDFium migration validation on fixed SEDICI-HUM 10

Date: 2026-09-11

## Decision

**The PDFium migration engineering gate is now closed for the current BiblioRef candidate.** The frozen SEDICI-10 differential gate remains **10/10 PASS**, the current application/test lane passes from the default requirements with PyMuPDF completely absent, and historical PyMuPDF regressions remain preserved in a separate opt-in compatibility lane.

The default application dependency is now `pypdfium2>=5.13,<6.0`. PyMuPDF is no longer installed by `requirements-app.txt`; it remains available through `requirements-pymupdf-compat.txt` for historical reproducibility and explicit A/B differential validation.

This is *backend-migration and packaging evidence*, not human-gold accuracy evidence. The downstream bibliography algorithm is unchanged (`0.6.7`), and no precision/recall/F1 claim is made without an independent human-labelled holdout.

## Frozen baseline and corpus

The differential experiment remains anchored to the green development baseline used when PR #33 was opened:

- `dev`: `f5cd32f4b1d1c332d9d41dfab76b91976f761567`
- integrated algorithm line: `0.6.7`
- original experiment branch: `feat/pdfium-dual-backend`
- validated test-harness/packaging branch: `feat/pdfium-test-harness-split`
- historical comparison backend: PyMuPDF
- current/default backend dependency: PDFium via `pypdfium2`

The ten PDFs are the same SHA-pinned SEDICI-HUM documents used in the first differential report; no document was added, removed, or selected after observing final adapter behavior. The companion CSV `benchmarks/pdfium_sedici10_migration_2026-09-10.csv` records exact SHA-256 identities and per-document outcomes.

## What changed in the compatibility adapter

The final candidate reconstructs the existing MuPDF-style `LayoutLine` contract using general PDF geometry rather than thesis-specific rules:

1. **MuPDF-compatible vertical font boxes.** PDFium ascent/descent metrics are transformed into the physical span box used by the stable path.
2. **Empty text objects as structural whitespace.** Empty extracted strings can remain topology evidence without becoming visible text.
3. **Source-order/native-line reconstruction.** Backward jumps, unbridged gaps and interleaved visible objects preserve native fragment boundaries before stable second-stage visual merge.
4. **Orientation-aware rotated text.** Rotated pages use the perpendicular axis for line identity and targeted character boxes for trailing-space advances.
5. **Geometry-based word/punctuation continuity.** Tight fragmentation, hyphens and detached punctuation are joined only when object spacing supports continuity.
6. **Extraction cache for differential replay.** PDFium layout extraction is cached by path/range/file identity during A/B validation without changing semantic output.

The validated adapter itself was not modified during the test-harness and packaging migration described below.

## Migration gate definition

The SEDICI-10 migration gate requires:

- identical pipeline summary counts and algorithm version;
- exact semantic zone decisions;
- identical record count and order;
- identical non-backend semantic metadata for every record;
- bibliographic text equivalence after whitespace removal and discretionary soft-hyphen normalization;
- no deletion, replacement, or reordering hidden by comparison.

A candidate may be labelled `possible_content_superset` only when it preserves the complete canonical stable string and adds insertion-only content. `strict_raw_gate` remains a diagnostic geometry/audit comparison rather than the migration decision.

## Final SEDICI-10 replay

| PDF | records PyMuPDF / PDFium | zones PyMuPDF / PDFium | semantic zones | bibliographic records | content supersets | strict raw | migration | PDFium / PyMuPDF time |
|---|---:|---:|---|---|---:|---|---|---:|
| 022 | 206 / 206 | 1 / 1 | yes | yes | 0 | no | PASS | 1.11× |
| 055 | 10 / 10 | 1 / 1 | yes | yes | 0 | no | PASS | 2.33× |
| 090 | 0 / 0 | 0 / 0 | yes | yes | 0 | yes | PASS | 3.95× |
| 092 | 395 / 395 | 12 / 12 | yes | yes | 0 | no | PASS | 1.33× |
| 093 | 0 / 0 | 0 / 0 | yes | yes | 0 | yes | PASS | 4.78× |
| 094 | 220 / 220 | 1 / 1 | yes | yes | 0 | no | PASS | 1.08× |
| 097 | 390 / 390 | 2 / 2 | yes | yes | 1 | no | PASS | 1.14× |
| 098 | 436 / 436 | 2 / 2 | yes | yes | 0 | no | PASS | 1.12× |
| 099 | 82 / 82 | 1 / 1 | yes | yes | 0 | yes | PASS | 1.19× |
| 100 | 130 / 130 | 1 / 1 | yes | yes | 0 | no | PASS | 1.35× |

Aggregate result:

- documents passing migration gate: **10/10**;
- selected references compared: **1869** on each backend;
- bibliography zones compared: **21** on each backend;
- strict-raw passes: **3/10**;
- documents with insertion-only candidate supersets: **1/10** (`097`);
- all remaining documents have canonical bibliographic text equivalence `1.0`.

## Adversarial cases retained as explicit evidence

### `SEDICI_HUM_097`

`097` has 390 references and two semantically identical zones on both backends. One record is an insertion-only candidate superset because PDFium recovers the remainder of a URL truncated by PyMuPDF: **74 added canonical characters**. The raw difference remains visible rather than being normalized away.

### `SEDICI_HUM_092`

The final orientation-aware adapter reconstructs the adversarial rotated/tabular page as **64/64 physical lines with exact text sequence**. Full pipeline output is **395/395 references and 12/12 zones** with semantic-zone equivalence.

### `SEDICI_HUM_098`

The punctuation-topology regression was closed by preserving interleaved visible objects as native-fragment barriers. Final output is **436/436 references and 2/2 zones** with canonical bibliographic similarity `1.0`.

## Performance

The frozen differential replay does not establish a speed advantage for PDFium:

- total PyMuPDF time: **58.06 s**;
- total PDFium-candidate time: **93.68 s**;
- aggregate ratio: **1.61×**;
- median per-document ratio: **1.26×**;
- large successful documents (`092`, `097`, `098`): approximately **1.1–1.3×** the stable pipeline in that environment.

Performance remains separable from the migration/packaging decision and should be optimized only with independent performance gates.

## Test-harness migration

The former packaging blocker was traced to the test harness rather than the current runtime. Direct `fitz`/`pymupdf` imports in current app, cover-metadata, title, front-matter, project, parallel-import and current integration tests were used primarily to manufacture synthetic PDFs.

Those current tests now use `tests_support/pdf_factory.py`, a test-only minimal PDF writer. Historical tests whose *subject* is a PyMuPDF-based frozen engine remain explicitly listed in `tests_support/pdf_backend_manifest.json`. Two individual A/B tests in `tests_core/test_pdfium_dual_backend.py` are classified by node ID so the pure PDFium tests in that module still run in the current lane.

The split therefore preserves both kinds of evidence:

- **current PDFium-only lane:** current application/runtime behavior with PyMuPDF absent;
- **legacy PyMuPDF lane:** historical engine reproducibility and explicit differential comparisons with PyMuPDF installed.

No historical test was deleted to obtain a green PDFium-only result.

## Packaging architecture

Default installation:

```text
requirements-app.txt
  -> pypdfium2>=5.13,<6.0
  -> no PyMuPDF
```

Historical/differential compatibility installation:

```text
requirements-pymupdf-compat.txt
  -> -r requirements-app.txt
  -> PyMuPDF>=1.23,<2.0
```

The full repository gate deliberately installs the compatibility requirements because it executes both current and frozen historical tests. The PyMuPDF-free isolation gate deliberately installs `requirements-app.txt` directly, without generating or filtering a temporary requirements file.

## Final CI evidence on the packaging candidate

At branch HEAD `d1bfa55f6401da406946609f986790a742fb2c7c` before this documentation-only update:

- **Repository Test Gate:** PASS — **807 passed, 3 skipped, 16 subtests passed**;
- **Current PDFium-only lane:** PASS — **722 passed, 3 skipped, 2 deselected, 6 subtests passed**;
- **PyMuPDF Legacy Gate:** PASS — **85 passed, 10 subtests passed**;
- **default-install isolation:** PASS;
- **PyMuPDF distribution installed by default:** **no**;
- **`pymupdf` importable in default isolated environment:** **no**;
- **`fitz` importable in default isolated environment:** **no**;
- **pypdfium2 in isolated default environment:** **5.13.0**;
- **PyMuPDF-free smoke matrix:** **12/12 PASS**;
- **Metadata Resolver Gate:** remains a required independent gate and is verified again at final branch HEAD.

The provenance guard also keeps `CURRENT_FIELD_TEST_STATE.json` synchronized with the effective software, algorithm, parser and StyleProfiler identifiers.

## Engineering conclusion

The evidence now supports this state:

- default PDF dependency: **PDFium**;
- PyMuPDF: **opt-in historical/differential compatibility dependency**;
- current runtime without PyMuPDF: **validated**;
- current test lane without PyMuPDF: **validated**;
- historical PyMuPDF regression lane: **preserved and green**;
- SEDICI-10 differential migration gate: **10/10 PASS**;
- downstream bibliography algorithm: **unchanged at 0.6.7**;
- validated PDFium adapter: **unchanged during packaging/test migration**;
- destructive equality hacks: **not used**;
- independent human gold: **still required before scientific precision/recall/F1 claims**.

The next engineering issue is therefore no longer PDF backend packaging. The next architecture item from the review is to eliminate the app-level second extraction authority (`_first_reference_guard`) by either moving its validated behavior into the versioned core pipeline or proving the core now covers those cases and removing the app repair. That work should be isolated behind interface-parity tests so CLI/package/app automatic extraction cannot diverge silently.

## Core first-reference authority migration (2026-09-12)

Validation candidate: `57d5f4b937f097b6ff0e7a0df867bb97960f5e00` (before this evidence-only update).

The automatic extraction authority now resides in `biblioref.pipeline.process_pdf()`. The app-level `_first_reference_guard()` and `app_repairs` provenance were removed; app persistence consumes the authoritative core result. Public provenance is algorithm **0.6.8** with `first_reference_repairs`, while software remains **0.9.10-rc2** and the stable engine remains **0.4.5**.

Verification on that candidate:

- **Repository Test Gate:** PASS — **822 passed, 3 skipped, 16 subtests passed**;
- **Current PDFium-only lane:** PASS — **737 passed, 3 skipped, 2 deselected, 6 subtests passed**;
- **PyMuPDF Legacy Gate:** PASS — **85 passed, 10 subtests passed**;
- **Metadata Resolver focused gate:** PASS — **93 passed**; its full-suite replay also passed **822 tests**;
- default-install PyMuPDF exclusion and the 12-case PDFium smoke matrix: **PASS**;
- omitted-entry and deferred-author app/core parity fixtures: **PASS**.
- malformed evidence metadata abstention and repaired-zone `n_segments` reconstruction: **PASS**.

### SEDICI-10 replay under algorithm 0.6.8

| PDF | records PyMuPDF / PDFium | migration |
|---|---:|---|
| 022 | 206 / 206 | PASS |
| 055 | 10 / 10 | PASS |
| 090 | 0 / 0 | PASS |
| 092 | 395 / 395 | PASS |
| 093 | 0 / 0 | PASS |
| 094 | 220 / 220 | PASS |
| 097 | 390 / 390 | PASS |
| 098 | 436 / 436 | PASS |
| 099 | 83 / 83 | PASS |
| 100 | 130 / 130 | PASS |

Aggregate result: **10/10 PASS**, with **1870** selected references on each backend.

The sole count change from the earlier adapter-migration baseline is `SEDICI_HUM_099`: **82 → 83**. Investigation confirmed an explicit `Bibliografía` heading followed by the physically present dated entry beginning `MASIELLO, Francis`, which the previous core output omitted. The new core repair recovers that first reference identically under PyMuPDF and PDFium. This is an evidenced algorithm correction, not backend drift or a relaxed comparison.

All ten downloaded bitstreams matched their pinned SHA-256 values. No frozen benchmark CSV or PDFium adapter file was modified. This remains engineering migration evidence, not independent human-gold precision, recall or F1 evidence.
