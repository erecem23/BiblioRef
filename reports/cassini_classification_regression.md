# Control estable de clasificación: lista APA con sangría francesa (T0150, 59 referencias)

**Fecha:** 2026-09-23 · **Versión de partida:** algoritmo 0.6.19, parser 0.12.7 · **Versión nueva:** algoritmo 0.6.19 (sin cambios), parser 0.12.8

**Fuente:** `BIBLIOREF_CASSINI_CLASIFICACION_PLAN_CLAUDE.md` y la exportación `dataset_practia_ca.zip`.

**Estatus:** la extracción de esta tesis ya era correcta. Queda en el benchmark como `X_CASSINI` (`stable_control_apa_hanging_indent`): caso de desarrollo/regresión, no held-out. No se tocó el detector de zona ni el segmentador.

## 1. Cómo clasifica hoy BiblioRef

El tipo sale de una cadena de capas (`biblioref/parsing/v12_*.py`), cada una sobre la anterior:

- La base heredada (v11/v12) decide por señales léxicas: revista con número, editorial, URL y palabras de evento.
- Las capas 12.1 a 12.7 corrigen conflictos puntuales:
  - informes institucionales;
  - capítulos con «, en / . En» y rol de editor o páginas;
  - `tesis` solo con evidencia fuera del título;
  - `material_inedito`;
  - revista con número y páginas.
- Cada corrección deja su regla en `parser_notes` y el tipo anterior en `type_candidates`. Esa es la trazabilidad que ya existía, y la regla nueva se registra ahí mismo (`v128_…`).

**Qué fallaba, y por qué:**

| patrón | causa técnica |
|---|---|
| **Decretos como `articulo_revista`** | «Boletín Oficial» coincide con la señal de serie «Boletín» de la capa 12.5. La regla legal de los parsers viejos (v02/v03) nunca llegó a la cadena moderna |
| **Resoluciones `sin_clasificar`** | Ninguna capa moderna reconoce la norma cuando va en el lugar del título: «(1995, 28 de diciembre). Resolución n.º 1956.» |
| **Reglamento y leyes con URL como `material_web`** | La URL se usaba como tipo y no como medio de acceso. En el corpus, además, 7 leyes quedaban como `conference_paper` porque las firma el «Honorable **Congreso** de la Nación» |
| **Capítulos como `libro`** | El contenedor de la capa 12.6 exige «. En» o «, en». En estos casos el «En» sigue a un «?» del título («¿…fragmentario? En E. …») o el título perdió el punto («…cualitativos En I. Vasilachis…»). Además, el patrón de nombres de editores no admitía partículas («de Giardino», «De la Garza») |
| **Informe institucional como `libro`** | La capa 12.1 solo mira títulos que *empiezan* con «Informe/Estadísticas…», y su lista de organismos no incluye «Dirección», «Secretaría», «Observatorio»… |
| **Nota de agencia de noticias como `libro`** | Nada distinguía una pieza fechada con día y mes, publicada por un medio y leída en una URL |

## 2. Qué cambió (parser 0.12.8, `biblioref/parsing/v12_8.py`)

Una sola capa nueva y un solo punto de decisión (`_retype`), con prioridad explícita: **norma → capítulo → informe de organismo → pieza web fechada**. Las señales secundarias (URL, «Boletín», fecha con día) nunca desplazan a una señal documental fuerte.

| regla (`parser_notes`) | señal fuerte | salvaguardas |
|---|---|---|
| `v128_legal_norm_in_author_slot` / `_in_title_slot` | «Decreto / Ley / Resolución / Disposición / Ordenanza / DNU + número» en el lugar del autor o del título, incluso con sigla («Resolución CFE N° 188/12») | Nunca si hay número de volumen y páginas, «pp.» o DOI, que es un artículo *sobre* la ley. Nunca sobre `tesis` ni `capitulo_libro` |
| `v128_legal_code_or_regulation_title` | Título que empieza con «Reglamento / Estatuto / Código / Constitución» | Solo con autor institucional o sin autor: «Bleichmar, S. Estatuto de lo histórico…» y «Código… comentado» siguen siendo libros |
| `v128_legal_official_gazette` | «Boletín / Diario / Registro Oficial» junto a una norma numerada | — |
| `v128_chapter_container_after_question_or_missing_period` | «En» después de «?», «!» o de una palabra en minúscula | El contenedor tiene que empezar con nombres de editores (con partículas) **y** llevar rol de editor o rango de páginas. No aplica si hay marcas de revista |
| `v128_public_body_data_report` | Autor que es un organismo público («Dirección, Secretaría, Ministerio, Instituto Nacional, Observatorio, INDEC, UNESCO…») y un título con datos («indicadores, estadísticas, censo, encuesta nacional, relevamiento, informe») | Solo sobre `libro` o `sin_clasificar` |
| `v128_dated_news_piece_online` | Fecha con día y mes + medio de prensa («Agencia de Noticias, Diario, Periódico…») + URL | Solo sobre `libro` o `sin_clasificar`. Una ponencia fechada sigue siendo ponencia |

