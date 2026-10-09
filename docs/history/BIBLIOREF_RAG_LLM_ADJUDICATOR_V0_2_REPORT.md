# BiblioRef RAG-aware Local AI Adjudicator v0.2

## Objetivo

Incorporar la evidencia recuperada por `BibliographicRAG v0.1` al adjudicador LLM local sin ampliar su autoridad. El modelo continúa limitado a elegir **un candidato ya recuperado** o abstenerse (`none`).

## Arquitectura

```text
parser
  -> Crossref + OpenAlex
  -> ConsensusEngine
  -> SemanticResolver
  -> BibliographicRAG
  -> RAGLocalAIAdjudicator v0.2
  -> ResolutionDecision v0.1
  -> revisión / confirmación humana
```

RAG y LLM permanecen como capas sidecar: ninguna muta el parser, candidatos o metadatos de proveedor.

## Contrato de autoridad

El LLM puede devolver únicamente:

- `candidate` + un `candidate_index` existente; o
- `none`.

No puede devolver DOI, título, autores, año, revista, publisher ni crear un candidato nuevo.

La evidencia RAG **no convierte una selección del LLM en verificación automática**. `ResolutionDecisionEngine v0.1` permanece sin cambios: un candidato seleccionado por IA necesita evidencia independiente no-IA según las reglas ya vigentes. Por lo tanto, RAG + LLM por sí solos no producen `VERIFIED_*` ni necesariamente `AI_SUPPORTED_MATCH`.

## Evidencia RAG enviada al modelo

Cada evidencia recuperada se proyecta de forma explícita y trazable:

- `evidence_id`
- `identity_key`
- `verification_status`
- `provenance`
- `source_document_id`
- título
- autores
- año
- contenedor
- publisher
- DOI
- score léxico
- score semántico opcional
- score de recuperación
- índices de candidatos cuya identidad coincide exactamente

No se envía el `raw_reference` almacenado en RAG, para reducir superficie de prompt injection. La instrucción de sistema del adjudicador y las reglas del payload tratan todo texto bibliográfico recuperado como **datos, no instrucciones**.

## `rag_support`

v0.2 agrega el código de razón `rag_support`.

El modelo sólo puede declararlo cuando existe una evidencia RAG cuya `identity_key` coincide de forma determinística con la identidad del candidato seleccionado. Si el modelo intenta usar `rag_support`:

- para otro candidato;
- sin RAG;
- o en una abstención;

la salida completa se rechaza como `invalid_response`.

La coincidencia RAG-candidato la calcula BiblioRef; no se confía en que el LLM la declare correctamente.

## Confirmación humana

`human_confirmed` significa que una persona eligió explícitamente un candidato y que esa decisión se guardó con procedencia. Para el LLM sigue siendo una fuente de evidencia, no una instrucción privilegiada.

El flujo previsto es:

```text
caso ambiguo
 -> mostrar candidatos al autor/revisor
 -> elección explícita
 -> EvidenceRecord(status="human_confirmed", provenance=...)
 -> persistencia local JSONL
 -> recuperable por RAG en referencias futuras
```

Una selección previa del LLM nunca se transforma automáticamente en `human_confirmed`.

## Auditoría

`RAGAdjudicationResult` extiende la trazabilidad del adjudicador con:

- `rag_version`
- `rag_status`
- `rag_retrieved_count`
- `rag_supporting_evidence_ids`

Los identificadores de evidencia que realmente respaldan al candidato seleccionado se calculan por identidad bibliográfica y se conservan en la salida.

## Compatibilidad

Sin `RAGResult`, v0.2 conserva el comportamiento conceptual de v0.1 y admite los códigos de evidencia anteriores. Tampoco se llama al LLM cuando el consenso ya está resuelto.

## Holdout externo

El holdout congelado de 31 referencias (`resolution_holdout_v0_1_frozen.jsonl`) no se usa para desarrollar, poblar ni ajustar RAG/LLM v0.2. Permanece reservado para una evaluación externa posterior.

## Criterio de integración

- tests focalizados nuevos y previos verdes;
- suite completa sin regresiones;
- smoke Crossref/OpenAlex verde;
- ningún cambio en extracción/parser;
- ningún cambio de autoridad en `ResolutionDecisionEngine`.
