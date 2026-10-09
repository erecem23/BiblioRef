# BiblioRef APP v2.6.6 — Parser bibliográfico v0.7

**BiblioRef:** 0.9.6  
**Algoritmo:** 0.6.2  
**Motor estable:** 0.4.5  
**APP:** 2.6.6  
**Parser downstream:** `biblioref-parser-v0.7` · schema 7

## 1. Alcance

Parser v0.7 refina exclusivamente la estructuración bibliográfica downstream. No modifica detección de zonas, segmentación, límites de referencia ni texto crudo. La referencia cruda sigue siendo la autoridad.

## 2. Objetivos de desarrollo

v0.7 usa como desarrollo únicamente errores ya expuestos por el holdout v0.6:

- restaurar `author` como **primer autor**, dejando el conjunto en `authors`;
- impedir que números dentro de URLs posteriores a `Disponível:` ganen como año;
- aceptar `(in)` y mejorar capítulo vs revista;
- limpiar metadatos ABNT de revista;
- ampliar iniciales compactas/dobles y autores sin coma;
- separar edición, reimpresión, extensión y año repetido del título;
- recuperar institución de grado en `Tese` / `Dissertação`.

Las 30 referencias del holdout v0.6 pasan formalmente a development/regression y no se usan como evidencia externa de v0.7.

## 3. Freeze antes del nuevo holdout

Parser v0.7 se congeló antes de ejecutar el nuevo holdout:

`099f62a1346c6055b8c17720676d643027070d62a1a0ab2f5448ed94a36a91b3`

Gold externo congelado antes de importar/ejecutar v0.7:

`863b1d3b03ff60ab9b4d9780d6d644fce52e665438d7e76c9a8f41bdf26099c8`

El código v0.7 permaneció idéntico después de abrir el holdout.

## 4. Holdout externo nuevo

30 referencias, 10 por tesis, de tres tesis doctorales y repositorios no usados en los holdouts anteriores de esta rama:

- UFPE, Psicología, Patricia Vitória Bezerra Caetano (2023);
- UFSCar, Lingüística, Nicolle de Brito Conceição Casanova (2022);
- UFC, Educación, Debora Klippel Fofano (2023).

El gold se fijó manualmente desde las cadenas bibliográficas antes de ejecutar el parser. Esta evaluación mide **parsing de referencias**, no detección/segmentación PDF end-to-end.

## 5. Resultado externo v0.6 → v0.7

| Campo | v0.6 | v0.7 |
|---|---:|---:|
| Primer autor exacto normalizado | 66,67% | **96,67%** |
| Bloque de autores | 90,00% | **90,00%** |
| Año exacto | 100,00% | **100,00%** |
| Título exacto | 60,00% | **73,33%** |
| Título fuzzy ≥ .90 | 63,33% | **76,67%** |
| Tipo documental exacto | 73,33% | **86,67%** |
| Revista fuzzy ≥ .90 | 54,55% | **54,55%** |
| Cobertura revista | 90,91% | **90,91%** |
| Editorial exacta | 55,56% | **72,22%** |
| Editorial observada exacta | 55,56% | **72,22%** |
| Cobertura editorial | 66,67% | **83,33%** |

No había DOI objetivo en estas 30 referencias.

### Comparación pareada

- `author`: **9 mejoras / 0 regresiones**;
- `authors`: 0 / 0;
- año: 0 / 0;
- título fuzzy≥.90: **6 mejoras / 2 regresiones**;
- tipo: **4 mejoras / 0 regresiones**;
- revista fuzzy≥.90: 0 / 0;
- editorial: **3 mejoras / 0 regresiones**;
- editorial observada: **3 mejoras / 0 regresiones**.

## 6. Límites observados, no corregidos post-holdout

v0.7 queda congelado con estos casos pendientes:

1. dos referencias de tesis/disertación conservan en `title` el descriptor de grado/institución; v0.6 tenía el título limpio;
2. revistas como `Cogitare Enfermagem, Curitiba` o `Escola Anna Nery, [S.l.]` aún conservan localización;
3. `[Scielo-Scientific Electronic Library Online]` puede quedar unido al nombre de revista;
4. `ARRAIS, Ana L. e VIEIRA-SANTOS, Salomé` todavía no separa bien el segundo autor;
5. un recurso institucional web sin año (`ASSOCIAÇÃO... Quem somos`) queda fuera de la gramática estricta ABNT;
6. un capítulo con título interrogativo (`O que é um dispositivo? In:`) aún puede tratarse como libro.

Estas observaciones quedan reservadas para una futura v0.8. Modificar v0.7 con ellas invalidaría el holdout.

## 7. No-regresión

Antes de abrir el holdout se verificó que la nueva ruta estricta v0.7 no alteraba el corpus histórico empaquetado de 29.027 referencias en el prefiltro estructural utilizado para el control de seguridad. El núcleo extractor permanece congelado y debe verificarse por SHA-256 en la release final.

## 8. Interpretación

v0.7 aporta una mejora externa clara en la semántica de primer autor, títulos, tipos y editoriales. No resuelve todavía la normalización de revistas ABNT y registra dos regresiones de título. Por ello debe describirse como una mejora incremental y auditable, no como un parser ABNT completo o universal.
