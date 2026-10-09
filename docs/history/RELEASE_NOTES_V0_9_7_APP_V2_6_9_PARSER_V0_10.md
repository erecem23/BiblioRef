# Release notes — BiblioRef 0.9.7 · APP 2.6.9 · Parser 0.10

- Parser downstream v0.10, schema 10. Extractor 0.9.7 y algoritmo 0.6.3 sin cambio; `biblioref_v0_2.py` conserva su hash congelado.
- **Número de revista sin volumen.** `Comunicar, (38), 51-58` y `Revista Cepal, (119), 89-107` ahora recuperan la revista. Todos los patrones previos exigían un dígito de volumen antes del paréntesis. La ruta pide número de página o de artículo después, y limita el número a tres dígitos para que un año entre paréntesis no pueda leerse como número de revista.
- El punto interno de un nombre como `Edutec. Revista electrónica de tecnología educativa` nunca fue el problema: con volumen presente ese nombre ya se recuperaba entero.
- **Imprenta después de lugar y país.** `Santiago de Chile, Chile: Divergente.` La editorial se acepta por el nombre de país que la precede, tomado de una lista cerrada, y no por figurar en el léxico de editoriales. Recupera `UNAE`, `Godot`, `ZEMOS98`, `Outliers School`, `World Health Organization` y similares.
- Corrección derivada: un nombre de revista mal partido que había quedado como editorial (`Iberoamericana`, `Docencia`, `CLAD`, `Feminaria`) se limpia cuando la revista se recupera entera. Trece casos, todos correcciones.
- Corpus objetivo, 310 referencias: revista 103 → 142, editorial 101 → 125, `sin_clasificar` 42 → 8, con 0 revistas reescritas.
- Regresión: el corpus de desarrollo de parsers (190 referencias) queda idéntico campo por campo, 0 mejoras y 0 regresiones. Barrido histórico de 29.027 filas: 0,76 % de filas modificadas, 165 revistas agregadas, 0 eliminadas, 0 modificadas, 87 coincidencias nuevas con la etiqueta curada y ninguna que se aleje.
- Batería completa: 510 tests pasan, 3 saltados, 16 subtests.
- **Sin validación externa.** La tesis que motivó la versión se inspeccionó para diagnosticarla.
- Parser SHA-256: `56993eed5a0c032e9c52495eb721a2cc8ecde73ca3ad0cefd9d1fb0d152d17f2`.
