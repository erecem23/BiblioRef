# Parches propuestos — diagnóstico dataset «Tesis doctorales de Psicología»

Complemento de `BIBLIOREF_DATASET_TESIS_PSICOLOGIA_DIAGNOSTICO_V0_1.md`.
Los cinco cambios están escritos contra el código actual y cada uno se midió por
separado reejecutando el pipeline sobre los 121 PDF del workspace.

> **Los archivos `biblioref_v0_2.py` y `biblioref_v0_4.py` están cubiertos por los
> manifiestos `EXTRACTION_CORE_NONREGRESSION_*_SHA256.json`.** Estos hunks están
> escritos sobre el núcleo para que se vea exactamente qué condición cambia; dónde
> aterrizarlos (núcleo con manifiesto nuevo, o capa de reparación en
> `biblioref/extraction/`) es decisión de proyecto.

---

## P1 — Estilo de marcador sin apoyo real (`biblioref_v0_2.py:355`)

Dos líneas que empiezan con `[on-line] en:` o `[Recuperado] 15 de junio…` convierten
toda la bibliografía en `bracket_key` y la vacían.

```diff
     # Activate structural markers only with repeated evidence. This prevents lines like
     # "1999. Capítulo..." from being treated as reference number 1999.
-    if n_key >= 2:
-        style = "bracket_key"
-    elif n_numeric >= 2 and seq >= 0.45:
-        style = "numeric"
-    elif n_bullet >= 2:
-        style = "bulleted"
+    # v0.6.9: "repeated" no alcanza. Dos lineas con "[on-line] en:" convierten una
+    # bibliografia autor-anio entera en bracket_key y la vacian. Un marcador con
+    # menos de 4 lineas marcadas pierde contra una alternativa con 5x mas evidencia.
+    if n_key >= 2:
+        style = "bracket_key"
+    elif n_numeric >= 2 and seq >= 0.45:
+        style = "numeric"
+    elif n_bullet >= 2:
+        style = "bulleted"
     ...
+    # al final, antes de construir el StyleProfile:
+    style = _demote_weak_marker(style, n_key, n_numeric, n_bullet, n_comma, n_initial, n_inst, seq)
```

```python
def _demote_weak_marker(style, n_key, n_numeric, n_bullet, n_comma, n_initial, n_inst, seq):
    conteo = {"bracket_key": n_key, "numeric": n_numeric, "bulleted": n_bullet}
    if style not in conteo or conteo[style] >= 4:
        return style
    alternativas = {
        "bracket_key": n_key, "numeric": n_numeric, "bulleted": n_bullet,
        "author_initial": n_initial, "author_year_comma": n_comma,
        "institutional": n_inst,
    }
    alternativas.pop(style)
    nombre, valor = max(alternativas.items(), key=lambda x: x[1])
    if valor < max(5 * conteo[style], 5):
        return style
    if nombre == "numeric" and seq < 0.45:
        return style
    return nombre
```

**Medido**

| Tesis | Antes | Después | Causa |
|---|---|---|---|
| T0016 | 55 | **481** | 2 líneas `[on-line] en:` contra 99 con forma autor-año |
| T0104 | 3 | **26** | 3 líneas `[Recuperado]` contra 25 con viñeta |
| T0056 | 225 | 225 | `numeric` con 6 marcadores: no se toca |
| T0110 | 51 | 51 | `numeric` legítimo: no se toca |

T0016 pasa a tener 481 referencias que van de `Abbagnano, N. (1978)` a
`Zysman, S. (2004)`: la zona completa, mediana de 150 caracteres y sólo 4 registros
cortos. Eso cierra además los 57 avisos `falta_de_verdad` de esa tesis, el 38 % del
total del corpus.

### El umbral hay que barrerlo, no elegirlo a mano

Probé también un piso proporcional (`marcador >= max(3, 0.12 × n_líneas)`). Es más
agresivo y llega más lejos en T0104 (3 → **286**, la zona entera de la A a la Z), pero
en T0056 demote el `numeric` de una zona chica, y eso hace que el arbitraje del
pipeline abandone las dos zonas con encabezado (`Referencias:` 214-218 y
`REFERENCIAS BIBLIOGRÁFICAS` 266-283, 219 referencias) y caiga en una «zona inferida
sin encabezado explícito» de 37 registros: **225 → 37**.

