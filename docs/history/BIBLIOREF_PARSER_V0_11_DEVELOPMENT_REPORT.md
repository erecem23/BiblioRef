# BiblioRef Parser v0.11 — development report

## Objetivo

Agregar un régimen conservador para bibliografías iberoamericanas de Humanidades/Ciencias Sociales donde el año de publicación aparece al final de la referencia (`autor → título → fuente/editorial → lugar → año`), sin modificar el extractor ni reinterpretar los regímenes APA/ABNT ya estabilizados.

## Corpus de desarrollo

Tesis de Luis María Palma, Doctorado en Sociología, Universidad de Belgrano. La extracción entregó 322 registros y se usa aquí exclusivamente como corpus de desarrollo del parser. No constituye validación externa independiente de v0.11.

## Cambios

- limpieza de bullets/list markers antes del parsing;
- ruta `v11_legacy_year_final` para autor y año final;
- reconocimiento de libros, artículos, capítulos, conference papers y tesis explícitas dentro de ese régimen;
- `en línea`/URL se trata como evidencia de acceso y no como autoridad automática sobre el tipo documental;
- la fecha de `última visita` deja de convertirse en año de publicación cuando no hay otra fecha editorial;
- `tesis` requiere evidencia documental explícita y deja de dispararse por títulos como `Diez tesis...` o editoriales llamadas `Nova Tesis`;
- preservación estricta de v0.10 fuera del nuevo régimen, con exclusión explícita de bloques ABNT en mayúsculas.

## Resultado sobre Palma

- autores no nulos: 66/322 → 311/322;
- años no nulos: 321/322 → 292/322. La caída es intencional: se eliminaron años que eran sólo fechas de acceso (`última visita`);
- journals no nulos: 0/322 → 69/322;
- publishers no nulos: 60/322 → 134/322;
- `tesis`: 4 → 1, eliminando tres falsos positivos léxicos.

La distribución de tipos de v0.11 es una predicción del parser, no un ground truth exhaustivamente anotado. Quedan casos complejos de autores institucionales, autores múltiples y títulos con muchas comas que requieren una segunda ronda de revisión manual.

## No regresión

Sobre las 190 referencias del corpus de desarrollo histórico de parser v0.10, v0.11 produjo **0 cambios sustantivos** en autor, autores, año, tipo, título, journal, publisher o DOI. Sólo cambian `parser_version/schema_version` al usar la API pública.

Batería integrada: **522 passed, 3 skipped, 16 subtests passed**.
