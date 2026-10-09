# Release notes — APP v2.7.0 · Google Drive + ZIP

Base funcional conservada:

- BiblioRef extractor **0.9.8 / algoritmo 0.6.4**
- parser **v0.11 candidate**
- StyleProfiler **v0.1-shadow**

La APP pasa de 2.6.9 a **2.7.0** exclusivamente por cambios de ingestión/interfaz.

## ZIP

- carga local `.pdf` y `.zip` desde selector, carpeta o drag-and-drop;
- búsqueda recursiva de PDF dentro del ZIP;
- ZIP anidados hasta profundidad 2;
- validación de firma PDF antes de entregar el archivo al preflight normal;
- protección contra path traversal, ZIP cifrado, miembros desmesurados, tamaño total descomprimido excesivo y relaciones de compresión sospechosas;
- provenance por tesis: miembro, cadena de archivos, SHA-256 y origen.

## Google Drive

- OAuth de aplicación de escritorio;
- scope único `drive.readonly`;
- navegador de carpetas en la UI;
- importación de PDF, ZIP o carpetas completas;
- recorrido recursivo de carpetas;
- soporte para accesos directos y parámetros de Shared Drives;
- token y `client_secret` almacenados localmente;
- ningún endpoint de escritura hacia Drive.

## Garantías de arquitectura

La nueva capa sólo entrega bytes PDF al pipeline existente. No modifica detección, segmentación, reconciliación de fronteras, parser v0.11 ni StyleProfiler.
