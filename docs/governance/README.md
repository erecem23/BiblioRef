# BiblioRef Governance

This directory contains the canonical governance layer used by the `biblioref-project-steward` skill.

## Why it exists

BiblioRef evolves through code changes, version reports, field tests, attached artifacts, and multiple development chats. These sources do not all have the same authority and they do not always move at the same time.

The governance layer prevents common project-history errors such as:

- treating a proposed chat fix as implemented;
- treating a passing development suite as an external effectiveness estimate;
- treating a candidate ZIP/wheel as a stable release;
- incrementing parser/app/extractor versions together when only one changed;
- forgetting an architectural constraint established several versions earlier;
- silently rewriting an older state file to make it fit the newest report.

## Files

- `PROJECT_STATE.md`: reconciled current state and known conflicts.
- `DECISIONS.md`: durable architectural decisions (ADR-style index).
- `../../skills/biblioref-project-steward/SKILL.md`: reusable workflow followed by the Project Steward.

## State model

```text
discussed
   ↓
implemented
   ↓
validated
   ↓
field_test_candidate / release_candidate
   ↓
released
```

`rejected` and `unknown` may branch from any non-released stage. A safe abstention is not a failure of governance.

## Recommended use from a chat

Typical requests:

- “Reconciliá lo que hicimos en este chat con BiblioRef y decime qué está realmente implementado.”
- “Actualizá GitHub con los cambios de esta sesión, sin hacer release.”
- “Compará el último chat con `main` y abrí un PR sólo con lo que esté respaldado por código/tests.”
- “¿Qué cambió desde la última versión validada y qué sigue siendo experimental?”
- “Prepará la siguiente release, pero no la publiques todavía.”

## GitHub policy

For non-trivial changes, prefer:

```text
main
  ↓
focused branch
  ↓
coherent commits
  ↓
PR with evidence + version impact + validation state
  ↓
explicit merge/release decision
```

The Steward may create/update a branch and PR when the user asks it to update GitHub. It must not merge, tag, or publish a release unless explicitly requested.

## What the Steward should read first

At minimum:

1. latest commits on the target branch;
2. current version/state metadata;
3. the version-specific report relevant to the subsystem;
4. current test or non-regression evidence when code behavior is affected;
5. open PRs touching the same subsystem.

Chat context is then used to recover intent and unresolved decisions, not to override repository evidence.

## Version axes

Treat these independently:

```text
software/extractor
algorithm
stable engine
app/UI
parser
StyleProfiler
field-test/helper/schema
```

A release summary should list only axes that actually changed.

## Definition of done for a Steward reconciliation

A reconciliation is complete when:

- each relevant change has a state (`discussed`, `implemented`, etc.);
- conflicts between chat and repository are explicit;
- version impact is identified;
- validation evidence is identified or explicitly absent;
- GitHub actions are recorded;
- candidate vs stable status is unambiguous.
