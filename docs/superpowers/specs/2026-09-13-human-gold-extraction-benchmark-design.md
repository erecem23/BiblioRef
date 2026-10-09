# Independent human-gold extraction benchmark v0.1

Date: 2026-09-13

## Status

Approved design for the first independent human-labelled benchmark of BiblioRef's extraction core after the PDFium migration and core-first first-reference repair were integrated into `dev`.

Baseline before this design:

- `dev = f185f96fc850084b8da785e06a83df99e452e59a`;
- public extraction algorithm `0.6.8`;
- automatic extraction authority is `biblioref.pipeline.process_pdf()`;
- repository/migration gates are green;
- SEDICI-10 remains engineering migration evidence, not human-gold effectiveness evidence.

This phase is evaluation infrastructure. It must not change extraction heuristics.

## Problem

BiblioRef already has strong engineering evidence: regression suites, migration gates, synthetic/adversarial fixtures, repository-specific challenge corpora and frozen differential comparisons. Those assets answer questions such as "did the PDF backend migration preserve behavior?" and "did a particular repair fix the failure it was designed for?". They do not estimate extraction effectiveness on an independent corpus because many of those documents influenced development.

The project therefore still lacks defensible estimates of:

- bibliography-region precision/recall;
- reference-boundary precision/recall/F1;
- document-level count error and catastrophic misses;
- text fidelity against what a human sees on the rendered PDF;
- uncertainty around those metrics under document clustering.

The benchmark must be isolated from the development loop so that its first result measures generalization instead of memorization.

## Goal

Create a reproducible, SHA-pinned, human-annotated benchmark whose primary test set is selected and labelled independently of BiblioRef outputs, then evaluate one frozen extraction candidate without modifying heuristics after seeing the gold.

The benchmark must support scientifically defensible descriptive claims such as:

> On the frozen human-gold v0.1 corpus, algorithm 0.6.8 achieved X boundary precision, Y boundary recall and Z macro-F1, with document-cluster bootstrap intervals.

It must not support a claim that the benchmark remains independent after its failures are used to design new rules.

## Non-goals

This phase will not:

- tune, broaden or remove extraction heuristics;
- modify bibliography-heading vocabularies, segmentation gates, first-reference repair, structural reconciliation or PDF adapters;
- optimize parser, metadata resolver or StyleProfiler behavior;
- use SEDICI-10, previous challenge PDFs, development fixtures or frozen migration cases as headline human-gold test items;
- let an LLM generate final gold labels;
- infer gold from current BiblioRef output;
- define an arbitrary accuracy target before observing the first independent baseline;
- claim normative citation-style correctness;
- convert the primary test set into a development set after the first evaluation.

## Independence contract

### 1. New documents

Every primary-test PDF must be unseen by extraction-rule development. Selection is performed from repository metadata before running BiblioRef on the selected PDFs.

A document is excluded if any of the following matches a known development/evaluation asset:

- exact SHA-256;
- canonical repository item/handle/DOI/URL;
- normalized title plus institution/year when no stable identifier exists.

The exclusion registry must include, at minimum, previous challenge documents, SEDICI migration documents, development corpora, manually diagnosed failures and any PDF explicitly used to create a rule.

### 2. Selection without model output

Primary sampling may use only source metadata available before BiblioRef execution, such as repository, country, language, year, thesis type, page count if supplied by repository metadata, and file availability.

Do not stratify or filter primary cases using:

- BiblioRef reference counts;
- detected zones;
- audit flags;
- confidence labels;
- parser output;
- StyleProfiler output;
- whether a current heuristic succeeds or fails.

### 3. Human labels from the rendered document

Annotators label what is visibly present in rendered PDF pages. Extraction text may be displayed only as a convenience after the visual decision is made and must never silently define a boundary.

### 4. One-shot first evaluation

Before the primary gold is scored, freeze and record the exact candidate commit and algorithm version. After metrics are revealed, v0.1 remains a blocked external test. Any heuristic change motivated by v0.1 errors requires a separate development set and a future unseen human-gold version for a fresh independence claim.

### 5. No benchmark-specific code paths

Production extraction code must not receive document IDs, repository names or benchmark flags. The evaluator may adapt output into a scoring representation, but it cannot modify extraction decisions.

## Corpus design

The benchmark has three partitions with different purposes.

### Pilot: 6 theses

Purpose: validate annotation UX, schema validation and evaluator mechanics only.

Rules:

- pilot cases are never included in headline metrics;
- pilot labels may be inspected while implementing the benchmark tooling;
- pilot results must not be used to change production extraction heuristics during this phase.

### Primary sealed test: 32 theses

Purpose: headline independent estimates.

Sampling constraints:

