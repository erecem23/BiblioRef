# BiblioRef v0.9.9 / algoritmo v0.6.5 — CandidateRegionV2 bridge

## Objetivo

Cerrar la brecha entre **descubrimiento de una región bibliográfica** y **reconciliación geométrica/estructural**. Hasta v0.9.8, una zona aceptada por el fallback podía producir registros, pero no entraba necesariamente en el mismo stack de reparación que una zona detectada por la ruta estable. En v0.9.9 candidata, una región aceptada puede reconstruirse como `AdaptiveLayoutZone` y pasar por los mismos gates posteriores.

## Cambio central

Se agregó un puente:

`CandidateRegionV2 -> effective zone geometry -> marker/layout/boundary reconciliation`

El detector estable no se amplió con una lista indiscriminada de encabezados. `Fuentes y bibliografía`, `Citas Bibliográficas` y otras frases siguen funcionando como **evidencia candidata** combinada con densidad de referencias.

Para regiones que la ruta pública todavía deja en `audit_required`, se permite materializar una zona **provisional sólo para intentar reparaciones estructurales**. Si ninguna reparación fuerte pasa su gate, los registros provisionales nunca se publican y se conserva `audit_required`.

## Continuidad de fin por secuencia numérica

Se agregó `extend_numeric_candidate_end_page()`. Una región candidata puede haber terminado una página antes porque la última página es corta. El final se extiende únicamente si:

- la región ya contiene una secuencia larga y exacta `1..N`;
- la página inmediatamente siguiente contiene `N+1` en el mismo margen de marcador;
- la secuencia continúa sin saltarse páginas.

No se aplica a zonas estables.

Caso UNR 14: la región candidata terminaba en p.111 con marcador 139; la p.112 contiene 140–147. El nuevo gate extiende 111 -> 112 y la resegmentación devuelve **147/147**.

## Resultados UNR focales

- UNR 12: **147/147**.
- UNR 13: **165/165**, sin cambio.
- UNR 14: **42 -> 147**, con bridge CandidateRegionV2 y extensión exacta del final.
- UNR 16: **126/126**.
- UNR 17: **175/175**.
- UNR 18: siete bibliografías jerárquicas, **101** referencias totales: 18+5+14+18+17+22+7.
- UNR 20: **208/208**.
- UNR 25: **188/188**, sin cambio.
- UNR 29: detección de gutter + reflow por columnas, **109** registros.
- UNR 02: CandidateRegionV2 conserva una zona `Fuentes y bibliografía`, 488 registros; no se fuerza una reparación adicional.
- UNR 28: sigue en **`audit_required`**. El sistema encuentra evidencia candidata, pero el layout bicolar todavía no supera el gate de segmentación. Esto se considera una abstención segura, no una extracción correcta.
- UNR 30: sigue con 181 registros y 3 segmentos >=180 palabras; queda como caso de desarrollo posterior.

## No regresión

Suite completa posterior al bridge:

**543 passed, 3 skipped, 16 subtests passed**.

El parser v0.11 permanece congelado. SHA-256:

`6009da2591940aa6a5aeb2ac459b03272788e379f2995e00a93ca0bbc9b75f93`

StyleProfiler v0.1-shadow permanece congelado. SHA-256 de `profiler.py`:

`18c1470b43a9e19891d9f2387e92f4a7e4db73524bcabd2c9ef30bf1b130babb`

## Estado

**Candidata de field test**, no release estable. La siguiente ronda debe priorizar tesis nuevas y, especialmente, layouts bicolares tipo UNR 28 y bibliografías de año final subsegmentadas tipo UNR 30.

## Actualización de field test UNC — boundary2

Una tesis externa de la UNC con bibliografía APA-like (p.158–172) permitió auditar 102 límites reales. La candidata anterior producía 109 por ocho falsos cortes `author+bare_year+local_geometry` en el margen de continuación y un límite institucional omitido con año en la línea siguiente. La nueva reconciliación `0.6.5-hanging-indent-boundary2` devuelve **102/102**, sin modificar el motor estable ni parser v0.11.

La aceptación de delta negativo está limitada a fronteras débiles fuera del margen inicial y se bloquea si hay entradas de autor heredado que comienzan solamente por año.

No regresión focal: UNR 12=147, 13=165, 14=147, 16=126, 17=175, 18=101/7 zonas, 20=208 y 25=188. Suite completa: **545 passed, 3 skipped, 16 subtests passed**.
