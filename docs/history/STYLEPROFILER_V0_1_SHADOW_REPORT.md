# BiblioRef StyleProfiler v0.1-shadow — nueva capa analítica

## Estado

Primera implementación estructural de la capa recomendada por el informe de deep research. Se integra **después del parser v0.11** y no posee ninguna ruta para modificar extracción, fronteras ni campos parseados.

Pipeline efectivo:

```text
PDF → extracción → reconciliación → parser v0.11 → salida estable
                                              └→ StyleProfiler v0.1-shadow → JSON lateral
```

## Qué implementa ahora

- paquete independiente `biblioref/styleprofiler/`;
- features morfológicas explicables por referencia;
- agregación por zona bibliográfica;
- dimensiones separadas `family`, `likely_style`, `variant`;
- `unknown` como resultado legítimo;
- `legacy_year_final` como **variant**, no como norma bibliográfica;
- contexto (país, universidad, disciplina, año) conservado con `used_in_decision=false`;
- salida por referencia y por zona;
- detección preliminar de `mixed_style`;
- `confidence=null`: los scores heurísticos actuales no se presentan como probabilidades calibradas;
- endpoint APP `GET /api/documents/{id}/style-profile`;
- sidecar descargable `GET /api/documents/{id}/style-profile.json`.

## Deliberadamente no implementado todavía

- HDBSCAN / clustering multialgoritmo;
- clasificador supervisado;
- cumplimiento normativo APA/ABNT/NLM/IEEE;
- retroalimentación hacia el parser;
- uso de país/universidad/área como predictor;
- cambio automático de etiquetas documentales.

Estos puntos requieren corpus externo y gold set, tal como recomienda el informe de investigación.

## Garantía arquitectónica

El contrato público declara:

```json
{
  "mutates_extraction": false,
  "mutates_parser": false,
  "context_used_in_decision": false
}
```

La función de profiling opera sobre copias/lecturas de las referencias. Los tests verifican que los registros y sus campos parseados no sean modificados.
