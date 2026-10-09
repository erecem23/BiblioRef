# BiblioRef v0.9.6 — APP v2.6.2 + parser bibliográfico v0.3

**Fecha:** 2026-09-02  
**Extractor:** `SOFTWARE=0.9.6` · `ALGORITHM=0.6.2` · `STABLE_ENGINE=0.4.5`  
**APP:** `2.6.2`  
**Parser downstream:** `biblioref-parser-v0.3` · schema 3

## 1. Alcance

Parser v0.3 es una revisión **downstream y no destructiva**. No cambia detección de zonas, segmentación, reparación de fronteras ni texto crudo. Su entrada es una referencia ya segmentada; su salida agrega campos estructurados.

Las familias que motivaron v0.3 provinieron del piloto externo de v0.2 de cinco tesis / 50 referencias. Desde el inicio del desarrollo de v0.3 esas 50 filas quedaron reclasificadas como **development/regression** y dejaron de ser evidencia externa.

Cambios principales:

1. gramática explícita para `autor ... año. título. revista` con año **sin paréntesis**;
2. gramática explícita para referencias **Vancouver-ish**;
3. preservación de nombres completos de revista con dos puntos/subtítulos;
4. soporte de article-number, página única y metadatos de volumen adicionales;
5. rescate conservador de editorial en monografías/capítulos;
6. separación explícita de instrumentos/manuales frente a libros ordinarios;
7. nuevo campo `parse_style`: `bare_year`, `vancouverish` o `legacy_parenthetical_or_fallback`.

## 2. Desarrollo: 29.470 referencias

Este corpus ya participó del desarrollo y **no es holdout**.

| Métrica | parser v0.2 | parser v0.3 |
|---|---:|---:|
| Primer autor, acuerdo estricto | 72,10% | 72,08% |
| Revista, fuzzy ≥ .90 | 76,79% | **78,70%** |
| Revista, cobertura | 82,63% | **84,60%** |
| Tipo documental, clase gruesa | 82,93% | **83,38%** |
| Tipo documental, detallado | 76,75% | **77,21%** |
| Editorial exacta sobre target v2 | 93,59% | **93,63%** |
| Editorial, cobertura sobre target v2 | 95,30% | **95,37%** |

En este corpus v0.3 detectó 7 referencias `vancouverish` y **0 `bare_year`**, señal de que la nueva gramática bare-year no se activó indiscriminadamente sobre el material histórico.

## 3. Freeze antes de reserva

Antes de abrir las tesis de reserva se congeló el código:

```text
biblioref/parsing/v03.py
SHA-256 = f0d62221105c4552c80ad1f6dff6014653070dcc22543fdf06c4239c2fde0b27
```

Suite pre-reserva:

```text
370 passed
3 skipped
16 subtests passed
0 failed
```

Suite final de release (incluye tests de freeze y reserva ya convertida en regresión de release):

```text
373 passed
3 skipped
16 subtests passed
0 failed
node --check: OK
py_compile: OK
14/14 archivos del núcleo extractor: SHA-256 idéntico
```

## 4. Evaluación externa estricta de reserva

Se anotaron **20 referencias directas** de dos tesis doctorales UCL de 2024 que habían quedado reservadas y no se usaron para escribir v0.3:

- Joanne Brown, DClinPsy, UCL;
- Daniel Pugh, DClinPsy, UCL.

El gold se escribió y congeló **antes de ejecutar v0.2 o v0.3**:

```text
PARSER_V03_RESERVE_STRICT_GOLD_FROZEN.csv
SHA-256 = 7ff4c1c6d8b9ad8b09925ab5b629ad6a61d45842d740e5af7252b0474fcd2d79
```

La tercera tesis reservada (Surrey/Petker) quedó sin usar: el entorno no permitió recuperar con suficiente garantía el texto exacto de sus referencias. No se sustituyó por referencias de un artículo derivado.

### Resultados

| Campo | v0.2 | **v0.3** |
|---|---:|---:|
| Primer autor exacto | 100% | **100%** |
| Año exacto | 100% | **100%** |
| Título exacto | 90% | **90%** |
| Título fuzzy ≥ .90 | 90% | **90%** |
| Revista exacta | 73,33% | **93,33%** |
| Revista fuzzy ≥ .90 | 73,33% | **93,33%** |
| Cobertura de revista | 93,33% | **100%** |
| Tipo documental exacto | 95% | **100%** |
| Tipo documental, clase gruesa | 95% | **100%** |
| Editorial exacta | 20% | **40%** |
| Cobertura editorial | 60% | **80%** |
| DOI exacto (n=14) | 100% | **100%** |

Comparación pareada v0.2→v0.3:

- revista fuzzy: **3 mejoras / 0 regresiones**;
- tipo documental: **1 mejora / 0 regresiones**;
- editorial exacta: **1 mejora / 0 regresiones**;
- autor, título y DOI: **0 regresiones**.

El hash de `v03.py` volvió a comprobarse después de evaluar la reserva y permaneció idéntico al freeze pre-reserva.

## 5. Errores externos que permanecen

La reserva dejó cinco casos útiles para una futura v0.4; **no se corrigieron en v0.3**:

1. `The British Journal of Criminology` aún puede colapsar a `Criminology`;
2. un capítulo con editorial `Willan` queda sin publisher;
3. `Essential Medical Statistics (2nd ed.)` conserva la edición dentro del título;
4. una referencia con título en dos oraciones (`How much change is enough? Evidence ...`) corta el título después de la pregunta;
5. normalización editorial puede devolver una variante canónica (`Blackwell`, `Guilford Press`) distinta del literal citado (`Blackwell Publishing`, `Guilford Publications`).

Estos errores quedan documentados, no parcheados contra la reserva.

## 6. Interpretación

La evidencia disponible apoya que v0.3 mejora especialmente **revista** y **tipo documental** sin degradar los campos maduros. La evaluación externa estricta es todavía pequeña (n=20, dos tesis), por lo que no debe presentarse como una estimación definitiva de rendimiento general. Sirve como evidencia de generalización inicial y como control metodológico de que la mejora no proviene solamente de las 50 referencias que motivaron el desarrollo.
