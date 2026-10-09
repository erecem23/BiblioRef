# BiblioRef — Project State

**Purpose:** canonical reconciliation page for the current repository state. Historical reports remain immutable evidence.

**Last reconciled:** 2026-09-08

## Current closure state

BiblioRef `0.9.10-rc2 / algorithm 0.6.7` is the **final technical snapshot of the current development cycle**.

The independent blind-human gold exercise is deferred and is no longer a blocking requirement for closing this software-development cycle. Simulated annotators are not accepted as independent human evidence.

This means the project is technically closed for the current cycle, but the snapshot must not be described as having known human-gold precision, recall or F1.

The software identifier remains `0.9.10-rc2` intentionally. It distinguishes a technically completed and externally exercised snapshot from a hypothetical future release whose extraction accuracy has been quantified against sealed independent gold.

## Preserved historical anchors

- `main` historical v0.9.9 baseline: `bfa9191118a1002f291f05816f675d7f40d0f179`.
- frozen pre-integration `dev`: `701faae257943a48c0ac7d14e095b69798e123a7`.
- frozen isolated RC1 validation: `c972ec17ecc6162e06fef830865e39ce236c559e`.
- frozen promoted RC2 runtime: `f8423e50f71b8943d9e935f2be020c13da59fda4`.
- current reconciled `dev` documentation state includes the RC2 external-holdout report and closure evidence.

Historical branches/reports must not be rewritten to make them appear to have used algorithm `0.6.7`; the version exists specifically to reconcile two independently developed lines that had both previously used the label `0.6.6`.

## Version axes

| Axis | Current final technical snapshot | Status |
|---|---|---|
| BiblioRef software | `0.9.10-rc2` | `final_technical_snapshot` |
| Algorithm | `0.6.7` | `integrated_green` |
| Stable extraction base | `0.6.1` | `preserved` |
| Stable engine | `0.4.5` | `preserved` |
| App/UI | `2.7.0` | `current` |
| Parser | `0.12.5` | `current` |
| StyleProfiler | `0.1-shadow` | `shadow_only` |
| Document title | `2.1` | `integrated_green` |
| Google Drive | `0.2` | `read_only` |
| Local AI runtime | disabled in current app | `preserved_policy` |

## Algorithm 0.6.7 provenance

Algorithm `0.6.7` preserves and integrates:

1. the validated v0.6.5 candidate-region / marker-regime / layout-regime pipeline in `pipeline_v065`;
2. the independent Cabrera dominant-margin topology reconciliation developed on `dev` and historically labelled `0.6.6`;
3. the frozen v0.9.10-rc1 UNR28/UNR30 structural repairs, independently also labelled `0.6.6` on their validation branch.

The RC1 code-only patch was reconstructed rather than merging the validation branch wholesale. Reconstructed gzip SHA-256:

`fd864daf57f1da8585fc36b3c97464694b9f1424f30d770b79f66e4437b044d4`

The integrated RC logic lives in `structural_repairs_v067.py`; `pipeline_v065` remains preserved.

## Structural repair precedence

ADR-011 remains authoritative:

1. validated v0.6.5 structural regimes retain precedence;
2. RC two-column/page-column candidates are considered only after the baseline column route abstains;
3. raw hanging-indent is attempted before vertical-gap fallback for the moderate long-segment regime;
4. Cabrera dominant-margin reconciliation is evaluated only when a stronger structural regime has not already repaired the zone.

Only one structural repair may mutate a zone effectively at a time; alternative diagnostics may remain visible for audit.

## Deterministic validation

The integrated line repeatedly passed the complete deterministic repository suite, including inside the pinned external-holdout environment:

- `770 passed`;
- `3 skipped`;
- `16 subtests passed`;
- `0 failed`.

The actual promotion merge tree also passed both the Repository Test Gate and Metadata Resolver Gate before integration into `dev`.

Two real document-title/metadata integration regressions discovered by the full suite were fixed before the candidate was promoted.

## External holdout evidence

The already frozen external-holdout manifest and runner were replayed against the frozen RC2 runtime without redefining document selection or policy after observing candidate behavior.