- 32 unique PDFs;
- no repository contributes more than 25% of the set;
- at least 8 repository sources when feasible;
- at least 4 countries;
- at least 3 document languages, targeting Spanish, Portuguese and English as the largest strata;
- at least 4 repositories not previously represented in extractor development when feasible;
- time diversity: at least 8 documents before 2015, at least 8 from 2015-2020 and at least 8 from 2021-2026, with the remaining 8 unconstrained;
- deterministic selection seed: `20260913`;
- one PDF bitstream per thesis, SHA-256 pinned.

If a stratum cannot be satisfied because of repository access or licensing, the manifest must record the failed constraint and the nearest feasible replacement. The selection rule may not be changed after BiblioRef results are known.

### Stress supplement: 8 theses

Purpose: describe behavior on difficult layouts without contaminating headline prevalence estimates.

The stress set is reported separately from the primary set. Cases are selected before BiblioRef execution based on human-visible or repository-level properties such as:

- scanned/OCR-heavy pages;
- chapter-wise bibliographies;
- multiple bibliography zones;
- two-column references;
- mixed scripts/languages;
- long bibliographies;
- weak or absent bibliography headings;
- reference entries spanning pages.

A stress document can be selected because it is visually difficult, but never because BiblioRef is already known to fail on it.

## Source acquisition and manifest

Create a versioned source manifest with one JSON object per PDF. Required fields:

```json
{
  "document_id": "hg01_repo_0001",
  "partition": "pilot|primary|stress",
  "repository": "repository_name",
  "country": "AR",
  "language": "es",
  "publication_year": 2021,
  "source_item_url": "https://...",
  "bitstream_url": "https://...",
  "stable_source_id": "handle/doi/oai-id/or-null",
  "sha256": "...",
  "bytes": 1234567,
  "selection_seed": 20260913,
  "selected_before_biblioref_run": true,
  "license_or_access_note": "public repository bitstream",
  "development_overlap": false
}
```

The manifest is frozen before annotation of the primary set begins. Replacement after freeze is allowed only for objective acquisition failure or corrupt/unreadable content and must be selected using the same pre-registered rule, with the replacement history recorded.

Do not commit redistributed PDFs unless licensing clearly permits it. Prefer source URLs + SHA-256 + a local cache ignored by git.

## Gold annotation model

The unit of truth is the visually rendered PDF, not the extractor's line model.

### Document label

Each document records:

- `document_has_target_bibliography`;
- annotator and annotation timestamps;
- rendering/backend version used by the annotation tool;
- optional document-level notes that do not alter scoring.

### Zone label

A target zone is a bibliography/reference list that BiblioRef's `all_reference_sections` scope is intended to return. This includes final bibliographies and chapter-level reference sections. It excludes tables of contents, publication lists, CV publication lists, indexes, prose citation lists and other bibliographic-looking regions that are not reference sections.

Each gold zone records:

```json
{
  "gold_zone_id": "z001",
  "role": "final_references|chapter_references|other_target_references",
  "start_page": 120,
  "end_page": 133,
  "start_y_ratio": 0.112,
  "end_y_ratio": 0.841,
  "heading_text": "Referencias",
  "heading_present": true,
  "notes": []
}
```

`start_y_ratio` and `end_y_ratio` are obtained by clicking the rendered page image. They are annotation coordinates, not PDFium extraction coordinates.

### Reference-start label

Every reference in every target zone receives one human-confirmed start marker. This is the main segmentation gold and avoids requiring full manual transcription of thousands of references.

```json
{
  "gold_ref_id": "z001-r0001",
  "gold_zone_id": "z001",
  "ordinal": 1,
  "start_page": 120,
  "start_y_ratio": 0.163,
  "start_anchor": "Smith, J. A. (2020).",
  "flags": ["multiline"]
}
```

`start_anchor` is a short visible prefix entered or confirmed by the annotator. It is secondary evidence for alignment; the visual start point is authoritative.

Recommended flags include:

- `multiline`;
- `page_spanning`;
- `numeric_style`;
- `inherited_author`;
- `no_year`;
- `url_or_doi_line`;
- `ocr_noise`;
- `non_latin_script`;
- `legal_or_normative`;
- `headingless_zone`.

### Full-text fidelity subset

To estimate text fidelity without manually transcribing the entire corpus, preselect 10 reference ordinals per primary document and 5 per stress document before seeing BiblioRef output.

For a zone with `N` references, include deterministic positions covering:

- first;
- last;
- approximately 25%, 50% and 75%;
- remaining positions chosen by stable hash of `document_id + ordinal`.

Annotators transcribe the full visible reference text for those sampled references into `visible_text_gold` using plain Unicode text. Line wrapping is ignored; visible characters are preserved. No correction to an external citation database is allowed: gold is what appears in the PDF.

## Annotation workflow

### Visual-first interface

Build a small local annotation application under `tools/human_gold/` that:

