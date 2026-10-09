# BiblioRef v0.9.6 — APP v2.5.1

## Alcance

Esta revisión completa la reorganización de APP v2.5.0 (Inicio → Proyecto/dashboard → Referencias por tesis → Exportar) y agrega una capa de lectura visual no destructiva para PDFs con espaciado OCR/font anómalo.

## Normalización visual

- Se conserva `reference.text` como texto original y las exportaciones siguen leyendo ese campo.
- `visualText()` se aplica sólo al renderizado de las tarjetas de referencia.
- El usuario puede alternar `Aa · vista limpia` / `Aa · texto original`.
- Se eliminan caracteres invisibles/soft-hyphen problemáticos y espacios espurios junto a puntuación.
- Se reparan de forma conservadora apellidos partidos por cambios de span, por ejemplo `Sevilla G uzm án` → `Sevilla Guzmán`.
- No se hace una reescritura lingüística agresiva: donde la reparación textual no es inequívoca se conserva el original.

## Títulos

La sugerencia de título desde portada ya no concatena todos los spans con un espacio. `_join_spans_for_reading()` decide por la distancia física entre bboxes y el tamaño tipográfico. Esto evita que un cambio de fuente dentro de una palabra cree un espacio artificial. Las sugerencias no confirmadas se recalculan una vez con esta nueva revisión; un título confirmado por el usuario no se toca.

## Estilo

Los títulos y referencias visibles fijan `letter-spacing: 0`, `word-spacing: normal` y kerning normal. La separación que aún pueda verse proviene del contenido OCR y no de CSS.

## Compatibilidad

La extracción v0.9.6 no cambia. Tampoco cambia el contenido de CSV/XLSX/JSON por esta normalización visual.

## Verificación

- `337 passed`
- `3 skipped`
- `16 subtests passed`
- `node --check static/app.js: OK`

## Migración de proyectos existentes

`EXTRACTION_REVISION` se elevó a `v096-project-dashboard-3` para que una lista persistida por una APP anterior no siga pareciendo actual. Las tesis sin trabajo manual se reextraen automáticamente; si existe trabajo manual, la APP conserva la revisión y ofrece `↻ Actualizar` antes de reemplazar la lista.
