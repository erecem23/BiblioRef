# BiblioRef v0.9.6 · APP v2.6.7 · Parser v0.8

Fecha de cierre: 2026-09-02.

## Alcance

Parser v0.8 es una capa **downstream**. No modifica detección de zonas, segmentación, fronteras ni texto crudo. El extractor sigue siendo BiblioRef v0.9.6 / algoritmo 0.6.2 / motor estable 0.4.5.

Código congelado antes de abrir material externo nuevo:

`b10079270b5df316ebbab4ad667df774280ab09f899f5b472f1e09f372bd885b`

## Cambios de v0.8

- evita que prefijos de editor consuman palabras como `Educação`;
- limpia descriptores de grado de títulos de Tese/Dissertação;
- reconoce `?`/`!` antes de `In:` como frontera de título cuando la estructura lo justifica;
- limpia ciudad, `[S.l.]` y anotaciones de plataforma de candidatos a revista en la ruta estricta;
- amplía separadores portugueses de autores y nombres dados en mayúsculas;
- corrige selección de año cuando el año aparece repetido dentro del título;
- mejora entrevista/recurso web y marcadores `Recuperado de` / `Recuperada de`;
- normaliza editoriales con edición/estado/lugar residual;
- agrega una ruta conservadora para autor institucional web sin año.

Las 30 referencias del holdout v0.7 pasan a ser desarrollo/regresión de v0.8 y no cuentan como validación externa nueva.

## No-regresión histórica

El corpus analítico histórico tiene 29.027 filas reales. Un barrido estructural previo al freeze encontró:

- activaciones de la nueva ruta ABNT v0.8: **0/29.027**;
- activaciones de la nueva ruta institucional web: **0/29.027**.

Fuera de las rutas nuevas, v0.8 hace fallback a v0.7; por ello el comportamiento histórico permanece preservado en ese barrido. Este corpus es desarrollo, no holdout externo.

## Holdout externo general

Gold SHA-256:

`47f90f7a0f4fddec0b5d07b71be2032682df6bb3574b7f17300a2520e5dac794`

30 referencias nuevas: UnB (doctorado), UFSC (doctorado) y UFES (disertación de maestría). El gold fue fijado antes de ejecutar v0.8.

Resultado: **v0.7 y v0.8 son idénticos en todos los campos evaluados**. No hay mejoras ni regresiones. Esto funciona como control externo de no-regresión para bibliografías APA/mixed, pero no prueba las nuevas rutas porque prácticamente no se activan en este conjunto.

Métricas v0.8: autor 93,33%; autores 93,33%; año 100%; título exacto 83,33%; título fuzzy>=.90 86,67%; tipo 66,67%; revista fuzzy>=.90 71,43% (cobertura 71,43%); editorial exacta 33,33%; DOI 100%.

## Holdout externo de estrés

Gold SHA-256:

`102221579f2ed46842c4c8b532fc1eade016a93fd86f0ab7769a30bae54dac89`

20 referencias nuevas, 10 de una tesis doctoral de UFT/UFU (Ingeniería) y 10 de una tesis doctoral de UFPB (Salud). Fue elegido después del freeze para estresar títulos de Tese/Dissertação, revistas con metadatos intermedios, publishers, DOI y estilos mixtos.

### v0.7 → v0.8

- autor: 65% → 65%;
- autores: 55% → 55%;
- año: 100% → 100%;
- título exacto: **35% → 55%**;
- título fuzzy>=.90: **35% → 55%**;
- tipo: 90% → 90%;
- cobertura revista: 87,5% → 87,5%;
- revista fuzzy>=.90: **0% → 0%**;
- editorial exacta: 90% → 90%;
- editorial observada: 80% → 80%;
- DOI: 100% → 100%.

Comparación pareada de título: **4 mejoras / 0 regresiones**. No hubo regresiones en los demás campos medidos.

### Límite externo principal

La normalización de revista continúa siendo el principal cuello de botella. En el stress set, 7/8 referencias con revista producen algún candidato, pero 0/8 alcanza fuzzy>=.90. Los errores incluyen:

- título del artículo pegado a la revista;
- entidad editora (`Institute of Electrical and Electronics Engineers`) pegada al nombre de revista;
- ciudad/volumen retenidos en estilos menos regulares;
- referencias con autor imperfectamente segmentado que contaminan la detección de fuente.

Por metodología, v0.8 **no se modificó después de abrir ninguno de los dos holdouts**. Esos errores quedan para una futura v0.9.
