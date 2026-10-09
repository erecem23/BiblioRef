# BiblioRef v0.9.10-rc2 / algorithm 0.6.7 — Final technical snapshot

Date: 2026-09-08

## Closure decision

BiblioRef `0.9.10-rc2 / algorithm 0.6.7` is designated the **final technical snapshot of the current development cycle**.

The independent blind-human gold exercise is explicitly deferred and removed as a blocking requirement for closing this software-development cycle. No simulated annotator is treated as independent human evidence.

This closure is a technical/software closure, not a claim of human-gold extraction accuracy.

## What is validated

- Integrated algorithm line: `0.6.7`.
- Software identifier retained: `0.9.10-rc2` to preserve the distinction between a technically completed snapshot and a gold-validated accuracy release.
- App/UI line: `2.7.0`.
- Parser: `0.12.5`.
- StyleProfiler: `0.1-shadow`, observational only.
- Google Drive integration: `0.2`, read-only.
- Document title: `2.1` integrated.
- Local AI runtime remains disabled in the current app.

The complete deterministic repository suite passed repeatedly on the integration and promotion paths, including in the pinned external-holdout environment:

- 770 passed
- 3 skipped
- 16 subtests passed
- 0 failed

The integration preserved the v0.6.5 structural base, the Cabrera dominant-margin repair developed independently on `dev`, and the frozen RC1 UNR28/UNR30 structural repairs under the reconciled algorithm identifier `0.6.7`.

## External evidence retained

The frozen external holdout was replayed without redefining its document selection or policy after inspecting RC2 behavior.

After correcting input identity:

- 11 valid thesis PDFs produced RC2 model output;
- 7 distinct institutions were represented;
- the preregistered aggregate threshold of at least 10 valid documents and at least 6 institutions was met;
- there were 0 operational pipeline failures on valid downloaded thesis PDFs;
- 2 Universidad de Chile inputs were excluded as repository-document substitutions rather than thesis PDFs;
- 1 LSE input remained an infrastructure/access failure in the RC2 replay.

Eight documents shared with the corrected RC1 external audit reproduced their previously recorded structural diagnostics exactly. This is structural no-regression evidence, not accuracy evidence.

## Explicitly unsupported claims

Because independent human gold was not completed, this snapshot does **not** support claims of:

- precision;
- recall;
- F1;
- exact-reference accuracy;
- true-positive/false-positive/false-negative rates;
- a statement that every structurally plausible output is correct.

Counts such as UNR28=306 or UNR30=437 remain model structural outputs, not human-gold denominators.

## Deferred work

The blind A+B annotation/adjudication workflow and the evaluation-harness PDF identity hardening are preserved as historical/future work but are not blockers for closure of the current project cycle.

If BiblioRef development resumes, the correct baseline is this snapshot. A future accuracy paper or validation release should either complete an independent gold protocol or preregister a new untouched evaluation corpus rather than retroactively treating simulated annotations as independent human evidence.

## Promotion policy

This snapshot may be promoted to `main` as the repository's final technical state for the current cycle, provided normal repository gates remain green on the proposed merge tree.

Promotion to `main` means **current technical baseline**, not **independently gold-validated accuracy release**.
