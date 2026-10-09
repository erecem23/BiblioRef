# Core first-reference repair migration

Date: 2026-09-11

## Status

Approved design for migrating the current app-level `_first_reference_guard()` into the versioned extraction core without broadening its heuristic scope.

## Problem

`app.py` currently calls `process_pdf()` and then runs `_first_reference_guard(path, result)`. That guard may mutate `result["records"]`, selected/occurrence/unique counts, boundary evidence, and coverage after the public pipeline has already completed its own extraction, audit, duplicate annotation, scope selection, and coverage pass.

This creates two extraction authorities:

1. `biblioref.pipeline.process_pdf()` for core/CLI/API callers;
2. `app.py` for the integrated app, which may silently return a different automatic bibliography for the same PDF and arguments.

The app-level guard was introduced for a narrow, real failure mode observed in the RIEA/Alonso case:

- a bibliography heading is explicit;
- physical text exists between that heading and the first returned record;
- either the author opening is omitted while a deferred-year continuation becomes record 1, or a complete first dated reference is omitted entirely.

The existing guard is deliberately heading-anchored and uses author-opening evidence. This migration must preserve that conservatism.

## Goal

Make the core pipeline the single authority for automatic extracted records while preserving the current Alonso/RIEA repair behavior and all previously validated PDFium/SEDICI behavior.

After the migration:

- `process_pdf()` already contains the repaired first reference when the narrow guard conditions are met;
- `app.py` does not mutate extracted automatic records after `process_pdf()` returns;
- app/core callers receive the same automatic records for identical inputs and options;
- duplicate metadata, counts, audit and coverage are computed from the final repaired core result;
- the repair remains explicitly inspectable in provenance.

## Non-goals

This change will not:

- broaden bibliography-heading detection;
- invent first references in headingless regions;
- change PDFium/PyMuPDF adapter behavior;
- change the validated SEDICI-10 PDFium geometry adapter;
- redesign general segmentation or boundary reconciliation;
- add new author/year heuristics beyond the behavior already used by `_first_reference_guard()`;
- claim precision, recall or F1 without independent human gold.

## Chosen architecture

### 1. Core repair module

Create a focused extraction module, expected path:

`biblioref/extraction/first_reference_repair.py`

It owns the narrow post-segmentation repair and exposes a function that accepts:

- `pdf_path`;
- the current all-zones extraction report or its zones/records;
- backend-neutral layout-line access through existing ingestion APIs.

The module must not import `app.py` and must not depend on UI state.

The repair preserves the current decision gates:

1. records and zones exist;
2. find the first returned record per zone;
3. inspect the physical page where that record begins;
4. locate the physical line that opens the current first record using the same conservative normalized-prefix logic;
5. search backward for an explicit bibliography heading;
6. collect non-empty physical lines between heading and returned first record;
7. require author-opening evidence;
8. if the prefix has no year and the returned first record is a deferred-year continuation, prepend the omitted author opening;
9. if the prefix contains a year, insert it as the omitted first reference;
10. otherwise abstain.

The migration may factor the guard's private text-normalization helpers into the core module, but their semantics must remain equivalent unless a failing test proves a defect.

### 2. Integration point

Apply the repair inside the current core extraction path after existing structural reconciliations have selected the final all-zones records, but before public rescoping, post-extraction audit, coverage, and return.

The preferred integration is in the effective all-zones pipeline (`biblioref/pipeline.py` / the v0.6.7 effective path), after the current structural repair stack has stabilized the records.

This ordering matters:

- earlier structural repairs still get first authority over segmentation;
- the first-reference repair only sees the final effective first record of each zone;
- scopes such as `final_reference_section` and `unique_references` are derived from the repaired all-zones report rather than repaired independently;
- downstream audit/coverage evaluates the exact records returned to callers.

### 3. Rebuild derived record metadata centrally

If a repair changes records, rebuild duplicate and scope-derived metadata using the same core utilities already used by the pipeline (`_annotate_duplicates`, `_select_scope`, and existing report-rebuild helpers) rather than setting counts by hand.

The core must recompute at least:

- `records`;
- `duplicate_groups`;
- `n_occurrences_all_zones`;
- `n_unique_references`;
- `n_duplicate_groups`;
- `n_occurrences_in_duplicate_groups`;
- `n_repeated_occurrences_beyond_first`;
- `n_records_selected` for the requested public scope.

This explicitly removes the current app-level shortcut that sets `n_unique_references = len(records)`.

### 4. Provenance

Expose the repair in the core report as:

`first_reference_repairs`

Each repair entry should preserve the currently useful evidence:

- `zone_id`;
- repair `kind` (`prepend_deferred_author` or `insert_omitted_first_reference`);
- physical `page`;
- recovered prefix text.

