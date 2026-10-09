# BiblioRef APP v2.6.5 — Parser bibliográfico v0.6

**Fecha:** 2026-09-02  
**Software:** BiblioRef 0.9.6  
**Algoritmo de extracción:** 0.6.2  
**Stable engine:** 0.4.5  
**APP:** 2.6.5  
**Parser downstream:** biblioref-parser-v0.6 · schema 6

## 1. Alcance

Parser v0.6 amplía la ruta ABNT introducida en v0.5 sin modificar el extractor de PDF. La referencia cruda continúa siendo la autoridad y el parser sólo añade metadatos downstream.

Familias nuevas o ampliadas:

- autor ABNT con **apellido + nombre desarrollado** (`ADICHIE, Chimamanda Ngozi`);
- combinaciones de iniciales, partículas y una inicial final sin punto antes de `;`;
- autores múltiples en variantes ABNT poco normalizadas;
- distinción entre `In:` que introduce un contenedor de libro y `In:` que precede una fuente periódica;
- reconocimiento explícito de `Tese` y `Dissertação`;
- artículos ABNT que no contienen obligatoriamente la secuencia rígida `v./n./p.`;
- recuperación conservadora de editorial canónica y forma observada.

No existen reglas por universidad, repositorio, país o nombre de tesis.

## 2. Desarrollo consumido

Las 30 referencias que constituyeron el holdout ABNT externo de v0.5 pasan formalmente a **development/regression** de v0.6. Las reglas de v0.6 se desarrollaron usando exclusivamente esos errores ya observados.

La suite específica verifica, entre otros, nombres desarrollados, partículas, `In:` revista/capítulo, Tese/Dissertação y artículos sin la terna estricta de volumen/número/páginas.

Estas cifras y casos no son validación externa de v0.6.

## 3. No regresión histórica

Antes del nuevo holdout se escanearon las **29.027 referencias históricas empaquetadas**. La nueva ruta ABNT ampliada de v0.6 se activó en **0/29.027**.

Por lo tanto, para ese corpus se conserva la semántica efectiva de v0.5. Las métricas de desarrollo heredadas quedan en aproximadamente:

- revista fuzzy ≥ .90: **79,13%**;
- cobertura de revista: **84,88%**;
- tipo documental (clase alta): **83,84%**;
- editorial canónica exacta: **93,67%**;
- cobertura editorial: **95,45%**.

## 4. Freeze previo al holdout externo

Se congelaron antes de ejecutar el parser sobre las nuevas referencias:

- `biblioref/parsing/v06.py`: `c09e87c6f76552d5b3e0f29f846e896224a81c353f2b60eeb4c0c34fb479c942`;
- gold externo: `23d575357fd38c0e54e2a497610d1339550fba31d70f2198e09d146d35f3bbb5`.

El hash de `v06.py` se volvió a comprobar después de la evaluación y permaneció idéntico. **No hubo parches post-holdout.**

## 5. Holdout externo v0.6

El conjunto contiene **30 referencias de 3 tesis y 3 repositorios nuevos**:

1. UFMG — Maurício, tesis doctoral;
2. UnB — Cerqueira, tesis doctoral;
3. UFRGS — Souza, tesis doctoral.

Composición del gold: 18 libros, 7 tesis/disertaciones, 3 capítulos y 2 artículos.

### Resultado global v0.5 → v0.6

| Campo | v0.5 | v0.6 |
|---|---:|---:|
| Autor exacto | 83,33% | **73,33%** |
| Año exacto | 96,67% | **96,67%** |
| Título exacto | 3,33% | **33,33%** |
| Título fuzzy ≥ .90 | 3,33% | **73,33%** |
| Revista exacta/fuzzy ≥ .90 | 0,00% | **0,00%** |
| Cobertura revista | 0,00% | **100,00%** |
| Tipo documental exacto | 3,33% | **70,00%** |
| Editorial canónica exacta | 3,57% | **50,00%** |
| Editorial observada exacta | 3,57% | **53,57%** |
| Cobertura editorial | 3,57% | **57,14%** |

La ruta ABNT ampliada se activó en **24/30** referencias.

### Comparación pareada

- título fuzzy: **21 mejoras / 0 regresiones**;
- tipo documental: **20 / 0**;
- editorial canónica: **13 / 0**;
- editorial observada: **14 / 0**;
- autor: **0 mejoras / 3 regresiones**;
- año: **1 mejora / 1 regresión**;
- revista: 0 mejoras/0 regresiones en exactitud, aunque cobertura pasa a 2/2.

## 6. Lectura metodológica

v0.6 es una **gran mejora estructural ABNT**, pero no es monotónicamente superior en todos los campos. Debe reportarse con las regresiones visibles.

Los tres retrocesos de `author` no son fallos de identificación del bloque completo de autores: son una **inconsistencia de esquema**. En referencias con varios autores de nombre desarrollado, v0.6 puede colocar todo el bloque en `author`; el contrato histórico de ese campo era primer autor, mientras `authors` contiene el conjunto.

La regresión de año ocurre cuando una URL posterior contiene el número `1843` y la referencia usa `Disponível:` en vez de la variante de acceso ya filtrada. v0.6 elige 1843 en lugar del año bibliográfico 2019.

## 7. Otros límites descubiertos — ya quemados para v0.7

1. limpiar `journal` de metadatos como `(in)`, `v.`, `n.` una vez recuperada la fuente;
2. aceptar `(in)` además de `In:`;
3. ampliar la detección de autor/editor del contenedor en capítulos;
4. autores de una sola palabra o sin coma (`ARISTÓTELES`, `ARENDT. Hannah`);
5. dobles puntos en iniciales (`R.G..`);
6. separar edición, extensión y año repetido del título;
7. recuperar institución/editorial en tesis y disertaciones;
8. referencias colon-rich atípicas como control de abstención.

No se corrigió ninguno después de abrir el holdout.

## 8. Estado de release

La APP v2.6.5 usa v0.6 como parser downstream por defecto y conserva alias de compatibilidad para v0.5, v0.4, v0.3, v0.2 y legacy. El parser no está importado por `biblioref/pipeline.py` y no participa en detección ni segmentación.

El próximo trabajo correcto es desarrollar **Parser v0.7** sólo a partir de los errores ya quemados de este holdout, congelarlo y evaluarlo sobre tesis ABNT nuevas.

## 9. Verificación final

- `pytest`: **412 passed, 3 skipped, 16 subtests passed**;
- `node --check static/app.js`: **OK**;
- `py_compile` de APP, runners, pipeline, configuración, CLI y `v06.py`: **OK**;
- núcleo extractor: **14/14 archivos SHA-256 idénticos** a la release v0.5;
- hash final de `v06.py`: `c09e87c6f76552d5b3e0f29f846e896224a81c353f2b60eeb4c0c34fb479c942` (**idéntico al freeze previo**).