1. renders the current page as an image;
2. lets the annotator mark zone start/end points;
3. lets the annotator click each reference start in order;
4. captures a short start anchor;
5. presents deterministic full-text transcription tasks;
6. allows explicit non-target lookalike notes;
7. saves append-safe JSONL/checkpoints without calling the production extractor.

The annotation app may use the same PDF rendering dependency as the project for convenience, but it must not pre-populate target zones or reference starts from BiblioRef.

### Quality control

At least 25% of primary documents should receive independent double annotation if two human annotators are available. Report agreement before adjudication using:

- zone-page overlap agreement;
- absolute difference in reference counts;
- start-boundary agreement within tolerance;
- disagreement categories.

If only one human annotator is available, perform a blinded second-pass audit on at least 25% after an interval and label the release explicitly `single_annotator_gold`; do not report that audit as inter-rater reliability.

All disagreements that affect the final gold are resolved by explicit adjudication, and raw annotations remain preserved beside the adjudicated gold.

### Gold validation

A validator must reject gold files with:

- duplicate document, zone or reference IDs;
- non-monotonic ordinals;
- reference starts outside the zone page interval;
- `y_ratio` outside `[0, 1]`;
- SHA mismatch against the source manifest;
- missing required full-text samples;
- primary document lacking an annotation-completeness marker;
- unexpected overlap with the exclusion registry.

## Scoring representation

The evaluator runs the public API:

```python
biblioref.pipeline.process_pdf(pdf_path, scope="all_reference_sections")
```

with the release/default extraction configuration. No benchmark-only extraction option is allowed.

Predicted records are converted to an evaluation-only representation containing:

- predicted zone page interval;
- record order and zone ID;
- reference text;
- reference start page;
- physical start location inferred from existing evidence/layout matching when available;
- review/audit status;
- algorithm/software provenance.

Failure to infer a predicted physical start is not silently ignored. It remains a measurable unmatched prediction.

## Matching rules

### Zone matching

Match predicted and gold zones one-to-one by maximum page-interval intersection-over-union (IoU), with order as a deterministic tie-breaker.

Report at least:

- page-level zone precision/recall/F1;
- zone detection precision/recall/F1 at IoU >= 0.50;
- exact start-page accuracy;
- exact end-page accuracy;
- missed whole-zone count;
- spurious-zone count.

### Reference-boundary matching

Within matched zones, align predicted record starts to gold starts monotonically. A start is considered matched when:

1. predicted and gold start page are equal; and
2. physical y distance is within a pre-registered tolerance when both coordinates are available; otherwise the normalized predicted opening text matches the human start anchor conservatively.

Initial y tolerance for the evaluator is `0.015` of page height. Pilot data may validate the annotation tool and coordinate transformation, but the tolerance must be frozen before primary scoring.

Report:

- boundary precision;
- boundary recall;
- boundary F1;
- per-document macro-F1;
- absolute reference-count error per document;
- mean/median absolute count error;
- exact-count document rate;
- split and merge error counts derived from sequence alignment;
- first-reference miss rate;
- last-reference miss rate.

Do not treat reference count equality alone as correct segmentation.

### Text fidelity

On the preselected full-text subset, compare predicted record text with `visible_text_gold` using both raw-visible and canonicalized forms.

Report:

- character error rate (CER);
- word error rate (WER);
- normalized Levenshtein similarity;
- exact canonical match rate;
- missing/extra visible-character examples for audit.

Canonicalization may normalize whitespace and discretionary soft hyphens only. It must not delete punctuation, author names, years, identifiers or substantive characters to improve scores.

### Review/abstention behavior

Where the public report exposes manual-review or audit status, report:

- fraction of documents/records flagged for review;
- error rate conditional on review vs no-review;
- catastrophic errors emitted without a review signal.

This is descriptive and must not redefine correctness.

## Statistical reporting

Reference-level observations are clustered within documents. Therefore headline uncertainty must not pretend that thousands of references are independent samples.

For the primary set report:

- micro metrics over all items;
- macro metrics averaged by document;
- 95% document-cluster bootstrap intervals with seed `20260913` and at least 10,000 resamples;
- Wilson intervals for simple document-level proportions such as exact-count rate when useful.

Stress-set metrics are reported separately and are not pooled into the headline primary estimate.

Do not select a preferred metric presentation after observing which one looks best; generate the complete pre-registered table every run.

## Error taxonomy

The evaluator should produce a diagnostic taxonomy without modifying extraction:

- `missed_zone`;
- `spurious_zone`;
- `early_zone_start`;
- `late_zone_start`;
- `early_zone_end`;
- `late_zone_end`;
- `missed_first_reference`;
- `missed_reference`;
- `spurious_reference`;
- `merged_references`;
- `split_reference`;
- `wrong_order`;
- `text_loss`;
- `text_insertion`;
- `layout_start_unresolved`.

