# Release notes — BiblioRef 0.9.7 · APP 2.6.8 · Parser 0.9

- Extractor 0.9.7, algoritmo efectivo 0.6.3. Motor estable 0.4.5, capa adaptativa y router sin cambio. Parser downstream v0.9 sin cambio.
- El separador de la numeración de capítulo en un encabezado acepta ahora todo el bloque Unicode de guiones. `IV–5-BIBLIOGRAFÍA.` se reconoce igual que `IV-5- BIBLIOGRAFÍA.`. El anclaje `re.fullmatch` sobre el encabezado despojado de prefijo no se relajó.
- Un marcador numérico pegado a un guión (`[1]-Autor`, `[23]- Autor`, `7.-Autor`) cuenta como arranque de referencia numerada. Antes exigía espacio, el estilo caía en autor-año y las referencias se fusionaban de a cuatro a once por registro.
- Los catorce módulos de zonas, segmentación, fronteras, rescates y auditoría son byte a byte idénticos a v0.9.6.
- No-regresión: dos tesis reales de 300 y 449 páginas dan `records + zones` con SHA-256 idéntico entre v0.9.6 y v0.9.7; las 752 líneas bibliográficas auténticas de los fixtures dan el mismo perfil de estilo y el mismo resultado línea a línea.
- Batería completa: 491 tests pasan, 3 saltados, 16 subtests.
- Sobre el documento que motivó la versión: 2 zonas / 5 registros → 6 zonas / 72 registros, sobre 147 referencias reales.
- Limitación conocida y medida: las zonas se siguen cerrando en su primera página porque el encabezado corrido de capítulo actúa como corte estructural. Ver el informe de desarrollo.
- `biblioref_v0_2.py` SHA-256: `8683e68c23773f113b27cb2453b48d7539c1ca9147d470baaf1de306d6d775fa`.
