# BiblioRef — snapshot de preparación de propiedad intelectual

**Fecha:** 2026-09-09  
**Repositorio:** `erecem23/BiblioRef`  
**Visibilidad al momento del snapshot:** privada  
**Propósito:** dejar una referencia documental interna de la versión existente durante la preparación del depósito/registro de software. Este archivo no constituye una licencia ni una publicación del software.

## Estado

El snapshot se crea después de incorporar:

- `docs/legal/IP_RELEASE_CHECKLIST.md`;
- `THIRD_PARTY_NOTICES.md`.

La aplicación continúa en desarrollo. El commit que incorpora este documento debe utilizarse como referencia Git inicial del snapshot y conservarse en el historial. Para el paquete final de depósito se generará adicionalmente un archivo fuente reproducible y su SHA-256.

## Condiciones de distribución

A la fecha de este snapshot:

- BiblioRef no tiene una licencia pública definida;
- PyMuPDF es una dependencia directa del pipeline PDF;
- el build de escritorio de Windows incorpora PyMuPDF;
- no se considera aprobada todavía una distribución propietaria/cerrada que incluya PyMuPDF;
- antes de una release pública o comercial se resolverá la licencia comercial de Artifex o una sustitución técnicamente validada de la dependencia.

## Evidencia que debe conservarse

- historial Git completo;
- SHA de este commit y de la release registrable definitiva;
- resultados de tests de la release;
- documentación de arquitectura y desarrollo;
- inventario de dependencias y licencias;
- SHA-256 del paquete presentado ante DNDA.
