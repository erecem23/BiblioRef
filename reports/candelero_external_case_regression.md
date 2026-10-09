# Caso de desarrollo: bibliografía con sangría francesa y autores repetidos (T0149, 151 referencias)

**Fecha:** 2026-09-23 · **Versión de partida:** algoritmo 0.6.17, parser 0.12.6
**Versión nueva:** algoritmo 0.6.19 (0.6.18 + 0.6.19), parser 0.12.7

**Fuente:** el diagnóstico `BIBLIOREF_CANDELERO_DIAGNOSTICO_Y_PLAN_CLAUDE.md` y la exportación `dataset_prueba_ultima` (tesis T0149 del workspace).

**Estatus:** desde este trabajo la tesis es un caso de **desarrollo/regresión**, no held-out. Está en el benchmark como `X_CANDELERO` (`regression_hanging_indent_repeated_author`). El 151 se usa solo como verdad de test: ninguna regla de producción depende del autor, del archivo, de la página ni del conteo esperado.

## Resultado

| problema | etapa | antes | cambio | después | regresiones | tests |
|---|---|---|---|---|---|---|
| 4 fusiones (Colovini + «Convergencia (1998)», Eribon + «Etchvers Martín (2010)», García Valdez + «González. O. (2016)», Muñoz «-------------» + «Nava Murcia (2012)») | segmentación (`biblioref/detection/signals.py`, `enhanced_start`) | 147 registros | Un renglón en el margen de inicio que abre con nombre(s) sin coma y fecha entre paréntesis («Apellido Nombre (2010)», «González. O. (2016)», «Convergencia (1998)») es inicio de referencia si el renglón anterior está sangrado o cerró la referencia | 151 registros; 0 fusiones | Ninguna. Corpus 0.6.17 → 0.6.18: 137 idénticos, 11 cambiados, todos revisados. Las fusiones reales se separan, se recupera una referencia, se corrigen dos cortes falsos y se recuperan URL/DOI en letra chica. Los tres defectos laterales que expuso el cambio de arbitraje se corrigieron antes de cerrar: URLs en cuerpo menor, cortes ABNT con sangría invertida y encabezado corrido de dos líneas | `tests_core/test_biblioref_v0_6_18_commaless_starts.py` |
| 66 marcadores de autor repetido quedaban como pseudo-autor («-------------», «—») | parser (`biblioref/parsing/v12_7.py`) y documento (`biblioref/parsing/inheritance.py`) | autor = «-------------» | El parser registra el marcador en `author_marker_raw` y deja el autor vacío. La herencia se resuelve sobre la lista ya segmentada, en orden y dentro de la misma zona, aunque la entrada cambie de página: `author_inherited = True` y `author_inherited_from` apuntan a la última referencia con autor explícito. Una referencia borrada no presta su autor. La herencia se aplica en la vista de la app, en la exportación pública, en los problemas de revisión y en las tablas derivadas | 66/66 heredados, 0 sin autor | Ninguna. En el corpus hay 372 marcadores y ninguno queda huérfano | `test_author_inheritance.py`, `test_parser_v0_12_7.py` |
| Cadena de Lacan que cruza 152 → 153 | herencia | pseudo-autor en 23 registros | idem | Lacan, J. en los 23 (20 en p. 152, 3 en p. 153) | — | `test_author_inheritance.py` (cruce de página) |
| Tipo documental (13 `sin_clasificar`, seminarios inéditos como `libro`, revistas como `libro`) | parser v0.12.7 (`_retype`) | ver tabla | Solo con evidencia explícita: «Inédito / no publicado» → `material_inedito`, salvo que haya evidencia de tesis (→ `tesis`) o de evento (→ `conference_paper`). «Revista, n.º pp. x-y» y «En: Anuario/Revista…» → `articulo_revista`, también cuando además hay URL. «Ciudad, Editorial.» → `libro`, o `capitulo_libro` si antes hay «En <obra>». No se convierte cuando el cierre es un país («Sevilla, España»), una ley («Registro Oficial») o una revista, ni cuando son notas de edición o traducción | ver tabla | Ver «Corpus» abajo | `test_parser_v0_12_7.py` (15 tests) |
| URLs partidas: orden 6 («actas-de-las primeras-jornadas-del-departamento de psicoanálisis-2.pdf») y orden 16 («download.php?gal_id= 479») | reconstrucción de texto (`biblioref/extraction/url_rejoin.py`), algoritmo 0.6.19 | 2 URLs con espacio | Se une el valor de una consulta cortado tras «=» si lleva un dígito. Un nombre de archivo con guiones cortado entre palabras se rearma con guiones solo si las palabras siguientes también tienen forma de slug y llegan a una extensión (.pdf, .html…). Nunca se une prosa, una palabra con mayúscula tras «=» ni texto sin extensión final | 0 URLs con espacio | Ninguna. Corpus 0.6.18 → 0.6.19: 148 de 149 idénticos; en T0149 cambian exactamente esas dos URLs, con el mismo número de registros | `tests_core/test_biblioref_v0_6_19_url_slugs.py` |
| La pantalla Faltantes decía «no quedan pegadas» mientras la barra lateral mostraba «Posibles fusionadas 3» | interfaz (`static/project-missing.js`, `/api/projects/{id}/missing`) | dos detectores con el mismo nombre coloquial | Faltantes cuenta los párrafos del layout que caen **adentro** de otra referencia. La barra cuenta referencias cuyo **texto** parece contener más de una (`merged_suspects`). La API devuelve también `n_merged_suspects` y el Paso 1 dice «no quedan párrafos pegados». Si quedan sospechas de texto, las nombra y aclara que se revisan en la hoja de cada tesis | mensajes coherentes | — | sin test propio (cambio de texto) |