O sea: el estilo no sólo decide cómo se segmenta, también alimenta el crecimiento de
zona y el arbitraje de rutas. La dirección del cambio es correcta —en T0016 es 2 contra
99, no hay ambigüedad— pero el umbral exacto merece un barrido sobre el corpus en vez
de un número elegido a ojo. La variante conservadora de arriba es la que no tiene
ninguna regresión medida.

---

## P2 — Encabezado con el folio pegado (`biblioref_v0_2.py:134` / `biblioref_v0_3.py:218`)

`_is_ref_heading_normalized` usa `re.fullmatch`, así que el folio impreso que el
extractor de líneas fusiona con el título rompe el match y la tesis queda en cero.

La relajación tiene que venir con guarda de índice, porque la misma cadena está en la
tabla de contenidos. Dos señales alcanzan: puntos conductores, y un numeral que apunta
**hacia adelante** (en el índice el número es la página destino; en el encabezado es el
folio de la página actual).

```python
# biblioref_v0_2.py — sólo vocabulario, sin geometría
EXTRA_QUALIFIER_RX = re.compile(
    r"^(?:otras\s+)?referencias\s+(?:generales|documentales|finales)$", re.I)

# biblioref_v0_3.py::_is_reference_heading — con geometría
LEADERS_RX = re.compile(r"(?:\.\s?){4,}|…{2,}")
TRAILING_FOLIO_RX = re.compile(r"[\s\.…]*\b(\d{1,4})\s*\.?\s*$")

def _is_reference_heading(line) -> bool:
    if <test original>:
        return True
    raw = line.text.strip()
    if LEADERS_RX.search(raw):
        return False                                  # entrada de indice
    m = TRAILING_FOLIO_RX.search(raw)
    if not m or int(m.group(1)) > line.page:
        return False                                  # el numero apunta adelante
    limpio = TRAILING_FOLIO_RX.sub("", raw).strip(" .-:")
    return bool(limpio and is_ref_heading(limpio, allow_chapter_prefix=allow))
```

**Medido**

| Tesis | Páginas | Antes | Después | Encabezado real |
|---|---|---|---|---|
| T0025 | 315 | 0 | **269** | `Referencias bibliográficas 151` (p. 290) |
| T0084 | 299 | 0 | **332** | `5. Referencias bibliográficas 138 .` (p. 279) |
| T0091 | 206 | 0 | **81** | `Referencias generales` (p. 188) |

Sin la guarda de índice, el `BIBLIOGRAFÍA: ……… 304` de la p. 9 de T0016 abre una zona
fantasma y le corta la zona real de 336 a 319 páginas (481 → 235 referencias). Con la
guarda, ninguna de las 121 tesis abre zona desde el índice por este camino.

Un detalle del guardarraíl «el numeral no apunta hacia adelante»: asume que el folio
impreso nunca es mayor que el número de página del PDF, que es lo normal cuando hay
carátula y preliminares sin numerar o en romanos. Si un PDF viniera recortado (página 1
del PDF = página 10 impresa) el guardarraíl rechazaría un encabezado legítimo. En las
121 tesis del corpus no pasa, pero conviene dejarlo anotado.

---

## P3 — La regla del «año en la línea 2» (`biblioref_v0_4.py:708-714`)

Cancela un borde que ya tenía margen de inicio **y** fecha entre paréntesis sólo porque
la línea anterior empieza con mayúscula y no tiene año — y esa línea anterior es, casi
siempre, la continuación de la referencia previa (`Sciences,`, `Neurobiology,`).

