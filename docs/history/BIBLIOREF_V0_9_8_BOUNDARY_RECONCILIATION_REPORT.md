# BiblioRef v0.9.8 — reconciliación de fronteras antes del parser

**Fecha:** 2026-09-02  
**Software:** 0.9.8  
**Algoritmo efectivo:** 0.6.4  
**APP:** 2.6.9  
**Parser downstream:** v0.10, **sin cambios**

## 1. Problema

La v0.9.7 + parser v0.10 mejoró el reconocimiento de zonas y el parsing de metadatos, pero la tesis de desarrollo adjunta mostró dos fallas de segmentación que ocurren **antes** del parser:

1. la primera referencia real (`5G Américas. (2016)...`) no se materializaba como registro;
2. varias referencias quedaban fusionadas porque su comienzo no satisfacía la gramática textual clásica: autores institucionales, listas de autores cuyo año cae en la línea siguiente y límites desplazados que comenzaban directamente por `(año)`.

La solución no consiste en ampliar indefinidamente una regex de inicio. Se agrega una segunda pasada entre la segmentación y el parser.

## 2. Nueva arquitectura

```text
PDF
 ↓
detección de zona
 ↓
segmentación estable / reparación v0.6.1
 ↓
RECONCILIACIÓN DE FRONTERAS v0.6.4
 ↓
referencias crudas definitivas
 ↓
parser v0.10
```

El nuevo módulo es `biblioref/extraction/boundary_reconciliation.py`.

## 3. Principio de la reconciliación

La unidad universalizada no es la forma textual de una referencia sino la **frontera física**. En una zona con sangría francesa fuerte se infieren dos clusters:

- margen de comienzo de referencia;
- margen de continuación.

Una línea situada en el margen de comienzo puede proponer una frontera aunque no coincida con `Apellido, Inicial. (año)`. La propuesta sólo se conserva cuando las primeras tres líneas del segmento contienen evidencia bibliográfica local (año, sin fecha o señal de fuente) y la segmentación completa supera controles conservadores.

Esto permite recuperar, entre otros:

- autores que empiezan con dígito: `5G Américas`;
- autores institucionales: `Asamblea Nacional`, ministerios, UNESCO, OEI, INEC;
- listas de autores cuyo `(año)` aparece en la segunda línea;
- límites desplazados una línea hacia abajo, en los que la salida anterior empezaba por `(2016)`, `(2007)`, etc.

## 4. Gate de autoaplicación

La segunda pasada sólo puede modificar la salida cuando se cumplen simultáneamente condiciones como:

- estilo no numérico;
- sangría francesa detectada;
- separación comienzo/continuación ≥ 14 puntos;
- ≥ 90 % de los registros base comienzan cerca del margen inferido;
- ≥ 94 % de los candidatos geométricos poseen evidencia bibliográfica local;
- ≥ 90 % de los segmentos reconciliados poseen evidencia bibliográfica;
- ningún segmento gigante;
- mediana entre 3 y 150 palabras;
- crecimiento acotado: como máximo 15 % del conteo base, con techo absoluto.

Si el gate no se supera, la salida efectiva anterior se conserva exactamente.

## 5. Resultado en la tesis de desarrollo

La bibliografía ocupa una zona autor-año con sangría francesa muy nítida. La v0.6.1 producía 310 registros; la segunda pasada produce **338**.

| Indicador | Resultado |
|---|---:|
| salida estable previa a reparación | 205 |
| candidato v0.6.1 aceptado | 310 |
| salida v0.6.4 | **338** |
| cambio neto vs v0.6.1 | **+28** |
| comienzos físicos recuperados vs v0.6.1 | **37** |
| fronteras previas eliminadas/desplazadas | **9** |
| margen de comienzo | 99,26 |
| margen de continuación | 141,86 |
| separación | 42,60 |
| pureza candidato/evidencia local | 1,000 |
| evidencia bibliográfica de segmentos | 1,000 |
| mediana de palabras | 22 |
| máximo de palabras | 69 |

La diferencia `+28` no significa simplemente “28 referencias nuevas”. La segunda pasada recupera 37 fronteras verdaderas que no estaban materializadas y, al mismo tiempo, elimina nueve límites incorrectos o desplazados que la segmentación anterior había creado. Por ejemplo, desaparecen registros que comenzaban por `2006. Revista Brasileira...`, `(2016). TIC Observatorio...` y las fechas desnudas de Senplades.

La primera referencia ahora es:

```text
5G Américas. (2016). Serie de Estudios TIC para el Desarrollo: Teleeducación en América Latina...
```

También quedan separados `Aguerre...`, `Asamblea Nacional`, los ministerios, INEC, UNESCO/OEI, Senplades y `Schiavo...`.

## 6. Parser v0.10 congelado

Las **338 referencias crudas** pasan por parser v0.10 sin excepciones: 338/338 procesadas.

La prueba reveló, sin embargo, una falla downstream independiente: el autor de la primera referencia cruda se parsea actualmente como `G Américas` en vez de `5G Américas`. No se corrigió en esta release porque el objetivo de v0.9.8 es la segmentación y se decidió congelar parser v0.10. Esto queda abierto para una versión futura del parser.

## 7. No-regresión automatizada

Batería integrada:

```text
515 passed
3 skipped
16 subtests passed
```

Los cinco tests nuevos cubren:

- recuperación de primera referencia iniciada por dígito;
- autor multilínea con año posterior;
- autor institucional con año en línea siguiente;
- abstención sin sangría francesa;
- abstención con clusters demasiado cercanos;
- rechazo de falsos comienzos geométricos sin evidencia local;
- guardia contra sobresegmentación.

Además, las pruebas históricas continúan pasando. Cuando la nueva capa no se activa, las estructuras históricas de reparación permanecen sin cambios; los nuevos metadatos de reconciliación sólo aparecen cuando el gate se acepta.

## 8. Alcance metodológico

La tesis utilizada para desarrollar v0.9.8 **ya no es holdout**. Los 338 registros son consistentes con 338 comienzos geométricos en el margen inferido y evidencia bibliográfica local en todos ellos, pero no se presentan como un ground truth independiente manual ni como una estimación de precisión/recall.

El siguiente paso metodológico correcto es congelar esta versión y probarla en tesis nuevas, separando al menos:

1. recall de fronteras;
2. precisión de fronteras;
3. recuperación de la primera referencia;
4. multireferencias residuales;
5. fronteras falsas introducidas;
6. tasa de abstención útil;
7. regresión sobre casos antes estables.

## 9. Archivos de validación

- `V098_TARGET_THESIS_VALIDATION.json`: detalle de la tesis de desarrollo, ejemplos recuperados y límites eliminados/desplazados.
- `FULL_V098_APP_V269_PARSER_V010_TEST_RESULTS.txt`: salida de la batería completa.
- `tests_core/test_biblioref_v0_9_8_boundary_reconciliation.py`: tests nuevos.
