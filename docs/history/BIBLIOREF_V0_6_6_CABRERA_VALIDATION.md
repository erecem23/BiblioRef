# BiblioRef algorithm v0.6.6 — Cabrera field validation

Date: 2026-09-04

## Scope

Private field validation of extraction only. The real thesis PDF and its real references are **not** committed to the repository. The development trigger was a UBA master's thesis with a 13-page bibliography and a dominant hanging-indent/first-line margin geometry.

## Failure hidden by count equality

The v0.6.5 export contained 158 rows and the bibliography contained 158 true references, but two opposite boundary errors cancelled numerically:

- one false split created a spurious row beginning with `51. Buenos Aires: ...`;
- one missed boundary fused two consecutive author-year references;
- additionally, 11 records lost continuation-only text lines, mainly URLs after `Disponible en:`.

Therefore raw row count alone was insufficient as an extraction validation metric.

## v0.6.6 repair

`dominant_margin_topology_reconciliation_v0_6_6` is a narrow post-segmentation repair. It only activates for author-year-like zones when:

- baseline reference starts have an overwhelmingly dominant x margin;
- local candidate starts have bibliographic year/source evidence;
- candidate evidence purity and segment-size gates pass;
- topology changes are very small;
- same-count replacement requires a balanced removed/added start pair and at least one off-margin baseline start.

Accepted records are rebuilt from physical document lines so continuation-only URLs are preserved.

## Real-PDF replay (not stored in repo)

- true bibliography references: 158
- v0.6.5 exported rows: 158
- v0.6.6 reconciled rows: 158
- removed spurious start signatures: 1
- recovered true start signatures: 1
- records with continuation text recovered: 11
- continuation characters recovered: 742
- dominant start-margin support: 0.994
- candidate evidence ratio: 1.000

A second real-PDF regression replay on the previously validated 99-reference Apolonio case remained 99/99 and did **not** activate the new dominant-margin repair.

## Automated regression

Synthetic regression tests cover:

- same-count false-split + missed-boundary repair;
- continuation URL preservation;
- clean bibliography abstention;
- low dominant-margin support abstention.

Local suite after integration: **548 passed, 3 skipped, 16 subtests passed**.

## Privacy

No real thesis, real reference list, or user export is committed. Only synthetic fixtures/tests and aggregate validation metrics are kept in the repository.
