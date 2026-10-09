# Refactor: decisión del tipo documental en un solo lugar

**Fecha:** 2026-09-23 · **Parser:** 0.12.8 (sin cambio de versión: la salida es la misma)

## Qué cambió

Antes, el tipo se volvía a decidir en tres capas superpuestas: `v12_6._overlay`, `v12_7._retype` y `v12_8._retype`. Cada una estaba escrita contra la salida de la anterior, y para saber por qué una referencia quedaba con un tipo había que leer las tres.

Ahora:

- **`biblioref/parsing/doctype.py`**: una sola función, `decide_type`, y una tabla declarada, `TYPE_PASSES`. Cada regla dice desde qué tipos puede partir, qué evidencia pide y a qué tipo lleva. `rule_table()` devuelve la tabla como filas.
- **`biblioref/parsing/parser.py`**: es el parser vivo y hace cuatro pasos:
  1. lectura base (v0.12.5 más la normalización del bloque de fecha de v0.12.6);
  2. marcador de autor repetido;
  3. `has_url`;
  4. `decide_type`.
- **`biblioref/parsing/__init__.py`** exporta `parser.py`.
- `v12_6/7/8.py` quedan como versiones históricas, igual que el resto de la cadena. `doctype.py` reutiliza sus patrones.

**Semántica de la tabla:**

- Cada *pasada* lee el tipo actual una vez.
- Dentro de una pasada decide la primera regla que aplica, y la pasada termina.
- La pasada siguiente lee el tipo que dejó la anterior.
- Cada regla deja su nombre en `parser_notes` y el tipo anterior en `type_candidates`, igual que antes.

| pasada | orden | regla | parte de | qué decide |
|---|---|---|---|---|
| palabra_tesis_en_titulo | 1 | `thesis_word_in_title_only` | tesis | «tesis» solo dentro del título no es una tesis: libro, o ponencia si hay evento |
| rotulo_ponencia | 1 | `explicit_ponencia_label` | cualquiera | «[Ponencia]», «[Comunicación]»… → ponencia |
| contenedor | 1 | `chapter_container` | articulo_revista, libro, sin_clasificar | «. En / , en <obra>» con rol de editor, páginas o nombres de editores → capítulo |
| contenedor | 2 | `title_and_publisher` | sin_clasificar | «Título. Editorial.» → libro |
| evidencia_explicita | 1 | `unpublished` | informe_documento, libro, material_web, sin_clasificar | «Inédito / no publicado» → material inédito, salvo tesis o evento |
| evidencia_explicita | 2 | `serial_container_online` | material_web | «En Revista/Anuario…» con URL → artículo (la URL es acceso) |
| evidencia_explicita | 3 | `journal_number_pages` | libro, sin_clasificar | «Revista, n. pp. x-y» o «En: Anuario…» → artículo |
| evidencia_explicita | 4 | `thesis_statement` | sin_clasificar | grado académico explícito → tesis |
| evidencia_explicita | 5 | `academic_event` | sin_clasificar | congreso, jornada, reunión… → ponencia |
| evidencia_explicita | 6 | `city_and_publisher` | sin_clasificar | «Ciudad, Editorial.» → libro, o capítulo si antes hay «En <obra>» |
| norma_capitulo_informe_web | 1 | `legal` | cualquiera salvo tesis, capítulo y legal | norma numerada, código o reglamento de un organismo → documento legal |
| norma_capitulo_informe_web | 2 | `loose_chapter` | libro, sin_clasificar | «¿…? En E. Editor (Comp.)… (pp.)» → capítulo |
| norma_capitulo_informe_web | 3 | `public_body_report` | libro, sin_clasificar | organismo público + datos → informe |
| norma_capitulo_informe_web | 4 | `dated_news_online` | libro, sin_clasificar | pieza fechada de un medio, en URL → web |

**Qué no se movió:** de v09 a v12_5 el tipo se decide junto con la separación de revista y editorial (qué parte del texto es la revista define si es artículo). Moverlo sería reescribir la extracción de campos, no refactorizar. Eso queda como «lectura base», y la tabla opera sobre ella.

## Verificación: cero cambios de comportamiento

Comparé la salida completa, todos los campos, del parser vivo contra `v12_8.parse_reference` en 40.481 textos: el corpus de 149 tesis, Russo, Cassini y la muestra de 300.

| resultado | referencias |
|---|---|
| salida idéntica en todos los campos | 40.453 |
| solo cambia el orden de las notas dentro de `parser_notes` | 28 |
| algún valor distinto | **0** |

Las 28 son referencias con marcador de autor repetido y además una regla de la antigua v12_6. Antes, la nota del marcador quedaba entre las de v12_6 y las de v12_7; ahora el marcador se registra antes de decidir el tipo. Ningún campo cambia de valor, por eso la versión del parser sigue siendo 0.12.8 y las referencias guardadas no se reprocesan.

**Muestra gold de 300** (`tools/benchmark_tipos.py`, gold v0 sin revisar): 280 correctas, 18 incorrectas y 2 sin clasificar. Es idéntico antes y después del refactor. Resultado en `benchmarks/tipos_gold/result_parser_0_12_8_gold_v0.json`.

**Tests:**

- `test_parser_doctype.py`, 97 tests:
  - la salida del parser vivo es igual a la de 0.12.8 para cada texto de los tests de 0.12.6, 0.12.7 y 0.12.8;
  - el orden declarado de la tabla;
  - que una regla no sale de sus tipos de partida;
  - que decide la primera regla de cada pasada;
  - que la muestra gold no retrocede de 280 correctas y 18 incorrectas.
- Suite de la raíz: 925 aprobados. `tests_core`: 560.
- Siguen excluidos los dos fallos previos de siempre: `test_current_field_test_state.py` y la reproducción de OpenAlex, que necesita WSL.

## Cómo seguir

Las correcciones del paso 3 (Obras Completas como capítulo, periódicos como artículo, «En: Revista, n, pp.», Memorias de Jornadas) se hacen en `doctype.py`. Para medir cada una:

```
python tools/benchmark_tipos.py --baseline benchmarks/tipos_gold/result_parser_0_12_8_gold_v1.json
```

Eso, más el diff de tipos sobre el corpus revisado por familia. Con el gold revisado se puede usar `--solo-revisadas`.

## Gold v1 (misma fecha)

Se revisaron las 114 filas pendientes con búsqueda web (`benchmarks/tipos_gold/BIBLIOREF_MUESTRA_300_TIPOS_GOLD_V1.xlsx`, hoja `CAMBIOS_V1`).

**Criterio:** el gold registra el tipo del documento tal como lo presenta la referencia.

**Cambios:**

- **M130** (Toro, Imago Agenda): web → artículo. Imago Agenda es una publicación periódica, ISSN 1515-3398.
- **M234** (Carpintero y Vainer, Topía): libro → artículo.
- **M083** (resumen de proyecto UBACyT): web → informe/documento.
- **M018** (Prensa AMET): excluida, no es verificable.
- El resto quedó confirmado. Por ejemplo, Freud en *Obras completas* es capítulo según las guías APA, y *lalengua* es una publicación periódica numerada.

**Línea de base del parser 0.12.8 contra el gold v1:** 278 correctas, 20 incorrectas y 1 sin clasificar, sobre 299. Resultado en `benchmarks/tipos_gold/result_parser_0_12_8_gold_v1.json`.
