# BiblioRef document-title v2.1 — validation report

Date: 2026-09-04

## Scope

This report validates the automatic thesis-title detector independently from bibliography extraction and reference parsing. The final implementation lives in `biblioref/document_title.py` and is integrated downstream through `biblioref.metadata.integration`; author, year, university, faculty and program suggestions remain owned by `biblioref.metadata.cover`.

The development process deliberately separated tuning documents from untouched holdouts. Once a holdout failure was inspected and used to modify the detector, that document was moved into development and was not counted again as independent validation.

## Main mechanisms in v2.1

- multiline title reconstruction before minimum-length filtering;
- relative typography, alignment and vertical continuity rather than absolute font size alone;
- barriers for author/advisor/institution/degree lines;
- section-page roles (`Acknowledgements`, `Declaration`, contents, abstract, etc.);
- explicit repository-cover-sheet detection and skip;
- repeated running-title evidence for PDFs whose original cover is missing;
- conservative PDF-metadata ranking instead of unconditional metadata acceptance;
- lexical corroboration of clean metadata against fragmented historical covers;
- numeric continuation lines such as `(2007-2019)`;
- filename fallback when PDF evidence is unsafe.

## Development set

After two diagnostic rounds, 15 real PDFs were used as development/regression material. v2.1 returned the expected title on 15/15. These documents are **not** reported as independent accuracy.

Representative failure classes included Word-generated metadata, university headers larger than titles, title/subtitle font changes, author lines attached to titles, declaration pages, acknowledgements before the title, repeated running headers, historical fragmented covers and repository-generated cover sheets.

## Second holdout — diagnostic, then consumed

The detector was frozen before opening five new PDFs. Exact-title accuracy was:

- legacy app title detector: 3/5;
- frozen pre-v2.1 detector: 3/5.

The new detector fixed a false Italian metadata title but exposed two new general failure classes: a fragmented historical cover and a Warwick repository cover sheet. Those two failures were then used to develop v2.1, so this holdout was consumed and is not the final independent estimate.

## Third holdout — untouched final validation

Five PDFs were selected before their true titles were inspected. Predictions were recorded before labels were read. The final v2.1 code was frozen before prediction.

| PDF | Expected title | Legacy app | `cover-metadata-v0.1` | `cover-metadata-v0.2` | v2.1 |
|---|---|---:|---:|---:|---:|
| `underpin.pdf` | *Underpinnings of dispositional optimism and pessimism and associated constructs* | wrong metadata | exact | exact | exact |
| `mvnavarro.pdf` | *Eficacia de la Terapia Dialéctica Comportamental en el tratamiento de pacientes con comorbilidad entre el trastorno límite de la personalidad y los trastornos de la conducta alimentaria* | truncated | truncated | truncated | exact |
| `379932_988108.pdf` | *Phonological and orthographic processes in Spanish deaf skilled readers* | exact | exact | author selected as title | exact |
| `SEDICI_HUM_095.pdf` | *La iniciativa para la integración en infraestructura regional suramericana. Estudio del Eje Hidrovía Paraguay-Paraná a partir del proyecto de reconversión del Puerto de Santa Fe* | corrupt glyphs | filename fallback | filename fallback | filename fallback |
| `SEDICI_HUM_096.pdf` | *Información y Tecnologías de Información Geográfica como herramientas para la gestión de riesgo de desastre en pequeños productores agropecuarios de la provincia de Buenos Aires, entre 2000 y 2018* | institution + title | truncated | truncated | exact |

Exact-title accuracy on this untouched holdout:

- legacy app detector: **1/5 (20%)**;
- `cover-metadata-v0.1`: **2/5 (40%)**;
- `cover-metadata-v0.2` (latest concurrent `dev` baseline): **1/5 (20%)**;
- `document-title-v2.1`: **4/5 (80%)**.

The `cover-metadata-v0.2` comparison was run after that concurrent commit appeared on `dev`; v2.1 was not retuned after seeing it. This is a small holdout and should not be interpreted as a population estimate. Its role is regression-resistant external validation across heterogeneous layouts.

## Known limitation

`SEDICI_HUM_095.pdf` uses a broken/private-use Unicode text mapping: the visual first page is readable, but programmatic PDF text extraction yields private-use glyphs. v2.1 therefore falls back conservatively to the filename instead of returning corrupted text. Recovering this class requires a separate OCR/visual-text fallback and should remain optional so the normal title path stays fast and dependency-light.

## Regression tests

Eight synthetic tests cover the core title mechanisms, including:

1. multiline reconstruction;
2. institution header vs. title prominence;
3. garbage Word metadata rejection;
4. valid metadata fallback;
5. conservative filename fallback;
6. lexical false-positive protection (`institucionalización`);
7. fragmented historical cover + metadata corroboration;
8. repository cover-sheet skip.

Focused local result before repository integration: **8 passed**.

## Integration policy

The title detector is intentionally independent from reference extraction/parser code. `biblioref.metadata.integration` combines the robust title suggestion with the existing cover metadata suggestions, including concurrent `cover-metadata-v0.2`. Existing human-confirmed titles are preserved. A combined metadata revision forces re-evaluation only where appropriate after upgrading the cover/title subsystem.
