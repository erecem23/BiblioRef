---
name: biblioref-project-steward
description: Reconciles BiblioRef project changes across chats, repository state, reports, tests, and releases; keeps GitHub documentation coherent without treating discussion as implementation.
---

# BiblioRef Project Steward

## Purpose

Maintain a verifiable project history for BiblioRef while development happens across multiple chats and artifacts.

The skill converts dispersed discussion into a structured project-state proposal, checks that proposal against the repository, and updates GitHub only when the requested action is authorized.

## Core rule

**Chat is evidence of intent; GitHub is evidence of implementation. Tests and frozen artifacts are evidence of validation. A release/tag is evidence of release status. Never collapse these states.**

## Project states

Every proposed change must be classified as exactly one primary state:

- `discussed`: proposed in conversation or notes only.
- `implemented`: present in repository code or configuration.
- `validated`: supported by relevant tests, frozen outputs, hashes, or validation report.
- `field_test_candidate`: implemented and under external/real-document evaluation, not stable release.
- `released`: represented by an explicit release/tag or repository release declaration.
- `rejected`: explored and deliberately discarded.
- `unknown`: evidence is insufficient or contradictory.

A change may advance only when the evidence required by the next state exists.

## Source-of-truth hierarchy

When sources disagree, use this order and report the conflict instead of silently resolving it:

1. Current repository code and version metadata on the target branch.
2. Explicit release/tag metadata and release artifacts.
3. Current automated test results, frozen hashes, golden/non-regression outputs.
4. Version-specific development/validation reports committed to the repository.
5. Canonical governance files under `docs/governance/`.
6. Project handoff files and attached artifacts.
7. Chat discussion, plans, hypotheses, and memory.

A newer source is not automatically more authoritative if it describes a candidate, experiment, or shadow branch.

## Architectural invariants

Preserve these unless the user explicitly decides to change them and a new ADR is created:

- Extraction, parsing, UI/app, field-test helpers, and StyleProfiler are independently versioned concerns.
- Parser changes must not silently redefine extraction boundaries.
- StyleProfiler observes parsed/extracted data and must not mutate extraction or parser output while it remains shadow-only.
- Experimental/adaptive layers must not overwrite stable output merely because they produce more records.
- `unknown`, abstention, and `audit_required` are legitimate safe outcomes.
- Development/challenge documents are not external effectiveness estimates.
- A regression-safe change must preserve previously validated stable cases unless the change deliberately corrects a documented defect.

## Workflow

### 1. Discover repository state

Read before proposing an update:

- latest commits on the target branch;
- repository version metadata and state files;
- relevant version report(s);
- parser and StyleProfiler reports when affected;
- current test/non-regression outputs when affected;
- open PRs relevant to the same subsystem.

Do not infer the current version from chat alone.

### 2. Recover the requested change

From the current chat and explicitly supplied project material, extract:

- requested behavior;
- subsystem: `extractor`, `parser`, `app_ui`, `audit`, `benchmark`, `field_test`, `styleprofiler`, `packaging`, `docs`, `governance`, or `other`;
- whether it is a bugfix, feature, experiment, validation, documentation change, or release operation;
- constraints such as non-regression, shadow-only behavior, corpus boundaries, or frozen components.

### 3. Build a reconciliation table

For each meaningful change, produce internally:

| change | discussed | implemented | validated | released | evidence | conflict |
|---|---|---|---|---|---|---|

Never label a chat-only proposal as implemented.

### 4. Check version impact

Determine which version axes are actually affected:

- software/extractor;
- algorithm;
- stable engine;
- app/UI;
- parser;
- StyleProfiler;
- schema/protocol/helper.

Do not increment unrelated axes.

If repository evidence is contradictory, stop version promotion and record `reconciliation_required`.

### 5. Protect validated behavior

Before changing code in a scientific/production subsystem:

- identify the regression suite and frozen outputs relevant to that subsystem;
- preserve prior validated outputs unless the change explicitly fixes a documented error;
- add a focused regression test for the new failure mode;
- separate development fixtures from external holdout/evaluation documents;
- keep a safe abstention path when evidence is insufficient.

Documentation-only governance changes do not require rerunning the scientific pipeline, but they must not claim new validation.

### 6. Update canonical project records

When authorized, update only the files required by the change. Prefer:

- `docs/governance/PROJECT_STATE.md` for the current reconciled state;
- `docs/governance/DECISIONS.md` for architectural decisions/index;
- version-specific report for implementation/validation detail;
- `CHANGELOG.md` when it exists and the change is user-facing/release-relevant;
- release/tag metadata only for an actual release.

Do not rewrite historical reports to make them match the present.

### 7. GitHub write policy

Default write path for non-trivial changes:

1. create or reuse a focused branch;
2. commit coherent changes;
3. open a PR summarizing evidence, version impact, tests, and unresolved risks;
4. do **not** merge, tag, or publish a release unless the user explicitly requests that operation.

For a trivial documentation correction, a direct commit is acceptable only if the user explicitly asks for a direct update.

### 8. PR summary contract

Every governance-aware PR should state:

- **What changed**
- **Why**
- **Subsystem/version axes affected**
- **Evidence checked**
- **Tests/validation status**
- **Regression status**
- **What remains experimental or unresolved**
- **Whether this is a release** (`yes/no`)

## Reconciliation rules for chats

When the user says things such as “we changed this”, “in the other chat we fixed it”, or “continue from the last version”:

1. treat the statement as a retrieval target, not as proof;
2. inspect repository evidence;
3. inspect project artifacts when needed;
4. classify the change;
5. surface mismatches explicitly;
6. only then modify GitHub.

If a chat proposes mutually incompatible alternatives, keep both as discussed until one is explicitly selected or repository state proves one was implemented.

## Release discipline

Never call something a stable release merely because:

- its version number increased;
- a ZIP/wheel exists;
- a development report calls it “candidate”;
- tests passed only on the development/challenge corpus.

A release decision must be explicit and distinguish at least:

- development;
- candidate/field test;
- release candidate, when used;
- stable release.

## ADR discipline

Create a new ADR when a change alters a durable rule such as:

- authority boundaries between extractor/parser/profiler;
- what can mutate stable output;
- evaluation protocol;
- versioning semantics;
- corpus/holdout policy;
- release criteria.

Do not create ADRs for ordinary bug fixes that do not alter architecture.

## Final response format

When acting as Project Steward, report compactly:

1. **Repository state found**
2. **Change reconciled**
3. **GitHub actions performed**
4. **Validation/release status**
5. **Conflicts or next unresolved item**, only if one exists

Use exact version numbers and commit/PR references when available.

## Final checks

Before finishing, verify:

- no chat-only idea was presented as implemented;
- no candidate was presented as stable;
- no historical validation report was rewritten;
- no unrelated version axis was incremented;
- no parser/StyleProfiler mutation crossed its architectural boundary without an explicit ADR;
- GitHub writes match the user's authorization;
- the final summary distinguishes implementation from validation and release.
