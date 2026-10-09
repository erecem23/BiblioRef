# BiblioRef — baseline del parser legacy V3.2.2 (v0.1)

Fecha de corte: 2026-09-01.

## 1. Integración comprobada con BiblioRef v0.8.9

Se ejecutó BiblioRef v0.8.9 sobre la tesis de Agrazar (2024) con `scope=all_reference_sections` y modo adaptativo `shadow`. La salida estable informó **432 ocurrencias bibliográficas**, **387 referencias únicas** y **14 zonas**. Esa salida fue entregada directamente al parser legacy V3.2.2 adaptado, sin modificar todavía sus reglas.

El parser produjo 432 filas. La cobertura de campos fue: autor 95.83%, año 99.54%, título 100.00%, revista 35.88% y `fuente_editorial` 57.64%. El DOI apareció en 0.69% de las filas; este último porcentaje es **presencia**, no recall, porque no se construyó un gold específico para esta tesis.

## 2. Baseline retrospectivo contra el corpus analítico previamente curado (N=29.470)

Este contraste sirve para localizar debilidades del parser, **no como validación externa para publicar**, porque el corpus de 29.470 referencias fue utilizado y curado durante el desarrollo analítico previo.

| Campo | Cobertura/recall | Acuerdo/precisión diagnóstica |
|---|---:|---:|
| Autor principal | 97.49% | 71.33% |
| Año | 97.38% | 93.81% |
| Título | 99.85% | 92.37% |
| Revista | 44.23% | 39.18% |
| DOI | 97.26% recall | 99.61% precisión |
| Editorial (proxy) | 94.34% con fuente | 88.26% contiene el nombre; solo 4.02% lo aísla exactamente |
| Tipo documental (6 clases amplias) | 100% clasificado | 68.71% |

La lectura operativa es clara: **título, año y DOI son el mejor punto de partida; revista, tipo documental, aislamiento de editorial y normalización de autor requieren el mayor trabajo**.

## 3. Por qué no conviene mejorar todavía usando Agrazar como “gold”

La salida v0.8.9 de Agrazar contiene 432 ocurrencias porque conserva todas las secciones bibliográficas, mientras que el corpus curado anterior contiene 204 registros para esa tesis. Se pudieron vincular retrospectivamente 175 de esos 204 registros (85.78%): 164 por igualdad normalizada y 11 por similitud >= .90. Las diferencias restantes mezclan cambios de alcance, duplicados entre zonas, números de página contaminantes y decisiones históricas de curación. Por eso este emparejamiento se entrega como **diagnóstico**, no como métrica end-to-end.

## 4. Seed estratificado para construir un verdadero gold de parsing

Se preparó una muestra reproducible de **120 referencias**, con semilla 20260901: 30 artículos, 30 monografías, 20 recursos web, 20 tesis, 10 conferencias y 10 registros de otros tipos. Incluye 55 referencias UNLP, 34 UNC y 31 UNMdP.

Los campos “gold” que aparecen precargados provienen del corpus curado previo y son solamente una ayuda de revisión. **Cada fila debe ser confirmada manualmente** (`SI` / `EXCLUIR`) antes de denominar este conjunto gold standard o usar sus métricas en REDC.

## 5. Próximo ciclo de desarrollo

1. Confirmar manualmente las 120 referencias sin modificar las reglas del parser.
2. Congelar ese baseline.
3. Mejorar primero revista, tipo documental, editorial y autores, conservando tests de no-regresión para título/año/DOI.
4. Separar una segunda muestra independiente que no intervenga en la escritura de reglas.
5. En el artículo REDC, presentar las métricas del parser como **validación instrumental del enriquecimiento**, y dedicar los resultados sustantivos al corpus construido: composición por tipos documentales, distribución temporal, autores, revistas y editoriales.
