# Release notes — BiblioRef 0.9.8 · APP 2.6.9 · Parser 0.10

- **Extractor 0.9.8 / algoritmo 0.6.4.** Se incorpora una segunda pasada efectiva de reconciliación de fronteras entre segmentación y parsing.
- **Parser v0.10 queda congelado.** No se modifican sus reglas ni su schema.
- La nueva pasada sólo actúa en zonas autor-año con sangría francesa fuerte y un gate conservador de geometría, evidencia bibliográfica, tamaño de segmento y magnitud del cambio.
- Ya no exige que todo comienzo pueda describirse como `Apellido, Inicial. (año)`: un comienzo físico puede ser confirmado por el layout y por evidencia local en las líneas siguientes.
- Caso de desarrollo: 310 → **338** registros. Recupera 37 comienzos físicos y elimina/desplaza 9 fronteras previas; cambio neto +28.
- Recupera la primera referencia `5G Américas. (2016)...` y separa múltiples referencias institucionales o con año en la segunda línea.
- La tesis de desarrollo no constituye validación externa ni ground truth independiente.
- Batería: **515 passed, 3 skipped, 16 subtests passed**.
- Pendiente downstream detectado: parser v0.10 transforma el autor `5G Américas` en `G Américas`; no se modifica en esta release.
