# BiblioRef — Handoff para nuevo proyecto de ChatGPT

Este documento resume todo lo necesario para que un chat nuevo (sin memoria de esta
conversación) entienda el producto, el sistema visual actual, y qué se hizo en la
última sesión de diseño. El .zip adjunto contiene el proyecto completo — este .md es
el mapa para orientarse rápido sin tener que leer todo el código.

## Qué es BiblioRef

App local (FastAPI + HTML/JS estático, empaquetada como app de escritorio Windows)
que extrae, segmenta y parsea referencias bibliográficas de tesis/PDFs académicos en
registros estructurados (autor, año, tipo, título, revista, DOI), permite revisión y
corrección manual de las zonas que el pipeline no pudo resolver con confianza, y
exporta el resultado limpio (CSV/XLSX/JSON) para un estudio bibliométrico agregado.

Usuarios: investigadores e instituciones académicas — pensado para instalarse y
correr localmente por institución, sin cuentas ni backend compartido (por ahora; ver
"Open/undecided" en PRODUCT.md). Corpus real de prueba abarca universidades de
Argentina, Brasil (convención ABNT), Reino Unido, etc.

Flujo real de pantallas: **Inicio** (carga) → **Proyecto** (tabla de documentos) →
**Referencias por tesis** (revisión/corrección manual) → **Exportar** (CSV/XLSX/JSON).

Ver `PRODUCT.md` en el zip para el detalle completo (capacidades, restricciones,
roadmap explícitamente NO construido aún: score de confianza por referencia,
detección de duplicados — no fabricar UI de esto).

## Sistema visual actual: "La Consola de Auditoría"

Ver `DESIGN.md` en el zip (fuente de verdad completa, con frontmatter de tokens +
`.impeccable/design.json` como sidecar) — resumen:

- **Identidad:** sala de control para auditar cientos de referencias. Sidebar oscuro
  fijo (`#101a30`) a la izquierda con navegación de las 4 pantallas reales; contenido
  a la derecha sobre canvas claro neutro (`#f4f5f7`) con cards blancas redondeadas y
  sombra suave.
- **Un solo acento:** azul consola `#2f6feb` — nunca un segundo color decorativo.
- **Tipografía:** stack sans del sistema (sin webfont custom), jerarquía por peso
  (700 headings, 600 labels, 400 body).
- **Formas:** todo redondeado (6–7px controles chicos, 8px botones/nav, 10px
  cards/inputs/modal, pill para badges) — reversa deliberada del mundo visual
  anterior, que era de esquinas rectas.
- **Sombras:** solo suaves/difusas, nunca hard-offset.
- **Estado:** siempre badge pill en color semántico (verde=ok, ámbar=revisión,
  rojo=audit-required), nunca decorativo.

**Historia de la decisión (importante para no revertir sin querer):** el producto
tenía un mundo visual anterior "Sala de Lectura" (papel/serif, kraft). El usuario pidió
explícitamente un rediseño completo (no pulido), revisó 3 imágenes de referencia estilo
pitch-deck (sidebar oscuro, acento azul, cards redondeadas), y confirmó conscientemente
adoptar ese lenguaje para la app real ("Cambié de idea, esto es lo que quiero"),
reemplazando la dirección anterior. Esto está documentado en `PRODUCT.md` bajo
`## Brand Commitments` con ambas fechas. No es deriva accidental — es una decisión
consciente y confirmada.

## Qué se hizo en la última sesión (orden cronológico)

1. **`/impeccable init`** → creó `PRODUCT.md`.
2. **`/impeccable document`** → capturó el mundo "Sala de Lectura" original en
   `DESIGN.md`.
3. **`critique` → `harden` → `layout` → `distill` → `critique` → `polish`** sobre ese
   mundo original: accesibilidad (teclado, ARIA live, focus trap en modal),
   manejo de errores (try/catch en ~8 llamadas `api()` que fallaban en silencio,
   fix de leak de HTML crudo en mensajes de error), fix de iconos emoji→SVG en el
   explorador de Drive, fix de un bug real de overflow de página (`.statsgrid` con
   grid fijo de 5 columnas forzando 690px de ancho mínimo). Score de critique subió
   de 22/40 a 30/40.
