# Release notes — StyleProfiler v0.1-shadow

Integrado sobre BiblioRef v0.9.8 + APP v2.6.9 + parser v0.11 candidate.

- Nueva capa analítica downstream `biblioref/styleprofiler/`.
- No modifica extracción ni parser.
- Features estructurales explicables por referencia.
- Perfil por zona con `family`, `likely_style`, `variant`, `mixed_style`, `consistency` y `evidence`.
- `unknown` es resultado de primera clase.
- `legacy_year_final` se conserva como variante observable; no se fuerza a APA/ABNT/Chicago/etc.
- País, institución, disciplina y año documental quedan como contexto y nunca participan en la decisión de v0.1.
- No se muestran probabilidades falsas: `confidence=null` hasta disponer de un clasificador calibrado.
- JSON sidecar disponible desde la APP.
- Palma (322 referencias): `family=author_year`, `likely_style=unknown`, `variant=legacy_year_final`, consistencia estructural 1.0.
- Suite completa integrada: 527 passed, 3 skipped, 16 subtests passed.

Pendiente para fases posteriores: corpus de descubrimiento, clustering HDBSCAN/agglomerative/k-means/DBSCAN, gold set y clasificación calibrada. Ninguna de esas fases debe retroalimentar extracción/parsing sin una decisión arquitectónica futura explícita.