```diff
         if start and index > 0 and effective_lines[index - 1].page == line.page and not is_paragraph_start(index, effective_lines, paragraph_profile) and paragraph_profile.separated:
             if evidence in {"author_or_institution+parenthetical_date+start_margin", "author+bare_year+start_margin"}:
-                prev = effective_lines[index - 1].text.strip()
-                if prev and prev[:1].isupper() and not YEAR_RX.search(prev):
+                previous_line = effective_lines[index - 1]
+                prev = previous_line.text.strip()
+                # Con sangria francesa la geometria ya distingue el registro: la
+                # linea candidata esta en el margen y la anterior esta sangrada.
+                at_margin = abs(line.x0 - effective_layout.start_margin) <= effective_layout.start_margin_tolerance
+                previous_indented = previous_line.x0 >= line.x0 + 6.0
+                hanging_new_record = (
+                    effective_layout.hanging_indent_detected and at_margin and previous_indented
+                )
+                if prev and prev[:1].isupper() and not YEAR_RX.search(prev) and not hanging_new_record:
                     start, evidence = False, ""
```

**Medido sobre las 121 tesis**: +263 referencias, **196 de 583 cortes de pegada
resueltos**, 12 tesis modificadas (11 suben), 109 tesis byte a byte iguales.

| Tesis | Base | Con P3 | Avisos | Cortes resueltos |
|---|---|---|---|---|
| T0070 | 136 | 228 | 62 | 62/62 |
| T0073 | 273 | 321 | 37 | 37/37 |
| T0126 | 77 | 117 | 26 | 26/26 |
| T0102 | 126 | 152 | 18 | 18/18 |
| T0034 | 111 | 135 | 25 | 25/25 |
| T0109 | 422 | 434 | — | — |
| T0085 | 139 | 147 | 7 | 7/7 |

Nota: T0008 figura como 351 en el dataset exportado y como 350 en una corrida fresca
del árbol actual, con o sin P3. El dataset sale de los resultados guardados en el
momento de la ingesta (columna `revision_extraccion`, dos versiones distintas), así que
esa diferencia de un registro es anterior a estos parches. Por eso la línea de base del
arnés se regenera corriendo el pipeline, no leyendo el dataset.

---

## P4 — Sangría de primera línea invertida (`biblioref_v0_4.py:331`)

`_weak_boundary_supported` sólo sabe pedir apoyo si la línea siguiente está **más a la
derecha**. En una bibliografía con sangría de primera línea el registro arranca a 120.5
y las continuaciones caen a 85.1, así que el apoyo se niega siempre y se tiran bordes
correctos.

```diff
     candidate = lines[index]
+    # Regimen de sangria: la continuacion puede caer a la izquierda del margen
+    # de inicio (sangria de primera linea) en vez de a la derecha (francesa).
+    left = sum(1 for l in lines if layout.start_margin - 80 <= l.x0 <= layout.start_margin - 14)
+    right = sum(1 for l in lines if layout.start_margin + 14 <= l.x0 <= layout.start_margin + 80)
+    reverse_indent = left >= 3 and left > right
     paragraph_open = bool(paragraph_profile and is_paragraph_start(index, lines, paragraph_profile))
     for follower in lines[index + 1:index + 3]:
         if follower.page > candidate.page + 1:
             break
-        indented = follower.x0 >= layout.start_margin + 14
+        if reverse_indent:
+            indented = follower.x0 <= layout.start_margin - 14
+        else:
+            indented = follower.x0 >= layout.start_margin + 14
```

**Medido**: T0117 pasa de 185 a **219** referencias y resuelve **31/31** de sus avisos
de pegada. T0008, T0018, T0034, T0046, T0111, T0118 quedan sin cambios (el régimen
invertido no se activa en bibliografías con sangría francesa).

---

## P5 y P6 — quedan juntos para la tanda siguiente

Los dos están correctos y los dos se quedaron afuera de 0.6.9, por la misma
razón: **están acoplados entre sí y al arbitraje de rutas**.

### P5 — Apellidos con partícula minúscula (`biblioref_v0_4.py:308`)

```python
if not at_margin or not text[:1].isupper() or not AUTHORISH_RX.match(text):
    return False, ""
```

`van Dijk`, `de Asúa`, `del Valle`, `von Foerster`, `da Silva` no empiezan con
mayúscula, así que **nunca** abren registro y quedan pegados a la referencia
anterior. Afecta a 49 referencias del corpus, con **76 registros perdidos**
(T0078 11, T0030 5, T0108 4, T0087 4, T0080 4, T0035 4). Ejemplo, T0078, un
registro de 3.072 caracteres:

```
Daston, L., & Galison, P. (1992). The Image of Objectivity… de Alzaga, S. (1944).
Higiene hospitalaria… de Asúa, M. (1986). Evolución de la formación médica… de Asúa,
M. (2012). La pediatría… de Asúa, M. (2016). Conversación telefónica…
```

El arreglo es aceptar la partícula exigiendo que el apellido que sigue sí abra
con mayúscula. **Medido**: T0008 351 → 361, de los cuales uno es el `van Dijk`
correcto y **diez son cortes equivocados**. Ese borde de más alcanza para dar
vuelta el arbitraje: T0008 abandona la ruta
`hanging_indent_start_margin+local_bibliographic_evidence` (350 registros
limpios) y cae en la ruta cruda, que expone justo el defecto P6.

### P6 — Margen en `author+bare_year+local_geometry` (`biblioref_v0_4.py:695`)

Acepta como borde cualquier línea con forma de «algo, número, año» cuando
`hanging_indent_detected` es verdadero, sin mirar el x0 de la línea — y ese flag
es del **documento**, no de la línea.

```diff
-                if effective_layout.hanging_indent_detected or is_paragraph_start(index, effective_lines, paragraph_profile):
+                at_margin = abs(line.x0 - effective_layout.start_margin) <= effective_layout.start_margin_tolerance
+                if at_margin and (effective_layout.hanging_indent_detected or is_paragraph_start(index, effective_lines, paragraph_profile)):
                     start, evidence = True, "author+bare_year+local_geometry"
```

Explica 304 de los 545 registros que arrancan a la derecha del margen modal.
**Medido solo**: elimina 249 registros espurios (T0029 −84, T0071 −49, T0030 −33,
T0068 −17, T0116 −12) y las fusiones son correctas:

```
antes   «Ābele, L., Haustein, S., Møller, M., & Zettler, I. (2020). Links between observed and self-»
        «Safety Research , 41 (2), 99–106. https://doi.org/10.1016/j.jsr.2010.02.005»
después «Ābele, L., … (2020). Links between … Safety Research, 41 (2), 99–106. https://doi.org/…»
```

**Medido con P5**: arregla el daño de P5 en T0008 (361 → 351, con el `van Dijk`
bien separado) y mejora T0029 (649 → 570). Pero rompe T0017: la tesis pasa de
172 registros limpios con
`hanging_indent_start_margin+local_bibliographic_evidence` a 183 por la ruta
cruda, de los cuales **41 no arrancan como autor** (`60. https://doi.org/…`,
`(2017). Effect of long-term omega 3…`).

### Por qué quedan afuera

El patrón es siempre el mismo y no es de estos parches: **una capa de reparación
gana o pierde el arbitraje según el conteo de la ruta cruda**, así que mejorar la
ruta cruda puede hacer que la reparación —que era mejor— deje de aplicarse. P5
sin P6 rompe T0008; P6 con P5 arregla T0008 y rompe T0017.

Lo correcto es entrar por el arbitraje: entender con qué criterio se elige entre
la ruta estable y cada candidata de reparación, y recién después tomar P5 y P6
juntos. El arnés de 128 documentos ya está para medirlo.

---

## Reproducción

Todo el arnés está en el scratchpad de la sesión:

| Archivo | Qué hace |
|---|---|
| `patch.py` | monkeypatch de `segment_adaptive_layout_zone` (P3 y P6, por separado) |
| `head_patch.py` | P2 |
| `style_patch.py` | P1 |
| `indent_patch.py` | P4 |
| `exp.py` / `exp_all.py` | corre el pipeline sobre las 121 tesis y guarda textos y evidencias |
| `val2.py` | cuenta cuántos `corte_en` de los avisos quedaron resueltos |
| `avisos_clasificados.csv` | los 583 avisos con su clase (real / falso positivo) |

La línea de base reproduce exactamente los conteos del dataset exportado, así que los
deltas son directamente comparables.
