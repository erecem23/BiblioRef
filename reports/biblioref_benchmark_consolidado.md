# Benchmark consolidado de BiblioRef: últimas tesis, antes y después

**Fecha:** 2026-09-23 · **Línea de base:** algoritmo 0.6.14 (HEAD `4430733`, rama `dev`) · **Nueva versión:** algoritmo 0.6.15 (sin commitear)

**Fuente:** `BiblioRef_consolidado_ultimas_tesis_antes_despues.xlsx`, con las hojas COMPARACION_ANTES_DESPUES, ANTES_DEV1, DESPUES_DEV2, NUEVAS_TESIS, NUEVAS_REFERENCIAS y LEEME.

## Resumen

- En el benchmark (23 tesis con PDF local) cambian 9 casos, todos para mejor. Los 14 restantes, incluidos los dos `stable_control`, dan un hash idéntico.
- En el corpus completo del workspace (147 tesis, un control fuera de muestra) quedan 132 idénticas y cambian 15. Revisé las 15 a mano: ninguna pierde una referencia real.
- Rescate principal: S20 / T0026 pasa de **9 a 345 referencias**. La bibliografía entera estaba perdida por una portadilla «Bibliografía y Anexos».
- Métricas agregadas sobre las 147 tesis:

  | métrica | antes | después |
  |---|---|---|
  | tails DOI/URL | 29 | 14 |
  | segmentos cortos | 54 | 38 |
  | segmentos ≥ 500 palabras | 14 | 4 |
  | segmentos ≥ 140 palabras | 53 | 38 |
  | posibles fusiones | 96 | 56 |
  | registros narrativos | 40 | 28 |
  | encabezado corrido dentro de un registro | 14 | 1 |
  | posibles fragmentos | 127 | 127 |

- Tests: `tests_core` pasa completo (530). Hay 23 tests nuevos en `tests_core/test_biblioref_v0_6_15_zone_guards.py`, incluidas las 4 pruebas de la declaración.

## Cómo se construyó el benchmark

- `benchmarks/consolidado_v0_1/cases.json` toma de COMPARACION_ANTES_DESPUES las 20 tesis de *selected20* con su categoría y las cifras del Excel (dev1 shadow, dev2 raw/candidate, zonas cuarentenadas), y las 3 tesis de NUEVAS_REFERENCIAS con sus 414 filas viejas.
- Los PDF se localizaron por nombre de archivo: `Downloads/master_tesis/…` para las 20, y `Documento_completo (1).pdf` (162 p.), `Documento_completo.pdf-PDFA (3).pdf` (374 p.) y `tesis - Maximiliano Apolonio (2).pdf` para las nuevas.
- `tools/benchmark_consolidado.py` corre `biblioref.pipeline.process_pdf` sobre cada caso, en paralelo (unos 3 minutos). No compara solo conteos: mide la **forma** de la segmentación. Las métricas:

  | métrica | qué mide |
  |---|---|
  | registros | cantidad de registros de la tesis |
  | caracteres totales | si no cambian, fue re-segmentación; si bajan, se perdió o descartó texto |
  | cortos | registros de menos de 5 palabras |
  | largos | registros de 140 palabras o más, y de 500 o más |
  | tails DOI/URL | registro que es casi solo un enlace o un «Recuperado de» |
  | posibles fusiones | dos cabezas autor-año, o un marcador `[n]` interno |
  | posibles fragmentos | registro que abre en minúscula o con puntuación |
  | narrativos | 80 palabras o más, con alta densidad de palabras funcionales y casi sin años |
  | encabezado adentro | «REFERENCIAS…» dentro de un registro |
  | zonas | zonas de la tesis |
  | zonas en revisión del shadow | el análogo vivo de las zonas cuarentenadas de 0.8.9 |
  | recall textual | solo para las filas viejas: cuántas aparecen en la salida nueva y cuántas abren registro |

