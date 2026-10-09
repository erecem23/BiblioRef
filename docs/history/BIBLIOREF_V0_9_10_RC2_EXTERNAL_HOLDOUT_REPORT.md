# BiblioRef v0.9.10-rc2 / algorithm 0.6.7 — external holdout replay report

Date: 2026-09-08

## Candidate under evaluation

The evaluated runtime is the promoted `dev` release candidate frozen at:

`f8423e50f71b8943d9e935f2be020c13da59fda4`

Version axes:

- software: `0.9.10-rc2`
- algorithm: `0.6.7`
- parser line: `0.12.5`

No extractor, parser, metadata, or application runtime file was modified for the external replay. The validation branch differed from the frozen candidate only by evaluation workflows.

## Frozen evaluation assets

The replay reused the already frozen RC1 external-holdout selection and policy rather than selecting new cases after seeing RC2 behavior.

Source manifest SHA-256:

`3a1837e72885fa30592bb8beef51f089a55f91a274dff16e6be2bc3a9e794662`

Frozen runner SHA-256:

`f431f1a3726b0a79300b0a2cff6e73e0561f6faeea758557625e0bba7846bc76`

The execution manifest changed only candidate-identification fields needed by the frozen runner (`software_version`, `algorithm_version`, benchmark id and candidate commit). The document selection, exclusion list and evaluation policy were asserted equal to the frozen source manifest before execution.

## Regression gate in the holdout environment

Both external runs installed the previously pinned evaluation environment and reran the complete RC2 repository suite before downloading holdout documents.

Result in both runs:

- `770 passed`
- `3 skipped`
- `16 subtests passed`
- `0 failed`
- one Starlette/AnyIO dependency deprecation warning

Therefore the holdout executions did not proceed on a runtime that failed its regression suite.

## Run A — untouched frozen access strategy

GitHub Actions run:

`34255827122`

Artifact:

- ID: `10067975229`
- ZIP SHA-256: `374c080462df4eb376c0e5c29804a6178b6039ce1a8807561dd72d27a6496358`

Raw runner summary:

- manifest documents: 14
- downloads reported `ok`: 13
- model outputs: 13
- distinct institutions reported by runner: 8
- raw aggregate threshold: `true`
- gold compared: `false`

### Required input-identity correction

The raw runner still does not itself guarantee that a downloaded PDF is the pre-registered thesis. The two Universidad de Chile entries again resolved to the same administrative form rather than their theses:

- resolved URL: `https://repositorio.uchile.cl/pdf/Formulario_de_Autorizacion_de_documentos.pdf`
- 1 page
- 465,410 bytes
- identical SHA-256 for both IDs: `ac14dccdc85663a4bd5ed6cc89e44aa3fb5d937ab710b74a0ec9581e0b7fd30a`
- zero detected bibliography zones and references

They are therefore classified as `invalid_input_identity / repository substitution`, not as valid model outputs.

Corrected Run A denominator:

- valid thesis PDFs with model output: **11**
- distinct valid institutions: **7**
- infrastructure failures: **1** (`GB_LSE_TOHIDI_2025`)
- invalid input identities: **2** (both Universidad de Chile cases)
- operational pipeline failures on valid downloaded PDFs: **0**
- corrected pre-registered aggregate threshold (`>=10` valid documents and `>=6` institutions): **met**
- gold compared: **no**

The threshold remains met after the identity correction, so the correction does not depend on preserving the runner's raw count.

## Run B — pre-existing access recovery with identity gate

GitHub Actions run:

`34256185832`

Artifact:

- ID: `10068073038`
- ZIP SHA-256: `c157c3aaaa14e7fbc5b27ce55199e1d8382cae04aa0b5ddd1c40dda0c3508976`

Run B reused the access-recovery configuration that had already been frozen on RC1 before this RC2 replay. It changes access routes only and does not change the extractor, parser, gold corpus or holdout document selection.

Raw runner summary was again 13 model outputs from 8 institutions, with the aggregate threshold marked `true` and no gold comparison.

### Identity-gate false positives on Universidad de Chile

The access-recovery identity gate correctly prevents some obvious substitutions, but it was still too permissive for the two Chile cases. It accepted repository guidance PDFs rather than the registered theses:

`CL_UCHILE_ZAMORANO_2014`

- resolved PDF: `Pauta_de_presentacion_de_tesis_2015.pdf`
- 17 pages
- 266,068 bytes
- SHA-256: `2337a5f276e4fd48f0b9ac5b46f5cccca20a0f9541a19a0ac58b1e1652c8a0e4`
- title token overlap reported by the gate: 0.2857
- author hits: 0

`CL_UCHILE_PARRA_2017`

- resolved PDF: `guia.pdf`
- 16 pages
- 135,403 bytes
- SHA-256: `dde33c5099d6104d6964ef926aea4f5d1d298f3d348e2511a6464b6ecf3f9d1d`
- title token overlap reported by the gate: 0.25
- author hits: 0

These files are not the registered thesis documents and are excluded from the scientific denominator. This is an evaluation-harness identity problem, not an extraction failure.

Corrected Run B denominator is therefore the same as Run A:

- **11 valid thesis outputs**
- **7 institutions**
- 1 infrastructure failure (LSE Tohidi)
- 2 invalid Universidad de Chile input identities
- 0 operational pipeline failures on valid inputs
- aggregate reporting threshold: **met**
- gold compared: **no**

The recovery run did not need to be used to rescue the denominator: Run A already reached the pre-registered threshold after identity correction. Its value here is diagnostic, confirming that the UChile access problem remains unresolved and that the current identity gate needs strengthening for future evaluation harnesses.

## Structural outputs on the 11 valid external theses

The following are model/auditor outputs only. They are **not accuracy metrics** and must not be interpreted as gold counts.

| ID | Records | Zones | Possible missing | Merged suspects | Max words/record | Audit status |
|---|---:|---:|---:|---:|---:|---|
| `UY_UDELAR_TOMMASINO_2026` | 239 | 1 | 1 | 0 | 68 | looks_consistent |
| `UY_UDELAR_PEREZ_2023` | 112 | 1 | 0 | 0 | 60 | looks_consistent |
| `BR_UNB_BRAGA_2026` | 148 | 1 | 15 | 1 | 54 | needs_review |
| `BR_UNB_MIRANDA_2026` | 84 | 1 | 0 | 5 | 51 | looks_consistent_shadow_caution |
| `BR_UFMG_BATISTA_2024` | 156 | 6 | 31 | 3 | 508 | needs_review |
| `GB_BHAM_KERR_2015` | 140 | 1 | 15 | 4 | 64 | looks_consistent |
| `GB_BHAM_GOH_2017` | 153 | 2 | 0 | 0 | 48 | looks_consistent |
| `GB_EDIN_BADAYA_2023` | 450 | 1 | 0 | 2 | 89 | looks_consistent_shadow_caution |
| `GB_EDIN_HAIG_2024` | 234 | 4 | 95 | 3 | 2494 | needs_review |
| `ES_UAB_ALFONSO_2025` | 219 | 5 | 31 | 16 | 600 | needs_review |
| `CA_MCGILL_DEDOVIC_2011` | 124 | 4 | 164 | 0 | 282 | needs_review |

`GB_LSE_TOHIDI_2025` was not scored in these RC2 runs because access failed and is recorded as an infrastructure failure.

## Cross-version external no-regression observation

Eight valid documents are directly shared between the corrected RC1 run #10 and the current RC2 replay:

- Tommasino
- Pérez
- Braga
- Miranda
- Badaya
- Haig
- Alfonso
- Dedovic

For all eight, the RC2 replay reproduced the same structural record counts, possible-missing counts, merged-suspect counts and maximum record lengths reported in the frozen RC1 run #10 audit.

This is evidence that integrating algorithm `0.6.7` did not destabilize those eight previously observed external outputs. It is **not** evidence of correctness against gold.

The current replay additionally obtained valid inputs for UFMG Batista and both Birmingham documents, which were unavailable in corrected RC1 run #10. Tohidi moved in the opposite direction: it was available in RC1 run #10 but was an infrastructure failure in both current RC2 runs.

## What the holdout now supports

The external replay now supports the following defensible claims:

1. the frozen RC2 runtime passes its complete deterministic test suite in the pinned holdout environment;
2. the pre-registered external aggregate coverage threshold is met after input-identity correction: 11 valid theses across 7 institutions;
3. there were no operational pipeline crashes on the valid downloaded thesis PDFs;
4. eight previously observed external outputs are structurally unchanged relative to the frozen RC1 audit;
5. several difficult documents still generate strong internal warnings and must remain unresolved until independent gold is completed.

It does **not** support:

- precision, recall or F1;
- exact extraction accuracy;
- treating model record counts as true reference counts;
- claiming that `looks_consistent` means correct;
- tuning algorithm `0.6.7` on Haig, Alfonso, Dedovic, Batista, Braga, Kerr or any other holdout behavior while still calling the same material untouched holdout for that correction.

## Blind-gold gate remains open

The independent blind-gold corpus was frozen before this replay and must not be reselected according to RC2 outputs. Its closed set contains 10 documents:

Tommasino, Pérez, Batista, Kerr, Goh, Badaya, Haig, Tohidi, Alfonso and Dedovic.

The gold protocol explicitly excludes the two Universidad de Chile cases because of invalid input identity and excludes the two Universidade de Brasília cases from that closed gold package according to the earlier recovery state.

Current annotation status remains incomplete:

- Annotator A regions complete for Tohidi, Goh (2 regions) and Kerr;
- seven other corpus documents still require blind region inspection;
- Tohidi has 65 numbered starts located but exact anchors still need sealing;
- Round B has not started;
- adjudication has not started;
- final gold is not sealed.

Therefore stable release promotion remains blocked.

## Next decision

Do **not** modify the extractor from the structural holdout warnings yet.

The next scientifically valid release gate is:

1. finish blind Annotator A on the frozen 10-document gold corpus;
2. independently complete Annotator B;
3. adjudicate region and boundary disagreements;
4. seal final gold files and hashes;
5. recover/replay the exact Tohidi input for RC2 if needed for the closed gold comparison;
6. only then compute region/boundary/reference metrics and decide whether `0.9.10-rc2 / 0.6.7` can become stable `0.9.10` or whether holdout failures justify a new development cycle.

`main` must remain unchanged until that decision.
