# Diagnóstico sobre el dataset «Tesis doctorales de Psicología» (121 tesis)

Fecha: 2026-09-20 · Base: 121 tesis, 32.221 referencias, 193 secciones, 761 avisos.

Todo se midió sobre el dataset exportado y se verificó reejecutando
`biblioref.pipeline.process_pdf` sobre los PDF del workspace
(`~/.biblioref/projects/default`, los 121 `document_id` están todos). La corrida de
línea de base reproduce **exactamente** los conteos del dataset, así que los deltas son
directamente comparables.

Los parches, con sus hunks, están en
`BIBLIOREF_DATASET_TESIS_PSICOLOGIA_PARCHES_V0_1.md`.

---

## 1. Resumen

| Familia | Qué pasa | Magnitud | Parche |
|---|---|---|---|
| **FN total** | Tesis enteras en cero o casi | 6 tesis; 5 recuperables → **+1.131 refs** | P1, P2 |
| **FN parcial** | Páginas de bibliografía sin ninguna referencia | 105 páginas en 28 tesis | P1 |
| **FP de zona** | El índice o un rótulo del cuerpo abre zona | 15 zonas de índice + 7 zonas de prosa (163.904 caracteres de texto corrido guardados como referencias) | P2 (guarda), G |
| **FP de registro** | Línea de continuación promovida a referencia | 545 registros; 422 refs de menos de 60 caracteres | P6 |
| **Pegadas** | Dos o más referencias en un registro | 391 reales sobre 583 avisos | P3, P4, P5 |
| **Ruido de revisión** | Avisos que no son pegadas | 191 de 583 (33 % de la cola) | filtro de aviso |

Seis defectos puntuales explican casi todo. Con cuatro de ellos corregidos a la vez el
corpus pasa de 32.221 a **33.648 referencias (+1.427)**, con 104 de 121 tesis idénticas
y una sola baja de un registro (§ 9).

**El orden por rendimiento es contraintuitivo**: lo que más referencias recupera no es
la lógica de bordes sino dos condiciones de umbral, una en el diagnóstico de estilo y
otra en el reconocimiento de encabezados.

---

## 2. Dos líneas entre corchetes vacían una tesis entera (P1)

`diagnose_style` (`biblioref_v0_2.py:355`) elige el estilo así:

```python
# Activate structural markers only with repeated evidence.
if n_key >= 2:
    style = "bracket_key"
```

Dos ocurrencias. Sin comparar contra nada. En T0016 las dos ocurrencias son:

```
[on-line] en:
[on-line] en: http://www.revistaaen.es/index.php/aen/article/view/15498/15358
```

contra **99 líneas** con forma `Apellido, N. (año).`. El estilo queda en `bracket_key`,
`diagnose_adaptive_layout` calcula el margen sobre esas dos líneas (106.46, que es el
margen de continuación), y todo lo que arranca en 85.1 — o sea, todas las referencias —
queda fuera de tolerancia. Resultado: 55 referencias rotas en 11 páginas, 6 de ellas
completamente vacías, y **57 avisos `falta_de_verdad`**, el 38 % de todos los del corpus.

T0104 es el mismo defecto con otra frase: tres líneas `[Recuperado] 15 de junio de 2015
de la World Wide Web:` sobre 69. Quedaron 3 referencias para una tesis de 335 páginas.

**Exigiéndole al marcador que tenga apoyo real** (variante conservadora: un marcador
con menos de 4 líneas marcadas pierde contra una alternativa con 5× más evidencia):

| Tesis | Antes | Después |
|---|---|---|
| T0016 | 55 | **481** |
| T0104 | 3 | **26** |
| T0056 | 225 | 225 (`numeric` con 6 marcadores: no se toca) |
| T0110 | 51 | 51 (`numeric` legítimo, intacto) |

T0016 queda con 481 referencias de la A (`Abbagnano, N. (1978)`) a la Z
(`Zysman, S. (2004)`), mediana de 150 caracteres, 4 registros cortos. Eso cierra además
sus 57 avisos `falta_de_verdad`.

Con un umbral más agresivo (piso proporcional al número de líneas) T0104 llega a **286**
—la zona entera— y T0079 mejora de 893 a 921, pero T0056 se cae de 225 a 37 porque el
cambio de estilo de una zona chica hace que el arbitraje del pipeline abandone las zonas
con encabezado. El umbral merece un barrido sobre el corpus; el detalle está en el
documento de parches.