- `--remeasure` recalcula las métricas desde una corrida guardada, sin volver a leer los PDF.
- Las métricas son indicadores, no ground truth. Cada cambio de texto se revisó con un diff registro a registro antes de aceptarlo.
- Las etiquetas del Excel siguen siendo las de 0.8.9. Varios casos ya estaban resueltos en 0.6.14; por ejemplo, S11 y S78 no tienen segmentos gigantes y S63 no tiene tails.
- **UNR28 y UNR30** no tienen PDF local ni filas referencia a referencia: quedan fuera de la medición. Del Excel solo se sabe lo que dice el resumen: 306 registros en UNR28, y 181 → 437 con 4 posibles fusiones en UNR30.

Reproducir:

```
.venv\Scripts\python.exe tools\benchmark_consolidado.py --out nuevo.json --baseline benchmarks\consolidado_v0_1\baseline_v0_6_14.json
```

## Resultados por caso

Formato de cada celda: `reg` = registros · `máx` = palabras del registro más largo · `≥500p` = segmentos de 500 palabras o más · `cortos` · `tails` = DOI/URL aislados · `fus` = posibles fusiones · `narr` = narrativos · `enc` = encabezado corrido adentro · `zonas` · `rev` = zonas en revisión del shadow.

| caso | categoría | baseline (0.6.14) | nueva versión (0.6.15) | cambio | mejora/regresión | observaciones |
|---|---|---|---|---|---|---|
| S07 | zone_or_narrative_contamination | 218 reg · máx 1863 pal · ≥500p 3 · cortos 0 · tails 0 · fus 0 · narr 1 · enc 0 · zonas 2 · rev 0 | 215 reg · máx 35 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | reg 218→215; máx pal 1863→35; ≥500p 3→0; ≥140p 3→0; narr 1→0; zonas 2→1 | mejora | Zona falsa p. 29 («…referencias bibliográficas.» final de oración) eliminada: 3 registros de prosa, uno de 1.863 palabras. Las 215 referencias reales (p. 214-227) quedan idénticas. Excel: dev1 235, dev2 cand. 210. |
| S08 | stable_control | 135 reg · máx 57 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 135 reg · máx 57 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | control estable | Sin cambios. Excel: dev1 133, dev2 cand. 127. |
| S11 | rescue_subsegmentation | 475 reg · máx 97 pal · ≥500p 0 · cortos 0 · tails 0 · fus 33 · narr 0 · enc 0 · zonas 1 · rev 1 | 476 reg · máx 97 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 1 | reg 475→476; fus 33→0 | mejora | Folio «[303]» pegado a la última referencia de 33 páginas; ahora se descarta. Se separa además «Navarro (1943)» de «Asociación de Neurología Pediátrica (ANEPA)», antes pegadas a través del folio. Excel: dev1 157, dev2 cand. 157. |
| S18 | rescue_missing_bibliography | 269 reg · máx 99 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 269 reg · máx 99 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | sin cambio | Ya rescatada en 0.6.14 (269). Excel: dev1 226, dev2 cand. 223. |
| S20 | rescue_subsegmentation | 9 reg · máx 715 pal · ≥500p 3 · cortos 0 · tails 0 · fus 0 · narr 2 · enc 0 · zonas 2 · rev 29 | 345 reg · máx 113 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 1 · rev 0 | reg 9→345; máx pal 715→113; ≥500p 3→0; ≥140p 4→0; fus 0→1; narr 2→0; zonas 2→1; rev 29→0 | mejora (rescate) | Portadilla «Bibliografía y Anexos» abría una zona vacía y el encabezado real de la p. 285 se descartaba como encabezado corrido; además el estilo se diagnosticaba `numeric` con listas del anexo. Ahora: zona p. 285-315, `author_year_comma`, 345 referencias de «A Casa (1991)» a «Zuluaga (2009)». Queda 1 registro con el comienzo de la lista del anexo pegado (113 palabras). La «fusión» restante es un capítulo «En Autor (año)» (falso positivo de la métrica). Excel: dev1 395, dev2 cand. 380. |
| S29 | blind_spot | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | idéntico (hash) | resuelto con OCR | PDF 100 % escaneado (392 páginas, 0 caracteres de texto). Con el OCR de BiblioRef (`biblioref/ocr.py`, 26 min): **0 → 212 referencias**, una zona p. 187-204 de «Aalto» a «Yorke», sin cortos ni fragmentos, máx. 82 palabras. Ver «Tesis escaneadas». Excel: dev1 0, dev2 cand. 0. |
| S32 | zone_or_narrative_contamination | 181 reg · máx 650 pal · ≥500p 1 · cortos 0 · tails 0 · fus 0 · narr 6 · enc 0 · zonas 2 · rev 1 | 181 reg · máx 650 pal · ≥500p 1 · cortos 0 · tails 0 · fus 0 · narr 6 · enc 0 · zonas 2 · rev 1 | idéntico (hash) | sin cambio | Zona 2 (p. 156-162) es un manual de intervención anexo con su propia lista: siguen 5 registros de prosa del manual. Pendiente. Excel: dev1 192, dev2 cand. 172. |
| S35 | blind_spot | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | idéntico (hash) | parcial con OCR | PDF 100 % escaneado a máquina de escribir, páginas con `/Rotate 90`. Con el OCR: 0.6.15 daba 9 registros basura; 0.6.16 da **27 referencias en 3 de 5 bibliografías por capítulo**. Ver «Tesis escaneadas». Excel: dev1 0, dev2 cand. 0. |
| S36 | stable_control | 299 reg · máx 61 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 299 reg · máx 61 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | control estable | Sin cambios. Excel: dev1 298, dev2 cand. 296. |
| S44 | blind_spot | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | 0 reg · máx 0 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 0 · rev 0 | idéntico (hash) | correcto (verdadero negativo) | El PDF es solo el resumen de la tesis (6 páginas) y no tiene bibliografía: 0 es la respuesta correcta. Excel: dev1 0, dev2 cand. 0. |
| S55 | shadow_fusion_regression | 465 reg · máx 58 pal · ≥500p 0 · cortos 8 · tails 8 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 454 reg · máx 58 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | reg 465→454; cortos 8→0; tails 8→0; frag 2→0 | mejora | 8 colas «Recuperado de: http…» abiertas como registro propio (incluidas «pareja. Recuperado de:», «00. Recuperado de:» y una al pie de página) vuelven a su referencia. Caracteres totales iguales (+11 por espacios): re-segmentación sin pérdida. Excel: dev1 463, dev2 cand. 452. |
| S56 | shadow_fusion_regression | 845 reg · máx 179 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 2 · enc 0 · zonas 1 · rev 1 | 845 reg · máx 179 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 2 · enc 0 · zonas 1 · rev 1 | idéntico (hash) | sin cambio | Los 2 «narrativos» son referencias largas legítimas (falso positivo de la métrica). Excel: dev1 937, dev2 cand. 849. |
| S63 | doi_or_tail_oversegmentation | 1389 reg · máx 57 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 1 · rev 0 | 1389 reg · máx 57 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | sin cambio | El caso «doi_or_tail_oversegmentation» ya estaba resuelto en 0.6.14: 0 tails. Excel: dev1 1443, dev2 cand. 1388. |
| S74 | shadow_fusion_regression | 167 reg · máx 71 pal · ≥500p 0 · cortos 2 · tails 3 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 157 reg · máx 71 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | reg 167→157; cortos 2→0; tails 3→0 | mejora | 10 colas («Disponible en:», «Recuperada de:», continuación «Geschichtswissenschaften , 21 (3-43). Recuperado de…») vuelven a su referencia. Excel: dev1 164, dev2 cand. 157. |
| S77 | shadow_fusion_regression | 223 reg · máx 51 pal · ≥500p 0 · cortos 3 · tails 0 · fus 0 · narr 0 · enc 13 · zonas 2 · rev 0 | 219 reg · máx 51 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 2 · rev 0 | reg 223→219; cortos 3→0; enc 13→0 | mejora (y rescate) | Encabezado de diccionario «REFERENCIAS BIBLIOGRÁFICAS» + «A/B» a la altura del 12 %: estaba dentro de 13 registros y partía URLs entre páginas. Se recupera la primera referencia («Alonso, Jaime (2010)»), antes perdida. Excel: dev1 221, dev2 cand. 217. |
| S78 | rescue_missing_bibliography_risky | 268 reg · máx 54 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 268 reg · máx 54 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | sin cambio | Ya rescatada en 0.6.14. Excel: dev1 268, dev2 cand. 268. |
| S81 | shadow_fusion_regression | 153 reg · máx 100 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 1 | 153 reg · máx 100 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 1 | idéntico (hash) | sin cambio |  Excel: dev1 167, dev2 cand. 160. |
| S86 | rescue_missing_bibliography | 81 reg · máx 52 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 1 · rev 0 | 81 reg · máx 52 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | sin cambio | La «fusión» es un capítulo «En E. Beker… (2002)» (falso positivo). Excel: dev1 95, dev2 cand. 85. |
| S87 | zone_or_narrative_contamination | 276 reg · máx 561 pal · ≥500p 1 · cortos 0 · tails 0 · fus 3 · narr 11 · enc 1 · zonas 8 · rev 4 | 276 reg · máx 561 pal · ≥500p 1 · cortos 0 · tails 0 · fus 3 · narr 11 · enc 1 · zonas 8 · rev 4 | idéntico (hash) | sin cambio / pendiente | Zona «Referencias» p. 17-31 es un estado del arte en prosa con citas autor-año: 11 registros narrativos. Pendiente: distinguir prosa con citas de una lista. Excel: dev1 368, dev2 cand. 262. |
| S94 | zone_or_narrative_contamination | 328 reg · máx 1936 pal · ≥500p 4 · cortos 0 · tails 0 · fus 1 · narr 5 · enc 0 · zonas 4 · rev 3 | 323 reg · máx 94 pal · ≥500p 0 · cortos 0 · tails 0 · fus 1 · narr 0 · enc 0 · zonas 2 · rev 1 | reg 328→323; máx pal 1936→94; ≥500p 4→0; ≥140p 5→0; narr 5→0; zonas 4→2; rev 3→1 | mejora | «REFERENCIAS» como celda de una tabla (p. 182) abría una zona: 5 registros de tabla/prosa (máx. 1.936 palabras) eliminados, y una zona vacía menos. Las 315 + 8 referencias reales, idénticas. Excel: dev1 354, dev2 cand. 343. |
| N_T0009 | numbered_fused_rows | 61 reg · máx 28 pal · ≥500p 0 · cortos 6 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 6 · rev 1 | 52 reg · máx 27 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 5 · rev 0 | reg 61→52; máx pal 28→27; cortos 6→0; zonas 6→5; rev 1→0 | mejora | Numeradas `[n]`: «(2005) 1.» se leía como marcador «(n)» y «Chem.184 (2002) 431.» abría registro: 6 fragmentos → 0. «[1 ]-J.-M. Basset…» (espacio en el corchete) se perdía: recuperada. Folios «- 24 -» fuera. 52 registros = 25+5+8+9+5, la suma exacta de marcadores. Las filas `[4]…[5]…[6]` pegadas del Excel (salida 0.9.6) ya no existen desde 0.6.x. Excel: 5 filas. |
| N_T0013 | nueva_tesis | 338 reg · máx 69 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | 338 reg · máx 69 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 0 | idéntico (hash) | sin cambio | Las 310 filas de la salida vieja están en la nueva; las 9 que no abren registro eran fragmentos de 0.9.6 (autor institucional separado de su año) que la versión actual ya reúne. Excel: 310 filas. |
| N_T0006 | nueva_tesis | 99 reg · máx 55 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 1 | 99 reg · máx 55 pal · ≥500p 0 · cortos 0 · tails 0 · fus 0 · narr 0 · enc 0 · zonas 1 · rev 1 | idéntico (hash) | sin cambio | 99/99 filas viejas abren registro: acuerdo total. Excel: 99 filas. |