Frozen manifest SHA-256:

`3a1837e72885fa30592bb8beef51f089a55f91a274dff16e6be2bc3a9e794662`

Frozen runner SHA-256:

`f431f1a3726b0a2cff6e73e0561f6faeea758557625e0bba7846bc76`

After correcting input identity:

- valid thesis PDFs with RC2 model output: **11**;
- distinct valid institutions: **7**;
- preregistered threshold (`>=10` valid documents and `>=6` institutions): **met**;
- invalid input identities: **2** Universidad de Chile repository substitutions;
- infrastructure failures: **1** LSE input;
- operational pipeline failures on valid downloaded thesis PDFs: **0**;
- independent human gold compared: **no**.

Eight documents shared with the corrected RC1 audit reproduced their reported structural counts and diagnostics exactly. This is structural no-regression evidence only.

The access-recovery replay also showed that the evaluation harness can falsely accept generic repository guidance PDFs. That is a future harness issue and does not change algorithm `0.6.7`.

## Field evidence preserved without overclaim

The RC field reports remain structural evidence:

- UNR28: 306 effective structural records after page/column-local hanging-indent recovery, with 26/26 columns profiled and no records >=100 words;
- UNR30: 437 effective structural records after raw hanging-indent reconciliation, maximum record length 49 words, with four merged-reference suspects retained as audit items.

These values are not human-gold denominators and must not be written as `306/306` or `437/437`.

## Blind gold — deferred, not simulated

A 10-document independent blind-gold corpus and partial Annotator A material are preserved historically. Round B and adjudication were not completed.

By explicit project-closure decision on 2026-09-08:

- the unfinished human-gold exercise is deferred outside the current development cycle;
- no simulated A/B annotation is presented as independent evidence;
- no precision, recall, F1 or exact extraction-accuracy metric is claimed;
- the gold branches and protocol remain available if a future validation study resumes.

## Final interpretation

Supported statements:

- the integrated RC2 technical line is green;
- algorithm `0.6.7` reconciles and preserves the intended structural repair lines;
- the preregistered external threshold was met after correcting input identity;
- no operational pipeline crashes occurred on the 11 valid external thesis PDFs;
- repeated deterministic validation is green;
- external shared-case structural diagnostics show no regression.

Unsupported statements:

- known human-gold precision/recall/F1;
- exact reference accuracy;
- equivalence between `looks_consistent` and correctness;
- treating model record counts as true reference counts.

## Main promotion policy

This final technical snapshot may be promoted to `main` after normal repository gates pass on the proposed merge tree.

A `main` promotion means **current technical baseline / completed development snapshot**. It does not retroactively convert this snapshot into an independently gold-validated accuracy release.

If development resumes in the future, start from this snapshot and open a new version line. Do not tune on the preserved holdout and then continue calling that same material untouched validation for the new correction.

## Historical state conflict

`CURRENT_FIELD_TEST_STATE.json` remains an older historical state (`software 0.9.8`, `algorithm 0.6.4`, app 2.7.0, parser v0.11, StyleProfiler v0.1-shadow). It is not silently rewritten as a live-state file.

## Architectural contracts preserved

- Parsing remains decoupled from extraction boundaries.
- StyleProfiler remains observational while shadow-only.
- Adaptive repairs remain gated and may abstain safely.
- `audit_required` / review-only output is acceptable under insufficient evidence.
- External evaluation remains distinct from development material.
- Historical reports remain immutable.
- Divergent algorithms cannot silently share an integration identifier.
- Structural repair precedence remains explicit and single-effective.
- External holdout failures are not used to retune the same candidate while preserving an untouched-holdout claim.

## Closure record

Detailed integration evidence: `BIBLIOREF_V0_9_10_RC2_INTEGRATION_REPORT.md`.

Detailed external evidence: `BIBLIOREF_V0_9_10_RC2_EXTERNAL_HOLDOUT_REPORT.md`.

Final closure policy: `BIBLIOREF_V0_9_10_RC2_FINAL_TECHNICAL_SNAPSHOT.md`.
