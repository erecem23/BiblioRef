# Release notes — BiblioRef v0.9.9 candidate

- Software: **0.9.9**
- Algorithm: **0.6.5**
- APP: **2.7.0**
- Parser: **0.11 frozen**
- StyleProfiler: **0.1-shadow frozen**

## Added

- CandidateRegionV2 -> effective geometry bridge.
- Provisional candidate regions are repair-only: if no structural gate accepts them, public output remains `audit_required`.
- Exact numeric continuation can extend a candidate bibliography by a short final page.
- Hierarchical numeric marker regime (`1.1.`, `1.2.`, ...).
- Persistent vertical-gutter detection for two-column bibliography layouts.
- Stronger numeric-marker authority over year-like continuation lines.

## UNR checkpoints

- 12: 147/147
- 13: 165/165
- 14: 147/147
- 16: 126/126
- 17: 175/175
- 18: 101 across seven local bibliography zones
- 20: 208/208
- 25: 188/188
- 29: two-column reflow accepted, 109 records

Known unresolved: UNR 28 remains `audit_required`; UNR 30 still has under-segmentation.

## Tests

543 passed, 3 skipped, 16 subtests passed.

## UNC boundary reconciliation update

External UNC field test added (`UNC_FERREYRA_2017`). Strong hanging-indent reconciliation is now symmetric under a strict gate: it can remove weak `author+bare_year+local_geometry` continuation-margin splits while recovering a true start-margin institutional author whose year appears on the following line. Result: **109 -> 102/102** on the audited UNC bibliography.

Repeated-author entries beginning with a year are explicitly protected from negative-delta reconciliation.

No change to stable `biblioref_v0_4.py`, parser v0.11 or StyleProfiler.

Updated suite: **545 passed, 3 skipped, 16 subtests passed**.
