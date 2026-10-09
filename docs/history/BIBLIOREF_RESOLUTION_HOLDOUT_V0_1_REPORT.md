# BiblioRef — Resolution Holdout v0.1

**Fecha de evaluación:** 2026-09-06  
**Rama:** `feature/resolution-holdout-v0-1`  
**Base congelada previa a observar el holdout:** `dev@58bf2bab069357ede0390bd1f30367cd339eeaee`  
**Parser:** `biblioref-parser-v0.12.5`  
**Resolver:** Crossref + OpenAlex + `metadata-consensus-v0.2` + SemanticResolver opcional  
**Umbral productivo congelado antes del holdout:** `verified_semantic_threshold=0.82`  
**Challenger pre-registrado:** `0.74`

## 1. Objetivo

Evaluar la generalización del sistema de resolución bibliográfica en un corpus que no haya intervenido en el desarrollo de reglas, consenso ni umbrales.

El benchmark v0.1 anterior utilizaba 12 obras reales y variantes generadas desde sus metadatos canónicos. Fue útil para desarrollo y permitió descubrir el caso UMAP, pero no era un holdout independiente. Esta evaluación cambia la fuente de la consulta: la entrada proviene de referencias bibliográficas **depositadas por trabajos citantes independientes**.

La pregunta principal es doble:

1. ¿Mantiene BiblioRef una política segura de auto-verificación fuera del conjunto de desarrollo?
2. ¿Existe evidencia externa para reemplazar el umbral conservador `0.82` por el candidato in-sample `0.74`?

## 2. Diseño del holdout

Se preseleccionaron 13 trabajos citantes heterogéneos mediante DOI, incluyendo documentación científica en español/REDC, educación latinoamericana, open science, psicología metodológica, investigación de datos, comunicación científica, cienciometría, biomedicina y métodos computacionales.

Para cada trabajo fuente:

1. se obtuvo su lista de referencias depositada en Crossref;
2. se seleccionaron como máximo tres referencias con DOI identificable y texto bibliográfico utilizable;
3. el DOI del target quedó exclusivamente como etiqueta `expected_doi`;
4. el texto observado se tomó de `unstructured` cuando estaba disponible o, en su defecto, de campos bibliográficos depositados por el trabajo citante;
5. se eliminaron DOI y URL antes de entregar la cita a BiblioRef;
6. el parser v0.12.5 procesó únicamente ese `query_reference` sanitizado;
7. no se inyectaron título, año, autores ni otros metadatos canónicos del target;
8. se excluyeron explícitamente los 12 DOI del gold de desarrollo `resolution_gold_v0_1.jsonl`;
9. los target DOI se deduplicaron globalmente entre trabajos fuente.

Así, el identificador esperado sirve para evaluar la respuesta, pero no para construir la consulta.

## 3. Disciplina de evaluación

El código del resolver, `metadata-consensus-v0.2` y los umbrales `0.82` y `0.74` quedaron congelados antes de observar el resultado externo.

La primera ejecución del workflow (`34002070419`) **no llegó a cosechar ni evaluar el holdout**: la suite se detuvo en collection porque ese workflow no instalaba `pandas`. La corrección posterior agregó exclusivamente dependencias de test (`pandas` y `httpx2`). Por lo tanto, no hubo acceso a resultados externos antes de corregir la infraestructura.

La primera ejecución que efectivamente cosechó y evaluó referencias fue:

- **run:** `34002206395`
- **artifact:** `9979865558`
- **SHA-256 del ZIP artifact:** `d32bbb436e9cb7ed714abd45a6ffcca77fb939aeaa598cba98c94b36483f754a`

El artifact exacto se congeló después en el repositorio. Los hashes son:

- `benchmarks/resolution_holdout_v0_1_frozen.jsonl`: `6556b1b1d2c09c51d4181bccb81c594fd79d2aa215ee4428a0808169dc112ec2`
- `benchmarks/evidence/resolution_holdout_v0_1/results.json`: `3f17e95268f5f0cb67f095b5560ea3164b94ce97c0bd199bc691b2c56d9fc5c9`
- `benchmarks/evidence/resolution_holdout_v0_1/summary.txt`: `619421339823f4fa8696747039d3479cac24f747b500b7f5d0f9ad6b3f9c864e`