---

## 3. El folio pegado al encabezado (P2)

Seis tesis quedaron en cero. Dos causas distintas:

**a) Sin capa de texto** — `T0038` (392 pp.) y `T0041` (370 pp.) devuelven **0 líneas**:
son PDF escaneados, necesitan OCR. `T0051` son 6 páginas, no es una tesis.

**b) Encabezado no reconocido** — `T0025`, `T0084`, `T0091` tienen el texto perfecto y
**0 zonas**:

| Tesis | Página | Línea tal como la ve el extractor | `is_ref_heading` |
|---|---|---|---|
| T0025 | 290 | `Referencias bibliográficas 151` | `False` |
| T0084 | 279 | `5. Referencias bibliográficas 138 .` | `False` |
| T0091 | 188 | `Referencias generales` | `False` |

El `151` y el `138` son el **folio impreso**, que cae en la misma banda vertical que el
título y el extractor de líneas lo fusiona. `_is_ref_heading_normalized`
(`biblioref_v0_2.py:134`) usa `re.fullmatch`: `Referencias bibliográficas` → `True`,
`Referencias bibliográficas 151` → `False`. Además el vocabulario de la rama
`referencias` sólo admite `bibliograficas|citadas|consultadas`; `generales`,
`documentales` y `finales` no están (mientras que `Bibliografía general` sí matchea,
por la otra rama).

**Medido**: T0025 0 → **269**, T0084 0 → **332**, T0091 0 → **81**.

La relajación **no se puede tomar sola**: la misma cadena está en el índice. Sin guarda,
el `BIBLIOGRAFÍA: ……… 304` de la p. 9 de T0016 abre una zona fantasma y le corta la
zona real de 336 a 319 páginas (481 → 235 referencias). Dos señales alcanzan para
distinguirlos:

1. puntos conductores (`…….` o `. . . .`), y
2. **el numeral apunta hacia adelante**: en el índice el número es la página destino
   (304 en la página 9); en un encabezado es el folio de la página actual (151 en la
   página 290).

Con las dos guardas, ninguna de las 121 tesis abre zona desde el índice por este camino.

---

## 4. Las pegadas

De los 583 avisos `pegada_divisible`: **391 son pegadas reales** y **191 son falsos
positivos del propio detector de avisos** (§ 6).

### 4.1 La regla del «año en la línea 2» (P3) — 196 cortes

`biblioref_v0_4.py:708-714`:

```python
# In block bibliographies, a year appearing on line 2 belongs to the paragraph
# opened immediately above; it must not split that reference in half.
if start and index > 0 and … and paragraph_profile.separated:
    if evidence in {"author_or_institution+parenthetical_date+start_margin", …}:
        prev = effective_lines[index - 1].text.strip()
        if prev and prev[:1].isupper() and not YEAR_RX.search(prev):
            start, evidence = False, ""     # ← cancela el borde
```

Cancela un borde que **ya tenía margen de inicio + fecha entre paréntesis**, sólo porque
la línea anterior empieza con mayúscula y no tiene año. Pero esa línea anterior es, casi
siempre, la continuación de la referencia previa, y esas líneas empiezan con el nombre
de la revista: `Sciences,`, `Neurobiology,`, `Journal of…`.

T0034, p. 102 — geometría inequívoca, sangría francesa detectada, bordes a 85.1 y
continuaciones a 120.5:

```
85.1   Adolphs, R. (1999). Social cognition and the human brain. Trends in Cognitive
120.5    Sciences, 3 (12), 469-479.
85.1   Adolphs, R. (2001). The neurobiology of social cognition. Current Opinion in   ← cancelado
120.5    Neurobiology, 11 , 231–239.
85.1   Adolphs, R. (2003). Recognizing Emotion From Facial Expressions: …             ← cancelado
```

→ un solo registro de 372 caracteres con tres referencias adentro.

