# BiblioRef APP v2.6.3 — Parser bibliográfico v0.4

**Fecha:** 2026-09-02  
**Software:** BiblioRef 0.9.6  
**Algoritmo de extracción:** 0.6.2  
**Stable engine:** 0.4.5  
**APP:** 2.6.3  
**Parser downstream:** biblioref-parser-v0.4 · schema 4

## 1. Alcance

Parser v0.4 es una revisión **downstream, no destructiva**. No modifica zonas, fronteras ni texto crudo de referencias. El núcleo extractor permanece byte-a-byte idéntico a v0.9.6/v0.6.2/v0.4.5 en los 14 archivos de control.

v0.4 parte de los errores ya observados en la reserva de v0.3, que por tanto se considera development/regression para esta versión. Los cambios son deliberadamente conservadores:

1. reconstrucción de títulos con `?`/`!` únicamente cuando la frontera con una revista está independientemente observada;
2. separación de descriptores terminales de edición (`2nd ed.`, etc.);
3. expansión de alias de revista excesivamente cortos sólo con evidencia estructural;
4. recuperación conservadora de editoriales de una palabra en capítulos;
5. separación explícita entre `publisher` (forma normalizada/canónica) y `publisher_observed` (forma literal observada).

## 2. Desarrollo / no regresión

La recomputación empaquetada contiene **29,027 filas** del CSV histórico incluido en la release (el nombre histórico del archivo conserva “29470”; esta recomputación exacta se informa con el número realmente leído).

- revista fuzzy ≥ .90: **79.13%**;
- cobertura de revista: **84.88%**;
- tipo documental de clase alta: **83.84%**;
- editorial canónica exacta: **93.67%**;
- cobertura editorial: **95.45%**.

Estas son métricas de desarrollo, no una estimación externa de accuracy.

## 3. Nuevo holdout externo congelado

Antes de importar o ejecutar v0.4 sobre las nuevas citas se congelaron:

- código `biblioref/parsing/v04.py`: `f12b43a4670615c9445112052b9714dd11c54f3f10c0889169c3083eb8f2d173`;
- gold de 30 referencias: `0db74739ad42c675fda7bc4d9afddc07faec83643a342a39875920b6cd86292d`.

El holdout contiene 30 referencias tomadas de tres tesis no usadas previamente para desarrollar el parser:

- Sheffield/Rutkauskas 2023: 10 referencias APA-like;
- York/Brennan 2024: 10 referencias APA-like con web, congreso, libro y capítulo;
- USP/Pizzimenti 2024: 10 referencias en portugués, estilo ABNT-like.

El hash de v0.4 **después** de la evaluación es idéntico al hash previo: `f12b43a4670615c9445112052b9714dd11c54f3f10c0889169c3083eb8f2d173`.

### Resultado global

| Campo | v0.3 | v0.4 |
|---|---:|---:|
| Autor exacto | 90.00% | **90.00%** |
| Año exacto | 100.00% | **100.00%** |
| Título exacto | 56.67% | **63.33%** |
| Título fuzzy ≥ .90 | 60.00% | **66.67%** |
| Revista fuzzy ≥ .90 | 85.71% | **85.71%** |
| Cobertura revista | 85.71% | **85.71%** |
| Tipo exacto | 73.33% | **73.33%** |
| Editorial canónica exacta | 30.77% | **30.77%** |
| Editorial observada exacta | 0.00% | **23.08%** |
| Cobertura editorial observada | 0.00% | **53.85%** |
| DOI exacto (n=13) | 100.00% | **100.00%** |

En la comparación pareada, v0.4 recuperó **2 títulos** y **3 editoriales observadas** sin regresiones pareadas en los campos evaluados.

## 4. Hallazgo externo principal: ABNT

El resultado global debe leerse por estilo. En Sheffield y York, v0.4 obtiene 100% en autor, año, título fuzzy, revista y tipo para las referencias seleccionadas. En las 10 referencias ABNT-like de USP/Pizzimenti:

- autor exacto: **70%**;
- año exacto: **100%**;
- título fuzzy ≥ .90: **0%**;
- revista fuzzy ≥ .90: **0/2**;
- tipo exacto: **20%**.

Esto revela un límite arquitectónico nuevo: el parser actual está muy orientado a gramáticas autor-año donde el año aparece cerca del bloque de autor. En ABNT, el año suele aparecer al final y el patrón `AUTOR. Título. Lugar: Editorial, año` requiere una ruta específica.

**No se añadió ninguna regla ABNT después de observar este holdout.** Estas 10 referencias quedan quemadas y deben pasar a development/regression de una futura v0.5.

## 5. Estado y siguiente paso

v0.4 se cierra como una mejora incremental y sin regresiones respecto de v0.3 en los campos objetivo. Su principal aporte práctico es la mejora de títulos complejos y la nueva distinción `publisher` / `publisher_observed`.

La prioridad para parser v0.5 debe ser una ruta **ABNT/autor en mayúsculas + año terminal**, desarrollada sobre las referencias USP ya observadas y validada luego con un **nuevo** holdout portugués/ABNT que no haya sido utilizado para diseñar esa ruta.

## 6. Verificación final de release

- `pytest`: **386 passed, 3 skipped, 16 subtests passed**;
- `node --check static/app.js`: **OK**;
- `py_compile`: **OK**;
- núcleo extractor: **14/14 archivos SHA-256 idénticos**;
- hash de `v04.py` posterior a la evaluación: **idéntico al freeze previo**.