These labels support later diagnosis. They are not permission to change heuristics on this branch.

## Freeze and evidence lifecycle

### Stage A: infrastructure

Implement and test the sampler, exclusion registry builder, annotation app, schema validator and evaluator using synthetic data plus the 6 pilot documents.

No production extraction code changes are allowed.

### Stage B: source freeze

Commit:

- primary/stress source manifest;
- exclusion registry;
- manifest SHA-256 summary;
- exact candidate-selection script/config;
- candidate commit intended for scoring.

At this point selected PDFs must not be replaced except under the objective replacement rule.

### Stage C: human annotation

Create raw annotation files outside the extraction-development loop. Validate them against the manifest. Preserve adjudication history.

The agent implementing BiblioRef heuristics must not use primary gold during this stage.

### Stage D: candidate freeze

Record the exact extraction commit and provenance before primary metrics are revealed. The candidate may differ from the design baseline only because of benchmark tooling/docs/tests; `biblioref/` and production extraction behavior must be unchanged relative to the chosen candidate.

### Stage E: one-shot evaluation

Run the frozen candidate against the frozen human gold once, save:

- machine-readable results;
- metric summary;
- per-document outcomes;
- bootstrap output;
- environment/provenance;
- source/gold/result SHA-256 values.

After this run, the v0.1 primary set is considered observed.

### Stage F: archival

Commit the frozen gold and results only after the candidate SHA is fixed and the first scoring run is complete, or store them in a dedicated benchmark-results branch/artifact with the candidate SHA embedded.

Once observed, v0.1 can be used as a regression set, but not as fresh independent evidence for rules designed from its errors.

## Repository structure

Expected implementation layout:

```text
benchmarks/human_gold_v0_1/
  README.md
  selection_config.json
  exclusion_registry.jsonl
  source_manifest.jsonl
  SHA256SUMS.txt
  pilot/
    ...
  raw_annotations/
    ...                  # only if policy permits committing them
  frozen_gold.jsonl      # added after candidate freeze / first scoring
  evidence/
    <candidate_sha>/
      results.json
      per_document.jsonl
      summary.md
      bootstrap.json
      environment.json
      SHA256SUMS.txt

tools/human_gold/
  build_exclusion_registry.py
  sample_sources.py
  annotation_app.py
  schema.py
  validate_gold.py
  evaluate.py
  metrics.py

tests_benchmarks/
  test_human_gold_schema.py
  test_human_gold_sampling.py
  test_human_gold_matching.py
  test_human_gold_metrics.py
  test_human_gold_no_production_mutation.py
```

Names may be adjusted to match existing project conventions, but responsibilities must remain separated.

## CI policy

Normal repository CI should test benchmark code on synthetic fixtures only. It should not require downloading the full primary corpus on every push.

A separate manual workflow may:

1. download SHA-pinned public PDFs;
2. verify hashes;
3. run the exact frozen extraction candidate;
4. validate gold;
5. score and archive evidence.

The manual workflow must fail closed on any PDF SHA mismatch.

## Production-code guard

Add a repository test that records the production extraction paths permitted to change during the benchmark-infrastructure PR. At minimum, the implementation PR must show no semantic diff under:

```text
biblioref/**
app.py
```

unless an unrelated pre-existing merge changes `dev`, in which case Work must rebase and explicitly prove that its own benchmark commits do not modify production extraction code.

The benchmark tooling may import public production interfaces but production code must not import `tools.human_gold` or `benchmarks.human_gold_v0_1`.

## Acceptance criteria

The benchmark-design phase is complete when:

1. the protocol is committed before any new primary-test output is observed;
2. sampling is deterministic and uses only pre-output metadata;
3. exclusion checks cover all known development/challenge/migration documents;
4. pilot tooling can create and validate visual-first zone/reference annotations;
5. primary labels can be produced without pre-population from BiblioRef;
6. evaluator computes zone, boundary, count and text-fidelity metrics using frozen rules;
7. document-cluster uncertainty is implemented and deterministic;
8. production extraction files remain semantically unchanged;
9. source, gold, candidate and result provenance are SHA-pinned;
10. the first primary evaluation is archived before any heuristic repair based on its errors;
11. the final report explicitly separates primary, stress and pilot evidence;
12. no precision/recall/F1 claim is made from SEDICI-10 or prior development corpora in place of this human gold.

## What happens after v0.1

After the first one-shot result, failure analysis is allowed. Repairs must be developed against synthetic reproductions or newly acquired development documents, not by iterating directly on the 32 primary gold theses.

If the project wants a new unbiased effectiveness estimate after such repairs, create `human_gold_v0_2` from a new unseen sample using the same protocol and a new deterministic seed.

The most important property of v0.1 is therefore not a particular F1 value. It is that the benchmark remains interpretable: the first score answers how well the frozen extractor generalized to documents that did not teach it how to behave.
