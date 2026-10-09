# Release notes — BiblioRef 0.9.6 / APP 2.6.2 / Parser 0.3

## Autoridades

- extractor: 0.9.6 / algorithm 0.6.2 / stable engine 0.4.5;
- APP: 2.6.2;
- downstream parser: biblioref-parser-v0.3, schema 3;
- parser source SHA-256 frozen pre-reserve: `f0d62221105c4552c80ad1f6dff6014653070dcc22543fdf06c4239c2fde0b27`.

## Evidencia

- development corpus: 29,470 referencias;
- burned v0.2 pilot: 50 referencias / 5 tesis, ahora regression/development;
- strict external reserve v0.3: 20 referencias directas / 2 tesis UCL, gold congelado antes de ejecutar parsers;
- Surrey/Petker permanece sin usar.

## Resultado externo de reserva

v0.2 → v0.3:

- revista fuzzy90: 73.33% → **93.33%**;
- cobertura revista: 93.33% → **100%**;
- tipo exacto: 95% → **100%**;
- editorial exacta: 20% → **40%**;
- cobertura editorial: 60% → **80%**;
- autor: 100% → 100%; año: 100% → 100%; DOI: 100% → 100%; título: 90% → 90%.

No se modificó v0.3 después de abrir la reserva.

## Archivos clave

- `BIBLIOREF_APP_V262_PARSER_V03_REPORT.md`
- `PARSER_V0_3_DEVELOPMENT_EVALUATION.json`
- `PARSER_V0_3_RESERVE_EVALUATION.json`
- `PARSER_V0_3_RESERVE_PREDICTIONS.csv`
- `parser_baseline/reserve_v03/PARSER_V03_RESERVE_STRICT_GOLD_FROZEN.csv`
- `PARSER_V0_3_PRE_RESERVE_FREEZE_SHA256SUMS.txt`
- `EXTRACTION_CORE_NONREGRESSION_V03_SHA256.json`
- `docs/handoff/BIBLIOREF_MASTER_HANDOFF_V0_9_6_APP_V2_6_2_PARSER_V0_3.md`
