# BiblioRef — paquete de continuidad para otro chat

## Qué contiene

Este ZIP reúne el estado de trabajo necesario para continuar el desarrollo del parser de BiblioRef y la preparación del artículo para REDC sin reconstruir el contexto desde cero.

### 01_baseline_parser
Paquete reproducible del baseline generado en la conversación:
- parser legacy modularizado;
- evaluación retrospectiva;
- muestra estratificada de 120 referencias;
- métricas JSON;
- errores diagnósticos;
- salida BiblioRef v0.8.9 sobre Agrazar;
- vinculación retrospectiva con el corpus curado;
- workbook `BiblioRef_parser_baseline_y_gold_seed_v0_1.xlsx`;
- README técnico.

### 02_datos_fuente
Datos usados para construir y diagnosticar el baseline:
- corpus analítico de 29.470 referencias;
- revisión manual de editoriales;
- revisión manual de tipos documentales;
- validación y resumen del pipeline previo;
- salidas legacy sobre Agrazar y challenge.

### 03_codigo_origen
- `extractor_v322.py`: extractor/parser previo del que se recuperó la lógica.
- `biblioref_parser_legacy_v0_1.py`: versión modularizada para integrarla como segunda etapa de BiblioRef.

### 04_contexto_REDC
Material para la redacción y posicionamiento del paper:
- estado del arte y problematización;
- aporte científico;
- antecedentes de software/herramientas publicados en REDC;
- plantilla REDC 2025;
- guía de buenas prácticas CSIC.

---

## Estado actual del desarrollo

La arquitectura que se está consolidando es:

PDF / tesis
→ BiblioRef detecta y segmenta referencias
→ parser bibliográfico estructura cada referencia
→ salida analítica: autores, años, títulos, revistas, editoriales, DOI y tipo documental.

Por lo tanto, la segmentación y el parsing son dos problemas distintos y deben evaluarse por separado.

### Integración actual BiblioRef v0.8.9 → parser legacy V3.2.2

En una tesis real (Agrazar), BiblioRef v0.8.9 produjo:
- 14 zonas bibliográficas;
- 432 ocurrencias;
- 387 referencias únicas.

Cobertura del parser sobre esas 432 ocurrencias:
- autor: 95,8%;
- año: 99,5%;
- título: 100%;
- revista: 35,9%;
- fuente/editorial: 57,6%;
- DOI: 0,69% de presencia en esta tesis.

Estas cifras son de cobertura, no de exactitud.

### Evaluación retrospectiva sobre 29.470 referencias previamente curadas

Este corpus NO es un holdout externo, porque fue construido durante el desarrollo anterior. Sirve como diagnóstico y baseline interno.

Resultados:
- autor principal: 97,5% de cobertura; 71,3% de acuerdo estricto normalizado;
- año: 97,4% de cobertura; 93,8% de acuerdo;
- título: 99,85% de cobertura; 92,4% de acuerdo fuzzy ≥ 0,90;
- revista: 44,2% de cobertura; 39,2% de acuerdo;
- DOI: 97,3% recall y 99,6% precisión;
- tipo documental (6 clases): 68,7% de exactitud;
- editorial: el nombre de la editorial aparece frecuentemente dentro de `fuente_editorial`, pero queda mal aislado como campo independiente.

Lectura práctica:
1. conservar y proteger la lógica de título, año y DOI;
2. mejorar primero revistas;
3. después tipo documental;
4. después separación/normalización de editoriales;
5. finalmente autores.

### Muestra de 120 referencias

Se generó una muestra estratificada reproducible:
- 30 artículos;
- 30 monografías;
- 20 recursos web;
- 20 tesis;
- 10 congresos;
- 10 otros.

Distribución institucional:
- UNLP: 55;
- UNC: 34;
- UNMdP: 31.

IMPORTANTE: la columna `confirmado_humano` está sin validar. Esta muestra todavía es un **seed de desarrollo**, no un gold standard publicable. Debe revisarse manualmente y marcarse como `SI` o `EXCLUIR`.

---

## Implicación para el artículo REDC

La validación del parser debe ocupar una parte instrumental del manuscrito. El aporte principal no debería presentarse como “otro parser bibliográfico”, sino como un pipeline que recupera del PDF de tesis la capa documental previa al matching con infraestructuras como Crossref/OpenAlex y la transforma en un corpus bibliográfico analizable.

No afirmar todavía:
- SOTA;
- superioridad sobre GROBID/CERMINE;
- generalización universal;
- validación end-to-end de geometría;
- métricas definitivas del parser usando el corpus de desarrollo como si fuera gold externo.

---

## Próximo paso recomendado

1. Auditar manualmente las 120 referencias.
2. Congelar ese gold seed una vez validado.
3. Separar una segunda muestra que NO se utilice para escribir reglas.
4. Mejorar parser por módulos, con tests de no-regresión:
   - revista;
   - tipo documental;
   - editorial;
   - autor.
5. Evaluar cada modificación contra:
   - gold de desarrollo;
   - holdout independiente;
   - pruebas previas de BiblioRef para asegurar que no se rompa segmentación ya estabilizada.
6. Recién después redactar la tabla definitiva de validación para REDC.

---

## Prompt sugerido para iniciar el otro chat

> Estoy continuando el desarrollo de BiblioRef para un artículo en la Revista Española de Documentación Científica (REDC). Te adjunto un ZIP de handoff. Lee primero `00_LEEME_PRIMERO.md`, después el README y las métricas de `01_baseline_parser`, y usa `04_contexto_REDC` para mantener el posicionamiento científico y editorial. Quiero continuar desde el baseline actual, sin rehacer lo que ya funciona y aplicando no-regresión. El próximo objetivo es auditar el gold seed de 120 referencias y mejorar el parser en el orden revista → tipo documental → editorial → autor, manteniendo título, año y DOI.
