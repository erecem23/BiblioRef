# BiblioRef APP v2.7.0 — integración Google Drive + ZIP

**Base preservada:** BiblioRef 0.9.8 / algoritmo 0.6.4 / stable 0.4.5  
**Parser:** v0.11 candidate  
**StyleProfiler:** v0.1-shadow  
**Cambio funcional:** sólo ingestión + UI + dependencias opcionales de Google Drive.

## 1. ZIP

Se agregó `biblioref/ingestion/archives.py` (`zip-ingestion-0.1`). El selector, carga por carpeta y drag-and-drop aceptan `.pdf` y `.zip`.

Un ZIP se interpreta como contenedor de tesis: se buscan PDF recursivamente y se aceptan ZIP anidados hasta profundidad 2. Los demás formatos se ignoran. Cada PDF resultante vuelve a entrar por el `pdf_preflight()` normal de BiblioRef antes de registrarse.

Controles de seguridad:

- path traversal / rutas absolutas bloqueadas;
- ZIP cifrados bloqueados;
- máximo 10.000 miembros;
- máximo 1 GiB por miembro y 2 GiB total descomprimido;
- control conservador de relación de compresión para archivos grandes;
- verificación de firma `%PDF-` antes del preflight;
- no se ejecuta ningún contenido del ZIP.

Provenance por documento: `source`, `archive_member`, `archive_chain`, SHA-256 y tamaño del PDF.

## 2. Google Drive

Se agregó `biblioref/integrations/google_drive.py` (`google-drive-readonly-0.1`).

Flujo de usuario:

1. `Cargar tesis → Google Drive…`;
2. configurar una sola vez un `client_secret.json` OAuth de tipo Desktop app;
3. conectar en navegador;
4. navegar Drive desde BiblioRef;
5. seleccionar PDF, ZIP o carpeta;
6. importar al proyecto local;
7. procesar con el pipeline normal.

La integración solicita exclusivamente `drive.readonly`. No existen endpoints de subida, modificación o borrado en Drive.

Se admiten carpetas recursivas, accesos directos cuyo destino sea compatible y parámetros de Shared Drives. Un ZIP descargado de Drive usa exactamente la misma capa segura de ZIP local.

Secretos y tokens se guardan fuera del workspace del proyecto, en `~/.biblioref/`, y no se exportan con los resultados.

## 3. Arquitectura

```text
local PDF ───────────────┐
local ZIP → safe unzip ──┤
Google Drive PDF ────────┤→ PDF local → pdf_preflight → extractor 0.9.8
Drive ZIP → safe unzip ──┘                              ↓
                                                   parser v0.11
                                                        ↓
                                              StyleProfiler shadow
```

La procedencia sólo acompaña al documento como metadato de ingestión. No interviene en detección, segmentación, parsing ni StyleProfiler.

## 4. No regresión

Comparación byte a byte contra el paquete anterior del proyecto:

- `biblioref/parsing/`: **idéntico**;
- `biblioref/styleprofiler/`: **idéntico**;
- `biblioref/extraction/`: **idéntico**;
- `biblioref/detection/`: **idéntico**;
- `biblioref/adaptive/`: **idéntico**;
- `biblioref/grammar/`: **idéntico**;
- `biblioref/core/`: **idéntico**.

Suite completa: **536 passed, 3 skipped, 16 subtests passed**.

## 5. Límite de validación de Drive

El contenedor de desarrollo no permite instalar las dependencias Google ni realizar el OAuth externo. Por eso se validaron en este entorno la configuración OAuth, selección de tipos, shortcuts, navegación mediante un servicio Drive simulado y toda la integración HTTP local; el login OAuth y la descarga real deben verificarse en el equipo del usuario con conexión a Internet. La distribución instala `google-api-python-client`, `google-auth-oauthlib` y `google-auth-httplib2` mediante `requirements-app.txt`.
