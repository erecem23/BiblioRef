# BiblioRef baseline sanitation — 2026-09-04

This change restores the deterministic repository baseline before integrating the MetadataResolver feature.

## Initial state

On `dev@f902b5701289aec4ad9c4d8fbb2ac6dffa83eb47`, the full Python 3.11 suite produced:

- 613 passed
- 17 failed
- 3 skipped
- 16 subtests passed

## Root causes and fixes

### Frozen gold byte locks

Seven parser freeze checks failed because release CSVs were originally hashed with CRLF bytes but Git checkouts on Linux normalized them to LF. The expected SHA-256 values were correct. `.gitattributes` now preserves CRLF for those seven frozen files; the gold contents and expected hashes are unchanged.

### Effective algorithm version

Eight historical tests still expected `ALGORITHM_VERSION == "0.6.5"`, while `dev` deliberately moved to `0.6.6` in the dominant-margin reconciliation integration. Those stale assertions now follow the effective algorithm version; behavioral assertions are unchanged.

### Parser v0.12.2

Parenthesized contextual ranges such as `(2005-2010)` were labeled as title-year evidence when an earlier parser layer retained the range inside the recovered title. v0.12.2 now preserves such parenthesized ranges as `context`, while ordinary title ranges such as `2020-2021` remain `title` evidence.

### Parser v0.12.5

A URL-only citation explicitly saying that editorial/publication data are absent could inherit `informe_documento` from a generic document noun. The recovery is intentionally narrow: it requires an explicit retrieval URL/cue, no publisher, and an explicit no-imprint phrase (`sin datos editoriales`, equivalent publication-data wording). Genuine institutional reports accessed online are not broadly reclassified.

## Validation

Final branch gate on Python 3.11:

- 630 passed
- 0 failed
- 3 skipped
- 16 subtests passed

A permanent `.github/workflows/repository-gate.yml` now runs the full deterministic suite for pushes and pull requests targeting `dev`.
