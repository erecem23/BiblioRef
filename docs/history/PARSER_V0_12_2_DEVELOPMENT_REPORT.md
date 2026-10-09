# BiblioRef parser v0.12.2 — development report

## Scope

v0.12.2 is a conservative audit overlay on v0.12.1. It changes no PDF geometry,
reference segmentation, or selected bibliographic fields. Its sole purpose is to
classify secondary year mentions by context and reduce false-positive review
flags.

No real thesis references or PDFs are stored in this report. Regression examples
in the test suite are synthetic.

## Year roles

Every detected year can now carry one or more of these roles:

- `publication`: primary bibliographic author-year date.
- `access`: year following a structured retrieval cue such as `Retrieved`,
  `Extraído el`, `Consultado` or `Última visita`.
- `url`: year occurring inside the URL segment.
- `title`: year found inside the parser-selected title.
- `context`: other year mention in citation prose/container context.

A bare Spanish word `acceso` is intentionally **not** an access-date cue. This
prevents titles discussing access to health/services from reclassifying later
years as retrieval dates.

## Review policy

The parser still emits its best publication year. `year_candidates` preserves all
observed year evidence.

Human review is requested when a distinct secondary year has role `access` or
`url`. A year range found only in `title`/`context` is retained as evidence but
does not lower parser confidence by itself.

## Field validation

The year-audit logic was run directly over the 99 extracted references of the
current field-validation workbook, without re-running PDF extraction.

- references evaluated: **99**
- selected publication years changed: **0 / 99**
- references with more than one distinct year: **14**
- reviewable because of competing access/URL dates: **12**
- informative title/context multi-year cases not flagged: **2**

The two removed false positives correspond to generic patterns represented by
synthetic fixtures:

1. a conference/contribution title containing the ordinary word `acceso` plus a
   historical interval such as `(2005-2010)`;
2. an article title containing a school/observation interval such as `2020-2021`
   while the publication year is 2021.

A genuine retrieval example remains reviewable, e.g. a citation with publication
`2012`, retrieval `2022`, and a historical year `1978` in its URL.

## Regression fixtures

`test_parser_v0_12_2.py` covers:

- ordinary lexical `acceso` vs structured retrieval cues;
- year ranges inside titles;
- structured `Retrieved` dates;
- URL years;
- `Extraído el` access dates;
- non-regression of v0.12.1 core bibliographic fields.

## Architecture

The change remains downstream-only:

`validated extraction -> parser v0.12.1 -> year audit v0.12.2`

The extraction core is not imported or modified by this revision.