**Medio de acceso aparte del tipo:** el campo nuevo `has_url` registra si la referencia se lee en una URL. Una norma puede ser `documento_legal` con `has_url = true`.

**Taxonomía:** no hizo falta ninguna categoría nueva. Ya existían `documento_legal`, `informe_documento`, `documento_guia_manual` y `material_inedito`. Inconsistencia encontrada y corregida: la ficha de referencia y el diálogo «corregir tipo» no ofrecían «Documento legal» ni «Guía o manual» (`static/project-reference-sheet.js`, `static/review-problems.js`). Queda documentado que la base heredada `legacy.py` usa otros nombres («conferencia», «capitulo») que las capas modernas reescriben.

## 3. Cassini antes / después

Tipo esperado asignado a mano sobre las 59 referencias. Se listan las que cambian o no terminan correctas; las otras 48 ya estaban bien y siguen igual.

| # | referencia | anterior | nuevo | esperado | regla | ¿correcto? |
|---|---|---|---|---|---|---|
| 22 | Barrios (2020, 12 de noviembre)… Agencia de Noticias… http… | libro | material_web | material_web | `v128_dated_news_piece_online` | ✓ |
| 33 | Centro Nacional de Documentación… (1908). Reglamento para las Escuelas… http… | material_web | documento_legal | documento_legal | `v128_legal_code_or_regulation_title` | ✓ |
| 34 | Chernobilsky (2009)… cualitativos En I. Vasilachis de Giardino (Coord.)… (pp. 239-271) | libro | capitulo_libro | capitulo_libro | `v128_chapter_…` | ✓ |
| 39 | De la Garza Toledo et al. (2010)… ¿…fragmentario? En E. De la Garza… (pp. 9-42) | libro | capitulo_libro | capitulo_libro | `v128_chapter_…` | ✓ |
| 41 | Decreto 297/2020… Boletín Oficial | articulo_revista | documento_legal | documento_legal | `v128_legal_norm_in_author_slot` | ✓ |
| 42 | Decreto 520/2020… Boletín Oficial | articulo_revista | documento_legal | documento_legal | `v128_legal_norm_in_author_slot` | ✓ |
| 55 | Dessors, G. B. (1998)… salud En D. Dessors… (pp. 24-79) | libro | capitulo_libro | capitulo_libro | `v128_chapter_…` | ✓ |
| 57 | Dirección General de Cultura y Educación (2019). El estado de la escuela. Datos e indicadores | libro | informe_documento | informe_documento | `v128_public_body_data_report` | ✓ |
| 58 | Dirección General… (1995, 28 de diciembre). Resolución n.º 1956. | sin_clasificar | documento_legal | documento_legal | `v128_legal_norm_in_title_slot` | ✓ |
| 59 | Dirección General… (2009, 1 de diciembre). Resolución n.º 3828, | sin_clasificar | documento_legal | documento_legal | `v128_legal_norm_in_title_slot` | ✓ |
| 18 | Asociación del magisterio… Salta (2017). La historia de AMET… Prensa AMET | sin_clasificar | sin_clasificar | material_web o sin_clasificar | — | — (ambiguo: sin URL ni editorial) |

| | correctas | incorrectas | sin clasificar |
|---|---|---|---|
| antes (0.12.7) | 48 | 8 | 3 |
| después (0.12.8) | **58** | **0** | **1** |

En Chernobilsky y Dessors el rol de editor estaba presente: lo que fallaba era el «En» sin punto antes, además de las partículas del apellido del editor. Davezies, Dejours y Dessors-Molinier ya eran capítulos y siguen así.

## 4. Regresión

**Estructura (sin cambios en el core, algoritmo 0.6.19):**

| caso | registros | zona | cambios |
|---|---|---|---|
| Cassini | 59 | 390–395 | textos idénticos a la exportación, 0 sin autor |
| Candelero | 151 | 149–155 | idéntico a 0.6.19 |
| Russo | 181 | 292–304 | idéntico |
| S08, S36 (controles estables) | 135, 299 | — | idénticos |

