# BiblioRef — checklist de propiedad intelectual y release

> **Actualización (2026-10-09):** la licencia pública quedó definida (AGPL-3.0, ver `docs/legal/PYMUPDF_DECISION.md`) y el código se publica en un repositorio con historial nuevo. Las secciones 1 y 6 describen el estado previo a esa decisión. Siguen abiertos los puntos de DNDA (sección 4) y de marca (sección 5).

**Estado:** preparación interna. Este documento no constituye una licencia ni concede derechos de uso a terceros.

**Fecha de inicio:** 2026-09-09

## 1. Estado actual

- Repositorio: privado.
- Licencia pública de BiblioRef: no definida.
- No publicar ni distribuir una release cerrada mientras permanezca sin resolver la licencia de PyMuPDF.
- Mantener separados los derechos sobre el código original de BiblioRef y las licencias de dependencias de terceros.

## 2. Release registrable

Antes del depósito/registro:

- [ ] Seleccionar un commit estable de `main` como snapshot registrable.
- [ ] Registrar SHA del commit.
- [ ] Generar archivo fuente reproducible de la versión.
- [ ] Generar SHA-256 del archivo fuente.
- [ ] Incluir README, documentación funcional y versión del software.
- [ ] Ejecutar la suite completa de tests y conservar el resultado.
- [ ] Generar inventario de archivos originales incluidos en la release.
- [ ] Excluir secretos, credenciales, tokens, PDFs de terceros y corpus cuya redistribución no esté autorizada.

## 3. Dependencias y licencias

- [x] Identificar PyMuPDF como dependencia directa.
- [x] Confirmar que el build de Windows incorpora PyMuPDF.
- [ ] Auditar todas las dependencias directas y transitivas de la aplicación.
- [ ] Completar `THIRD_PARTY_NOTICES.md` con licencia, copyright y enlace oficial de cada dependencia redistribuida.
- [ ] Decidir estrategia para PyMuPDF antes de distribución pública o comercial.

### PyMuPDF — decisión pendiente

PyMuPDF se ofrece bajo licencia AGPL y licencia comercial de Artifex. En BiblioRef no es una dependencia marginal: participa en la apertura del PDF, extracción de texto y geometría, conteo de páginas y renderizado, y actualmente se recopila dentro del build de Windows.

Para una versión propietaria/cerrada, las rutas previstas son:

1. obtener una licencia comercial de Artifex para el caso de uso de BiblioRef; o
2. reemplazar PyMuPDF por una dependencia con licencia compatible y validar equivalencia/no regresión antes de release.

No se asumirá que separar el paquete, instalarlo aparte o declararlo como dependencia elimina por sí mismo las obligaciones de su licencia.

## 4. Derecho de autor — Argentina

- [ ] Preparar el paquete para depósito/registro de software ante DNDA.
- [ ] Identificar autoría y titularidad en la presentación sin atribuir como propio código de terceros.
- [ ] Conservar constancia, número de trámite y certificado/depósito.
- [ ] Registrar una nueva versión cuando exista una actualización material que convenga documentar.

## 5. Marca BiblioRef — Argentina

- [ ] Buscar antecedentes de la denominación `BiblioRef` en INPI.
- [ ] Definir clases de Niza pertinentes para software y servicios asociados.
- [ ] Presentar solicitud de marca cuando se confirme disponibilidad suficiente.
- [ ] Conservar expediente y renovaciones.

## 6. Política de release

Hasta cerrar las decisiones anteriores:

- repositorio privado;
- sin `LICENSE` pública;
- sin publicación del código;
- sin distribución pública/comercial del instalador que incorpora PyMuPDF;
- demos y pruebas internas permitidas conforme a las licencias aplicables, sin convertirlas automáticamente en una release pública.

## 7. Evidencia de autoría y evolución

Conservar de manera versionada:

- historial Git y commits;
- informes de desarrollo y validación;
- tests y resultados congelados;
- archivos SHA-256;
- documentación de arquitectura y decisiones;
- releases internas y sus fechas;
- contribuciones de terceros, si las hubiera, claramente identificadas.

## 8. Próximos pasos operativos

1. Congelar el snapshot registrable.
2. Completar auditoría de dependencias.
3. Resolver PyMuPDF.
4. Preparar paquete DNDA.
5. Buscar y solicitar marca BiblioRef ante INPI.
6. Recién después definir la licencia pública/comercial de BiblioRef y la política de distribución.