Record-level `boundary_evidence` must use a core/versioned label rather than the app-specific `app252_*` label.

The app-specific `app_repairs` key is removed once parity is proven.

### 5. App simplification

`app.py::_analyze_document()` must consume `process_pdf()` as authoritative and must no longer call `_first_reference_guard()` or rebuild coverage because of an app-only record mutation.

The old private guard and any private helpers used exclusively by it should be deleted from `app.py`. Helpers still used by manual-click/presentation behavior stay in the app; extraction-only logic moves to core.

## Public behavior and compatibility

### Automatic extraction parity

For the same PDF and extraction arguments, app and direct-core callers must observe the same automatic reference texts, order, zones and counts.

UI conversion (`_record_to_ui`) may still add app identifiers, parser overlays, status and display fields; those are not extraction differences.

### Existing Alonso/RIEA behavior

The two existing app tests become core-facing regression tests:

1. complete first dated reference omitted between bibliography heading and current first record -> insert omitted first reference;
2. author opening omitted while deferred-year continuation is current first record -> prepend recovered author text.

The expected recovered bibliography content remains unchanged.

### Abstention safety

Add negative tests proving no repair when:

- no explicit bibliography heading is found;
- there is no physical prefix between heading and first returned record;
- prefix lacks sufficient author-opening evidence;
- prefix lacks a year and the first returned record is not a deferred-year continuation;
- the first returned record cannot be matched to a physical opening line.

## Versioning policy

The repair changes the public core output for the Alonso/RIEA failure class. Therefore version provenance must be reviewed explicitly.

Implementation must not silently leave provenance inconsistent. Before final GREEN:

1. run the new regression/parity tests and determine whether the core's effective automatic output changes only for cases that the app already repaired;
2. inspect the project's current software/algorithm version policy;
3. if moving an already-shipping app repair into core counts as a new algorithm output contract, increment `ALGORITHM_VERSION` to the next appropriate value and update provenance fixtures/reports;
4. if project policy treats it strictly as interface-parity consolidation with no new integrated-app behavior, document why an algorithm bump is not required.

No version bump is assumed in advance.

## Testing strategy

Use TDD.

### RED 1: core recovery regressions

Create core tests using backend-neutral synthetic PDFs that reproduce the two existing app guard cases. They must call `biblioref.pipeline.process_pdf()` and initially fail because the core does not recover the omitted prefix.

Assertions cover:

- repaired record text;
- record order;
- repair provenance;
- selected/occurrence/unique counts;
- no app-specific provenance label.

### RED 2: app/core interface parity

For the same synthetic inputs, compare the authoritative core result with the automatic records stored by `_analyze_document()` after UI normalization. The app must not contain a second extraction repair step.

### RED 3: abstention contract

Negative fixtures must show that the repair abstains outside its current narrow gates.

### GREEN implementation

Implement the minimal core module and integration needed to satisfy the tests. Do not modify PDF backend adapters or unrelated structural repair heuristics.

### Regression verification

At final HEAD require all of the following:

- full repository suite GREEN;
- default PDFium-only current lane GREEN with PyMuPDF absent;
- PyMuPDF legacy lane GREEN;
- Metadata Resolver Gate GREEN;
- frozen SEDICI-10 PDFium migration evidence remains 10/10 PASS with the previously validated counts unless a deliberately added first-reference repair is independently demonstrated on that corpus;
- no change to the frozen PDFium adapter solely to make these tests pass.

If SEDICI-10 output changes unexpectedly, stop and investigate before integration.

## Error handling

The repair is conservative and non-fatal:

- layout extraction failure for the candidate page -> abstain and leave records unchanged;
- missing or malformed physical evidence -> abstain;
- no qualifying repair -> return the original records and no repair entry.

Unexpected programmer errors should not be broadly swallowed inside the new pure decision helpers; only backend/layout acquisition failures that are already non-fatal to this optional repair should degrade to abstention.

## Acceptance criteria

The migration is complete when:

1. `process_pdf()` itself reproduces both existing Alonso/RIEA repairs;
2. `_analyze_document()` performs no post-`process_pdf()` mutation of automatic extraction records;
3. app/core automatic bibliography parity tests pass;
4. duplicate/count metadata is derived by core utilities rather than manually approximated;
5. negative abstention tests pass;
6. all current PDFium, legacy and repository gates are green;
7. SEDICI-10 migration evidence remains green;
8. provenance/version treatment is explicit and internally consistent.

## Follow-up, out of scope

After this migration, separately evaluate whether the first-reference repair can eventually be generalized into the broader boundary-reconciliation framework using independent corpus evidence. That is intentionally not part of this change.