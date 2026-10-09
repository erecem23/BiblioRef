# Algoritmo 0.6.10 — cuatro condiciones del núcleo de extracción

Fecha: 2026-09-20 · Software v0.9.10-rc2 · Algoritmo 0.6.8 → **0.6.10**
Declaración: `EXTRACTION_CORE_NONREGRESSION_V0610_SHA256.json`
Diagnóstico de origen: `BIBLIOREF_DATASET_TESIS_PSICOLOGIA_DIAGNOSTICO_V0_1.md`

---

## Resultado

| | 0.6.8 | 0.6.10 |
|---|---|---|
| Documentos | 128 | 128 |
| Registros | 32.993 | **34.421 (+1.428)** |
| Documentos idénticos byte a byte | — | **109 / 128** |
| Documentos modificados | — | 19, **ninguno con menos registros** |

`tests_core`: 356 tests, 0 fallas. Los 6 errores de importación son de módulos que
piden `pytest`, que no está instalado en el entorno; son anteriores a este cambio.

Las 19 tesis que se mueven:

| Tesis | 0.6.8 | 0.6.10 | Δ | Causa |
|---|---|---|---|---|
| T0016 | 55 | 481 | +426 | estilo de marcador sin apoyo (`[on-line] en:`) |
| T0084 | 0 | 332 | +332 | folio pegado (`5. Referencias bibliográficas 138 .`) |
| T0025 | 0 | 269 | +269 | folio pegado (`Referencias bibliográficas 151`) |
| T0070 | 136 | 228 | +92 | año en la línea 2 |
| T0091 | 0 | 81 | +81 | vocabulario (`Referencias generales`) |
| T0073 | 273 | 321 | +48 | año en la línea 2 |
| T0126 | 77 | 117 | +40 | año en la línea 2 |
| T0117 | 185 | 219 | +34 | sangría de primera línea |
| T0102 | 126 | 152 | +26 | año en la línea 2 |
| T0034 | 111 | 135 | +24 | año en la línea 2 |
| T0109 | 422 | 434 | +12 | año en la línea 2 |
| T0085 | 139 | 147 | +8 | año en la línea 2 |
| T0110 | 51 | 59 | +8 | vocabulario (`Referencias Generales`) |
| T0104 | 3 | 26 | +23 | estilo de marcador sin apoyo (`[Recuperado]`) |
| T0112 | 200 | 204 | +4 | año en la línea 2 |
| T0026 | 8 | 9 | +1 | año en la línea 2 |
| T0103 | 106 | 106 | 0 | un registro reorganizado |
| T0120 | 185 | 185 | 0 | uniones y cortes que se compensan |
| T0045 | 223 | 223 | 0 | una pegada resuelta y otra nueva |

T0120 vale mirarlo porque el conteo no se movió y el contenido sí: se unieron
referencias que estaban partidas en el salto de línea (`Acosta S.J.R… Revista /
Habanera de Ciencias Médicas`) y se separaron registros que estaban pegados
(`Marshakova I. V. (1973)… Mazzanti, F. (2019)`, `Código Civil y Comercial`,
`Montero, A. S. (2011)`). Las dos correcciones se compensaron.

## Los cuatro cambios

### 1. Dos líneas entre corchetes vacían una tesis entera (`biblioref_v0_2.py`)

`diagnose_style` activaba un estilo de marcador con dos ocurrencias, sin comparar
contra nada. En T0016 esas dos ocurrencias son `[on-line] en:` contra **99 líneas**
con forma `Apellido, N. (año)`: el estilo quedaba en `bracket_key`, el margen se
calculaba sobre esas dos líneas —que son continuaciones— y todas las referencias
quedaban fuera de tolerancia. T0104 es lo mismo con `[Recuperado] 15 de junio de
2015 de la World Wide Web:`, tres líneas sobre 69.

Con menos de cuatro líneas marcadas, un marcador pierde contra una alternativa que
tenga al menos cinco veces más evidencia. T0016 queda con 481 referencias que van de
`Abbagnano, N. (1978)` a `Zysman, S. (2004)`, mediana de 150 caracteres y 4 registros
cortos; eso cierra además sus 57 avisos `falta_de_verdad`, el 38 % del corpus.

El umbral es conservador a propósito: con un piso proporcional al número de líneas
T0104 llega a 286 en vez de 26, pero T0056 se cae de 225 a 37 porque el cambio de
estilo de una zona chica hace que el arbitraje abandone las zonas con encabezado.

### 2. El folio impreso pegado al encabezado (`biblioref_v0_2.py`, `biblioref_v0_3.py`)

El folio cae en la misma banda vertical que el título de la sección y
`extract_layout_lines` los fusiona. `_is_ref_heading_normalized` está anclado con
`re.fullmatch`, así que `Referencias bibliográficas 151` no matchea y la tesis
entera queda sin zona: T0025 (315 pp.), T0084 (299 pp.) y T0091 (206 pp.) daban 0.

