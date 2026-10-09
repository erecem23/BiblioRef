# BiblioRef ResolutionDecision v0.1

## Objetivo

Unificar las señales de resolución bibliográfica ya disponibles en BiblioRef (consenso determinístico, similitud semántica y adjudicación IA local opcional) en una salida final auditable, sin mutar el parser ni sobrescribir metadatos externos.

## Estados

- `VERIFIED_EXACT`: DOI de la consulta y del candidato coinciden exactamente.
- `VERIFIED_EXTERNAL_CONSENSUS`: dos o más fuentes externas independientes convergen sobre la misma identidad bibliográfica.
- `VERIFIED_SEMANTIC`: un candidato ya `probable_candidate` por reglas determinísticas mantiene el liderazgo y recibe apoyo semántico fuerte.
- `AI_SUPPORTED_MATCH`: el LLM local selecciona un candidato existente y existe apoyo independiente no-IA. Siempre requiere revisión humana.
- `POSSIBLE_MATCH`: evidencia útil pero insuficiente para un nivel verificado; requiere revisión.
- `UNRESOLVED`: evidencia insuficiente, contradictoria, inválida o no reproducible.

Los estados son niveles de evidencia, no probabilidades ni afirmaciones de verdad absoluta.

## Reglas conservadoras

1. La IA nunca puede generar un estado `VERIFIED_*`.
2. Una selección IA sin apoyo independiente queda `UNRESOLVED`.
3. Un desacuerdo fuerte entre el líder semántico y la selección IA queda `UNRESOLVED`.
4. Un candidato semántico fuerte puede llegar como máximo a `POSSIBLE_MATCH` si el consenso determinístico sigue sin resolver.
5. El objeto final sólo conserva índices, identidad, método, evidencias, advertencias y versiones de las capas; no copia ni normaliza metadatos de candidatos.
6. `selected_candidate_index` siempre apunta a `CandidateBatch.candidates`.
7. Parser, extracción y metadatos de portada permanecen sin autoridad compartida con esta capa.

## Umbrales v0.1

- apoyo semántico para `VERIFIED_SEMANTIC`: `>= 0.82`, sólo si coincide con el líder determinístico;
- candidato semántico como `POSSIBLE_MATCH`: `>= 0.88` + evidencia determinística `>= 0.55` + sin contradicciones;
- apoyo independiente mínimo para una selección IA: evidencia determinística `>= 0.65`, o similitud semántica `>= 0.82`, o identidad compartida entre fuentes.

Estos umbrales son reglas operativas iniciales y deben calibrarse posteriormente con un gold set; no se interpretan como probabilidades.

## Integración

Flujo objetivo:

`CandidateBatch -> ConsensusResult -> SemanticResult (opcional) -> AdjudicationResult (opcional) -> ResolutionDecision`

La salida sigue siendo sidecar/shadow respecto del parser. La integración posterior con UI/exportadores deberá preservar esta separación.