El parche no cancela cuando la geometría ya distingue el registro (sangría francesa +
candidata en el margen + anterior sangrada). **Medido sobre las 121 tesis**: +263
referencias, **196 de 583 cortes resueltos**, 12 tesis modificadas, 109 idénticas. En
las tesis que toca resuelve el 100 % de sus avisos: T0070 62/62, T0073 37/37,
T0126 26/26, T0034 25/25, T0102 18/18, T0085 7/7.

### 4.2 Sangría de primera línea invertida (P4) — 31 cortes

T0117 tiene el registro sangrado a 120.5 y las continuaciones a 85.1: el corrimiento va
hacia la **izquierda**. `_weak_boundary_supported` (`biblioref_v0_4.py:331`) sólo sabe
pedir apoyo si la línea siguiente está más a la derecha
(`follower.x0 >= layout.start_margin + 14`), así que niega el apoyo siempre y tira
bordes correctos con evidencia `author_initial+start_margin`:

```
120.5  Andari, E., Duhamel, J-R., Zalla, T., Herbrecht, E., Leboyer, M. y Sirigu,   ← borde negado
 85.1    A. (2010). Promoting social behavior with oxytocin in high-functioning autism
```

**Medido**: T0117 185 → **219**, **31/31** cortes resueltos. Sin efecto en las
bibliografías con sangría francesa (T0008, T0018, T0034, T0046, T0111, T0118 sin
cambios).

### 4.3 Apellidos con partícula minúscula (P5) — 76 registros

`biblioref_v0_4.py:308` exige `text[:1].isupper()`, así que `van Dijk`, `de Asúa`,
`del Valle`, `von Foerster` y `da Silva` **nunca** abren registro. 49 referencias del
corpus tienen uno o más adentro, con 76 registros perdidos. El peor, T0078, con 3.072
caracteres:

```
Daston, L., & Galison, P. (1992). The Image of Objectivity… de Alzaga, S. (1944).
Higiene hospitalaria… de Asúa, M. (1986). Evolución de la formación médica… de Asúa,
M. (2012). La pediatría… de Asúa, M. (2016). Conversación telefónica…
```

### 4.4 Lo que queda

- **T0061 (105 avisos)** — bibliografía estilo Chicago/humanidades:
  `Anzieu, Didier. «Los significantes formales y el yo-piel.» En Las envolturas
  psíquicas, de Didier Anzieu… Buenos Aires: Amorrortu, 1987.` Autor con nombre
  completo, título entre comillas angulares y **año al final**. El detector busca
  `Apellido, Inicial. (año)` y pega 3 y 4 registros por párrafo. Es **una sola tesis**
  del corpus (72 registros con esa forma en total), pero concentra el 27 % de todos los
  avisos de pegada: es el cluster individual más grande que queda.
- El resto (≈35) se reparte entre T0092, T0079, T0057, T0114, T0105, T0086, T0058.

---

## 5. Falsos positivos

### 5.1 De zona

- **15 zonas nacidas en el índice**: T0080 abre **13 zonas** en las páginas 5-6, una por
  cada línea del índice que dice «Referencias bibliográficas» (es una tesis con
  bibliografía por capítulo, así que el rótulo se repite); T0076 y T0092 una cada una.
  Todas con 0 referencias. Son ruido, pero envenenan el conteo de secciones y cualquier
  selección por «última zona». **Barrerlas es trivial: una zona con cero segmentos no es
  una sección.**
- **7 zonas de texto corrido**: un «REFERENCIAS» del cuerpo abre una zona que se traga
  páginas enteras de prosa.

  | Tesis | Rótulo | Páginas | Refs | Largo promedio | Máximo |
  |---|---|---|---|---|---|
  | T0014 | referencias bibliográficas. | 29-41 | 3 | 6.856 | 11.619 |
  | T0101 | REFERENCIAS | 182-193 | 5 | 6.162 | 12.242 |
  | T0073 | REFERENCIAS | 208-216 | 2 | 3.999 | 7.762 |
  | T0026 | bibliografía citada. | 85-93 | 8 | 2.018 | 7.889 |
  | T0094 | Referencias | 17-31 | 29 | 854 | 3.745 |

  **163.904 caracteres de prosa** guardados como si fueran referencias (78 registros de
  más de 800 caracteres). El marcador `sospechosa` del dataset ya señala 33 de 193
  secciones: el problema *se detecta*, lo que falta es **no abrir la zona**.