### Tesis del corpus completo que cambian fuera del benchmark (control de generalización)

| tesis | antes → después | qué cambió | veredicto |
|---|---|---|---|
| T0079 | 886 → 924 | El folio «- 617 -» al pie funcionaba como «pegamento»: unos 38 pares de referencias estaban fusionados (Abt / Academia Argentina de Letras, Allué / Altamirano, Colombres / CONICET…). Posibles fusiones 9 → 1. Aparece 1 fragmento real, «Aires: Sudamericana.», una línea huérfana del propio PDF que antes quedaba dentro de una fusión. | mejora |
| T0117 | 219 → 203 | La zona falsa «referencias.» (final de oración, p. 417) tragaba 16 líneas de una entrevista transcrita. | mejora |
| T0121 | 243 → 236 | La zona falsa «referencias.» (p. 37) tomaba 7 viñetas de objetivos específicos. | mejora |
| T0023 | 241 → 240 | Un registro que solo decía «Referencias» (encabezado corrido). | mejora |
| T0104, T0123, T0136 | −1, −1, −3 | Colas «Disponible en:», «URL:», «Recuperado de:» y continuaciones en minúscula («la humanidad. Vatican News: https://…») vuelven a su referencia. | mejora |
| T0146 | igual que S74 | Es la misma tesis de Grassi (290 p.), cargada de nuevo en el workspace como `Documento_completo _1_`. | mejora |

## Tesis escaneadas: OCR de BiblioRef (0.6.16)

S29 y S35 no son blind spots del segmentador: son PDF sin capa de texto. Se pasaron por `biblioref.ocr.ocr_pdf_pages`, el mismo paso explícito de la app, sobre copias `.ocr.pdf`; el proyecto no se tocó.

| caso | antes del OCR | OCR + 0.6.15 | OCR + 0.6.16 |
|---|---|---|---|
| S29 (asma bronquial, 392 p.) | 0 | 212 | 212 |
| S35 (diferencial semántico, 370 p., `/Rotate 90`) | 0 | 9 registros basura | 27 referencias, 3 zonas |

S35 destapó dos errores, que se corrigieron en 0.6.16 con un test cada uno:

1. **Etapa extracción, páginas rotadas.** `get_text` devuelve las cajas en el espacio sin rotar. En una página con `/Rotate 90` cada línea queda vertical, y el extractor agrupaba «renglones» que en la página vista son columnas: la bibliografía salía en palabras sueltas y en orden invertido. `biblioref_v0_3.py` ahora lleva las cajas al espacio visible con `page.rotation_matrix`, igual que el escritor del OCR.
2. **Etapa detección de zona, regresión propia de 0.6.15.** La guarda de «celda de tabla» contaba como celdas la basura del borde del escaneo («·», «|»). Rechazaba los encabezados reales de p. 121, 183 y 221. Ahora una celda necesita al menos dos caracteres alfanuméricos.

Sobre las 147 tesis del workspace, 0.6.16 da 147 idénticas contra 0.6.15. Se declara en `EXTRACTION_CORE_NONREGRESSION_V0616_SHA256.json` y `EXTRACTION_CORPUS_EQUIVALENCE_V0_6.json`.

**Pendiente en S35 (calidad del OCR, no del segmentador):**

- El OCR pega al comienzo de cada línea basura del borde de la hoja: «_ 1.- BOLLES», «a 2.~ GREENWOOD». El marcador numerado queda fuera del inicio y varias referencias se funden o se pierden.
- Dos encabezados salen mal leídos: «bibliogr&ficas» en p. 21 y «Referencias bibliográficas: ae» en p. 221. Esas dos bibliografías no se detectan.

La corrección que corresponde es en `biblioref/ocr.py`: armar cada línea desde las palabras de Tesseract y descartar las palabras sin letras ni dígitos o de un solo carácter pegadas al borde. Eso exige subir la revisión del OCR y volver a correrlo (unos 30 min por tesis como esta).

## Actualización posterior (0.6.16 y 0.6.17)

- **0.6.16:** S29 y S35 se pasaron por el OCR de BiblioRef; ver «Tesis escaneadas».
- **0.6.17** sale de un caso externo de desarrollo, una tesis con bibliografía con viñetas que quedó en el benchmark como `X_RUSSO`. El detalle está en `reports/russo_external_case_regression.md`. En resumen:
  - las URLs partidas por el salto de línea se reúnen: 1.441 referencias de 112 tesis, solo espacios quitados, sin cambios de conteo;
  - los avisos falsos de borde de página bajan de 250 a 99 en el benchmark;
  - junto con el algoritmo cambiaron el parser (0.12.6: capítulos, «tesis» en el título, fechas con día y mes, «s/f») y la lectura del año de portada (v0.5.2).
- El resultado vigente del benchmark está en `benchmarks/consolidado_v0_1/result_v0_6_17.json`. Contra 0.6.15, los controles `stable_control` solo cambian por espacios quitados dentro de URLs.

## Problemas encontrados y dónde nacen

| # | patrón | etapa donde nace | casos |
|---|---|---|---|
| 1 | Un final de oración en minúscula («…no ha sido reportado en la / bibliografía.») se acepta como encabezado y abre una zona de prosa | detección de zona | S07, T0009 (p. 113), S20 (p. 85), T0117, T0121 |
| 2 | La portadilla «Bibliografía / y / Anexos» abre una zona que «Anexos» corta enseguida, y el encabezado real de la página siguiente se descarta como encabezado corrido repetido. La bibliografía entera queda sin zona | detección de zona (deduplicación de encabezados) | S20 |
| 3 | «REFERENCIAS» como celda de una tabla abre una zona | detección de zona | S94 |
| 4 | El estilo se diagnostica sobre un cuerpo que todavía incluye el anexo (listas numeradas). El recorte por densidad corta con ese estilo, y 10 líneas numeradas le ganan a 283 inicios autor-año. El margen de inicio queda mal y no se segmenta nada | detección de zona / diagnóstico de estilo | S20 |
| 5 | «Recuperado de: http://…», «Disponible en: …», «pareja. Recuperado de:», «00. Recuperado de:» y «de: http://…» coinciden con `NAMED_WEB_SOURCE_RX` («Nombre: URL») y abren registro. La regla «autor + recuperado de» abre con continuaciones como «Zeitschrift , 21 (3-43). Recuperado de www…». `deferred_author_year` abre con «Recuperado de: www…2011-2012.pdf» por el año de la URL | segmentación (estilo con viñetas) | S55, S74, T0104, T0123, T0136 |
| 6 | En listas `[n]` sin sangría francesa: «(2005) 1.» se lee como el marcador «(n)», y «Chem.184 (2002) 431.» abre registro por «palabra + año entre paréntesis» | segmentación (estilo `numeric`) | T0009 |
| 7 | «[1 ]-» (espacio dentro del corchete) no se reconoce como marcador y la primera referencia de la zona se pierde | segmentación (`NUMERIC_MARKER_RX`) | T0009 |
| 8 | Folios decorados «[303]», «- 24 -», «-105-» no se reconocen como pie. Se pegan a la última referencia de la página y además funcionan como pegamento entre dos referencias | extracción / decoraciones | S11, T0009, T0079 |
| 9 | Encabezado corrido a la altura del 12 % (fuera de la banda del 8 %) y palabras guía de diccionario «A/B» fundidas con la primera línea. Quedaban dentro de los registros y partían URLs entre páginas | extracción / decoraciones | S77 |

Las filas de NUEVAS_REFERENCIAS con `[4] … [5] … [6]` en una sola celda (T0009, salida 0.9.6 / algoritmo 0.6.2) ya no existen en la versión actual. Los marcadores `[n]` separan bien, y los problemas que quedaban en esa tesis eran los 6 y 7: fragmentación, no fusión. En ningún caso se tocó el parser.

## Código modificado

La arquitectura se mantiene: `PDF → extracción → zona → segmentación → selección → parser`. No se tocó el parser ni las capas de reparación de `biblioref/pipeline.py`.

- **`biblioref_v0_4.py`**, detección de zona (`detect_adaptive_layout_zones`):
  - `_is_prose_tail` (1): minúscula inicial, con la línea anterior del mismo párrafo sin puntuación final.
  - `_is_table_cell` (3): dos o más celdas cortas en la misma banda horizontal. El folio no cuenta.
  - `_is_divider_before` (2): entre dos encabezados iguales hay 3 líneas o menos, menos de 40 caracteres y ningún año. El anterior era una portadilla y queda el nuevo.
  - Rediagnóstico de estilo (4): si el estilo del cuerpo recortado difiere del que se usó para recortar, se vuelve a recortar desde el mismo cuerpo con el estilo correcto.
- **`biblioref_v0_4.py`**, estilo (`_demote_minor_numeric`): `numeric` cede cuando los marcadores son menos de un cuarto de los inicios autor-año, con al menos 20 de estos (4). T0056, el riesgo que señalaba el handoff, no se mueve: su zona principal no es numérica.
- **`biblioref_v0_4.py`**, segmentación:
  - `ACCESS_LABEL_RX` y `_is_named_web_source`: la etiqueta de una fuente web con nombre empieza en mayúscula y no es una frase de acceso (5).
  - `ACCESS_START_RX`: una línea que abre con «Recuperado / Disponible / Retrieved…» nunca abre registro (5).
  - `AUTHOR_THEN_NAME_RX`: después de la coma del apellido viene un nombre, no un número (5).
  - Un «marcador» entre 1500 y 2099 es un año (6).
  - `_continues_marked_entry` (6): mientras hay una entrada `[n]` abierta, una línea sin marcador solo abre registro si es «Apellido, I.». La guarda tiene estado: antes del primer marcador rigen las reglas autor-año de siempre. Así se corrigió una pérdida de recall en T0001 que apareció en la primera versión, sin estado.
- **`biblioref_v0_2.py`**: `NUMERIC_MARKER_RX` admite un espacio dentro del corchete o del paréntesis (7).
- **`biblioref_v0_3.py`**: `_is_footer` acepta folios con corchetes o guiones, no con paréntesis, porque «(12)» puede ser un marcador (8).
- **`biblioref_page_decorations.py`**:
  - `detect_running_headers` (9): el mismo texto a la misma altura, arriba de 3 páginas o más, sin año y con contenido debajo.
  - `strip_guide_words` (9): el prefijo «X/Y» de la primera línea, en 3 páginas o más.
- **`biblioref/core/config.py`**: `ALGORITHM_VERSION` pasa de 0.6.14 a 0.6.15. Se declara en `EXTRACTION_CORE_NONREGRESSION_V0615_SHA256.json`, con la equivalencia en `EXTRACTION_CORPUS_EQUIVALENCE_V0_5.json`: 147 documentos, 132 idénticos, 15 cambiados y listados.
- Tests de versión y el SHA del módulo base congelado se actualizaron igual que en las versiones 0.6.12 a 0.6.14.

## Tests agregados

Van en `tests_core/test_biblioref_v0_6_15_zone_guards.py`, con fixtures sintéticos de `LayoutLine`, sin nombres de tesis ni páginas reales. Cada bug tiene un test que falla antes del cambio y un control que debe seguir pasando.

| clase | qué prueba |
|---|---|
| `ProseTailIsNotAHeading` | Un final de oración no abre zona. Control: un encabezado en minúscula después de un párrafo cerrado sí abre |
| `DividerPageBeforeTheBibliography` | Portadilla más encabezado real. Control: el encabezado corrido de la página siguiente sigue deduplicándose |
| `TableCellIsNotAHeading` | Una celda de tabla no abre zona. Control: el encabezado con el folio en la misma banda sí abre |
| `AccessTailStaysWithItsReference` | Cinco variantes de cola, incluida la que cruza de página. Controles: una fuente web con nombre y «autor + recuperado de» siguen abriendo |
| `NumberedListContinuations` | Continuaciones `[n]`, «[1 ]», autor-año antes del primer marcador, `numeric` minoritario frente a autor-año, lista numerada con líneas autor-año |
| `DecoratedFolio` | Folios decorados. Controles: un marcador en el cuerpo, «(12)», una referencia `[12]` al pie |
| `DictionaryRunningHeader` | Encabezado y palabras guía. Control: «A/B testing…» en una sola página |
| `DeclarationTests` | Versión, archivos declarados, hashes y equivalencia de corpus |

## Mejoras

- **Rescate de bibliografía perdida:** S20 / T0026 pasa de 9 a 345. Otras primeras referencias recuperadas: S77 («Alonso»), T0009 («Basset, [1 ]»).
- **Contaminación narrativa y zonas falsas:** fuera en S07, S94, T0117 y T0121, sin tocar sus bibliografías reales.
- **Colas DOI/URL:** S55 8 → 0, S74 3 → 0, y colas de T0104, T0123 y T0136. El texto total no cambia: es re-segmentación.
- **Numeradas `[n]`:** T0009 pasa de 6 fragmentos a 0, y el conteo coincide con los marcadores.
- **Referencias partidas entre páginas o pegadas por decoraciones:** S11, S77, T0079 y T0009.

## Regresiones

**Ninguna en el estado final.** Estas regresiones intermedias se detectaron y corrigieron antes de cerrar:

| regresión | causa | corrección |
|---|---|---|
| S20 cayó a 7 registros | La guarda numérica sin estado, combinada con un estilo `numeric` mal diagnosticado | `_demote_minor_numeric` |
| T0001 perdía 3 referencias antes del primer marcador | La misma guarda sin estado | `_continues_marked_entry`, con estado |
| El control existente «encabezado corrido de una sola referencia por página» | El umbral de portadilla por caracteres | Condición sin años |
| El control «una referencia por página a la misma altura» | La normalización quitaba los dígitos al comparar encabezados | Texto idéntico con dígitos, sin año |

Dos fallas de la suite raíz no vienen de este cambio:

- `test_human_gold_openalex_candidates` falla igual en HEAD.
- `test_current_field_test_state` tiene una modificación local sin commitear que espera 0.6.13, y ya fallaba en HEAD, que está en 0.6.14. No se tocó.

## Problemas pendientes

1. **Tesis escaneadas:** S29 queda resuelta con el OCR (212). S35 queda parcial (27): hay que limpiar la basura de borde en `biblioref/ocr.py`, ver arriba. Convendría que el pipeline marcara «sin texto, pasar por OCR» en vez de «0 referencias». S44 no es un blind spot: el PDF es solo el resumen.
2. **Estado del arte titulado «Referencias»:** en S87 (p. 17-31) una zona de prosa con citas autor-año produce 11 registros narrativos. La detección de zona no distingue prosa densa en citas de una lista.
3. **Manual anexo con su propia lista:** en S32 (p. 156-162) siguen 5 registros de instrucciones numeradas.
4. **S20:** el último registro lleva pegado el comienzo de la lista del anexo, «Libros de AT editados…» (113 palabras).
5. **T0123:** la URL de «Recuperado de: …» sigue pegada a la referencia siguiente, «Edwards, A. (2010)», en la misma línea física. Ya estaba así en 0.6.14.
6. **UNR28 / UNR30:** sin PDF ni salida detallada, no se pudieron medir. La evidencia del Excel se limita a los conteos del resumen.
7. **Métricas:** los detectores de fusión y narrativa tienen falsos positivos (capítulos «En Autor (año)», referencias largas legítimas, apellidos con partícula «de Saussure»). Sirven para ordenar la revisión, no como verdad.

## Próximo cambio recomendado

**Distinguir prosa con citas de una lista de referencias dentro de una zona** (pendientes 2 y 3). La señal ortogonal es geométrica y de ritmo:

- una lista tiene inicios de registro regulares, con el año en la primera línea y sangría francesa o bloque;
- la prosa tiene sangría de primera línea de párrafo, líneas justificadas y citas «Autor (año)» a mitad de oración.

Conviene medirlo primero como diagnóstico, sin cambiar la salida: contar por zona la fracción de registros con cita en mitad de oración. Después, con esta misma batería y la equivalencia del corpus, decidir si esas zonas se descartan o se recortan. En paralelo, y fuera del algoritmo, marcar automáticamente las tesis sin capa de texto para que vayan a OCR.
