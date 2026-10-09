# BiblioRef v0.9.9 candidate UNC boundary2 — migración de frontend Claude

**Fecha:** 2026-09-03  
**Base funcional:** BiblioRef v0.9.9 · APP v2.7.0 · parser v0.11 · StyleProfiler v0.1 · candidate UNC boundary2  
**Fuente visual:** `BiblioRef_completo.zip` / sistema “La Consola de Auditoría”

## Objetivo

Migrar el frontend/rediseño producido con Claude a la última rama funcional `candidate UNC boundary2` sin sustituir ni degradar los cambios más recientes del pipeline de extracción.

## Estrategia de integración

Se tomó `candidate UNC boundary2` como base autoritativa y se migraron **sólo** los artefactos de frontend y documentación visual:

- `static/index.html`
- `static/app.js`
- `PRODUCT.md`
- `DESIGN.md`
- `.impeccable/design.json`
- `HANDOFF_CLAUDE_UI.md` (proveniencia del diseño)

No se copiaron desde el paquete visual los módulos Python del pipeline, porque la comparación detectó diferencias en `biblioref/pipeline.py` y `biblioref/extraction/boundary_reconciliation.py` respecto de `boundary2`.

## Garantías de preservación

Se verificó identidad SHA-256 entre la base `boundary2` y el paquete integrado para:

- `app.py`
- `biblioref/pipeline.py`
- `biblioref/extraction/boundary_reconciliation.py`
- `tests_core/test_biblioref_v0_9_9_regimes.py`
- `BIBLIOREF_V0_9_9_UNC_BOUNDARY2_REPORT.md`
- `V099_UNC_BOUNDARY2_VALIDATION.json`

Por lo tanto, la migración no modifica la lógica runtime de extracción/parser/StyleProfiler: el cambio de producto está restringido al frontend estático.

## Funciones visuales migradas

- Sidebar oscuro fijo y canvas claro del sistema “La Consola de Auditoría”.
- Navegación Inicio / Proyecto / Referencias por tesis / Exportar.
- Vista de Proyecto en **Tabla** o **Agrupado**.
- Agrupamiento por Universidad / Área-disciplina / Estado.
- Vista de referencias en **Tarjetas** o **Planilla**.
- Toolbar del visor reorganizada y adaptable.
- Mejoras de feedback de errores y mensajes no bloqueantes.
- Modal con manejo de foco y cierre por Escape.
- Estados/badges semánticos y responsive mobile.
- Integración visual de Google Drive conservando las mismas rutas API de APP v2.7.0.

## Compatibilidad frontend ↔ API

Se compararon las rutas utilizadas por ambos `static/app.js`: los dos consumen el mismo conjunto de **33 rutas `/api/...`**. No se agregó, quitó ni renombró un endpoint backend durante la migración.

## Tests

### Pruebas de app/frontend/API

`58 passed`.

Dos tests históricos fueron actualizados porque verificaban cadenas CSS/JS literales del mundo visual anterior. Las aserciones funcionales se conservaron y se añadieron comprobaciones explícitas de las vistas **Agrupado** y **Planilla**.

### Suite completa

```text
545 passed, 3 skipped, 16 subtests passed
```

Ver `FULL_UI_MIGRATION_TEST_RESULTS.txt`.

### Smoke HTTP

Comprobado mediante `FastAPI TestClient`:

- `/` → 200
- `/static/app.js` → 200
- `/api/health` → 200

También se validó sintaxis JS con `node --check` y compilación Python de `app.py`, `pipeline.py` y `boundary_reconciliation.py`.

## Resultado

La rama resultante conserva `candidate UNC boundary2` como base funcional y adopta el frontend completo de “La Consola de Auditoría”. Es la base recomendada para continuar el desarrollo visual sin perder la última corrección de fronteras UNC.