- Caso aparte: la segunda zona de T0117 (`referencias.`, pp. 417-420) captura la
  desgrabación de una entrevista (`- Y el autismo?`, `- Gracias por tu participación.`).

### 5.2 De registro

**545 registros arrancan a la derecha del margen modal de su propia tesis** (largo
mediano 84 caracteres; 84 de ellos por debajo de 60): son líneas de continuación
convertidas en referencias. La regla, `biblioref_v0_4.py:695-697`, acepta cualquier
línea con forma de «algo, número, año» cuando `hanging_indent_detected` es verdadero —
y ese flag es del **documento**, no de la línea, así que no mira el x0. Por eso
`author+bare_year+local_geometry` aparece 304 veces fuera del margen modal.

En T0034, `Neuron , 65 , doi:10.1016/j. neuron .2010.03.006.` queda como referencia
propia y `Adolph, R. (2010). Conceptual Challenges…` queda mutilada sin su cita.

Exigir margen (P6) elimina **249 registros espurios** (T0029 −84, T0071 −49, T0030 −33,
T0068 −17, T0116 −12) y las fusiones son correctas:

```
antes   «Ābele, L., Haustein, S., Møller, M., & Zettler, I. (2020). Links between observed and self-»
        «Safety Research , 41 (2), 99–106. https://doi.org/10.1016/j.jsr.2010.02.005»
después «Ābele, L., … (2020). Links between … Safety Research, 41 (2), 99–106. https://doi.org/…»
```

**Pero** al cambiar los conteos invierte el arbitraje de rutas del pipeline en T0017 y
T0071 y ahí la segmentación empeora. Verificado por aislamiento: con P3 solo, T0017 y
T0071 quedan idénticas a la base. No tomarlo en crudo.

---

## 6. Un tercio de la cola de revisión no son pegadas

191 de los 583 avisos `pegada_divisible` son **falsos positivos del detector de
avisos**: el corte cae en un salto de línea dentro de *una sola* referencia.

```
T0044  «…Barsalou, L. W. (1992). Cognitive Psychology. An overview for cognitive scientist.»
       ||CORTE||  «Hillsdale, NJ: Lawrence Erlbaum Associated.»

T0092  «…levels of special educational support needs in autism. Research in Autism Spectrum»
       ||CORTE||  «Disorders, 5 (1): 368–376. https://doi.org/10.1016/j.rasd.2010.05.002»
```

Concentrados en T0044 (23), T0092 (20), T0086 (17), T0055 (17), T0062 (15). El
discriminante que los separa bien es el lado derecho del corte: **¿el fragmento que
sigue abre como registro** (`Apellido, Inicial.` o `Apellido, Nombre`) **y tiene un año
en los primeros ~200 caracteres?** Si no, es continuación de línea. Aplicado a los 583
avisos da 391 reales / 191 falsos, y coincide con la revisión manual de muestras
(`avisos_clasificados.csv`).

Los 27 avisos `pegada_ya_extraida` (T0078, T0094, T0106, T0120) son inofensivos.

---

## 7. Orden sugerido

| # | Cambio | Qué devuelve | Riesgo |
|---|---|---|---|
| 1 | **P1** umbral de evidencia para el estilo de marcador | +426 refs (T0016) y sus 57 avisos `falta_de_verdad` cerrados | umbral a barrer (ver § 9) |
| 2 | **P2** folio pegado + guarda de índice | +682 refs (3 tesis hoy vacías) | bajo, va junto con la guarda |
| 3 | **P3** «año en la línea 2» | +263 refs, 196 cortes | ninguno medido |
| 4 | **P4** sangría invertida | +34 refs, 31 cortes | ninguno medido |
| 5 | **P5** partícula minúscula | +76 registros | bajo |
| 6 | barrer zonas con 0 segmentos | −15 secciones fantasma | ninguno |
| 7 | filtro del lado derecho en los avisos | −33 % de ruido en la cola | ninguno |
| 8 | **P6** margen en `local_geometry` | −249 registros espurios | **revisar arbitraje de rutas** |
| 9 | perfil «autor nombre completo + año final» | T0061, 105 avisos | diseño nuevo |
| 10 | OCR para T0038 y T0041 | 2 tesis de 762 páginas | ingestión |

