# BiblioRef parser v0.12.4 — validación de autores

## Alcance

Replay directo del parser de autores sobre las 99 referencias crudas del caso de validación de campo de Apolonio. No se almacena en el repositorio ninguna referencia real, PDF ni fila del corpus; este informe conserva sólo conteos y familias de patrones.

La comparación es exacta para autores: v0.12.2 y v0.12.3 no modifican los campos `author`/`authors`, por lo que el estado inmediatamente anterior a v0.12.4 es el producido por la capa de autores de v0.12.1.

## Resultado

- Referencias evaluadas: **99**.
- Listas de autores estructuralmente completas según la cita observada: **98**.
- Lista con elipsis APA explícita: **1**.
- Casos `et al.` en este corpus: **0**.
- Cambios nuevos de cadena de autores v0.12.3 → v0.12.4: **2**.
- Nuevas alertas de truncación explícita: **1**.
- Cambios acumulados de campos de autor desde el Excel v0.12: **6**.

## Familias corregidas acumulativamente

1. Dos autores corporativos unidos por `y`, sólo cuando el segundo segmento comienza con una entidad organizacional inequívoca.
2. Nombre corporativo con `y` interna que no debe dividirse, por ejemplo la forma `Ministerio de ..., ... y ...`.
3. Partículas de apellido en minúscula (`del`, `de la`, etc.).
4. Inicial final en minúscula en formas bibliográficas del tipo `M. d.`.
5. Espacio espurio después de guion introducido por salto de línea del PDF dentro de un apellido compuesto.
6. Conservación de la última autoría visible en listas APA con elipsis sin presentar la lista como exhaustiva.

## Auditoría nueva

`author_list_status` toma uno de cuatro valores:

- `complete`
- `explicit_ellipsis`
- `et_al`
- `unresolved`

Cuando la fuente usa elipsis o `et al.`, el parser mantiene la mejor lista observable pero agrega:

- `needs_review = True`
- `review_reasons += author_list_truncated`

La alerta no supone que el parser pueda inventar las autorías omitidas: expresa que la propia cita no contiene una lista exhaustiva y que un análisis bibliométrico de coautoría podría requerir verificación externa.

## Regresión

Se añadieron fixtures sintéticos para:

- apellidos con guion y espacio de salto de línea;
- coautoría corporativa;
- `y` interna en nombres ministeriales;
- partículas y minúsculas en iniciales;
- `y` entre autores personales;
- elipsis APA;
- `et al.`;
- autor personal + autor corporativo;
- subdivisiones institucionales con coma;
- autor individual con apellido complejo.

La extracción y segmentación de referencias permanecen fuera de esta capa y no fueron modificadas.
