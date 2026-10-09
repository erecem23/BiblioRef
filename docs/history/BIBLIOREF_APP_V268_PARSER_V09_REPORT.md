# BiblioRef v0.9.6 · APP v2.6.8 · Parser v0.9

Fecha de cierre: 2026-09-02.

## Alcance

Parser v0.9 sigue siendo una capa **downstream**. No modifica detección de zonas, segmentación, fronteras ni texto crudo. El extractor sigue siendo BiblioRef v0.9.6 / algoritmo 0.6.2 / motor estable 0.4.5.

Código congelado:

`4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320`

El núcleo de extracción es byte a byte idéntico al de la release de v0.8: los 14 módulos de zonas, segmentación, reparación, rescates y auditoría verifican el mismo SHA-256 (`EXTRACTION_CORE_NONREGRESSION_V09_SHA256.json`).

## El diagnóstico que motiva la versión

El informe de v0.8 dejó la normalización de revista como cuello de botella principal, con 0/8 fuzzy>=.90 en el stress set pese a 87,5% de cobertura. Al abrir esas ocho referencias una por una, la causa dominante no está en la ruta de revista.

En `ALMEIDA, R. S.; BOURLIATAUX-LAJOINIE, S.; MARTINS, M. Satisfaction measurement instruments...`, el bloque de autores se cortaba en `ALMEIDA, R.`. El resto de la lista de autores pasaba a ser el título, el título real pasaba a ser la revista y el nombre de la revista quedaba fuera del campo. Cuatro de los ocho fallos de revista se originan así, y con ellos caen autor, autores y título de la misma referencia.

La causa concreta es que v0.8 localiza el final del bloque de autores buscando el primer punto seguido de espacio. Un nombre de pila escrito con más de una inicial contiene ese punto antes de que el bloque termine. En un corpus ABNT eso no es un caso raro.

## Familias implementadas

Bloque de autores. La frontera deja de buscar un punto y pasa a recorrer la gramática del bloque: apellido, parte de nombre de pila, separador. Cubre nombres de pila con varias iniciales (`ALMEIDA, R. S.`), iniciales sin punto final antes de `;` (`AGUIAR, W. M. J; OZELLA, S.`), partículas (`ALMEIDA, S. L. de`, `COSTA, F. J da`), pérdida de puntuación entre autores (`ALBUQUERQUE, Else de F. MENEZES Marilda`), listas con `&` y coma (`BROWNE, M. W., & CUDECK, R.`), `et al.` como marcador de truncamiento y no como nombre, y apellido seguido de iniciales sin coma (`DONABEDIAN A.`).

La ambigüedad real del bloque es una palabra en mayúscula inicial que sigue a un punto de abreviatura. Es un nombre de pila más en `BICUDO, Maria A. Viggiani; ...` y es la primera palabra del título en `ALBUQUERQUE, P. P. Autogestão. In: ...`. Lo que las separa no es la palabra sino lo que cierra la secuencia: un separador de lista de autores la mantiene dentro del bloque, cualquier otra cosa lo cierra en el punto.

Contenedor de fuente. La clasificación de la fuente considera ahora los metadatos de periódico que aparecen **después** del año de publicación (`... Quarterly, 1966, 44: 166-206`) y no sólo los que aparecen antes. Esto no exige ampliar el vocabulario de revistas.

Candidato de revista. Se corta antes de metadatos compactos escritos sin `v.`/`n.`/`p.` (`31(1):11-25`, `44: 166-206`, `e25314`); se elimina la entidad editora pegada al nombre (`..., Institute of Electrical and Electronics Engineers (IEEE), v. 128`); se elimina el lugar de publicación pegado con coma o con punto (`Arq Catarinense de Medicina. Santa Catarina`); y se deja de eliminar un segmento final que es en sí mismo parte del nombre de la revista, que era lo que convertía `Trabalho, Educação e Saúde` en `Trabalho`.

Rescate de revista APA. Cuando la ruta base no produce revista porque el bloque de volumen y número no es puramente numérico (`7(MAR)`, `43, e25314`, `19.`, `(online)`), una ruta nueva la recupera. Está condicionada a evidencia explícita de publicación periódica y a la ausencia de evidencia de monografía, capítulo o tesis, de modo que sólo puede agregar fuente donde antes había abstención.

## Desarrollo y regresión

Las 190 referencias de todos los gold ya consumidos hasta v0.8 son material de desarrollo y regresión de v0.9. No son validación externa.

| campo | v0.8 | v0.9 | mejoras | regresiones |
|---|---:|---:|---:|---:|
| autor | 92,63 % | 99,47 % | 13 | 0 |
| autores | 86,25 % | 98,75 % | 10 | 0 |
| año | 99,47 % | 99,47 % | 0 | 0 |
| título exacto | 87,89 % | 94,74 % | | |
| título fuzzy>=.90 | 92,11 % | 97,89 % | 11 | 0 |
| tipo | 93,68 % | 95,26 % | 3 | 0 |
| revista exacta | 78,38 % | 98,65 % | | |
| revista fuzzy>=.90 | 79,73 % | 100 % | 15 | 0 |
| cobertura de revista | 93,24 % | 100 % | | |
| editorial | 86,79 % | 86,79 % | 0 | 0 |
| DOI | 100 % | 100 % | 0 | 0 |

