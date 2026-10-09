# Algoritmo 0.6.11 — las reglas que abrían registro sin mirar el margen

Fecha: 2026-09-20 · Software v0.9.10-rc2 · Algoritmo 0.6.10 → **0.6.11**
Declaración: `EXTRACTION_CORE_NONREGRESSION_V0611_SHA256.json`
Antecedente: `BIBLIOREF_ALGORITHM_V0_6_10_VALIDATION.md`

---

## Por qué esto no se pudo hacer de a un parche

En 0.6.9 dejé afuera dos cambios correctos —el margen en
`author+bare_year+local_geometry` y los apellidos con partícula minúscula—
porque cada uno, aplicado solo, rompía una tesis distinta. La lectura de
entonces fue que el arbitraje de rutas estaba acoplado. Era cierto, pero no era
la causa.

Midiendo con el arnés apareció el cuadro completo. El primer parche **no sacaba**
los bordes fuera de margen: los **redistribuía**. Impedía que disparara una
regla, y las mismas líneas abrían registro igual por otras dos:

```
T0017, con sólo el primer parche — 183 registros, 41 de ellos malformados
  inherited_author+date_only_entry  x0=72.15  (2017). Effect of long-term omega 3…
  numeric_marker                    x0=72.15  60. https://doi.org/10.1016/j.neuarg.2017.11.002
  numeric_marker                    x0=72.15  693. https://doi.org/10.1016/j.stemcr.2021.01.019 Barcelo-Coblijn, G.,…
```

Con 41 de 183 arranques fuera del margen, la reparación de sangría francesa se
negaba —y con razón: `base_start_margin_support` caía a 0.776 contra un piso de
0.90, o sea que la base ya no parecía una línea de base de sangría francesa.

**No era que mejorar una cosa empeorara otra.** Era que había tres reglas con el
mismo defecto y yo estaba arreglando una.

## Los cinco cambios

### 1. `author+bare_year+local_geometry` (`biblioref_v0_4.py`)

`hanging_indent_detected` es una constante **del documento**, no de la línea.
Con sangría francesa detectada, cualquier línea con forma de «algo, número,
año» abría registro, estuviera donde estuviera. Ahora exige margen de inicio.

### 2. El marcador numérico (`biblioref/detection/signals.py`)

```python
if NUMERIC_MARKER_RX.match(text):
    return True, "numeric_marker"        # antes de la guarda de margen
```

El motivo original es bueno: en una bibliografía numerada, el marcador vale como
borde aunque la primera página de la zona use otro margen. El problema es que se
aplicaba en cualquier estilo, y en una zona autor-año
`60. https://doi.org/10.1016/j.neuarg.2017.11.002` es el **número de página** de
una línea de continuación. Ahora sólo ignora el margen si la zona es numerada.

### 3. `inherited_author+date_only_entry` (`biblioref/extraction/resegmentation.py`)

`(2017). Effect of long-term…` hereda el autor del registro de arriba. Eso es
correcto cuando el de arriba ya es una referencia, y es exactamente al revés
cuando la lista de autores ocupó toda la primera línea y el año se fue a la
siguiente. Lo que los separa es cómo termina el de arriba:

```
… Caribe (CEPAL) Andrieu, S., Guyonnet, S., Coley, N., Bordes, S. & Olivier-Abbal, P.
(2017). Effect of long-term omega 3 polyunsaturated fatty acid supplementation…
```

Una referencia completa no termina en `& Apellido, X.` El patrón quedó en
`biblioref/core/patterns.py` porque lo usan dos capas.

### 4. Apellidos con partícula minúscula (`biblioref_v0_4.py`)

El caso simétrico: `van Dijk`, `de Asúa`, `del Valle`, `von Foerster` no empiezan
con mayúscula, así que `text[:1].isupper()` los rechazaba y quedaban pegados a la
referencia anterior. 49 referencias del corpus con 76 registros perdidos. Se
acepta la partícula exigiendo que el apellido que sigue sí abra con mayúscula,
para no confundirla con prosa que arranca en «de la».