Sacar el numeral sólo es seguro con dos guardarraíles, porque la misma cadena está
en el índice:

1. **puntos conductores** — `……` o `. . . .` es una entrada de índice;
2. **el numeral no apunta hacia adelante** — en el índice el número es la página
   destino (304 en la página 9), en un encabezado es el folio de la página que se
   está leyendo (151 en la página 290).

Sin el segundo guardarraíl, el `BIBLIOGRAFÍA: ……… 304` de la página 9 de T0016 abre
una zona fantasma y le corta la zona real de 33 a 16 páginas.

Aparte, `referencias` pasó a admitir calificador (`generales`, `documentales`,
`finales`) como `bibliografia` ya hacía.

### 3. La cancelación del «año en la línea 2» (`biblioref_v0_4.py`)

La regla cancelaba un borde que **ya tenía margen de inicio y fecha entre
paréntesis**, sólo porque la línea anterior empieza con mayúscula y no tiene año.
Esa línea anterior es, casi siempre, la continuación de la referencia previa, que
abre con el nombre de la revista: `Sciences,`, `Neurobiology,`, `Journal of…`.

`_hanging_indent_opens_new_record` no cancela cuando la geometría ya distingue el
registro: hay sangría francesa en el documento, la línea candidata está en el
margen de inicio y la anterior está sangrada a la derecha. Las tres condiciones
juntas, ninguna sola.

### 4. El apoyo geométrico en sangría de primera línea (`biblioref_v0_4.py`)

`_weak_boundary_supported` pedía que la línea siguiente estuviera **más a la
derecha**. En T0117 el registro arranca a 120.5 y las continuaciones caen a 85.1:
el corrimiento va hacia la izquierda, el apoyo se negaba siempre y se descartaban
bordes correctos con evidencia `author_initial+start_margin`.

`_reverse_indent_regime` mira la nube de x0 de la zona y decide en qué dirección
buscar el apoyo.

## El arnés

`tools/extraction_corpus_equivalence.py` corre el pipeline sobre los documentos del
workspace y guarda, por tesis, el conteo de registros y el sha256 del texto de
todos ellos. La línea de base del algoritmo 0.6.8 está en
`EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json`: 128 documentos, 16 minutos.

```bash
python tools/extraction_corpus_equivalence.py --out /tmp/nuevo.json \
    --baseline EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json
```

Reemplaza a `EXTRACTION_EQUIVALENCE_V097.json`, que probaba la equivalencia con dos
documentos. Para iterar sobre un cambio alcanza con `--ids` sobre las tesis que
debería tocar más algunas de control, que son un par de minutos.

## Lo que no entró

**P5 (apellidos con partícula minúscula) y P6 (margen en
`author+bare_year+local_geometry`)** están correctos y medidos, y quedaron afuera
porque están acoplados entre sí y al arbitraje de rutas:

- P5 solo da T0008 351 → 361: uno es el `van Dijk` correcto y diez son cortes
  equivocados. Ese borde de más da vuelta el arbitraje y T0008 abandona
  `hanging_indent_start_margin+local_bibliographic_evidence` por la ruta cruda,
  que expone justo el defecto P6.
- P6 arregla eso (T0008 vuelve a 351 con el `van Dijk` bien separado, T0029 mejora
  649 → 570) pero rompe T0017: pasa de 172 registros limpios a 183, de los cuales
  41 no arrancan como autor.

El patrón no es de estos parches: **una capa de reparación gana o pierde el
arbitraje según el conteo de la ruta cruda**, así que mejorar la ruta cruda puede
hacer que la reparación —que era mejor— deje de aplicarse. Entran juntos después
de mirar el arbitraje, que ahora se puede medir con el arnés.

### Lo que se aprendió midiendo P6

Al probar P6 apareció algo que cambia su lectura. P6 no *saca* los bordes fuera de
margen: los **redistribuye**. Impide que dispare `author+bare_year+local_geometry`,
y las mismas líneas abren registro igual por `numeric_marker` (sobre cosas como
`60. https://doi.org/…`) y por `inherited_author+date_only_entry`. En T0017 la base
pasa a tener 41 de 183 arranques fuera del margen, y ahí la reparación de sangría
francesa se niega con razón: `base_start_margin_support` cae a 0.776 contra un piso
de 0.90, o sea que la base ya no parece una línea de base de sangría francesa.

**P6 no es un parche suelto, es el primero de un grupo.** Hay al menos tres reglas
que abren registro sin mirar el margen, y arreglar una deja a las otras haciendo el
mismo daño. La tanda correcta es las tres juntas más el arreglo del arbitraje.
