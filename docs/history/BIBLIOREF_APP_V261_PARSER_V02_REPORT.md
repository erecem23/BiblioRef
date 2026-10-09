# BiblioRef v0.9.6 — APP v2.6.1 + parser bibliográfico v0.2

**Fecha:** 2026-09-02  
**Núcleo:** `0.9.6 / 0.6.2 / 0.4.5`  
**Parser:** `biblioref-parser-v0.2` (`development_candidate`)

## Resultado

Se promovió el parser downstream desde el baseline legacy v0.1 a v0.2 sin modificar la detección ni la segmentación de referencias. Los 14 archivos centrales de extracción conservan el SHA-256 registrado antes de esta rama.

### No-regresión obligatoria

En las 29.470 referencias de desarrollo, `year`, `title` y `doi` son **idénticos 29.470/29.470** entre v0.1 y v0.2. El parser v0.1 permanece accesible en `biblioref.parsing.legacy` para reproducibilidad.

### Cambios

- revista: patrón de metadatos de artículo + normalización por alias;
- tipo documental: reglas jerárquicas con prioridad para capítulo/congreso/tesis/legal antes de artículo/libro;
- editorial: separación explícita de `publisher`, limitada a referencias monográficas;
- autor: soporte de iniciales compactas (`LI` → `L. I.`) y pares repetidos `Apellido, Iniciales`.

### Desarrollo 29.470

| Métrica | v0.1 | v0.2 |
|---|---:|---:|
| autor estricto normalizado | 71,33% | 72,10% |
| revista fuzzy ≥ .90 | 39,26% | 76,79% |
| revista cobertura | 44,23% | 82,63% |
| tipo, clase gruesa | 68,71% | 82,93% |
| editorial aislada exacta sobre target v2 | — | 93,59% |
| editorial cobertura sobre target v2 | — | 95,30% |

El target de editorial y el lexicón de revistas/editoriales provienen de artefactos de desarrollo del propio proyecto. Estas cifras **no estiman generalización externa**.

### Seed 120

- año/título/DOI: 120/120 idénticos a v0.1;
- revista fuzzy ≥ .90: 46,67% → 80,00%;
- tipo grueso: 70,83% → 80,00%;
- editorial: 22/23 exactas/cubiertas; el caso restante es una referencia de congreso cuyo seed trataba a la facultad organizadora como editorial, promoción que v0.2 rechaza deliberadamente.

## Suite

```text
359 passed, 3 skipped, 16 subtests passed
node --check static/app.js: OK
python -m py_compile: OK
extraction core SHA-256: 14/14 identical
```

## Dictamen

v0.2 es una mejora defendible como **candidate de desarrollo**. Revista y tipo muestran ganancias grandes sobre el corpus usado para desarrollo; editorial queda estructuralmente separada; autores mejora poco y sigue siendo el frente menos maduro. El próximo test fuerte debe ser externo y anotado manualmente.