### 5. La licencia del arbitraje (`biblioref/extraction/boundary_reconciliation.py`)

La reparación de sangría francesa puede **quitar** bordes, y su licencia era
`n_baseline_off_margin_weak_local_geometry >= |delta|`: contar los registros de
la base que arrancan fuera del margen **y tienen la etiqueta**
`author+bare_year+local_geometry`. Un string literal. Cambiás la regla que
produce ese borde y la licencia se revoca aunque el borde siga estando mal.

En T0017 la propuesta de la reparación era idéntica y de calidad perfecta en los
dos casos —172 registros, pureza 0.994, evidencia 1.0, mediana 32 palabras— y se
aceptaba o se rechazaba según esa etiqueta.

Ahora se decide por geometría: en una bibliografía autor-año con sangría
francesa, un arranque fuera del margen que no sea una entrada de autor repetido
es débil, lo haya producido quien lo haya producido. La protección de las
entradas de autor repetido se mantiene, con el mismo discriminante del punto 3.

**Medido aislado**: 126 de 128 documentos idénticos, 2 modificados y los dos son
mejoras. En T0065 se unen diez referencias que estaban partidas en el salto de
línea y desaparece un `PARTE V. REFERENCIAS` que figuraba como registro.

## Resultado

Contra 0.6.10, sobre los 128 documentos: 72 idénticos, 56 modificados,
34.421 → 34.114 registros (**−307**).

**Los registros bajan y eso está bien.** La verificación que lo decide no es el
conteo sino el texto: en **55 de las 56 tesis modificadas el total de caracteres
es idéntico**. Los 307 registros que faltan son fragmentos que se unieron a su
referencia, no referencias perdidas. T0029 pierde 79 registros con cero cambio de
texto; T0071 pierde 82, T0030 32, T0084 64, T0092 32, todos con cero cambio de
texto.

La única tesis que pierde texto es T0050, −650 caracteres, y lo que pierde es el
encabezado de página `ALCOHOL EN UNIVERSITARIOS 74` que venía pegado al final de
cada referencia.

Acumulado desde 0.6.8:

| | 0.6.8 | 0.6.10 | 0.6.11 |
|---|---|---|---|
| Registros | 32.993 | 34.421 | 34.114 |
| Caracteres totales | 5.474.015 | — | **5.635.204** |
| Fragmentos de menos de 60 caracteres | 428 | 470 | **354** |
| Registros de más de 800 caracteres (prosa) | 81 | 66 | **60** |
| Registros que no abren como autor | 1.105 | 1.126 | **1.084** |
| Largo mediano | 180 | 179 | **181** |

0.6.11 mejora **todos** los indicadores de segmentación rota a la vez, incluyendo
los dos que 0.6.10 había empeorado levemente.

`tests_core`: 366 tests, 0 fallas.

### El conteo de registros dejó de ser la métrica

Hasta 0.6.10 «más registros» y «mejor» iban juntos, porque el problema dominante
eran las tesis en cero y las referencias pegadas. A partir de acá el problema
dominante es el contrario —fragmentos promovidos a registro— y el conteo se
mueve en dirección opuesta a la calidad.

Por eso la declaración pasó a registrar contadores de calidad y el test a
verificarlos: no se puede perder texto, y los fragmentos, la prosa capturada y
los registros que no abren como autor no pueden aumentar.

## La trampa de la duplicación

`biblioref_v0_6_1.py` contiene una copia de `_enhanced_start` y de
`_segment_enhanced_zone` que **no corre**: el pipeline usa
`biblioref/detection/signals.py` y `biblioref/extraction/resegmentation.py`. La
copia histórica sólo la usan tres tests de equivalencia. Apliqué el arreglo en la
copia muerta primero y el corpus no se movió, que es cómo apareció.

Conviene dejarlo anotado, o mejor, que la copia histórica importe de la viva en
vez de duplicar el cuerpo.
