# Human-gold extraction benchmark v0.1

## Pilot handoff status

The six-document pilot annotation package is acquired and SHA-pinned. Source
selection used repository metadata only, before any BiblioRef run. The PDFs are
kept only in the git-ignored `pdf_cache/`; the manifest records their public
source URLs, access/licence metadata, byte sizes, and SHA-256 values.

No human annotator was available in this run. Therefore `pilot/gold.jsonl` does
not exist, the pilot validator and evaluator have not been run, and no
extraction output or headline metric has been observed. The initially
preregistered record-start tolerance remains `0.015` page height, pending human
mechanical validation of rendered-image coordinates; it was not tuned against
BiblioRef results.

## Metadata-only selection provenance

- OpenAlex Works API query:
  `/works?filter=from_publication_date:2000-01-01,open_access.is_oa:true,to_publication_date:2026-12-31,type:dissertation&sample=200&seed=20260913&per_page=200`
- OpenAlex response SHA-256:
  `693dea4e110c8829c8ccae372accf76fa6735750593515979e4f74febc0c1b1d`
- The response contained 200 records, including 95 with a
  `primary_location.pdf_url`. The deterministic candidate transform retained
  57 records with a bitstream URL, landing URL, integer year, language, and an
  unambiguous repository-host ccTLD. Repository is the bitstream host and
  country is its ISO ccTLD (`uk` maps to `GB`); generic resolvers/hosts were not
  inferred.
- The checked-in selection seed (`20260913`), 32-primary constraints, and
  six-pilot target were used. For this pilot-only sampler invocation,
  `stress_n` alone was set to zero because no stress set was being selected.
  Pilot rows are the six sampler results remaining after the temporary
  32-document primary allocation; only those six rows were frozen here.
- A freshly built development-exclusion registry contained 162 canonical
  identities. None overlaps the frozen pilot rows.
- Four candidates were removed only after objective acquisition checks, then
  the same transformation and seed were rerun: `W2499566873` returned 404 for
  a URL naming a ZIP, `W2946583782` returned JavaScript, `W7132325446` returned
  HTML, and `W3015144331` produced different SHA-256 values on repeated
  same-size downloads. No document content, BiblioRef prediction, count, zone,
  audit flag, parser output, or StyleProfiler output informed selection.
- Each final PDF was downloaded twice from its recorded URL with matching
  byte size and SHA-256, then opened successfully with `pypdfium2.PdfDocument`
  to verify a readable bitstream. Because redistribution permission was not
  independently established for every item, no PDF is committed.

The replay package under `pilot/` commits the hash-pinned OpenAlex response,
the exact transform configuration, full and post-rejection candidate pools,
the exclusion registry used at selection time, the structured objective
rejection ledger, the pilot-only selection configuration, and the complete
38-row sampler result. `pilot/SHA256SUMS.txt` pins those artifacts and the six
local PDF inputs. A shared `metadata_snapshot_sha256` value is provenance, not
a document checksum; exclusion identity accepts only the explicitly supported
document hash fields `sha256`, `document_sha256`, and `pdf_sha256`.

The frozen pilot source manifest is
`benchmarks/human_gold_v0_1/pilot/source_manifest.jsonl` (SHA-256
`b6b88559155ec3388bec5b405a2e281deb4483319398359a37f7cfbd42a74f30`).

## Byte-for-byte selection replay

From the repository root, run:

```bash
bash benchmarks/human_gold_v0_1/pilot/replay_selection.sh /tmp/hg-pilot-replay
```

The command rebuilds both normalized pools from `openalex_snapshot.json`,
applies `objective_rejections.jsonl`, reruns the existing sampler, and uses
`cmp` to require byte-for-byte equality with all three committed outputs.

## Pilot human continuation

Restore the six PDFs to `benchmarks/human_gold_v0_1/pdf_cache/` under the
manifest filenames, then verify them and the replay package with:

```bash
(cd benchmarks/human_gold_v0_1 && sha256sum -c pilot/SHA256SUMS.txt)
```

Then run:

```bash
python -m tools.human_gold.annotation_app \
  --manifest benchmarks/human_gold_v0_1/pilot/source_manifest.jsonl \
  --pdf-cache benchmarks/human_gold_v0_1/pdf_cache \
  --output benchmarks/human_gold_v0_1/annotation_work \
  --annotator <human-id>
```

Open <http://127.0.0.1:8000/>. A human must create complete zone and
reference-start labels plus every required full-text transcription. After the
human-produced `pilot/gold.jsonl` exists, validate it with:

```bash
python -m tools.human_gold.validate_gold \
  --manifest benchmarks/human_gold_v0_1/pilot/source_manifest.jsonl \
  --gold benchmarks/human_gold_v0_1/pilot/gold.jsonl
```

Only after that validation passes may the pilot evaluator be run. Pilot
evidence remains diagnostic and must never enter headline metrics or drive
production extraction changes in this phase.

## Frozen 40-document annotation handoff

The preregistered source-freeze phase is complete. The public benchmark
manifest contains 40 non-pilot documents selected before any BiblioRef run:
32 `primary` documents and 8 visually selected `stress` documents. The six
pilot documents remain separate and do not enter headline metrics.

The 32-document primary partition spans 23 repositories, 15 countries and 11
languages. Its preregistered time-band counts are 10 documents before 2015, 12
from 2015 through 2020, and 10 from 2021 through 2026; no repository contributes
more than five primary documents. The source-freeze audit recorded 41 unique
accepted acquisitions across 102 acquisition observations before the final
40-document partition was fixed.

Frozen handoff values:

```text
source_manifest_sha256 = 9eb833f11a056da664f29d15abfacad373f1171f00911610907c3c63451ff892
exclusion_registry_sha256 = 4d525f408bfbcfce49b32bfcbb5c7691a594dc4618f40aa4f5625591de1f1aa1
selection_config_sha256 = e7ec0c0edc41707539c51ec460e90ab041b67b017fc263b83bbd3bf81b3c0bba
candidate_git_sha = c53a861fb2324b28a37536f1a05b3dad8d616f46
algorithm_version = 0.6.8
boundary_y_tolerance = 0.015
primary_metrics_observed = false
human_annotation_exists = false
```

Candidate `c53a861fb2324b28a37536f1a05b3dad8d616f46` was frozen before any
primary scoring. Its benchmark-specific test suite passed 119 tests, the
repository's documented `Repository Test Gate` passed with 941 tests passed,
3 skipped and 16 subtests passed, and the comparison against implementation
start `c71098003bb7e04143ca8a226e19e37560a7d69e` showed no changes under
`biblioref/**` or `app.py`.

The next required action is human annotation. Restore the 40 SHA-pinned PDFs to
`benchmarks/human_gold_v0_1/pdf_cache/` under their manifest document IDs and
run exactly:

```bash
python -m tools.human_gold.annotation_app \
  --manifest benchmarks/human_gold_v0_1/source_manifest.jsonl \
  --pdf-cache benchmarks/human_gold_v0_1/pdf_cache \
  --output benchmarks/human_gold_v0_1/annotation_work \
  --annotator <human-id>
```

No `frozen_gold.jsonl` has been created. No primary precision, recall, F1 or
other headline metric has been calculated. Human annotations must be completed,
validated and quality-controlled before gold finalization or the single
preregistered primary evaluation. Extraction heuristics must not be changed on
the basis of these unlabelled benchmark documents.
