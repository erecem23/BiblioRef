# BiblioRef v0.9.10-rc2 / algorithm 0.6.7 — integration report

Date: 2026-09-08

## Status

`v0.9.10-rc2 / algorithm 0.6.7` is the current integrated release candidate. It is not a stable release and `main` remains unchanged at the v0.9.9 baseline.

Integration branch:

`integration/v0.9.10-rc2-algo-0.6.7`

Validated merge commit after the current-version lock migration:

`27532257747b5ac1ffa6fc183dda00266057387b`

## Purpose of the integration

The integration resolves a historical version-number collision. Two independent developments had both been labelled algorithm `0.6.6`:

1. the Cabrera dominant-margin topology reconciliation already present on `dev`;
2. the isolated v0.9.10 RC1 UNR28/UNR30 structural repairs.

The combined implementation is therefore identified as algorithm `0.6.7`; neither historical `0.6.6` result is retroactively renamed.

## Preserved architecture

The candidate preserves the validated extraction lineage rather than replacing it wholesale:

- base validated extraction lineage: `0.6.1`;
- preserved `pipeline_v065` candidate/marker/layout regime stack;
- Cabrera dominant-margin reconciliation retained as an independent repair;
- RC1 UNR28/UNR30 logic ported into `biblioref/extraction/structural_repairs_v067.py`;
- parsing remains downstream and decoupled, with current parser line `0.12.5`;
- StyleProfiler remains shadow-only;
- Google Drive remains read-only;
- the current application continues without an enabled local-model runtime.

## RC1 provenance

The RC1 scientific patch was reconstructed from the frozen validation branch fragments rather than merging the validation branch wholesale.

Reconstructed gzip SHA-256:

`fd864daf57f1da8585fc36b3c97464694b9f1424f30d770b79f66e4437b044d4`

The frozen patch touched five scientific/runtime areas: coverage audit, version config, boundary reconciliation, column reflow, and pipeline orchestration. The integration ports the relevant scientific behavior while preserving the later `dev` architecture.

## Structural repair precedence

Algorithm `0.6.7` makes repair precedence explicit:

1. strong validated v0.6.5 structural regimes keep precedence;
2. RC1 page/column-local hanging-indent recovery is considered only after the baseline column route abstains;
3. moderate long-segment under-segmentation attempts raw hanging-indent recovery before weaker vertical-gap fallback;
4. Cabrera dominant-margin reconciliation acts only when a stronger structural regime has not already repaired the zone.

Only one structural repair is effective per zone; diagnostics for rejected candidates may remain available for audit.

## Integrated document-title work

Document-title v2.1 was ported onto the current `dev` line instead of merging its stale branch wholesale. During full-suite validation two integration regressions were found and corrected:

- Spanish degree-purpose text such as `Para obtener el título de ...` could remain as an automatic title;
- a title-only revision could trigger metadata recalculation and overwrite already-current verified cover metadata.

After the fixes, both functional failures disappeared.

## Current-version test migration

The candidate intentionally changes public current-version assertions from software `0.9.9` / algorithm `0.6.6` to software `0.9.10-rc2` / algorithm `0.6.7`.

Before changing tests, all old literals were inventoried. The migration changed only:

- 31 current software-version locks;
- 8 current algorithm-version locks.

A historical `{"software_version": "0.9.9"}` input fixture in the v0.7.0 audit-bundle regression was intentionally preserved.

No runtime code, corpus, field-result artifact, or historical report was modified by the version-lock migration.

## Full-suite validation

GitHub Actions workflow run `34057306558` executed the complete repository suite against the PR merge tree and completed successfully.

Result:

- `770 passed`
- `3 skipped`
- `16 subtests passed`
- `0 failed`
- one dependency deprecation warning from Starlette/AnyIO, not a BiblioRef test failure.

Compilation of `biblioref` and `tests_core` also completed successfully before pytest.

## Relation to dev

At the validated RC2 merge commit, the integration branch is a strict descendant of the pre-integration `dev` HEAD `701faae257943a48c0ac7d14e095b69798e123a7`:

- ahead of `dev`: 24 commits;
- behind `dev`: 0 commits.

Therefore promotion to `dev` does not require conflict reconciliation with a newer parallel `dev` history at this point.

## Preserved RC1 field evidence

The frozen RC1 branch reported:

- UNR28: 306 structural records; no record >=100 words; coverage scan with no plausible missing references;
- UNR30: 437 structural records; no record >=100 words; coverage scan with no plausible missing references; four merged-reference suspects retained for audit.

These remain structural field results, not exhaustive human-gold accuracy denominators. They must not be presented as `306/306` or `437/437` accuracy.

## Remaining release gates

A green full suite is necessary but not sufficient to promote RC2 to stable `0.9.10`.

Still required before `main` release:

1. replay available focal/private field cases on the integrated tree without rewriting frozen historical evidence;
2. complete and seal the independent blind/manual gold subset for difficult layouts;
3. run the untouched external holdout according to the frozen protocol;
4. review any discrepancies without tuning on the same holdout;
5. only then decide whether to rename `0.9.10-rc2` to stable `0.9.10` and promote from `dev` to `main`.

## Promotion decision

The candidate is technically ready to be proposed for `integration -> dev` because:

- the integration branch is a strict descendant of `dev`;
- the full deterministic suite is green;
- version locks were migrated only after functional failures were separated from version assertions;
- historical RC and baseline evidence remain preserved.

It is **not** yet approved for `dev -> main` stable release because the independent external/manual validation gate remains incomplete.