**Parser sobre el corpus (40.122 referencias, 149 tesis + Russo):** cambian **130** tipos. Russo y Candelero no cambian ninguno. Los 130 se revisaron por familia:

| cambio | n | revisión |
|---|---|---|
| libro → capitulo_libro | 54 | Los 54 son capítulos con «¿…? En X (Ed.)… (pp.)» |
| material_web → documento_legal | 25 | Leyes de infoleg o impo, códigos de ética y el Código Civil con URL |
| libro → informe_documento | 16 | Censos, anuarios estadísticos, encuestas nacionales e indicadores de organismos |
| sin_clasificar → documento_legal | 9 | Códigos de ética, constituciones, reglamentos y leyes |
| conference_paper → documento_legal | 7 | Leyes firmadas por el «Honorable Congreso de la Nación» |
| libro → documento_legal | 5 | Leyes, códigos y una resolución |
| informe_documento → documento_legal | 5 | Constitución de la OMS, Código Civil |
| sin_clasificar → capitulo_libro | 4 | Capítulos |
| sin_clasificar → informe_documento | 3 | Censos y encuesta nacional |
| articulo_revista → documento_legal | 2 | Decreto en el Boletín Oficial; resolución publicada en una gaceta |

Durante la revisión aparecieron 4 conversiones incorrectas y se corrigieron antes de cerrar con la salvaguarda de autor personal. Las tres primeras tienen test propio; la cuarta queda cubierta por la misma regla:

- «Estatuto de lo histórico en psicoanálisis»;
- «Constitución de subjetividades…»;
- «Código Civil… comentado»;
- «Código Penal argentino. Zavalía».

Después de esa corrección no quedan conversiones incorrectas identificadas.

**Tests:**

- `test_parser_v0_12_8.py`: 25 casos, uno por fixture obligatorio más las salvaguardas. Sobre los 21 casos iniciales, con 0.12.7 fallaban los 12 que describen los errores y pasaban los 9 controles. Los 4 agregados después cubren las salvaguardas de «Estatuto / Código / Constitución».
- Suite de la raíz: 828 aprobados. Se excluyen dos fallos previos que no tienen que ver con este cambio:
  - `test_current_field_test_state.py`, modificación local que espera el algoritmo 0.6.13;
  - la reproducción de OpenAlex, que necesita el `bash` de WSL.
- `tests_core`: 560 aprobados.

## 5. Lo que queda

- **«Prensa AMET» (Cassini #18):** sin URL ni editorial, no hay evidencia suficiente para asignar tipo, así que queda `sin_clasificar` a propósito.
- **Pieza web fechada:** la regla solo se ejerció en Cassini, porque en el corpus no convierte nada. Conviene vigilarla en la próxima tesis con prensa.
- **Informe de organismo:** depende de una lista de organismos y de palabras de datos. Un informe con otro vocabulario («Situación de…», «Panorama…») sigue como `libro`.
- **`material_web`:** conserva páginas y notas que son genuinamente web. Todavía hay artículos de revista en línea sin contenedor explícito que quedan como `material_web`: el parser 0.12.7 ya corrige los que dicen «En Revista…».

## 6. Fuera del clasificador (solo documentado)

- En el workspace, la tesis de Candelero sigue guardada con **147** referencias. Es la extracción anterior a 0.6.18: al reprocesarla desde la app quedan las 151.
- `legacy.py` y los parsers v02/v03 conservan una regla legal que ya no se usa. Se podría retirar o unificar con la de 0.12.8 cuando se limpie la cadena de capas.

## 7. ¿Está lista esta capa para BiblioRef 1.0?

**Sí para la clasificación que depende de señales explícitas, con una salvedad:**

- **Lo que ya es estable:** normas, capítulos, tesis, artículos con número y páginas, inéditos y ponencias rotuladas. En Cassini quedó en 58/59 correctas y 0 incorrectas. En el corpus hubo 130 cambios revisados sin errores remanentes.
- **La salvedad:** la cadena de 8 capas superpuestas (v12 → v12_8) funciona, pero cada regla nueva tiene que razonar sobre las anteriores. Antes de 1.0 conviene consolidar la decisión de tipo en una sola función con prioridad declarada, la de `_retype` en 0.12.8. Hacerlo es un refactor sin cambio de comportamiento, verificable con el diff de corpus que ya existe.
- **Para medir exactitud y no cobertura:** hace falta un gold de tipos. Serviría una muestra estratificada de ~300 referencias etiquetadas a mano.
