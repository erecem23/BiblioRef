# BiblioRef Local AI Adjudicator v0.1

Fecha de integración candidata: 2026-09-05

## Objetivo

Agregar una capa de IA local y opcional para adjudicar únicamente casos que siguen ambiguos después de:

1. extracción estable;
2. parser;
3. MetadataResolver (Crossref/OpenAlex);
4. ConsensusEngine;
5. SemanticResolver opcional.

La capa IA no forma parte del extractor ni del parser y no tiene autoridad para modificar sus salidas.

## Posición en la arquitectura

```text
PDF
 ↓
Extractor / segmentación
 ↓
Parser
 ↓
MetadataResolver
 ↓
Crossref + OpenAlex
 ↓
ConsensusEngine
 ↓
SemanticResolver (opcional)
 ↓
¿ambiguous_conflict / unresolved?
 ├─ no → no se llama al LLM
 └─ sí
     ↓
LocalAIAdjudicator (shadow)
     ├─ candidate_selected
     ├─ abstained
     ├─ invalid_response
     └─ backend_error
```

## Contrato de seguridad epistemológica

El modelo sólo puede devolver:

- `decision = candidate` o `none`;
- `candidate_index`, que debe pertenecer al conjunto de candidatos presentado;
- `reason_codes` pertenecientes a un vocabulario cerrado.

No puede devolver metadatos bibliográficos nuevos. Una respuesta con claves adicionales, un índice fuera de rango o un código no permitido se convierte en `invalid_response`.

La selección del modelo es explícitamente **shadow evidence**, no verdad bibliográfica.

## Casos en los que NO se invoca IA

- `exact_identifier`;
- `external_consensus`;
- `probable_candidate`;
- cualquier otro estado que no sea `ambiguous_conflict` o `unresolved`;
- ausencia total de candidatos externos.

Si no hay candidatos, la IA no puede inventarlos y el resultado es `skipped_no_candidates`.

## Privacidad y ejecución local

`LocalAIAdjudicator` exige `local_only=True` en el backend.

`OllamaJSONBackend` usa por defecto:

```text
http://127.0.0.1:11434/api/chat
```

y rechaza hosts no-loopback salvo habilitación explícita. Esto evita que referencias de tesis inéditas o privadas salgan accidentalmente a un servicio remoto.

El backend utiliza salida estructurada JSON, `stream=false` y `temperature=0`.

Modelo por defecto inicial:

```text
qwen3:4b
```

El modelo es configurable; no es una dependencia del core de BiblioRef.

## Evidencia enviada al modelo

Se envía únicamente un paquete reducido:

- referencia cruda y campos ya parseados;
- top-N candidatos existentes;
- score determinístico de consenso;
- evidencias positivas y contradictorias;
- similitud semántica si existe;
- grupos de acuerdo entre fuentes.

No se envían `raw_metadata` completos de los proveedores ni URLs de candidatos.

## Prompt-injection / texto no confiable

Autores, títulos y la referencia cruda son tratados como datos no confiables. El prompt del sistema ordena ignorar instrucciones contenidas en esos campos y usar sólo la evidencia bibliográfica presentada.

No se habilitan herramientas, navegación, búsquedas externas ni capacidad de crear candidatos.

## Salida auditable

`AdjudicationResult` registra:

- versión del adjudicador;
- backend y modelo;
- estado de consenso de entrada;
- número de candidatos;
- candidatos considerados;
- índice elegido, si existe;
- identity key del candidato elegido;
- códigos de evidencia;
- líder semántico, si existe;
- notas de auditoría;
- `shadow_mode=true`.

No se incluye una pseudo-probabilidad de confianza del LLM.

## Tests agregados

`test_local_ai_adjudicator_v0_1.py` cubre:

- no llamada en casos ya resueltos;
- no invención cuando no hay candidatos;
- selección válida en shadow mode;
- abstención;
- rechazo de índices inexistentes;
- rechazo de claves/códigos fuera del schema;
- errores del backend no fatales;
- obligación de backend local;
- ranking top-N por consenso y semántica;
- payload mínimo;
- ausencia de campo `confidence`;
- rechazo de Ollama remoto por defecto;
- contrato HTTP de salida estructurada de Ollama.

## Criterio de integración

La rama sólo debe integrarse si:

1. pasa el conjunto focalizado MetadataResolver + IA;
2. pasa la suite completa de BiblioRef sin regresiones;
3. el cambio continúa sin tocar extracción, segmentación ni parser;
4. el adjudicador permanece shadow-only.

## Siguiente etapa recomendada

Construir un `ResolutionDecision` unificado que combine de forma explícita:

- estado del consenso determinístico;
- score semántico;
- decisión IA shadow;
- nivel de evidencia final (`VERIFIED_EXACT`, `VERIFIED_SEMANTIC`, `AI_SUPPORTED_MATCH`, `POSSIBLE_MATCH`, `UNRESOLVED`);
- trazabilidad por campo y fuente.

Sólo después de evaluar un gold externo debería considerarse cualquier promoción automática de decisiones IA.
