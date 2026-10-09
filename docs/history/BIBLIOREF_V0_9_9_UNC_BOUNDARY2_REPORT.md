# BiblioRef v0.9.9 candidate — UNC hanging-indent boundary2

## Caso externo

Documento de field test: tesis UNC, Leandro Ezequiel Ferreyra (2017), 172 páginas. La bibliografía explícita ocupa las páginas físicas 158–172 y contiene 102 referencias auditadas geométricamente.

SHA-256 del PDF usado en la prueba: `fca84979f450a97d3dff67d391698cc00c306242df95ac9b86c6243e1c4f2303`.

## Falla observada antes de la corrección

La candidata v0.9.9 devolvía 109 registros. El contraste con la geometría del PDF mostró:

- 8 falsos límites en el margen de continuación (x≈119.69–120.53) aceptados por `author+bare_year+local_geometry`.
- 1 límite verdadero omitido en el margen de inicio (x≈84.98): autor institucional en una línea y `(2013)` en la línea siguiente, después de una referencia que cruza de página.
- Resultado neto: 109 registros frente a 102 referencias reales.

## Cambio

Se evolucionó exclusivamente la capa posterior de reconciliación geométrica:

`BOUNDARY_RECONCILIATION_VERSION = 0.6.5-hanging-indent-boundary2`

No se modificó `biblioref_v0_4.py` (motor estable) ni parser v0.11.

La reconciliación ahora puede aceptar un delta negativo sólo si se cumplen simultáneamente gates conservadores:

1. sangría francesa fuerte y separación inicio/continuación >=14 pt;
2. pureza de candidatos geométricos >=0.97;
3. soporte del margen inicial del baseline >=0.90;
4. todos los starts fuera del margen que se pretende eliminar provienen de `author+bare_year+local_geometry`;
5. no existen starts protegidos del régimen de autor heredado, por ejemplo `(1995). Título...`;
6. no hay otras fronteras fuertes fuera del margen;
7. la nueva segmentación mantiene evidencia bibliográfica alta y no crea segmentos gigantes.

La misma reconstrucción por margen de inicio recupera autores institucionales cuyo año aparece en las siguientes líneas, incluso cuando la referencia anterior cruza de página.

## Resultado UNC

Después de la corrección:

- registros efectivos: **102/102**;
- comparación normalizada contra el oracle geométrico: **102/102 exactos**;
- zona: p.158–172;
- método: `post_segmentation_boundary_reconciliation_v0_6_5`;
- delta respecto del baseline: `-7` = 8 falsos límites eliminados + 1 límite verdadero recuperado;
- tiempo local de retest: ~9.5 s.

## No regresión focal UNR

Reejecutados con `adaptive_mode=off`, sin rescue audit:

- UNR 12: **147/147**
- UNR 13: **165/165**
- UNR 14: **147/147**
- UNR 16: **126/126**
- UNR 17: **175/175**
- UNR 18: **101** en 7 zonas (18+5+14+18+17+22+7)
- UNR 20: **208/208**
- UNR 25: **188/188**

## Suite

**545 passed, 3 skipped, 16 subtests passed**.

Se añadieron dos tests específicos:

- eliminación de un límite `bare_year+local_geometry` en margen de continuación;
- protección de entradas de autor heredado que empiezan sólo con año.

## Congelados

`biblioref_v0_4.py` permanece byte a byte idéntico a la candidata anterior.

Parser v0.11 permanece byte a byte idéntico. SHA-256:

`6009da2591940aa6a5aeb2ac459b03272788e379f2995e00a93ca0bbc9b75f93`

El falso positivo documental `Tesis psicológica` detectado en este corpus queda registrado como issue de parser, pero **no se corrigió en esta iteración** para no mezclar cambios de extracción y parsing.

## Estado

Sigue siendo **v0.9.9 candidate**, no release estable. La corrección está incorporada al banco externo mediante `field_test_examples/UNC_FERREYRA_V099_EXTERNAL_CASE.json`.
