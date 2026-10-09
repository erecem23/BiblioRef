# BiblioRef — Architectural Decision Log

This is the index of durable project decisions that Project Steward must preserve unless a later explicit decision supersedes them.

## ADR-001 — GitHub is implementation truth

**Status:** accepted

Chats, handoffs, and working notes may describe intent, hypotheses, and proposed fixes. A change is not `implemented` until repository evidence supports it. Validation and release are separate states.

**Consequence:** Project Steward must reconcile chat claims against the repository before updating project state.

---

## ADR-002 — Version axes remain decoupled

**Status:** accepted

BiblioRef software/extraction, algorithm, stable engine, app/UI, parser, StyleProfiler, and helper/schema versions are distinct axes.

**Consequence:** a change increments only the axis it actually modifies. A UI change does not imply a parser or extraction change; a parser change does not imply an extraction algorithm change.

---

## ADR-003 — Parser does not own extraction boundaries

**Status:** accepted

Parsing consumes extracted references but must not silently redefine which textual boundaries belong to extraction.

**Consequence:** parser work requires parser-specific tests and must preserve the extraction contract unless a separate explicit extraction change is made.

---

## ADR-004 — StyleProfiler remains observational while shadow-only

**Status:** accepted

StyleProfiler profiles extracted/parsed references but does not modify extraction, segmentation, or parser output while its state is `shadow_only`.

**Consequence:** StyleProfiler failure cannot invalidate a successful extraction/parsing result. Any future feedback from StyleProfiler into extraction/parser requires a new ADR and explicit validation protocol.

---

## ADR-005 — Safe abstention is a valid output

**Status:** accepted

`unknown`, `audit_required`, review-only states, or refusal to apply an experimental repair are valid results when evidence is insufficient.

**Consequence:** experimental code must not force output merely to increase recall or record count.

---

## ADR-006 — Repairs require evidence and regression protection

**Status:** accepted

Adaptive/experimental repairs may replace a candidate result only when explicit gates are satisfied and previously validated stable behavior is protected.

**Consequence:** every new failure mode should receive focused tests; stable outputs should remain unchanged unless a documented defect is intentionally corrected.

---

## ADR-007 — Development material is not external effectiveness evidence

**Status:** accepted

Documents, fixtures, or challenge cases that influenced rule construction belong to development evaluation. They cannot be reported as an unbiased estimate of effectiveness.

**Consequence:** holdout/external evaluation must use material not used to define the tested rule, and reports must identify when a corpus ceased being holdout because it influenced development.

---

## ADR-008 — Candidate, validated, and released are different states

**Status:** accepted

Passing a test suite, producing a wheel/ZIP, or increasing a version number does not by itself create a stable release.

**Consequence:** documentation and PRs must state explicitly whether the result is development, field-test candidate, release candidate, or stable release.

---

## ADR-009 — Historical reports are immutable evidence

**Status:** accepted

Version-specific reports document the state and reasoning of that version at that time.

**Consequence:** do not rewrite old reports to match the current architecture. New corrections belong in a new report, governance note, or superseding ADR.

---

## ADR-010 — Version identifiers cannot silently collapse divergent algorithms

**Status:** accepted — 2026-09-06

Two independent development lines were historically labelled algorithm `0.6.6`: the Cabrera dominant-margin topology reconciliation on `dev`, and the UNR28/UNR30 structural repairs on the frozen `v0.9.10-rc1-unr28-unr30` validation branch.

**Decision:** both historical labels remain immutable evidence. Their combined implementation is identified as algorithm `0.6.7`; neither old report is retroactively renamed.

**Consequence:** when a version-number collision is discovered, Project Steward must preserve both provenances and allocate a new integration identifier before promotion.

---

## ADR-011 — Structural repair precedence is explicit and single-effective

**Status:** accepted — 2026-09-06

A bibliography zone may satisfy more than one candidate repair. Applying several mutating repairs sequentially without a declared order would make the final boundary set difficult to audit.

**Decision:** validated v0.6.5 regimes retain first precedence. The RC1 column/page-column route is evaluated through the existing column gate after baseline v0.6.5 abstention. For moderate long-segment under-segmentation, raw hanging-indent is tried before the less-specific vertical-gap fallback. The Cabrera dominant-margin repair runs only when stronger structural regimes have not already repaired the zone.

**Consequence:** rejected/abstained candidate diagnostics may be retained, but one effective structural repair owns a zone at a time. Any future change to this order requires a new ADR and combined non-regression evidence.

---

## How to supersede an ADR

A durable architectural change must:

1. identify the ADR being changed;
2. explain why the old rule no longer applies;
3. specify affected version axes;
4. define migration/non-regression consequences;
5. define validation evidence required;
6. mark the old ADR `superseded by ADR-XXX` rather than deleting it.