Sobre el stress set de 20 referencias que motivó la versión, revista fuzzy>=.90 pasa de 0 % a 100 % y autor de 65 % a 100 %. Ese conjunto fue el material de diagnóstico, así que la cifra describe el ajuste al corpus de desarrollo y no la generalización.

## Barrido histórico

El corpus analítico de 29.027 filas se usó como control estructural, no como estimación de efectividad. Su columna `gold_author` sigue otra convención de autor y no sirve para puntuar; `target_journal` y `target_type_v2` sólo se usan para orientar las filas que cambian.

- filas modificadas: **361 de 29.027 (1,24 %)**;
- revista: **360 agregadas, 0 eliminadas, 0 modificadas**;
- de las 305 agregadas con etiqueta curada, 264 coinciden exactamente y ninguna se aleja de la etiqueta;
- la ruta ABNT de v0.9 se activa en **1 fila**, y la única diferencia que produce es el título;
- tipo: 229 filas cambian de clase, 185 hacia la etiqueta curada y 25 en contra.

Las 41 revistas agregadas que no coinciden con la etiqueta se revisaron una por una. Treinta y dos son más limpias que la etiqueta, que suele arrastrar volumen y páginas (`Physical Education and Sport, 51(-1), 61-66`) o normalizaciones ortográficas (`Journal Homosexuality` frente a `Journal of Homosexuality`). Cuatro contienen un número de página que ya está incrustado en la cadena cruda (`Computers in Human 213 Behavior`) y no es corregible aguas abajo. Cinco son errores del parser: conservan un resto de título o de metadatos, o recortan de más.

Los 25 cambios de tipo contrarios a la etiqueta son todos `material_web` a `articulo_revista`. Las 25 filas tienen DOI en la cadena cruda y las 25 reciben nombre de revista. La etiqueta curada procede de una versión anterior de este mismo pipeline, que clasificaba como material web toda referencia con URL, así que el recuento no es evidencia de regresión.

## Estado de validación

**Parser v0.9 no tiene validación externa.** Los dos holdouts de v0.8 se abrieron para diagnosticar esta versión y pasaron a desarrollo. Las cifras de arriba describen el corpus contra el que se desarrolló v0.9.

El arnés `evaluate_parser_v09_external_holdout.py` queda listo para un gold nuevo. Recibe la ruta del CSV, registra el SHA-256 del gold y de ambos parsers, ejecuta v0.8 y v0.9 sobre las mismas cadenas y escribe la evaluación pareada y las predicciones por referencia. Las columnas obligatorias son `raw_citation`, `gold_author`, `gold_year`, `gold_title`, `gold_publication_type`, `gold_journal`, `gold_publisher` y `gold_doi`; `gold_authors` es opcional y, si falta, el campo `authors` no se puntúa. El gold debe congelarse y hashearse antes de ejecutar el arnés, y el código no debe tocarse después.

## Familias diagnosticadas y no implementadas

Quedan fuera del alcance elegido para esta versión. Están documentadas porque se observaron en material ya quemado y no pueden volver a contarse como evidencia externa.

1. **Descriptor de grado entre corchetes dentro del título APA.** `... ciclo de vida [Tese de doutorado, Universidade de Brasília, Instituto de Psicologia]` deja el corchete dentro del título y el tipo no llega a `tesis`. Aparece en dos referencias del holdout general de v0.8.
2. **Bloque de autores APA con partículas en minúscula.** `Costa, J. L. dos S., Wall, M. L., & da Paixão, T. T. (2023)` devuelve `Wall, M. L.` como primer autor. La ruta ABNT no interviene porque hay año entre paréntesis, y la reparación tendría que tocar la extracción de autores APA, que es la de mayor superficie sobre el corpus histórico y la peor medida, porque las etiquetas de autor de ese corpus siguen otra convención.
3. **`(Eds.).` antes del año.** `Arthur, N., & McMahon, M. (Eds.). (2019). Contemporary theories...` deja el bloque de editores como título.
4. **Título de tesis cuando el descriptor de grado va después del año.** `ARAÚJO, Eduardo Pucu de. Um estudo sobre Etnografia aplicada ao Design. Pontifícia Universidade Católica do Rio de Janeiro. Rio de Janeiro, 2012. Dissertação.` incorpora la universidad al título.
5. **Números de página incrustados en la cadena cruda.** Cuatro filas del corpus histórico traen el folio dentro del nombre de la revista. Es un problema de capa de texto, no de parser, y corresponde al extractor.

## Integración

- `biblioref/parsing/__init__.py` publica v0.9; v0.8 sigue importable como `parse_reference_v08`.
- APP v2.6.8, sin cambios funcionales de interfaz.
- Batería completa: 473 tests pasan, 3 saltados, 16 subtests.
- `test_parser_v0_9.py` cubre una familia por test; `test_parser_v0_9_freeze.py` fija el hash del código, el del v0.8 heredado, la ausencia de regresiones en la evaluación de desarrollo y el resultado del barrido histórico.