## Criterios de aceptación del diagnóstico

| criterio | resultado |
|---|---|
| Zona 149–155 | ✓ 149–155 |
| 151 referencias | ✓ 151 (28/23/24/23/17/20/16 por página) |
| 0 de las 4 fusiones auditadas | ✓ 0; `possible_fusion` = 0 |
| Sin splits falsos nuevos | ✓ Revisión registro a registro contra el PDF |
| 66 marcadores reconocidos, ninguno como pseudo-autor | ✓ 66 / 66 heredados, 0 sin autor |
| Marcador original conservado | ✓ `author_marker_raw` |
| Cadena de Lacan cruza 152 → 153 | ✓ |
| Menos `sin_clasificar` solo con evidencia | ✓ 13 → 0 en esta tesis |
| URL ≠ `material_web` | ✓ Un artículo en «En Anuario de investigaciones, 14. Recuperado de: http…» pasa a artículo. Una página web sin contenedor sigue siendo `material_web` |
| Las dos URLs multilínea reconstruidas | ✓ |
| No se alteran URLs ya correctas | ✓ En el resto del corpus no cambia ningún registro |

Tipos en esta tesis (parser 0.12.6 → 0.12.7):

| tipo | antes | después |
|---|---|---|
| libro | 86 | 83 |
| articulo_revista | 16 | 23 |
| capitulo_libro | 16 | 16 |
| material_web | 10 | 9 |
| conference_paper | 8 | 10 |
| material_inedito | — | 7 |
| tesis | 2 | 2 |
| sin_clasificar | 13 | 0 |

Los 21 cambios de tipo de esta tesis se revisaron uno por uno y los 21 son correctos.

## Corpus completo (40.122 referencias: 149 tesis + Russo)

**Parser 0.12.6 → 0.12.7:** cambian 253 tipos. El resto es idéntico, salvo los autores literales de marcador, que ahora quedan vacíos y se heredan.

| tipo | antes | después |
|---|---|---|
| articulo_revista | 21.632 | 21.679 |
| libro | 8.922 | 8.874 |
| capitulo_libro | 4.015 | 4.019 |
| sin_clasificar | 1.552 | 1.393 |
| material_web | 1.466 | 1.449 |
| conference_paper | 943 | 963 |
| tesis | 450 | 467 |
| material_inedito | 0 | 138 |

Las familias de cambio se revisaron por muestreo. En una muestra aleatoria de 40 cambios hubo 38 correctos. Los dos errores eran:

- una comunicación personal «en el marco de una reunión de doctorantes», que se tipó como ponencia. Ya está corregido y tiene su test;
- un capítulo de «Escritos I» tipado como `libro`, que antes estaba `sin_clasificar`.

Errores encontrados y corregidos durante la revisión:

- tesis portuguesas («Tese de doutorado», «Dissertação de mestrado») tipadas como `libro`;
- «Trabajo presentado en la XV Reunión…» tipado como `libro`;
- notas de edición y traducción de Freud tipadas como artículo;
- «Library of Congress» tomado como congreso;
- «Sevilla, España» y leyes con «Registro Oficial» tomadas como libro;
- «en la revista El Gráfico» dentro de un título tomado como contenedor.

## Benchmark consolidado (0.6.17 → 0.6.19)

Los 23 casos del Excel, `X_RUSSO` y `X_CANDELERO` se corrieron con `tools/benchmark_consolidado.py`.

- **Cambian S32 y S94.** Son las fusiones reales que separa 0.6.18 y que ya se revisaron en el corpus.
- **S77 mejora.** Sus avisos de borde bajan de 14 a 7.
- **Todo lo demás queda igual.** Los controles estables `S08`, `S36` y `X_RUSSO` son idénticos.
- **Candelero entra al benchmark** con 151 registros, 0 fusiones posibles y 1 borde a revisar.

Resultado: `benchmarks/consolidado_v0_1/result_v0_6_19.json`.

## Declaraciones

- `EXTRACTION_CORE_NONREGRESSION_V0618_SHA256.json` + `EXTRACTION_CORPUS_EQUIVALENCE_V0_8.json`
- `EXTRACTION_CORE_NONREGRESSION_V0619_SHA256.json` + `EXTRACTION_CORPUS_EQUIVALENCE_V0_9.json`
- Tests: `tests_core` 560 aprobados.
- En la raíz, 803 aprobados. Fallan dos que no tienen que ver con este cambio:
  - `test_current_field_test_state.py` es una modificación local que ya esperaba el algoritmo 0.6.13;
  - la reproducción de la selección OpenAlex necesita el `bash` de WSL, que no está instalado.
