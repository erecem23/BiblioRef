# BiblioRef — PDFium object-level compatibility adapter

Date: 2026-09-09

## Decision

The first character-by-character PDFium prototype should be retired. The new object-level compatibility adapter is substantially closer to BiblioRef's current MuPDF `LayoutLine` contract and removes the earlier Python-level performance penalty.

**PyMuPDF still remains the stable authority.** This development is not yet a backend switch. A full pipeline replay on the current `0.6.7` line across the fixed ten-thesis corpus is still required before packaging experiments may remove PyMuPDF.

## What changed

The adapter now reconstructs physical lines from PDFium text objects rather than calling character boxes for every glyph.

For each page it:

1. extracts PDF text objects and their bounds, matrices, fonts and font sizes;
2. converts PDFium coordinates to BiblioRef's top-left convention;
3. derives effective font size from the text-object transform;
4. groups objects by visual baseline;
5. concatenates adjacent objects with the same font/size as surrogate spans;
6. joins surrogate spans with one space, matching the current MuPDF `get_text("dict")` contract;
7. maps legacy Word/PDF discretionary-hyphen controls to soft hyphens;
8. preserves dense detached mid-row bullet/marker objects on pathological OCR-era pages so conservative fallback ambiguity is not accidentally erased;
9. performs BiblioRef's existing second-stage y-band merge without changing downstream extraction logic.

The stable application route is unchanged.

## Fixed SEDICI-10 replay

The exact same SHA-pinned SEDICI-HUM corpus from `PDFIUM_SEDICI10_DIFFERENTIAL_REPORT.md` was reused. The table below measures the final 50 pages of each thesis, as in the first benchmark.

| PDF | v1 matched fraction | object adapter | median page ratio | PDFium/PyMuPDF time |
|---|---:|---:|---:|---:|
| 022 | 0.9308 | **0.9741** | 1.0000 | 0.380x |
| 055 | 0.5579 | **0.9515** | 0.9602 | 1.587x |
| 090 | 0.4986 | **0.7072** | 0.8259 | 0.747x |
| 092 | 0.8588 | **0.9372** | 1.0000 | 0.753x |
| 093 | 0.7637 | **0.9762** | 0.9787 | 2.278x |
| 094 | 0.8102 | **0.9858** | 1.0000 | 0.407x |
| 097 | 0.7555 | **0.9899** | 1.0000 | 0.280x |
| 098 | 0.9399 | **0.9657** | 1.0000 | 0.289x |
| 099 | 0.8539 | **0.9529** | 1.0000 | 0.431x |
| 100 | 0.9746 | **0.9873** | 1.0000 | 0.478x |

Eight of ten documents now exceed 0.95 exact physical-line text matching in the bibliography-tail stress window. `SEDICI_HUM_055`, previously one of the two worst documents, improves from about 0.558 to about 0.952.

`SEDICI_HUM_090` remains the clear layout outlier. Its raw line match rises from about 0.499 to about 0.707, but raw physical-line identity is not by itself the migration criterion; the important question is whether downstream bibliographic decisions remain equivalent.

The companion raw metrics are frozen in `benchmarks/pdfium_sedici10_object_adapter_2026-09-09.csv`.

## Performance

The earlier adapter called PDFium character geometry from Python at very high frequency and ran about 2.5x to 11.5x slower than PyMuPDF on these windows.

The object-level adapter removes that bottleneck. In eight of ten documents the measured PDFium window is faster than PyMuPDF. The two slower cases are `055` (about 1.59x) and `093` (about 2.28x). These are single-run development measurements, so they should be treated as directional rather than as a formal microbenchmark, but the prior order-of-magnitude regression is gone.

## Adversarial pipeline checks

### SEDICI_HUM_090

The first candidate produced a false late bibliography zone. Inspection showed that MuPDF also sees the pages around 306–309 as reference-like, but its richer physical layout preserves several other ambiguous late regions, causing the conservative fallback to abstain. The simplified PDFium representation had erased many detached marker glyphs and made 306–309 look uniquely plausible.

The fix is entirely backend-local: on pages containing a dense population of detached marker objects, mid-row marker objects are preserved as separate physical fragments. No bibliography detector, fallback threshold or downstream extraction rule was relaxed.

With that representation the local differential run returns the same stable result for `090`: **0 bibliography zones and 0 records**.

### SEDICI_HUM_055

The object adapter recovers the same local pipeline structure as the stable backend: **1 bibliography zone and 10 references**, with the same semantic zone decision. Remaining raw record differences are backend-specific geometry/audit diagnostics and tiny OCR-era physical-wrap spellings, such as a normal hyphen versus a discretionary soft hyphen.

After canonicalizing only physical line-wrap hyphens, reference-text similarity is at least approximately **0.9996** in the local adversarial replay. This is why the pipeline differential helper now reports two separate gates rather than silently pretending raw byte identity and bibliographic equivalence are the same concept.

## Two-level migration gate

The experimental A/B helper now exposes:

- `strict_raw_gate`: exact raw records plus semantic-zone equivalence;
- `migration_gate`: same record count/order, exact semantic record metadata, exact semantic-zone decisions, and canonical reference/annotation text similarity >= 0.999.

Raw geometry, audit flags and fingerprints derived from raw PDF spelling remain visible as diagnostics but do not decide bibliographic equivalence. The canonicalization is intentionally narrow: it joins only obvious physical-wrap normal/soft-hyphen variants; an internal string such as `New York-London` is left unchanged.

This distinction prevents harmless engine-coordinate differences from blocking a migration while still making any bibliographically material change fail the gate.

## Fixture regression

`fixtures/document_grammar_stress.pdf` remains 44 lines with both engines and exact ordered line text. Effective median font sizes remain exact. Raw vertical bbox differences use a wider diagnostic tolerance because PDFium exposes glyph-tight bounds while MuPDF span boxes include different ascender/descender padding.

A pipeline-level fixture test also requires semantic-zone and bibliographic-record equivalence.

## Next blocking validation

Before PyMuPDF can be removed from installation or distribution:

1. run the current `0.6.7` pipeline A/B over all ten fixed PDFs, not only the two adversarial cases;
2. inspect every migration-gate failure rather than changing thresholds globally;
3. require all existing repository CI gates to remain green;
4. only after the fixed corpus passes, test a PyMuPDF-free package/wheel in an isolated environment;
5. retain PyMuPDF as the application default until those gates pass.

Current status: **compatibility adapter materially improved; replacement not yet approved.**
