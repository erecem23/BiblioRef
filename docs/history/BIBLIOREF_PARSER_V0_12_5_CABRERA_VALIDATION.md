# BiblioRef parser v0.12.5 — Cabrera validation

Date: 2026-09-04

Private development validation. The real thesis/PDF and its extracted references are **not** committed to the repository.

## Corpus

One UBA Psychology master's thesis (2015), 158 bibliography records after algorithm v0.6.6 dominant-margin reconciliation.

## Extraction prerequisite

Algorithm v0.6.6 repaired a same-count topology error in the bibliography: one false split and one missed boundary had cancelled numerically at 158 records. The accepted repair also rebuilt records from physical lines so continuation-only URL lines were retained. The local regression suite after integration passed **548 tests**, with **3 skipped** and **16 subtests passed**.

## Parser replay

The corrected 158 raw references were replayed through the v0.12.4 state and then the v0.12.5 overlay logic.

Resulting document-type distribution:

- libro: 89
- conference_paper: 23
- articulo_revista: 22
- capitulo_libro: 12
- material_web: 7
- informe_documento: 2
- documento_guia_manual: 2
- sin_clasificar: 1

Audit outcome:

- 158/158 publication years present
- 158/158 author-list status resolved as `complete` for the visible citation form
- 22 journal containers recovered
- 1/158 remains `document_type_unresolved`
- 157/158 no longer carry a document-type review flag

The single unresolved record is a talk/interview-like item whose citation names a source and date but does not provide enough stable bibliographic structure to force article/book/web classification. It is intentionally left for human review.

## New v0.12.5 families

- legacy serial syntax using `N°`, `Número`, `Tomo`, `Año`, or `Vol.`
- explicit multiword serial names
- same-year suffixes such as `(2008-a)` / `(2008-b)`
- URL-only unresolved records -> `material_web` (without inferring a book)
- narrow edition + place:publisher book recovery
- protection against stealing chapter/book containers that merely contain words such as `Cuadernos`

## Privacy

Only synthetic regression fixtures are committed. No real thesis text or reference list is added to GitHub.
