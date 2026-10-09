# Caso externo de regresión: tesis con bibliografía con viñetas (304 p., 181 referencias)

**Fecha:** 2026-09-23 · **Versión de partida:** algoritmo 0.6.16, parser 0.12.5, metadatos de portada v0.5.1
**Versión nueva:** algoritmo 0.6.17, parser 0.12.6, metadatos de portada v0.5.2

**Fuente:** el diagnóstico de la prueba y la exportación `dataset_prueba 2.zip` (tesis T0148 del workspace).

**Estatus:** desde este trabajo la tesis pertenece al conjunto de **desarrollo/regresión**, no al held-out. Quedó en el benchmark como `X_RUSSO` (`stable_control_bulleted_bibliography`).

## Resultado

| problema | etapa | baseline | cambio | resultado nuevo | regresiones | test asociado |
|---|---|---|---|---|---|---|
| Año de la tesis = 1917 (nota al pie «…nacida el 4 de octubre de 1917») | metadatos de portada (`biblioref/metadata/cover_v05.py`, `_detect_year`) | `anio = 1917` | Una etiqueta explícita en línea corta («Año 2025», «Fecha», «Year») pesa +0,5. Una nota al pie (numeral de llamada, cuerpo menor que el de la página, banda inferior) no fecha la tesis. Una fecha que empieza con el día («10 DE NOVIEMBRE DE 2014») no es nota | `anio = 2025` | Ninguna. Sobre 148 documentos solo cambia esta tesis. Aparecieron 3 regresiones intermedias (T0005, T0064, T0136) y se corrigieron antes de cerrar | `test_frontmatter_metadata_v0_6.py` (5) |
| «Cómo se hace una tesis» → `tesis` | parser | `tesis` | `tesis` exige evidencia fuera del título: «[Tesis de doctorado]», «Tesis del Profesorado», «Master´s Dissertation», «tesina», «trabajo final»… | `libro` | Ninguna. En el corpus cambian 7 (Eco ×3, «Tesis sobre Stanislavski» ×2, «Tesis sobre la Historia», y una ponencia sobre «las primeras tesis médicas» → `conference_paper`). Las 448 tesis restantes siguen siendo tesis | `test_parser_v0_12_6.py::test_the_word_thesis…`, `test_real_theses_stay_theses` |
| Capítulos clasificados como `libro` / `articulo_revista` | parser | Russo: 1 `capitulo_libro` | «…, en / En / In <contenedor>» es capítulo si el contenedor tiene rol de editor (Comp., Coord., Ed., Dir., Org.), rango de páginas o empieza con nombres de editores. No lo es si hay marcas de revista antes o dentro del contenedor | Russo: 35 `capitulo_libro` | Ninguna comprobada. Muestra aleatoria de 40 sobre 790 «libro → capítulo»: 40/40 correctos. Quedan 3 dudosos en 38 «artículo → capítulo» (un número especial de revista y dos registros fusionados por la segmentación) | `test_chapters_…`, `test_en_inside_a_title…`, `test_a_container_that_opens_with_its_editors…` |
| URLs partidas por el salto de línea | segmentación / reconstrucción de texto (`biblioref/extraction/url_rejoin.py`, paso final de `biblioref/pipeline.py`) | 13 URLs con espacio en Russo | Dentro de una URL, se quita el espacio si lo que sigue lleva `/ = & % ? # _ ;`, una extensión o es hexadecimal. Nunca si sigue otra URL, una fecha o prosa | 0 URLs con espacio. DOI: 5 → 5 | Ninguna. En el corpus cambian 1.441 referencias de 112 tesis, **todas solo por espacios quitados** (verificado registro a registro). También repara DOI partidos como «https://doi.⟦ ⟧org/10…», que antes no se detectaban | `tests_core/test_biblioref_v0_6_17_url_rejoin.py` (11 casos de URL partida y 6 controles de prosa, fecha y otra URL) |
| Autor corporativo absorbe «(s/f» | parser (bloque de fecha) | `autor = "…(API), (s/f"`, año vacío | Las variantes «(s/f)», «(sin fecha)», «(s/f. Varias versiones)», «(s/d)» y «(n.d.)» se normalizan a «(s.f.)», la convención que el parser ya leía | `autor = "Asociación Psicoanalítica Internacional (API)"`, `año = "s.f."` | Ninguna | `test_corporate_author_without_date…`, `test_a_bullet_before_an_undated…` |
| «De Souza, L.» → «De, Souza» | parser (bloque de fecha) | `autor = "De, Souza"` | La causa **no era la partícula**: era la fecha «(4 y 5 de noviembre de 2011)». Con día y mes, el parser caía en la ruta de año final y partía cualquier apellido compuesto («Pérez Souza» → «Pérez, Souza»). La fecha se normaliza al año. De la lectura normalizada se toman solo autor, año y título; el tipo solo cambia si antes era `sin_clasificar` o si ahora aparece una revista explícita | `autor = "De Souza, L."`, año 2011, `conference_paper` | Ninguna comprobada. En el corpus mejoran unos 200 autores y 46 años (por ejemplo años que eran fecha de acceso: «2024» → `s.f.`). Los titulares de prensa sin autor no se convierten en autor | `test_surname_particles_are_kept`, `test_a_day_and_month_date…` |
| «[Ponencia]» explícito clasificado como `libro` | parser | `libro` | La etiqueta explícita «[Ponencia]», «[Presentación]» o «[Comunicación]» → `conference_paper` | `conference_paper` | Ninguna | `test_an_explicit_ponencia_label…` |
| Libros `sin_clasificar` («Título. Editorial.») | parser | Russo: 11 `sin_clasificar` | «Título. Editorial.» → `libro`, salvo que el cierre sea un lugar, un país, una universidad o instituto, una abreviatura, «Seminario», «Sin datos», un catálogo, software, etc. | Russo: 4 `sin_clasificar` | Precisión estimada ~85–90 % sobre 236 conversiones (muestra de 40). Los errores restantes son informes técnicos y software, que antes también estaban sin clasificar | `test_title_and_publisher_alone_is_a_book` |
| `n_bordes_a_revisar = 12` sin ningún aviso | auditoría de cobertura (`biblioref_page_boundary.py`) | 12 bordes `review`, sin evidencia en ningún sentido | El evaluador ignora el folio al pie y la marca de lista («○», «•», «-», «12.», «[12]»). Una URL al comienzo de página es continuación, y la barra final de una URL no es línea abierta | 2 `review` (dos bordes genuinamente dudosos) | Ninguna. En el benchmark los avisos de borde pasan de 250 a 99 y ningún caso sube (dos subas intermedias en S18 y S20 se corrigieron) | `PageBoundaryWithListMarkers` (5 tests) |

## Criterios de aceptación del diagnóstico

| criterio | resultado |
|---|---|
| Sección 292–304 | ✓ 292–304 |
| 181 referencias | ✓ 181 |
| Páginas de la sección sin referencias = 0 | ✓ 0 |
| `n_fusionadas_detectadas = 0` | ✓ 0 |
| `n_faltan_de_verdad = 0` | ✓ 0 |
| Calzada (2009) unida entre 293 y 294 | ✓ 293–294 |
| Sin contaminación narrativa | ✓ Los textos de las 181 referencias son idénticos a la exportación, salvo los espacios quitados en URLs |
| Año ≠ 1917 (año documental = 2025) | ✓ 2025 |
| «Cómo se hace una tesis» deja de ser tesis | ✓ `libro` |
| Capítulos inequívocos = `capitulo_libro` | ✓ Barbarosch, Abelleira, Freud (1990), Winnicott (2016), Tkach (2022), Liberman (2011) y 29 más |
| No degradar artículos, tesis ni ponencias | ✓ Artículos 37 → 36 (Winnicott 2016 era un capítulo mal tipado), tesis 8 → 7 (Eco), ponencias 7 → 8 |
| URLs sin espacios internos, DOI conservados | ✓ 13 → 0 URLs con espacio, 5 → 5 DOI |
| No incorporar «(s/f)» al autor | ✓ |
| Preservar «De Souza» | ✓ |

Distribución de tipos en esta tesis:

| tipo | antes | después |
|---|---|---|
| libro | 111 | 85 |
| capitulo_libro | 1 | 35 |
| articulo_revista | 37 | 36 |
| sin_clasificar | 11 | 4 |
| tesis | 8 | 7 |
| conference_paper | 7 | 8 |
| material_web | 6 | 6 |

## Efecto sobre el corpus completo del workspace (39.785 referencias de 148 tesis)

**Parser 0.12.5 → 0.12.6:**

| tipo | antes | después |
|---|---|---|
| articulo_revista | 21.612 | 21.614 |
| libro | 9.409 | 8.829 |
| capitulo_libro | 3.135 | 3.998 |
| sin_clasificar | 1.834 | 1.548 |
| material_web | 1.451 | 1.454 |
| conference_paper | 929 | 934 |
| tesis | 455 | 448 |

Las referencias sin año pasan de 250 a 228. Cada familia de cambios se revisó con una muestra aleatoria antes de aceptarla. El arnés es un script de trabajo, no quedó en el repo: parsea todo el corpus con cada versión en unos 20 s y compara campo por campo.

**Algoritmo 0.6.16 → 0.6.17:**

- Sobre 147 documentos con línea de base, 112 cambian, y todos solo por espacios quitados dentro de URLs. Los conteos no cambian.
- T0148 (esta tesis) no tenía línea de base.
- Declarado en `EXTRACTION_CORE_NONREGRESSION_V0617_SHA256.json` y `EXTRACTION_CORPUS_EQUIVALENCE_V0_7.json`.

**Metadatos de portada v0.5.1 → v0.5.2:** sobre 148 documentos solo cambia T0148. Al abrir el proyecto, la app refresca los metadatos automáticos y respeta los que se corrigieron a mano.

## Decisiones

- **Año:** no se agregaron campos nuevos (`anio_documento` / `anio_publicacion_repositorio`). BiblioRef trabaja solo con el PDF, y `anio` es el año documental de la portada. Separar el año del repositorio corresponde al día que se integre metadata externa.
- **Sin fecha:** se usa la convención existente `year = "s.f."` en lugar de un campo nuevo, porque aguas abajo ya se lee así.
- **Taxonomía:** los `sin_clasificar` evitables eran reglas insuficientes, no un problema de orden entre reglas ni de taxonomía. No se crearon categorías (por ejemplo `resena`).
- **Varios años en una referencia:** no se usó como señal de fusión, como pedía el diagnóstico.

## Pendiente

- Dos bordes siguen en `review`. En p. 293 la línea siguiente es «[Ficha de cátedra].»; en p. 302 la referencia siguiente llega sin viñeta. Los dos son genuinamente ambiguos para el evaluador.
- Registros fusionados por la segmentación (dos referencias en un registro) siguen confundiendo al parser: el tipo sale de la primera referencia y el contenedor de la segunda. Se corrige en la segmentación, no en el parser.
- «Título. Editorial.» conserva errores en informes técnicos y software. Ampliar la taxonomía (`software`, `informe_tecnico`) exige revisar primero cómo se usan aguas abajo.

## Reproducir

```
.venv\Scripts\python.exe -m pytest -q test_parser_v0_12_6.py test_frontmatter_metadata_v0_6.py tests_core\test_biblioref_v0_6_17_url_rejoin.py
.venv\Scripts\python.exe tools\benchmark_consolidado.py --cases X_RUSSO --out russo.json
```
