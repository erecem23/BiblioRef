# Release notes — BiblioRef 0.9.6 · APP 2.6.6 · Parser 0.7

- Restaura el contrato `author = primer autor`; `authors` conserva el bloque completo.
- Filtra marcadores de acceso antes de inferir año y amplía variantes ABNT conservadoras.
- Mejora tipos, títulos y recuperación de institución/editorial para tesis/disertaciones.
- Parser congelado pre-holdout: `099f62a1346c6055b8c17720676d643027070d62a1a0ab2f5448ed94a36a91b3`.
- Gold externo congelado: `863b1d3b03ff60ab9b4d9780d6d644fce52e665438d7e76c9a8f41bdf26099c8`.
- Holdout externo nuevo: 30 referencias de UFPE/UFSCar/UFC.
- v0.6→v0.7: autor 66,67→96,67%; título fuzzy 63,33→76,67%; tipo 73,33→86,67%; editorial 55,56→72,22%.
- Año permanece 100%; revista fuzzy permanece 54,55%.
- Transparencia: 2 regresiones pareadas de título; 0 regresiones en autor, año, tipo y editorial.
- `v07.py` no se modifica después del holdout; extractor PDF permanece congelado.
