# T0145: libro escaneado con el margen corrido (algoritmo 0.6.20)

## El caso

T0145 (Baumgart, *Ataque de pánico y subjetividad*, UBA 2001) es un libro de la
colección «Tesis de doctorado» de Filosofía y Letras, escaneado con su propia
capa de OCR. La bibliografía ocupa las páginas 81 a 85, con unas cien entradas.
Con 0.6.19 salían **19 referencias y 72 posibles faltantes**. T0137 es el mismo
PDF cargado otra vez.

## Por qué

1. **Viñetas que no son viñetas.** El OCR del escaneo leyó cada «———» (autor
   repetido) como «·». Con 19 líneas que empiezan con «·», `diagnose_style`
   eligió `bulleted` aunque 75 líneas abrieran con «Apellido, N.», y se cortaba
   solo en las «viñetas».
2. **El margen de inicio caía en las continuaciones.** El año cierra cada
   entrada, así que los renglones con año son continuaciones («DC, APA, 1987.»,
   «Universidad Complutense de Madrid, 1992.») y fijaban el margen de la página
   una sangría a la derecha: cada referencia arrancaba con el último renglón de
   la anterior.
3. **El margen cambia por página y una página está torcida.** Inicios en x≈7
   (p. 81), x≈98→77 (p. 82, torcida) y x≈24 (p. 83).

Rehacer el OCR con BiblioRef no cambia nada de esto (20 referencias, 70
faltantes): el problema es la segmentación, no el texto.

## Cambios

- `biblioref_v0_2.py`, `_demote_unsupported_marker`: con cuatro o más viñetas,
  el estilo `bulleted` pierde si hay el triple de inicios de autor. En una lista
  con viñetas real el nombre va después de la viñeta y casi no hay inicios
  «Apellido, N.» sueltos.
- `biblioref/detection/signals.py`, `local_hanging_starts`: en una página donde
  la geometría no coincide con el margen de inicio (corrida una sangría, o con
  los inicios desparramados más que la tolerancia), abre entrada el renglón que
  no tiene otro más a la izquierda cerca (±80 pt) y sí una continuación sangrada
  (14–60 pt a la derecha). Solo se activa si esos renglones abren como entradas
  («Apellido, N.» o «· (año)»): al menos el 60 %. `page_start_margins` devuelve
  un `PageMargins` con esas páginas y `enhanced_start` las respeta.

## Resultado

| | 0.6.19 | 0.6.20 |
|---|---|---|
| T0145 referencias | 19 | 72 |
| T0145 posibles faltantes | 72 | 9 |

Quedan errores que vienen del orden de la capa de texto original (por ejemplo
«Freud, disorder in the Unites States…», donde el OCR del escaneo mezcló dos
renglones).

## No regresión

- Corpus (contrato de `tools/extraction_corpus_equivalence.py`, en paralelo):
  149 documentos comparables, 146 idénticos, 3 cambiados: T0145 y T0137
  (19 → 72) y T0073 (321 → 320), una zona de conclusiones en prosa que ya se
  tomaba mal como bibliografía antes y después. T0150 no estaba en la línea de
  base. Declarado en `EXTRACTION_CORE_NONREGRESSION_V0620_SHA256.json` y
  `EXTRACTION_CORPUS_EQUIVALENCE_V0_10.json`.
- Benchmark consolidado (`benchmarks/consolidado_v0_1/result_v0_6_20.json`):
  idéntico a 0.6.19 en los 24 casos comparables, incluido el control con viñetas
  reales X_RUSSO.
- Tests: `tests_core` 567 y raíz 810 pasan.

## Descartado

Heredar el autor en «· (1896):» cuando el marcador se perdió (parser): en el
corpus solo se activa en este libro y en siete referencias de T0092, T0079 y
T0123 a las que la extracción les cortó el autor. Incluso en T0145 heredaría
«Da Costa» en las obras de Freud, porque la entrada «Freud, S.: …» quedaba
pegada a la de Da Costa.
