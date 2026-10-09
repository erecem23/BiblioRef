# PDFium dual-backend experiment

Date: 2026-09-09

## Baseline

The experiment is now synchronized with the latest green `dev` observed during the benchmark:

- branch: `dev`
- commit: `f5cd32f4b1d1c332d9d41dfab76b91976f761567`
- message: `test: follow active cover metadata revision`
- Repository Test Gate: success

The repository technical identifier remains `0.9.10-rc2`; this branch does not claim a new release.

## Purpose

Evaluate whether BiblioRef can eventually replace the mandatory PyMuPDF/MuPDF dependency with a PDFium backend without changing validated bibliographic behavior.

PyMuPDF remains the stable authority during this experiment. PDFium is shadow-only.

## Implementation state

- keep `PyMuPDF>=1.23,<2.0` installed;
- add `pypdfium2>=5.13,<6.0`;
- experimental PDFium `LayoutLine` extraction;
- convert PDFium bottom-left coordinates to BiblioRef top-left coordinates;
- differential layout report;
- pipeline-level A/B helper that injects PDFium only for offline comparison;
- batch CLI for repeated fixed-corpus replay;
- no rerouting of the default application backend.

## Evidence

### Repository fixture

`fixtures/document_grammar_stress.pdf` produced 44 lines with both engines, exact page/text sequence equality, median bbox difference around 0.30 pt, maximum around 2.34 pt and identical median font sizes.

### Real SEDICI-10 corpus

Ten historical `SEDICI_HUM_*.pdf` files were replayed with SHA-256 identities frozen in `benchmarks/pdfium_sedici10_2026-09-09.csv`.

The result is mixed:

- normalized full-page text is extremely similar across engines;
- physical-line grouping is not yet equivalent on several real theses;
- `SEDICI_HUM_055` and `SEDICI_HUM_090` are clear adversarial cases;
- the current character-by-character PDFium layout adapter is substantially slower than PyMuPDF, although raw text extraction is roughly comparable.

See `PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md` for the full interpretation.

## Migration gate

PDFium must not become the stable backend until the same frozen corpus passes all of these levels:

1. PDF ingestion: same pages and substantively equivalent text;
2. layout compatibility: stable physical-line reconstruction or explained/tolerated geometry differences;
3. structural decisions: equivalent headings, pages, styles, columns, margins, boundaries and rescue routes;
4. bibliographic output: **exact `records`** on frozen stable cases;
5. performance: acceptable elapsed time and memory after adapter optimization;
6. packaging/licensing: PyMuPDF absent from distributed artifacts and third-party notices updated.

Raw bbox identity is not required. Exact bibliographic records and semantic zone decisions are the blocking contract.

## Current decision

Do not switch BiblioRef to PDFium yet. Continue with a compatibility adapter that more faithfully reconstructs MuPDF-style physical lines, then replay the exact same SHA-pinned corpus.
