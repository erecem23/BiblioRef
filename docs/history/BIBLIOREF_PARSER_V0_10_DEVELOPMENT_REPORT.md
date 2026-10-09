# BiblioRef v0.9.7 · APP v2.6.9 · Parser v0.10

Fecha de cierre: 2026-09-02.

## Alcance

Parser v0.10 es capa **downstream**. No modifica detección de zonas, segmentación, fronteras ni texto crudo. El extractor sigue siendo v0.9.7 / algoritmo 0.6.3 / motor estable 0.4.5, y `biblioref_v0_2.py` conserva el hash congelado de v0.9.7.

Código congelado:

`56993eed5a0c032e9c52495eb721a2cc8ecde73ca3ad0cefd9d1fb0d152d17f2`

Dos familias, las dos observadas sobre una tesis de educación de 374 páginas con 310 referencias, y las dos sobre formas de metadatos habituales en la edición iberoamericana que los patrones heredados del trabajo de léxicos de v0.2 no contemplan.

## Familia 1 — número de revista sin volumen

`Comunicar, (38), 51-58`. `Revista Cepal, (119), 89-107`. `Edutec. Revista electrónica de tecnología educativa, (7), 1-21`.

Todos los patrones de metadatos de la cadena esperan un dígito de volumen antes del paréntesis del número, así que la fuente nunca se localizaba. Medido sobre los 310 registros:

| forma de los metadatos | registros | revista recuperada |
|---|---:|---:|
| `, 20(40), 127-135` (con volumen) | 94 | 92 (97,9 %) |
| `, (7), 1-21` (sólo número) | 44 | **0** |

Conviene registrar por qué la hipótesis inicial era otra. Parecía que el problema era el punto interno de `Edutec. Revista electrónica…`, es decir que el parser cortaba el nombre en dos oraciones. No es así: con volumen, el mismo nombre se recupera entero, punto incluido. El bloqueo era exclusivamente el volumen ausente.

La ruta nueva exige número de página o de artículo después del paréntesis, y limita el número a tres dígitos, de modo que un año entre paréntesis no puede leerse como número de revista. Se abstiene ante capítulo, tesis, congreso, documento legal y ante los indicios de monografía de v0.2.

Sub-caso resuelto en el mismo trayecto: `Psicothema, 17, (1), 39-45`, donde el volumen va entre el nombre y el número separado por coma. El nombre de una revista no termina en un número desnudo, así que un par coma-número final es metadato y se recorta.

## Familia 2 — imprenta después de lugar y país

`Santiago de Chile, Chile: Divergente.` La editorial cierra la referencia, pero sólo se aceptaba cuando figuraba en el léxico de editoriales o traía una palabra de forma como `Press`, `Editorial` o `Ediciones`. Editoriales con nombre institucional o inventado quedaban fuera: `UNAE`, `Divergente`, `Godot`, `ZEMOS98`, `Outliers School`, `Fundación AUNA`, `Ministerio de Educación de España`, `Cultura Acadêmica`, `La Cebra`, `World Health Organization`.

Las 24 editoriales faltantes de la tesis tienen exactamente la misma forma. La evidencia que vuelve seguro el segmento no es la imprenta sino su izquierda: **un nombre de país de una lista cerrada inmediatamente antes de los dos puntos, al final de la referencia**. La lista de países es cerrada y estable; la de editoriales, no. El número de página que el extractor deja pegado (`… Divergente. [273]`) se descarta antes de aplicar la regla.

## Corrección derivada

Al levantar el gate que impedía la ruta de revista cuando ya había editorial, apareció una corrección que no estaba buscada. En `Revista Iberoamericana de Educación, (20), 217-225` la versión anterior había tomado `Iberoamericana` como editorial y clasificado la referencia como libro. Ese «editorial» no es evidencia de monografía: es el propio nombre de la revista mal partido.

El gate quedó estructural en vez de binario: la ruta se abstiene si la editorial previa **no** aparece dentro del candidato a revista, y procede si sí aparece, en cuyo caso limpia el campo. Las 13 reescrituras de editorial observadas —5 en la tesis y 8 en el corpus histórico— son todas de este tipo: `Feminaria` → revista `Feminaria`, `Docencia` → revista `Ciencia, docencia y tecnología`, `CLAD` → revista `Revista del CLAD Reforma y Democracia`.

## Corpus objetivo

310 referencias, material de desarrollo.

| | v0.9 | v0.10 |
|---|---:|---:|
| con revista | 103 | **142** |
| con editorial | 101 | **125** |
| `sin_clasificar` | 42 | **8** |
| revistas reescritas | | 0 |
| editoriales reescritas | | 5, todas correcciones |

Quedan 10 referencias con metadatos de número sin revista. Dos son consecuencia de fallas del extractor: un registro fusionado y un fragmento de continuación suelto. Las otras ocho fallan en la separación título/revista, que es otra familia.

## Regresión

**Corpus de desarrollo de parsers (190 referencias, todos los gold quemados hasta v0.8):** salida idéntica campo por campo. 0 mejoras y 0 regresiones en autor, autores, año, título, revista, tipo, editorial y DOI. Ninguna de esas referencias, brasileñas ABNT y APA, usa la forma de número sin volumen.

**Barrido estructural del corpus histórico (29.027 filas):**

- filas modificadas: **221 (0,76 %)**;
- revista: **165 agregadas, 0 eliminadas, 0 modificadas**;
- de las agregadas con etiqueta curada, **87 coinciden y ninguna se aleja** de la etiqueta;
- editorial: 64 filas cambian, 56 son altas y 8 son las correcciones descritas arriba;
- tipo: 145 filas cambian, 113 hacia la etiqueta curada y 8 en contra.

Los 8 movimientos de tipo contrarios a la etiqueta son todos `material_web` a `articulo_revista` sobre referencias con DOI y nombre de revista. La etiqueta curada procede de una versión anterior de este mismo pipeline, que clasificaba como material web toda referencia con URL.

**Batería completa:** 510 tests pasan, 3 saltados, 16 subtests.

## Estado de validación

**Parser v0.10 no tiene validación externa.** La tesis de educación se inspeccionó para diagnosticar estas dos familias, así que es corpus de desarrollo y regresión. El arnés `evaluate_parser_v09_external_holdout.py` sigue sirviendo: recibe un gold congelado y hasheado y compara dos versiones sobre las mismas cadenas.

## Familias abiertas del parser

1. **Separación título/revista sin metadatos fuertes.** Ocho referencias de la tesis conservan metadatos de número y siguen sin revista porque el corte entre título y nombre de revista no alcanza el umbral de puntuación.
2. **Bloque de autores APA con partículas en minúscula.** `Costa, J. L. dos S., Wall, M. L., & da Paixão, T. T. (2023)` devuelve `Wall, M. L.` como primer autor. Diagnosticada en v0.9 y todavía abierta.
3. **Descriptor de grado entre corchetes dentro del título APA** y **`(Eds.).` antes del año**, ambas heredadas del informe de v0.9.
