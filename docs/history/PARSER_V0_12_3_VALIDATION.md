# BiblioRef parser v0.12.3 — field-validation note

## Scope

- Parser-only validation; reference extraction/segmentation is unchanged.
- External field corpus: 99 extracted references from one real thesis used locally for replay.
- The thesis PDF and its real bibliography are **not** committed to the repository.
- Repository regression fixtures are synthetic and reproduce only structural patterns.

## Residual families targeted after v0.12.2

1. Multi-sentence monograph/report titles truncated before the imprint.
2. Journal articles with `volume(issue)` but no explicit page range.
3. Generic `material_web` classification overriding a stronger institutional report/guide identity.
4. Weak lexical publisher fragments where an explicit institutional publisher is present.
5. Web source/title inversion in `Extraído de ...` forms.
6. Repository URLs that plausibly indicate a thesis but lack explicit textual thesis evidence.
7. Conference locator/page numbers retained inside the parsed title.
8. Web source duplicated as publisher.
9. Article-shaped metadata whose selected container name is semantically monographic (`Manual ...`).

## Replay impact on the 99-reference field corpus

The v0.12.3 overlay is expected to alter selected bibliographic fields in 15 references relative to the reconstructed v0.12.2 field output:

| Field family | References changed |
|---|---:|
| Publication type | 6 |
| Title | 5 |
| Publisher | 4 |

Four references receive new semantic review evidence rather than forced reinterpretation:

- 3 repository-access records: `possible_repository_thesis` with `tesis` retained only as a type candidate.
- 1 article-shaped record with a monographic/manual-like container: `serial_container_monograph_like`.

The three repository cases already carry date-related review evidence in the year-audit layer, so the new flag adds a reason rather than necessarily increasing the number of unique references sent to review.

## Safety rules

- Article recovery without pages requires a serial cue plus `volume(issue)` geometry.
- Multi-sentence title recovery requires a closing imprint and only applies to monograph/report/guide types.
- Institutional PDF reclassification requires an institutional author plus strong document evidence.
- Repository/thesis URLs never force `tesis` without explicit bibliographic wording; they only create a candidate and a review flag.
- Manual-like serial containers are flagged, not auto-retyped.
- v0.12.2 contextual year roles remain untouched.

## Regression coverage

`test_parser_v0_12_3.py` adds synthetic fixtures for all nine families above plus a normal-article guard case.
