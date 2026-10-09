# Field Test Toolkit v0.1

Esta capa operacionaliza la prueba real sin modificar el comportamiento de BiblioRef.

## Congelado

- BiblioRef: **v0.9.8**
- algoritmo efectivo: **v0.6.4**
- stable engine: **v0.4.5**
- APP: **v2.7.0** (ZIP + Google Drive; helper sin cambios)
- parser: **v0.11 candidate**
- StyleProfiler: **v0.1-shadow**

## Nuevo

`field_test_bundle.py` toma un CSV exportado por BiblioRef y genera un bundle de evidencia reproducible. No reextrae ni reparsea. Incluye hash del CSV, versiones observadas, rutas del parser, distribución de tipos, cobertura de campos, perfil shadow por zona, diagnóstico por referencia y una plantilla opcional de revisión.

`generar_bundle_prueba.bat` permite crear el mismo bundle en Windows arrastrando el CSV sobre el archivo.

El manifest detecta si el CSV proviene de un parser distinto del parser actual del paquete. La discrepancia se informa y nunca se corrige silenciosamente.

## Validación

Suite completa tras añadir el toolkit:

- **536 passed**
- **3 skipped**
- **16 subtests passed**

Se verificó además el flujo con el CSV Palma de parser v0.11: 322 referencias, una zona, variante `legacy_year_final`, consistencia 1.0 y sin discrepancia de versión.