El workflow posterior quedó en modo `workflow_dispatch` y usa el JSONL congelado; ya no vuelve a reconstruir el corpus.

## 4. Corpus obtenido

De los 13 trabajos fuente preseleccionados, 11 aportaron al menos una referencia elegible. Dos no aportaron referencias que cumplieran simultáneamente los criterios de DOI gold y texto utilizable:

- `mx_rosenberg_2022` — `10.15174/au.2022.3441`
- `arg_health_2022` — `10.19136/hs.a21n1.4509`

El holdout final contiene **31 referencias reales y únicas**.

Distribución de fuentes aportantes:

- REDC/documentación científica en español: 4 casos;
- educación latinoamericana: 3;
- open science: 3;
- psicología metodológica: 3;
- research data: 3;
- scholarly communication: 3;
- scientometrics: 6;
- life science: 3;
- computational biology/methods: 3.

Controles de fuga posteriores al congelamiento:

- 31/31 consultas sin DOI;
- 31/31 consultas sin URL;
- 0 target DOI solapados con el gold v0.1 de desarrollo;
- hash del JSONL local idéntico al hash declarado por la corrida.

## 5. Integridad del software

En la corrida efectiva del holdout:

- tests focalizados de holdout: **4 passed**;
- suite completa: **702 passed**;
- **3 skipped**;
- **0 failed**;
- **16 subtests passed**.

No se modificaron extracción, segmentación ni parser para esta evaluación.

## 6. Resultado principal

### 6.1 Recuperación de candidatos

El DOI correcto apareció entre los candidatos devueltos en **30/31 casos = 96,77%**.

Este resultado separa dos problemas: la recuperación externa tiene cobertura alta, mientras que la conversión de esos candidatos en una decisión automática sigue siendo mucho más conservadora.

### 6.2 Resolución determinística, sin señal semántica

| Métrica | Resultado |
|---|---:|
| Casos | 31 |
| Candidate recall | **96,77%** |
| Selection accuracy | **16,13%** |
| Selection precision | **62,50%** |
| Auto-verified coverage | **16,13%** |
| Auto-verified precision | **100%** |
| False `VERIFIED_*` | **0** |
| Review required | **83,87%** |
| Unresolved | **74,19%** |
| Possible match | **9,68%** |

La señal más importante para seguridad es que los cinco casos auto-verificados fueron correctos: **0 falsos `VERIFIED_*`**.

La señal más importante para utilidad es la contraria: sólo 5/31 casos quedaron auto-verificados y 23/31 quedaron sin resolver.

## 7. Comparación 0.82 vs 0.74

La comparación se hizo sobre exactamente los mismos candidatos y embeddings.

| Métrica | 0.82 | 0.74 |
|---|---:|---:|
| Candidate recall | 96,77% | 96,77% |
| Selection accuracy | 16,13% | 16,13% |
| Selection precision | 62,50% | 62,50% |
| Auto-verified coverage | 16,13% | 16,13% |
| Auto-verified precision | 100% | 100% |
| False `VERIFIED_*` | 0 | 0 |
| Review required | 83,87% | 83,87% |
| Casos cuya decisión cambió | **0** | **0** |

**Resultado:** bajar `verified_semantic_threshold` de 0.82 a 0.74 no cambió una sola decisión.

Por lo tanto, el óptimo in-sample 0.74 del benchmark de desarrollo **no se reproduce como mejora en este holdout**. No existe evidencia externa para bajar el umbral productivo.

**Decisión: mantener `0.82`.**

## 8. Diagnóstico de la brecha de generalización

La distribución de estados de consenso en los 31 casos fue:

- `ambiguous_conflict`: **19/31 = 61,29%**;
- `external_consensus`: **5/31 = 16,13%**;
- `unresolved`: **4/31 = 12,90%**;
- `probable_candidate`: **3/31 = 9,68%**.

La distribución final de decisiones fue:

- `UNRESOLVED`: **23/31 = 74,19%**;
- `VERIFIED_EXTERNAL_CONSENSUS`: **5/31 = 16,13%**;
- `POSSIBLE_MATCH`: **3/31 = 9,68%**.

Los tres casos `probable_candidate` terminaron como `POSSIBLE_MATCH`, y en los tres la señal semántica discrepó con el líder determinístico (`semantic_leader_disagrees_with_consensus_leader`). Ninguno fue promovido a `VERIFIED_SEMANTIC`, con 0.82 ni con 0.74.

