# BiblioRef v0.9.7 · APP v2.6.8 · Parser v0.9

Fecha de cierre: 2026-09-02.

## Autoridades

| capa | versión |
|---|---|
| `SOFTWARE_VERSION` | **0.9.7** |
| `ALGORITHM_VERSION` | **0.6.3** (era 0.6.2) |
| `BASE_VERSION` | 0.6.1 (sin cambio) |
| `STABLE_ENGINE_VERSION` | 0.4.5 (sin cambio) |
| `ADAPTIVE_ANALYSIS_VERSION` | 0.8.10-shadow23 (sin cambio) |
| `RESCUE_ROUTER_VERSION` | 0.9.4-selective-router3-plausibility (sin cambio) |
| parser downstream | biblioref-parser-v0.9 (sin cambio, `4148701452…`) |
| APP | 2.6.8 (sin cambio) |

`biblioref_v0_2.py` congelado en `8683e68c23773f113b27cb2453b48d7539c1ca9147d470baaf1de306d6d775fa`.

## Alcance

Dos clases de caracteres. Nada más. Los catorce módulos de detección de zonas, segmentación, fronteras, rescates y auditoría son byte a byte idénticos a los de la release v0.9.6 (`EXTRACTION_CORE_NONREGRESSION_V097_SHA256.json`).

### A. Separador de la numeración de capítulo

`_strip_heading_prefix` aceptaba como separador de la numeración jerárquica solamente punto, guión ASCII y dos puntos. Una tesis con bibliografía por capítulo escrita en un procesador de texto trae guión medio: el autocorrector convierte `IV-5-` en `IV–5-`. Con eso, `iv–5-bibliografia.` no coincide con el vocabulario y el capítulo entero deja de existir para el extractor.

La clase de separadores pasa a incluir el bloque Unicode de guiones `U+2010`–`U+2015`. El anclaje no se relaja: el encabezado despojado de prefijo se sigue comparando con `re.fullmatch` contra el vocabulario, que es la condición que v0.9.5 fijó para ampliar el vocabulario de encabezados.

Control negativo verificado: `IV–5-Bibliografía consultada durante el trabajo de campo` sigue sin ser encabezado, `literatura` conserva su texto y `Capitulo V. Anexo I` sigue siendo corte estructural.

### B. Marcador numérico pegado a un guión

```
antes:  ^\s*(?:\[(\d{1,4})\]|\((\d{1,4})\)|(\d{1,4})[\.)])\s+
ahora:  ^\s*(?:\[(\d{1,4})\]|\((\d{1,4})\)|(\d{1,4})[\.)])(?:\s+|\s*[\-‐-―]\s*)
```

El `\s+` exigía espacio después del marcador. Las bibliografías escritas `[1]-Autor`, `[23]- Autor` quedaban invisibles para el diagnóstico de estilo: sobre la zona de prueba, 35 líneas con `numeric_starts` 3 y `numeric_sequence_score` 0,0. El estilo caía en `author_year_comma` y la segmentación cortaba por fronteras autor-año, fusionando entre cuatro y once referencias en cada registro.

Los marcadores que ya se reconocían (`[1] `, `1. `, `(4) `, `1) `) no cambian, y los que no eran marcadores (`p. 241 y referencias allí citadas.`, `[Smith2010] `, prosa) siguen sin serlo.

## No-regresión

**Equivalencia por hash sobre documentos reales.** Dos tesis ajenas al problema, procesadas con v0.9.6 y con v0.9.7:

| documento | páginas | v0.9.6 | v0.9.7 | `records+zones` SHA-256 |
|---|---:|---|---|---|
| tesis de química, bibliografía por capítulo con marcador numérico desnudo | 300 | 10 zonas / 28 registros | 10 zonas / 28 registros | idéntico |
| tesis de humanidades, bibliografía única APA | 449 | 1 zona / 78 registros | 1 zona / 78 registros | idéntico |

**Líneas bibliográficas auténticas de los fixtures.** Las 752 líneas guardadas en `fixtures/*.json`, procedentes de tesis de Helsinki, Birmingham, Waikato, UMS y del catálogo de errores SEDICI-HUM, dan el mismo perfil de estilo (`bracket_key`, 81 arranques numéricos, 12 claves de corchete, 242 autor-año-coma, `numeric_sequence_score` 0,85) y el mismo resultado línea a línea para el valor de marcador, el test de encabezado bibliográfico, el test de corte estructural y el despojado de prefijo, todo verificado por hash.

**Batería completa.** 491 tests pasan, 3 saltados, 16 subtests. Antes de actualizar las cadenas de versión fallaban 30 tests, todos por comparar `"0.9.6"` con `SOFTWARE_VERSION`; ninguno por comportamiento.

## Documento que motivó la versión

Tesis de doctorado en ciencias exactas, 162 páginas, seis bibliografías de capítulo, 147 referencias reales.

