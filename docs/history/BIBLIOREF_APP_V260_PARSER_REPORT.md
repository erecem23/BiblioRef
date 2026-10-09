# BiblioRef v0.9.6 — APP v2.6.0 + parser bibliográfico v0.1

**Fecha:** 2026-09-02  
**Núcleo de extracción:** `SOFTWARE=0.9.6` · `ALGORITHM=0.6.2` · `STABLE_ENGINE=0.4.5`  
**Parser:** `legacy-v3.2.2-adapted-v0.1`  
**Estado del parser:** `development_baseline`

## 1. Corrección de alcance

La integración anterior había consolidado el historial del **segmentador**, pero faltaba recuperar la segunda etapa contenida en `BiblioRef_HANDOFF_completo_otro_chat_2026-09-01`: el parser bibliográfico del viejo extractor V3.2.2.

La arquitectura queda ahora explícitamente separada:

```text
PDF → detección/segmentación v0.9.6 → referencia cruda → parser v0.1 → campos internos
```

El parser no participa en la detección de zonas ni en las decisiones de frontera.

## 2. Campos incorporados

Cada referencia de la APP contiene `parsed` con:

- `author`
- `authors`
- `year`
- `publication_type`
- `title`
- `journal`
- `source_publisher`
- `doi`
- `parser_version`
- `parser_status`

El texto `reference/text` permanece intacto como fuente autoritativa.

## 3. Integración funcional

- extracción automática → parseo automático;
- edición humana → reparseo;
- split → parseo independiente de cada fragmento;
- merge → reparseo del registro fusionado;
- inserción manual / desde PDF → parseo automático;
- UI → botón **Campos** y resumen visible autor/año/tipo/revista/DOI;
- JSON → conserva `parsed` anidado;
- CSV/XLSX → exporta columnas `parsed_*` además del texto crudo;
- CLI → nuevo `--parsed-csv`, opcional y no destructivo.

## 4. Fidelidad respecto del parser recuperado

El nuevo módulo `biblioref/parsing/legacy.py` elimina la dependencia de pandas en runtime, pero conserva la semántica del parser handoff.

Control de equivalencia:

- seed estratificado: 120 referencias, **0 diferencias** respecto del parser original;
- Agrazar congelado: 432 referencias, **0 diferencias campo por campo** respecto del parser original.

## 5. No-regresión del extractor

Se compararon SHA-256 de 14 archivos centrales de detección/segmentación entre APP v2.5.2 y esta release. Los 14 son idénticos. El detalle está en `EXTRACTION_CORE_NONREGRESSION_SHA256.json`.

Suite completa:

```text
351 passed
3 skipped
16 subtests passed
0 failed
node --check static/app.js: OK
py_compile: OK
```

## 6. Estado metodológico

El baseline retrospectivo de 29.470 referencias del handoff reportaba aproximadamente:

| Campo | Resultado diagnóstico |
|---|---:|
| Autor principal | 71,33% acuerdo estricto normalizado |
| Año | 93,81% acuerdo |
| Título | 92,37% acuerdo fuzzy ≥ .90 |
| Revista | 39,18% acuerdo fuzzy ≥ .90 |
| DOI | 97,26% recall / 99,61% precisión |
| Tipo documental | 68,71% exactitud |

Estas cifras son **diagnóstico de desarrollo**, no validación externa publicable.

El orden de mejora heredado se conserva:

```text
revista → tipo documental → editorial/fuente → autor(es)
```

Título, año y DOI deben tratarse primero como invariantes de no-regresión.