Los tres `POSSIBLE_MATCH` seleccionaron un DOI incorrecto, pero permanecieron correctamente marcados como **requieren revisión** y nunca fueron contados como verificados. Esta distinción es esencial: un candidato sugerido puede equivocarse; un `VERIFIED_*` no debería hacerlo.

### 8.1 Parser sobre las citas depositadas

En las consultas reales sanitizadas:

- año recuperado: **31/31 = 100%**;
- autores disponibles en parse: **23/31 = 74,19%**;
- título recuperado: **19/31 = 61,29%**;
- DOI recuperado desde la consulta: **0/31**, como exige el control anti-fuga.

Por tanto, parte de la caída frente al benchmark de desarrollo está asociada a citas más compactas/heterogéneas en las que el parser no siempre ofrece un título estructurado. Sin embargo, el hecho de que el target correcto esté entre candidatos en 30/31 indica que el problema inmediato no puede reducirse a candidate generation.

## 9. Interpretación

El holdout revela una diferencia importante entre **seguridad** y **cobertura**.

La arquitectura actual es segura bajo esta muestra: auto-verifica poco, pero lo que auto-verifica es correcto. Al mismo tiempo, es demasiado conservadora para explotar la alta cobertura de candidatos: el target correcto casi siempre está disponible, pero las reglas de consenso/decisión lo dejan frecuentemente en conflicto.

Esto también redefine el papel de la semántica. En el gold de desarrollo, SemanticResolver aumentó la selección y la cobertura auto-verificada. En este holdout independiente, **su valor incremental fue 0 decisiones** bajo la arquitectura actual. El resultado no demuestra que los embeddings no aporten información; demuestra que el umbral `verified_semantic_threshold` no es el cuello de botella en este corpus, porque la mayoría de los casos nunca llega a un estado susceptible de ser promovido por ese umbral.

## 10. Veredicto

1. **El gate de seguridad pasa:** 0 falsos `VERIFIED_*` en 31 referencias reales.
2. **El recall de candidatos es fuerte:** 96,77%.
3. **La cobertura automática no generaliza al nivel del benchmark de desarrollo:** 16,13% auto-verificado frente a 94,44% del gold controlado previo.
4. **No bajar 0.82 a 0.74:** el challenger produjo exactamente 0 cambios.
5. **No reajustar ahora el resolver usando este holdout.** El corpus queda congelado como evaluación externa y no se convierte retroactivamente en conjunto de entrenamiento.

## 11. Próximo ciclo de desarrollo recomendado

El siguiente trabajo debe realizarse sobre un **nuevo conjunto de desarrollo**, distinto de este holdout, y atacar la transformación `candidate set → consensus/decision`, no la mera búsqueda de candidatos.

Prioridades empíricas:

1. estudiar por qué múltiples identidades cross-source forman `ambiguous_conflict` aun cuando el target correcto está presente;
2. medir ranking del target dentro del candidate set y margen de evidencia entre target y rivales;
3. mejorar la interpretación de citas compactas donde el parser no recupera título, sin usar reglas específicas de las 31 referencias congeladas;
4. evaluar una política semántica que pueda resolver conflictos bajo condiciones adicionales de evidencia, en vez de limitarse a bajar un threshold;
5. desarrollar y calibrar esa política en un nuevo dev set;
6. finalmente volver a ejecutar **sin modificar** este holdout para medir generalización.

El holdout v0.1 pasa a funcionar como **test externo bloqueado**, no como fuente de reglas.

## 12. Limitaciones

- N=31 sigue siendo pequeño para estimar errores raros con precisión estrecha.
- Sólo se incluyen referencias con DOI depositado, porque el DOI se utiliza como ground truth de identidad.
- Las citas provienen de metadatos de referencias depositadas por trabajos citantes en Crossref; no son líneas extraídas directamente de PDFs de tesis.
- Sólo 11 de 13 fuentes preseleccionadas aportaron casos elegibles.
- Crossref/OpenAlex son servicios live y sus candidate sets pueden cambiar en futuras re-evaluaciones; por eso las consultas y gold se congelaron y la corrida original se preservó con hash.
- El holdout evalúa identificación/resolución bibliográfica; no sustituye los benchmarks de extracción y segmentación de BiblioRef.
