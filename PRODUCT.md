# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Academic researchers and institutions who need to extract structured bibliographic
reference data from PDF theses/dissertations and other academic documents. Confirmed
by the user: BiblioRef started as a solo research tool (built by the current user for
their own work) and is now being turned into professional software for **other
researchers and institutions** to install and run themselves — not just personal use.

The parser's real-document test corpus (see Evidence on Hand) spans universities across
Argentina, Brazil (ABNT convention), UK, and elsewhere, so the intended user base is not
limited to a single country or institution.

## Product Purpose

BiblioRef extracts, segments, and parses bibliographic references out of PDF documents
(primarily theses and dissertations) into structured records — author(s), year, type,
title, journal, publisher, DOI — then lets a person manually review and correct the
references in zones the automated pipeline could not resolve with confidence
("Referencias por tesis" screen), and export clean results (CSV/XLSX/JSON).

**Confirmed:** the exported reference data feeds a bibliometric/scientometric study —
references extracted across many theses are aggregated for citation, co-authorship, or
disciplinary-clustering analysis. The per-thesis manual review screen exists to produce
clean, trustworthy records for that aggregate dataset, not as an end in itself.

## Positioning

Unlike a generic reference parser, BiblioRef is built and continuously validated against
real, messy Ibero-American academic documents — Spanish, Portuguese/ABNT, and mixed
formats — rather than clean bibliography datasets. Its extraction/parsing logic evolves
through versioned algorithm changes, each checked with byte-for-byte non-regression
hashes against frozen fixtures and evaluated on external holdout reference sets pulled
from real theses across many universities (e.g. UFPE, UFSCar, UFC, UnB, UFSC, USP,
Universidad de Belgrano, Sheffield, York). Every parsing-behavior change is documented
and traceable to the specific real-world formatting quirk that motivated it (hyphen
variants in chapter headers, institutional authors, ABNT thesis descriptors, etc.).

## Operating Context

- Runs locally per user/institution: a FastAPI backend serves a local single-page web UI
  (`static/index.html` + `static/app.js`), packaged as a Windows desktop app (PyInstaller
  onedir build + Inno Setup installer) for non-technical distribution.
- Per-user local workspace under `~/.biblioref/projects/<name>` (or
  `BIBLIOREF_WORKSPACE`); no shared backend or accounts today.
- Ingests: individual PDFs, local ZIP archives (recursive PDF discovery, nested up to
  depth 2, with path-traversal/zip-bomb/encrypted-zip protections), and Google Drive
  folders/files via read-only OAuth (desktop-app flow; credentials stay local, never
  exported with results).
- Core workflow/screens: Inicio (upload/ingest) → Proyecto (project/document table) →
  Referencias por tesis (per-thesis manual review and correction, especially zones
  flagged `audit_required`) → Exportar (CSV/XLSX/JSON export).
- UI language is Spanish; the reference material it parses spans Spanish and
  Portuguese (ABNT) academic conventions.

## Capabilities and Constraints

- Pipeline is strictly layered and downstream-respecting: zone detection → segmentation/
  boundary reconciliation → reference parsing → style profiling (shadow mode). Each
  layer never overrides the authority of the layer before it.
- Every ingested document carries provenance: source, archive membership/chain,
  SHA-256, size.
- Accuracy is a first-class, versioned constraint, not an implementation detail:
  algorithm/parser changes are validated via frozen non-regression hashes and external
  holdout evaluation against real theses before being accepted; regressions are tracked
  explicitly rather than silently absorbed.
- Ingestion security is an established product requirement: blocked path traversal,
  blocked encrypted ZIPs, member/size/compression-ratio limits, PDF signature
  verification, no execution of archive contents, Google Drive scope limited to
  `drive.readonly` with no write/delete capability.
- **Open/undecided (explicitly, by the user's own choice):** whether a future
  "professional, multi-institution" version needs a shared/hosted component with
  accounts, or stays local-install-per-institution as it is today. The user deferred
  this decision rather than picking one — do not design toward either architecture
  until it is decided; keep near-term work (UI polish, packaging, docs) compatible
  with both.
- **Future roadmap, confirmed not yet real (do not design or build as if they exist):**
  a per-reference numeric confidence score, and automatic duplicate-reference detection.
  Neither exists today — StyleProfiler deliberately keeps `confidence: null` in its
  current shadow-mode implementation, and no duplicate-detection logic exists anywhere
  in the pipeline. These surfaced from an external UI concept the user reviewed and
  confirmed as aspirational; any future design work may plan for them as a stated
  direction, but must not present them as working, and must not fabricate the specific
  numbers/rates a mockup showed.

## Brand Commitments

Name: BiblioRef. Visual identity: the product shipped a "Sala de Lectura" paper/serif
world (2026-09-03, documented and refined), then the user explicitly replaced it with a
dark-sidebar, blue-accent "Consola de Auditoría" system after reviewing a concrete
pinned reference — a deliberate, confirmed choice, not drift (2026-09-03). See
`DESIGN.md` for the current committed system. No other binding brand commitments
confirmed.

## Evidence on Hand

Extensive internal versioned reports (`BIBLIOREF_*_REPORT.md`, `RELEASE_NOTES_*`,
`PARSER_*_EVALUATION.json`) documenting real accuracy numbers against real thesis
holdouts, broken down by university/country. This is real, existing evidence — future
design or marketing work can cite it factually, but must not fabricate testimonials,
customer names, institutional endorsements, or pricing beyond what is recorded here.

## Product Principles

1. Extraction/parsing accuracy is provable, not assumed — every behavior change is
   validated against frozen non-regression fixtures and real external holdout theses
   before shipping.
2. Downstream layers never override upstream authority — segmentation, parsing, and
   style profiling each respect the boundaries set by the layer before them.
3. Ingestion trust is explicit — every source (local file, ZIP, Google Drive) is
   provenance-tracked and defensively validated before entering the pipeline.
4. The tool meets real documents as they are — Ibero-American thesis formatting
   irregularities (accented/variant characters, institutional authors, ABNT
   conventions) are the primary target, not an edge case.
5. Local-first, low-trust-surface — no accounts, no shared backend by default; each
   install's data and credentials stay on that machine.

## Accessibility & Inclusion

No product-specific accessibility requirement established yet.
