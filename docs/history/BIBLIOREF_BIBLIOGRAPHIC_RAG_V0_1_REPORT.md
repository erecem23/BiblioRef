# BiblioRef Bibliographic RAG v0.1

## Objetivo

Agregar una capa RAG bibliográfica local, auditable y conservadora antes de ampliar el uso del LLM. La capa recupera evidencia desde referencias previamente verificadas o confirmadas por una persona, pero **no toma decisiones bibliográficas por sí sola**.

## Posición en la arquitectura

```text
PDF
  -> extracción / segmentación
  -> parser
  -> Crossref + OpenAlex
  -> ConsensusEngine
  -> SemanticResolver
  -> BibliographicRAG (evidencia local recuperada)
  -> LocalAIAdjudicator (fase posterior)
  -> ResolutionDecision
  -> revisión / confirmación humana
```

La v0.1 implementa únicamente `BibliographicRAG`; no conecta todavía el RAG al LLM.

## Principio de no auto-refuerzo

El almacén RAG sólo acepta registros con uno de estos estados:

- `verified_exact`
- `verified_external_consensus`
- `human_confirmed`

Quedan excluidos como conocimiento RAG:

- `verified_semantic`
- `ai_supported_match`
- `possible_match`
- `unresolved`

Esto impide que una inferencia semántica o una decisión previa del LLM vuelva a entrar silenciosamente como supuesto ground truth.

## Confirmación humana

La categoría `human_confirmed` está prevista para el flujo sugerido en auditoría: cuando BiblioRef no puede resolver de forma segura un conflicto, puede mostrar candidatos al autor/revisor y registrar su elección como evidencia con procedencia explícita. Esa confirmación puede alimentar futuras recuperaciones RAG sin alterar retrospectivamente el parser ni la salida original.

## Recuperación

`BibliographicRAG` opera sobre un `EvidenceStore` local.

### Señal léxica

Siempre disponible y determinística. Usa normalización Unicode, folding de acentos y solapamiento de tokens entre los campos parseados de la consulta y el registro verificado.

### Señal semántica opcional

Puede inyectarse un backend local de embeddings compatible con el contrato ya usado por BiblioRef. La combinación léxico-semántica conserva los scores como señales de recuperación, no como probabilidades de identidad.

Defaults v0.1:

- `lexical_weight = 0.65`
- `semantic_weight = 0.35` si existe backend local;
- sin backend, la recuperación queda 100% léxica;
- `top_k = 5`;
- `min_score = 0.10`.

Estos valores son de infraestructura y todavía no se presentan como calibrados empíricamente.

## Trazabilidad

Cada evidencia conserva:

- `evidence_id`
- `identity_key`
- estado de verificación
- procedencia
- título
- autores
- año
- contenedor
- publisher
- DOI
- referencia original opcional
- documento fuente opcional

Cada resultado recuperado expone por separado:

- `lexical_score`
- `semantic_score`
- `retrieval_score`
- registro y procedencia recuperados

`RAGResult` declara expresamente que la evidencia recuperada **no es una decisión de resolución**.

## Deduplicación

El DOI es la identidad prioritaria. Sin DOI se usa una clave conservadora título + año + primer autor cuando están presentes. Si la misma identidad aparece varias veces, el store no multiplica artificialmente su peso. Se prioriza:

1. `human_confirmed`
2. `verified_exact`
3. `verified_external_consensus`

## Seguridad y aislamiento

- no muta `ResolverQuery`;
- no muta candidatos;
- no modifica parser ni extracción;
- no consulta APIs externas;
- no requiere modelo en el import base;
- no usa outputs del LLM como conocimiento confiable;
- no introduce probabilidades artificiales;
- puede funcionar completamente offline.

## Relación con el holdout v0.1

El holdout externo congelado de 31 referencias **no se utiliza para poblar ni calibrar esta capa**. Su función permanece exclusivamente como evaluación externa posterior. El desarrollo del RAG debe usar fixtures y, más adelante, un dev set separado.

## Próxima fase

Tras integrar y validar RAG v0.1, `LocalAIAdjudicator v0.2` podrá recibir una sección `retrieved_evidence` además de candidato/consenso/semántica. El LLM seguirá limitado a:

- elegir un candidato existente, o
- abstenerse.

La evidencia RAG deberá incluir procedencia y nivel de confianza documental, y el LLM no tendrá autorización para crear metadatos nuevos.