4. **Rediseño completo** (no pulido) a "La Consola de Auditoría" tras revisar
   referencias del usuario — reescritura completa de `static/index.html` (CSS +
   estructura) preservando el 100% de la lógica de `static/app.js` (se verificaron
   todas las dependencias de clases/IDs antes de reescribir, así que `app.js` casi no
   cambió).
5. **Pulido** del rediseño: fix de overflow horizontal en nav/status en mobile,
   fix de `.statsgrid` (mismo bug, mismo patrón `repeat(auto-fit,minmax(...))`),
   wrap de la viewerbar.
6. **Dos features nuevas** pedidas por el usuario, últimas en implementarse:
   - **Vista jerárquica agrupada en Proyecto**: toggle "Tabla / Agrupado" +
     selector de variable (Universidad / Área-disciplina / Estado). Cada grupo es
     un `<details>` colapsable compacto con conteo de tesis/referencias. Convive con
     la tabla plana existente (no la reemplaza). Diseñado para agregar más variables
     de agrupamiento fácilmente a futuro.
   - **Vista planilla en "Referencias por tesis"**: toggle "Tarjetas / Planilla"
     junto al contador de referencias. Tabla estilo Excel con columnas Autor / Año /
     Tipo / Título / Revista-editorial / DOI / Estado. Clic en fila selecciona la
     referencia igual que una tarjeta. El buscador funciona en ambas vistas.
     **Limitación conocida, no resuelta:** la columna de referencias es angosta
     (diseñada para tarjetas), así que la planilla con 7 columnas necesita scroll
     horizontal interno — funciona bien pero no es una planilla "ancha". Ensancharla
     a costa del visor de PDF sería un cambio de layout mayor, pendiente de
     confirmación del usuario si lo quiere.

Todo verificado en navegador (server estático de prueba, sin backend real disponible
en el entorno de desarrollo): sin overflow en mobile 375px, consola sin errores
reales, contraste WCAG verificado a mano en los estados críticos (botón deshabilitado,
etc.).

## Pendiente / próximos pasos sugeridos

- `DESIGN.md` y `.impeccable/design.json` **todavía no documentan** los dos
  componentes nuevos (`.groupbox`/`.grouprow` de la vista agrupada, `.reftable` de
  la planilla) como parte formal del sistema. Un detector mecánico de deriva
  (`detect.mjs`) corrió sobre el HTML final y encontró 28 hallazgos (3 falsos
  positivos ya conocidos de `.refitem` con `side-tab`, 15 de tamaño de fuente y 10
  de radio — advertencias, no colores nuevos fuera de sistema; no se introdujo
  ningún color no documentado en las features nuevas).
- Decisión pendiente del usuario: si la planilla de referencias debería ensancharse
  (a costa del visor de PDF) para evitar el scroll horizontal.
- Decisión de arquitectura explícitamente diferida por el usuario (no resolver sin
  preguntar): si la futura versión "profesional multi-institución" necesita backend
  compartido con cuentas, o sigue siendo instalación local por institución.

## Cómo orientarse en el .zip

- `PRODUCT.md` — verdad de producto (usuarios, capacidades, qué NO existe todavía).
- `DESIGN.md` — sistema de diseño completo, fuente de verdad visual actual.
- `.impeccable/design.json` — mismo sistema en formato estructurado (tokens, tonal
  ramps, componentes con HTML/CSS de referencia).
- `static/index.html` + `static/app.js` — la UI real, único frontend de la app.
- `app.py`, `biblioref/` — backend FastAPI y pipeline de extracción/parsing (Python).
- `.impeccable/critique/` — snapshots de las revisiones de UX de esta sesión.
- El resto (`BIBLIOREF_*_REPORT.md`, `PARSER_*`, `FULL_*_TEST_RESULTS.txt`, etc.) es
  evidencia real de evaluación del parser contra corpus de tesis reales — útil como
  contexto de precisión del producto, no relevante para trabajo de diseño/UI.
