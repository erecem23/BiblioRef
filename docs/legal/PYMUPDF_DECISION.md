# BiblioRef — decisión pendiente sobre PyMuPDF

> **Resolución (2026-10-09): opción B.** BiblioRef se distribuye bajo la GNU AGPL-3.0 (`LICENSE`), compatible con el uso de PyMuPDF bajo AGPL, incluido el build de Windows que lo empaqueta. La instalación por defecto depende sólo de PDFium (`pypdfium2`); PyMuPDF queda como extra opcional. Lo que sigue documenta el análisis previo a la decisión.

**Fecha:** 2026-09-09  
**Estado:** bloqueo de release propietaria; no bloqueo de desarrollo interno.

## Situación técnica

PyMuPDF es una dependencia directa y funcionalmente relevante de BiblioRef. Se utiliza para abrir PDFs, leer cantidad de páginas, extraer texto y geometría y renderizar páginas. El build de escritorio de Windows recopila explícitamente el paquete `pymupdf` dentro de la distribución.

Por lo tanto, retirar el nombre de `requirements-app.txt`, instalar PyMuPDF por separado o evitar copiar su código al repositorio no se considera una solución suficiente por sí misma a la cuestión de licenciamiento.

## Situación de licencia

La documentación oficial de PyMuPDF/Artifex ofrece el software bajo dos vías: GNU AGPL y acuerdos de licencia comercial. La política oficial de Artifex indica que una aplicación/servicio que utilice la vía AGPL debe cumplir las obligaciones correspondientes, incluidas las relativas a disponibilidad del código fuente cuando se despliega como parte de una aplicación o servicio de red. Si ese modelo no es compatible con la estrategia de distribución, Artifex indica que se requiere una licencia comercial.

## Opciones para BiblioRef

### A. Mantener PyMuPDF + licencia comercial

Ventaja principal: preserva el pipeline PDF ya validado y minimiza el riesgo técnico de regresión. Permite plantear una edición propietaria/cerrada bajo las condiciones que se acuerden con Artifex.

Antes de release deben conservarse por escrito las condiciones comerciales aplicables a BiblioRef y verificar que cubran los modos previstos de distribución (desktop, servidor/SaaS u otros).

### B. Mantener PyMuPDF + cumplimiento AGPL

Implica diseñar la distribución de BiblioRef de forma compatible con AGPL y con las obligaciones que correspondan al caso de uso. No es la ruta elegida automáticamente por el mero hecho de que PyMuPDF pueda instalarse gratuitamente.

### C. Sustituir PyMuPDF

Requiere identificar una alternativa de licencia compatible y demostrar equivalencia suficiente en las funciones que BiblioRef usa actualmente. La sustitución sólo podría aceptarse después de pruebas de no regresión sobre el corpus histórico y los holdouts relevantes.

## Decisión provisional

Hasta resolver A, B o C:

- continuar desarrollo y pruebas internas;
- mantener el repositorio privado;
- no publicar una licencia definitiva de BiblioRef basada en una presunción sobre PyMuPDF;
- no distribuir públicamente/comercialmente el instalador actual de Windows;
- conservar PyMuPDF sin modificaciones funcionales para no introducir regresiones innecesarias durante la preparación jurídica.
