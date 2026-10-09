# Release notes — BiblioRef 0.9.6 · APP 2.6.8 · Parser 0.9

- Parser downstream v0.9, schema 9. Extractor 0.9.6 sin cambios: el núcleo de extracción verifica el mismo SHA-256 que en la release de v0.8.
- Nueva frontera del bloque de autores ABNT por recorrido de gramática en lugar de búsqueda del primer punto. Cubre iniciales múltiples, iniciales sin punto antes de `;`, partículas, pérdida de puntuación entre autores, listas con `&`, `et al.` y apellido con iniciales sin coma.
- El contenedor de fuente considera metadatos de periódico posteriores al año de publicación.
- Limpieza del candidato de revista: metadatos compactos sin `v.`/`n.`/`p.`, entidad editora pegada al nombre, lugar de publicación pegado con coma o punto, y fin de la poda de segmentos que forman parte del nombre.
- Ruta nueva de rescate de revista APA para bloques de volumen no numéricos (`7(MAR)`, `43, e25314`, `19.`, `(online)`), condicionada a evidencia de publicación periódica y a la ausencia de evidencia de monografía, capítulo o tesis.
- Desarrollo y regresión sobre las 190 referencias ya quemadas: autor 92,63 % → 99,47 %, autores 86,25 % → 98,75 %, título fuzzy>=.90 92,11 % → 97,89 %, revista fuzzy>=.90 79,73 % → 100 %, tipo 93,68 % → 95,26 %. **0 regresiones en todos los campos.**
- Sobre el stress set de v0.8, que fue el material de diagnóstico: revista fuzzy>=.90 0 % → 100 % y autor 65 % → 100 %.
- Barrido estructural de 29.027 filas históricas: 1,24 % de filas modificadas, 360 revistas agregadas, 0 eliminadas, 0 modificadas.
- **Sin validación externa.** Los dos holdouts de v0.8 se abrieron para diagnosticar esta versión. `evaluate_parser_v09_external_holdout.py` queda listo para un gold nuevo congelado.
- Parser SHA-256: `4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320`.