| | zonas | registros | recuperación |
|---|---:|---:|---:|
| v0.9.6 | 2 (una falsa) | 5 | 3,4 % |
| v0.9.6 + rescate numérico recomendado | 2 | 25 | 17 % |
| v0.9.7 | 6 (una falsa) | 72 | 49 % |

De los seis capítulos, cinco pasan a detectarse y los cinco se diagnostican como `numeric`. El sexto tiene la capa de texto dañada: el encabezado sale truncado a `III–7-BIBL` y a cada renglón le falta el `[n` inicial. Son 45 referencias que ninguna regla puede reconstruir aguas abajo.

Este documento es ahora corpus de desarrollo y regresión. No puede volver a reportarse como evidencia externa de v0.9.7.

## Lo que v0.9.7 no arregla

El techo del 49 % tiene una causa única y medida: **cada zona se cierra en su primera página**. `_is_structural_stop` trata como corte cualquier línea que empiece por `capitulo`, y el encabezado corrido de la tesis es exactamente eso, repetido entre 8 y 45 veces por capítulo a una `y` relativa constante de 0,042 a 0,054. La bibliografía del capítulo I ocupa las páginas 36 a 38 y la zona se cierra al llegar al encabezado corrido de la 37.

La señal ya está calculada: `adaptive_shadow.input_hygiene.decorations.confirmed` lista ese encabezado como decoración corrida confirmada de banda superior con `relative_y_spread` 0,0. `_is_structural_stop` no la consulta. Conectarla es el mismo tipo de cambio que fue v0.9.4, y en una sonda lleva el documento a 125 registros con el capítulo I exacto en 48. Queda fuera de v0.9.7 porque toca la lógica de cierre de zona y porque empeora un falso positivo conocido: la palabra `bibliografía.` sola al final de una oración de prosa abre hoy una zona falsa de una página y con ese cambio crece a once. Las dos cosas deben resolverse en el mismo release.

Efecto colateral que conviene tener presente: con 72 registros el documento ya no dispara `implausible_reference_yield`, porque 44 referencias por 100 páginas está muy por encima del umbral de 8. Sigue quedando en `needs_review` por el informe de cobertura y por la recomendación del router, pero el gate de rendimiento ya no ve el truncamiento.

## Familias abiertas observadas en otras dos tesis

Ninguna se implementó. Ambos documentos ya fueron inspeccionados, así que son material de desarrollo.

1. **Marcador numérico desnudo.** Tesis de química, 300 páginas, 10 bibliografías de capítulo, unas 389 referencias reales, 28 extraídas. Las referencias se escriben `1  E. D. Campbell, J. Amer. Chem. Soc., 1900, 22(5), 307.`: número, dos espacios, sin punto ni corchete. `NUMERIC_MARKER_RX` exige puntuación después del número, así que el estilo cae en `author_year_bare`. No basta con agregar el número desnudo a la clase: en esa misma página hay renglones de continuación que empiezan con `53, 2139.` y con `Z7.4.1.`. La evidencia que sí separa unos de otros es geométrica y está disponible: los arranques están en `x0` 92,2 y las continuaciones en 106,4, con sangría francesa. Corresponde a la familia `marker_only_numeric_resegmentation` ya prevista en la guía del proyecto.
2. **Marca de autor repetido escrita con puntos.** Tesis de humanidades, 449 páginas. La convención `..................(1995).` para «mismo autor que arriba» no se reconoce: `REPEATED_AUTHOR_MARKER_RX` y sus cuatro gemelas aceptan `___`, `---`, `–––` y glifos de uso privado, pero no puntos ni `…`. Además la regla que usa el marcador está condicionada a `style.style == "author_year_bare"` y esta zona se diagnostica `author_year_comma`, así que ampliar el alfabeto no alcanza por sí solo. Con las dos partes, una sonda lleva el documento de 78 a 103 registros, con 25 arranques nuevos reconocidos como `repeated_author_mark+start_margin`.

## Rendimiento

Se midió sobre la tesis de química, 300 páginas y 18 MB, que es la más pesada de las tres:

- pipeline completo: **13,1 s**;
- guardia de primera referencia: 0,8 s;
- informe de cobertura: 1,0 s;
- renderizado de una página para el visor: 0,13 s.

El costo se reparte entre la extracción del layout (7,4 s, dominada por `get_text` de PyMuPDF sobre 300 páginas) y el router de rescates (5,7 s). No hay ningún punto patológico.

El documento declara 3.962 objetos de imagen por página, casi 1,19 millones de referencias en total, porque el diccionario de recursos es compartido por todo el árbol de páginas. Eso hace lentísima cualquier enumeración de imágenes, pero **BiblioRef no enumera imágenes en ningún momento**: sólo llama a `get_pixmap` para el visor, y eso cuesta 0,13 s por página.