## 8. Nota sobre el núcleo congelado

`biblioref_v0_2.py`, `biblioref_v0_3.py` y `biblioref_v0_4.py` están cubiertos por los
manifiestos `EXTRACTION_CORE_NONREGRESSION_*_SHA256.json`. Los parches están escritos
sobre el núcleo para que se vea exactamente qué condición cambia, pero aterrizarlos ahí
rompe las guardas de no regresión. Las dos salidas son landearlos en
`biblioref/extraction/` como una capa de reparación más (como `boundary_reconciliation`
en 0.6.5 y `dominant_margin_reconciliation` en 0.6.6) o rehacer el manifiesto con una
validación nueva. Es una decisión de proyecto.

Vale notar que P1 y P2 no son de segmentación sino de **diagnóstico de estilo y de
encabezado**, que es una etapa anterior: son más fáciles de aislar en una capa previa
sin tocar la lógica de bordes.


---

## 9. Resultado combinado sobre las 121 tesis

Corrida con P1 (variante conservadora) + P2 + P3 + P4 aplicados a la vez; P5 y P6 fuera.

| | Base | Combinado |
|---|---|---|
| Referencias | 32.221 | **33.648** (+1.427) |
| Tesis modificadas | — | 17: 16 suben, 1 baja, **104 idénticas** |
| Cortes de pegada resueltos | — | **224 / 583** |
| Avisos `falta_de_verdad` recuperados | — | **71 / 151** (56 de los 57 de T0016) |
| Registros de más de 800 caracteres (prosa) | 78 | **63** |
| Largo mediano | 180 | 179 |

| Tesis | Base | Combinado | Δ | | Tesis | Base | Combinado | Δ |
|---|---|---|---|---|---|---|---|---|
| T0016 | 55 | 481 | +426 | | T0126 | 77 | 117 | +40 |
| T0084 | 0 | 332 | +332 | | T0117 | 185 | 219 | +34 |
| T0025 | 0 | 269 | +269 | | T0102 | 126 | 152 | +26 |
| T0070 | 136 | 228 | +92 | | T0034 | 111 | 135 | +24 |
| T0091 | 0 | 81 | +81 | | T0104 | 3 | 26 | +23 |
| T0073 | 273 | 321 | +48 | | T0109 | 422 | 434 | +12 |

La única baja, T0008 351 → 350, resultó **no ser de los parches**: una corrida fresca
del árbol actual sin ningún parche también da 350. El dataset exportado sale de los
resultados guardados en el momento de la ingesta —la columna `revision_extraccion`
tiene dos versiones distintas— así que esa diferencia de un registro es anterior. Por eso
la línea de base del arnés se regenera corriendo el pipeline y no se lee del dataset.

Con la variante agresiva de P1 el total sube a 33.736 (+1.515) y aparecen dos bajas más
que en realidad son mejoras —T0121 deja de capturar los objetivos de la tesis, T0037 un
manual de intervención clínica con un bloque de prosa de 3.924 caracteres— pero también
la única regresión real medida: T0056 225 → 37.

### Lo que esto dice del pipeline

Tres de los seis defectos (P1, P6 y en parte P2) tienen el mismo patrón: **un cambio de
conteo aguas arriba invierte el arbitraje de rutas**, y el resultado final puede mejorar
o empeorar por un camino que no tiene nada que ver con la corrección en sí. Vale la pena
mirar ese arbitraje con la misma lupa: hoy una decisión de estilo tomada sobre dos
líneas puede decidir qué ruta gana para un documento de 300 páginas.


---

## 10. Qué se landeó

El algoritmo **0.6.9** (`BIBLIOREF_ALGORITHM_V0_6_9_VALIDATION.md`) toma P2, P3 y P4.
Medido con el arnés nuevo sobre los 128 documentos del workspace —el dataset era un
subconjunto de 121—, contra una línea de base regenerada del árbol actual:

| | 0.6.8 | 0.6.9 |
|---|---|---|
| Registros | 32.993 | **33.978 (+985)** |
| Documentos idénticos byte a byte | — | **111 / 128** |
| Documentos modificados | — | 17, **ninguno con menos registros** |

P1, P5 y P6 quedaron afuera: los tres tocan el arbitraje de rutas y hay que entrar por
ahí primero.
