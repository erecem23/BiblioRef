# BiblioRef MetadataResolver v0.1 — isolated candidate branch

**Date:** 2026-09-04  
**Branch:** `feature/metadata-resolver`  
**Base:** `dev@084ebbe8462676eab6674521fc812c74ad3acf24`  
**Parser at base:** `biblioref-parser-v0.12.5`  
**Authority:** downstream / read-only with respect to extraction and parser output

## 1. Scope

This branch introduces the first external-resolution stack for BiblioRef without wiring it into the application pipeline.

It intentionally does **not** modify:

- `biblioref/parsing/`
- `biblioref/extraction/`
- `biblioref/pipeline.py`
- bibliography-region detection or reconciliation
- cover/front-matter metadata detection
- StyleProfiler

All production code added by this branch lives in `biblioref/resolver/`.

## 2. Architecture

```text
parsed reference (immutable snapshot)
          |
          v
    ResolverQuery
          |
          v
   MetadataResolver
      /        \
Crossref      OpenAlex
      \        /
       candidates
          |
          +--------> ConsensusEngine   (deterministic, explainable)
          |
          +--------> SemanticResolver  (optional local embeddings)
```

The resolver never writes external metadata back into `parsed`. Later integration must preserve the distinction:

```text
raw reference != parsed metadata != external candidates != consensus != semantic signal
```

## 3. Candidate contract

`ResolverQuery` captures a copy of:

- raw reference
- title
- authors
- year
- journal/container
- publisher
- DOI
- publication type
- parser version/confidence

`Candidate` preserves:

- source (`crossref`, `openalex`, future backends)
- source identifier
- DOI
- title/authors/year/container/publisher/type
- provider rank and provider score when available
- retrieval method
- source-specific raw metadata

Cross-source candidates are deliberately **not** collapsed. If Crossref and OpenAlex return the same DOI, both remain visible as independent evidence for consensus.

## 4. Crossref backend

Retrieval strategy:

1. exact DOI -> `/works/{doi}`
2. otherwise -> `/works?query.bibliographic=<citation>`
3. small candidate set only (default 5; hard cap 20)

The transport is injectable, so tests do not require network access. An optional email can be supplied for Crossref's polite pool.

## 5. OpenAlex backend

Retrieval strategy:

1. exact DOI -> Works filter `doi:https://doi.org/<doi>`
2. otherwise -> Works `search=` using parsed title when available
3. add `publication_year` filter when parser year exists
4. small candidate set only (default 5; hard cap 20)

An optional API key is accepted through the Authorization header. The transport is injectable.

## 6. Deterministic consensus

`ConsensusEngine` provides an explainable evidence score, explicitly **not a probability**.

Signals currently used:

- DOI exact/conflict
- title similarity
- year exact/conflict
- first-author similarity
- container similarity
- identity agreement across independent sources

Possible statuses:

- `exact_identifier`
- `external_consensus`
- `probable_candidate`
- `ambiguous_conflict`
- `unresolved`

No status changes parser fields.

## 7. Optional semantic resolver

`SemanticResolver` accepts an injected embedding backend and ranks candidate titles semantically.

A lazy `SentenceTransformerEmbeddingBackend` is provided. The initial configurable default is:

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

The model is not loaded at BiblioRef import time. The heavyweight dependency remains optional in `requirements_semantic_resolver.txt`.

Semantic similarity is stored as a signal, **not** a match probability and not an automatic correction.

## 8. Tests added

23 offline tests were added across:

- resolver contract / immutability
- DOI normalization
- conservative deduplication
- backend failure isolation
- Crossref mapping/query construction
- OpenAlex mapping/query construction
- deterministic consensus/conflict behavior
- semantic ranking with fake embeddings

The GitHub connector used to create this branch cannot execute the repository test suite, and this repository currently has no GitHub Actions workflow. Therefore these tests are **added but not yet execution-validated**. Do not merge before running the full local suite.

## 9. Merge gate

Before merging into `dev`:

1. run all legacy tests plus the 23 new tests;
2. confirm parser/extraction output hashes are unchanged;
3. run at least a small live Crossref/OpenAlex smoke test outside the unit suite;
4. keep network integration opt-in and downstream;
5. do not wire semantic models into default application startup.

## 10. Repository note

PR #1 (`feature/document-title-v1`) predates the current `dev` metadata/cover work and is currently stale/non-mergeable. It should not be merged into `dev` without a fresh comparison against the newer cover-metadata implementation.
