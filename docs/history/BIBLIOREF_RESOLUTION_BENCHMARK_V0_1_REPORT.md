# BiblioRef — Resolution Benchmark v0.1

Fecha de validación: 2026-09-05/06  
PR: #9 — `Resolution benchmark v0.1: real-work gold, calibration and audit export`  
Benchmark live final ejecutado sobre: `13dc6090b154140236879e8b3d958ae6f9a9a0c7`  
Workflow run: `34001343854`  
Artifact: `resolution-benchmark-v0-1` (`9979629992`)  
SHA-256 del artifact ZIP: `73aeaf3b9e4be27ed157165c111a7b7f84dc21d9a7f189e383c56e675f7d8cd9`

## 1. Objetivo

Evaluar la cadena de resolución bibliográfica de BiblioRef sobre obras reales e identificables, comparar el aporte incremental de Crossref, OpenAlex y la capa semántica local, detectar falsos positivos de alta confianza y obtener una primera evidencia empírica para calibrar `ResolutionDecision`.

Este benchmark no modifica la extracción ni el parser. Trabaja exclusivamente sobre la capa downstream de resolución.

## 2. Gold v0.1

El gold abierto contiene 12 obras académicas reales con DOI distribuidas entre psicología, psicometría, machine learning, NLP, computer vision y ciencias de la vida. Se incluyen trabajos como Cohen (1992), Miller (1956), Bandura (1977), Baron y Kenny (1986), Cronbach (1951), BERT, Random Forests, UMAP, ResNet y AlphaFold.

El corpus privado de Cabrera usado previamente para validar el parser no se incorporó: el PDF y sus 158 referencias no están versionados en el repositorio y no corresponde reconstruirlos ni inventar un gold a partir de información incompleta.

Archivo versionado: `benchmarks/resolution_gold_v0_1.jsonl`.

## 3. Construcción de casos

Para cada DOI del gold se recuperan primero metadatos canónicos mediante una resolución DOI de Crossref. A partir de esos metadatos se generan de forma determinística tres variantes de consulta:

- `clean`: título, autores, año y revista/contenedor;
- `title_year`: título y año;
- `short_title`: título truncado de forma determinística, primer autor y año.

Total: 12 obras × 3 variantes = 36 casos.

El DOI objetivo nunca se entrega a las consultas evaluadas. El DOI se usa únicamente como etiqueta gold y para obtener el registro canónico que permite construir las variantes.

## 4. Comparación de capas

Se evalúan tres configuraciones de recuperación:

1. Crossref solo;
2. OpenAlex solo;
3. Crossref + OpenAlex.

Cada configuración recupera su `CandidateBatch` una sola vez. Sobre ese mismo conjunto de candidatos se calculan dos decisiones:

- `deterministic`: consenso + `ResolutionDecision`, sin embeddings;
- `with_semantic`: exactamente los mismos candidatos + `SemanticResolver` + `ResolutionDecision`.

Esto permite atribuir la diferencia a la capa semántica y no a variaciones entre llamadas sucesivas a APIs externas.

## 5. Métricas

Se registran:

- `candidate_recall_at_returned`;
- `selection_accuracy`;
- `selection_precision`;
- `auto_verified_coverage`;
- `auto_verified_precision`;
- `false_verified_count`;
- `review_required_rate`;
- `unresolved_rate`;
- `possible_rate`.

`VERIFIED_EXACT`, `VERIFIED_EXTERNAL_CONSENSUS` y `VERIFIED_SEMANTIC` cuentan como auto-verificados. `POSSIBLE_MATCH` y `AI_SUPPORTED_MATCH` no se tratan como verificación automática.

## 6. Resultados finales

| Capa | Semántica | Recall candidatos | Accuracy selección | Precision selección | Cobertura auto-verificada | Precision auto-verificada | Falsos VERIFIED | Revisión requerida |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Crossref | no | 69.44% | 66.67% | 100% | 0% | — | 0 | 100% |
| Crossref | sí | 69.44% | 69.44% | 96.15% | 58.33% | 100% | 0 | 41.67% |
| OpenAlex | no | 100% | 52.78% | 100% | 0% | — | 0 | 100% |
| OpenAlex | sí | 100% | 88.89% | 96.97% | 50.00% | 100% | 0 | 50.00% |
| Crossref + OpenAlex | no | 100% | 94.44% | 100% | 83.33% | 100% | 0 | 16.67% |
| Crossref + OpenAlex | sí | **100%** | **100%** | **100%** | **94.44%** | **100%** | **0** | **5.56%** |

La configuración combinada con semántica resolvió correctamente los 36/36 casos. Dos casos quedaron correctamente seleccionados pero deliberadamente no auto-verificados y requieren revisión: `psych_positive_2000:title_year` y `ml_umap_2018:title_year`.

## 7. Hallazgo crítico: falso consenso UMAP

Una corrida anterior a la corrección detectó un falso `VERIFIED_EXTERNAL_CONSENSUS` para `ml_umap_2018:title_year`.

Gold esperado:

`10.21105/joss.00861`

Candidato incorrectamente verificado:

`10.32614/cran.package.umap`

Crossref y OpenAlex coincidían en el registro del paquete R `umap`, mientras existía simultáneamente otra identidad cross-source correspondiente al artículo JOSS. La regla previa interpretaba la coincidencia de dos fuentes como evidencia suficiente aun cuando hubiera identidades cross-source rivales con evidencia cercana.

### Corrección

`ConsensusEngine` pasa a `metadata-consensus-v0.2` e incorpora:

- `EXTERNAL_CONSENSUS_MIN_EVIDENCE = 0.78`;
- `EXTERNAL_CONSENSUS_MIN_GROUP_MARGIN = 0.10`;
- comparación del grupo cross-source líder contra el grupo rival más fuerte;
- si dos identidades cross-source compiten dentro del margen, el estado pasa a `ambiguous_conflict`;
- nota auditable: `competing_cross_source_identities_prevent_auto_consensus`.

Después de la corrección, la capa combinada determinística y la combinada + semántica quedaron ambas con **0 falsos `VERIFIED_*`**. El caso UMAP se degrada correctamente a revisión en vez de auto-verificarse.

## 8. Aporte de la capa semántica

Sobre Crossref + OpenAlex, mantener exactamente los mismos candidatos y agregar semántica produjo:

- accuracy de selección: 94.44% → 100%;
- cobertura auto-verificada: 83.33% → 94.44%;
- precision auto-verificada: 100% → 100%;
- falsos `VERIFIED_*`: 0 → 0;
- revisión requerida: 16.67% → 5.56%.

Por lo tanto, dentro de este gold la capa semántica agrega cobertura y reduce revisión sin degradar la precisión de las decisiones auto-verificadas.

## 9. Calibración preliminar del umbral semántico

La calibración se restringió exclusivamente a los 47 casos evaluados con `consensus.status == probable_candidate`, porque `verified_semantic_threshold` sólo puede modificar la promoción `probable_candidate → VERIFIED_SEMANTIC`. Los estados ya resueltos por DOI o consenso externo no participan del cálculo.

| Umbral | Cobertura VERIFIED_SEMANTIC | Precision | Falsos VERIFIED |
|---:|---:|---:|---:|
| 0.70 | 95.74% | 100% | 0 |
| 0.74 | 95.74% | 100% | 0 |
| 0.78 | 93.62% | 100% | 0 |
| 0.82 | 91.49% | 100% | 0 |
| 0.86 | 91.49% | 100% | 0 |
| 0.90 | 91.49% | 100% | 0 |
| 0.94 | 85.11% | 100% | 0 |

El criterio programado propone **0.74** como candidato in-sample: máxima cobertura con cero falsos `VERIFIED_SEMANTIC` dentro de este conjunto.

### Decisión de v0.1

**No se modifica el valor productivo/default de 0.82.**

Razones:

1. el gold todavía es pequeño: 12 obras / 36 variantes;
2. las variantes derivan de metadatos canónicos y no constituyen un holdout externo totalmente independiente;
3. 0.74 es un óptimo in-sample, no una probabilidad ni un umbral calibrado estadísticamente para producción;
4. con 0.82 la configuración Crossref + OpenAlex + semántica ya alcanza 94.44% de cobertura auto-verificada y 100% de precisión auto-verificada en este benchmark.

`0.74` queda registrado como **candidato a evaluar en un holdout independiente**.

## 10. Auditoría y exportación

Se agregó una proyección de sidecars de resolución mediante:

- `resolution_audit_columns(batch, decision)`;
- `attach_resolution_columns(records, sidecars)`.

La proyección expone estado, método, necesidad de revisión, candidato seleccionado, DOI/título/año de ese candidato, evidencia, warnings y versiones de las capas. Es una vista: no reescribe el parser ni duplica la autoridad de los metadatos.

Los exportadores de auditoría aceptan una tabla de resolución opcional y pueden generar:

- hoja `Resolution` en XLSX;
- `resolution_decisions.csv` dentro del audit bundle;
- conteos por estado y número de casos que requieren revisión en `processing_report_audited.json`.

La aplicación principal todavía no activa automáticamente llamadas de red al resolver. Esta separación es intencional: la UI/pipeline no debe adquirir dependencia silenciosa de Crossref, OpenAlex, modelos o conectividad.

## 11. Validación de código

Sobre el head que incorpora la corrección del consenso:

- resolver/benchmark/auditoría focalizados: **68 passed**;
- suite completa: **698 passed**;
- skipped: **3**;
- failed: **0**;
- subtests: **16 passed**;
- Crossref smoke: PASS;
- OpenAlex smoke: PASS.

El benchmark semántico live se mantiene como workflow manual y no bloqueante para no instalar el stack pesado de SentenceTransformers/PyTorch en cada PR ni convertir el core offline en una dependencia de servicios/modelos externos.

## 12. Limitaciones

- El gold v0.1 es deliberadamente pequeño y no sustituye un benchmark externo de tesis reales.
- Las tres variantes se generan a partir de registros canónicos; sirven para pruebas controladas de degradación, no para estimar por sí solas rendimiento poblacional.
- No se evaluó Ollama/`LocalAIAdjudicator` en CI, porque el backend está diseñado como local-only. El rendimiento del adjudicador requiere un benchmark local separado.
- La cobertura de Crossref varió entre corridas live, lo que confirma la necesidad de conservar métricas de recuperación separadas de las métricas de decisión.
- Un candidato semántico incorrecto puede seguir aparecer como `POSSIBLE_MATCH`; esto es compatible con el diseño porque requiere revisión y no cuenta como verificado.

## 13. Conclusión

El benchmark v0.1 valida la arquitectura por capas y, sobre todo, demuestra el valor de mantener estados de evidencia explícitos. El proceso no sólo midió rendimiento: encontró un falso consenso realista que habría producido una verificación incorrecta y permitió corregir la regla general sin hardcoding para UMAP.

La mejor configuración observada fue Crossref + OpenAlex + semántica, con 36/36 selecciones correctas, 94.44% de cobertura auto-verificada, 100% de precisión auto-verificada y cero falsos `VERIFIED_*` en el gold v0.1.

El siguiente paso de calibración debe ser un holdout externo e independiente, manteniendo 0.82 como umbral conservador hasta contar con esa evidencia.
