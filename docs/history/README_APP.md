# BiblioRef v0.9.8 — APP v2.7.0 + parser v0.11 + StyleProfiler v0.1-shadow

**Núcleo de extracción:** `SOFTWARE=0.9.8` · `ALGORITHM=0.6.4` · `STABLE_ENGINE=0.4.5`  
**Parser downstream:** `biblioref-parser-v0.11` · schema 11
**StyleProfiler:** `biblioref-styleprofiler-v0.1-shadow` · observador, sin autoridad sobre extracción/parser

## Arquitectura

```text
PDF
 ↓
detección de zona bibliográfica
 ↓
segmentación estable + reparación v0.6.1 cuando corresponde
 ↓
reconciliación conservadora de fronteras v0.6.4
 ↓
texto crudo de cada referencia (autoridad)
 ↓
parser v0.11
 ↓
autor / autores · año · tipo · título · revista · editorial · DOI
```

La novedad de v0.9.8 está **antes del parser**. En zonas autor-año con sangría francesa fuerte, el sistema aprende el margen físico de primera línea y el de continuación. Una segunda pasada busca fronteras físicas omitidas o desplazadas y sólo reemplaza la segmentación cuando supera un gate conservador de geometría, densidad bibliográfica y tamaño de cambio. No se relajaron las regex globales de inicio.

El parser continúa siendo downstream: recibe las referencias ya reconciliadas y no decide fronteras ni modifica el texto crudo. StyleProfiler se ejecuta después y tampoco modifica la salida.

## Novedades v0.7

- restaura el contrato `author = primer autor` y conserva el bloque completo en `authors`;
- corta marcadores de acceso como `Disponível:` antes de inferir el año, evitando números de URL;
- amplía variantes ABNT de autor, iniciales compactas/dobles y casos sin coma;
- acepta `(in)` como variante de `In:` y mejora la distinción de contenedores;
- limpia metadatos `v./n./p.` de nombres de revista cuando la estructura es inequívoca;
- separa descriptores de edición/reimpresión/extensión del título;
- recupera universidades como fuente/editorial en `Tese`/`Dissertação`;
- conserva v0.6/v0.5 como fallback fuera de la ruta ABNT estricta.

### Holdout externo v0.7

El código v0.7 y un gold de 30 referencias nuevas se congelaron y hashearon antes de ejecutar el parser. Las tesis provienen de **UFPE (Psicología), UFSCar (Lingüística) y UFC (Educación)**. Frente a v0.6: primer autor 66,67→96,67%; título fuzzy≥.90 63,33→76,67%; tipo 73,33→86,67%; editorial exacta 55,56→72,22%; cobertura editorial 66,67→83,33%; año permanece 100%.

La mejora no es perfectamente monotónica: hay **2 regresiones pareadas de título** y no mejora todavía el acuerdo de revista (54,55% fuzzy sobre 11 revistas objetivo). No hubo regresiones pareadas en primer autor, año, tipo ni editorial. El código v0.7 no se modificó después de observar estos resultados.

Véase `BIBLIOREF_APP_V266_PARSER_V07_REPORT.md` y `PARSER_V0_7_EXTERNAL_HOLDOUT_EVALUATION.json`.

## Historial reciente

## Novedades v0.4

- títulos complejos que contienen `?`/`!` pueden reconstruirse hasta una frontera de revista independientemente observada;
- descriptores de edición se separan del título;
- nombres de revista excesivamente abreviados se expanden sólo con evidencia estructural;
- recuperación conservadora de editoriales de una palabra en capítulos;
- `publisher` conserva la forma normalizada/canónica;
- `publisher_observed` conserva la forma literal vista en la referencia.

CSV, XLSX y JSON exportan ambos campos editoriales.

## Holdout externo v0.4

Se congelaron código y gold antes de ejecutar el parser. Son 30 referencias de tres tesis nuevas: Sheffield, York y USP. Globalmente v0.4 mejora título fuzzy de 60.0% a 66.67% y agrega 3 recuperaciones exactas de `publisher_observed`, sin regresiones pareadas. Año y DOI permanecen en 100% dentro de la muestra.

El hallazgo más importante es negativo y útil: la ruta actual no generaliza bien al estilo **ABNT**. En las 10 referencias USP/ABNT del holdout, título y revista fallan sistemáticamente y tipo sólo alcanza 20%. Por metodología, v0.4 quedó intacto después de observarlo; ABNT pasa a ser el objetivo explícito de v0.5.

Véase `BIBLIOREF_APP_V263_PARSER_V04_REPORT.md` y `PARSER_V0_4_EXTERNAL_HOLDOUT_EVALUATION.json`.


## Parser v0.8 / APP v2.6.7

Parser v0.8 sigue siendo downstream: no modifica zonas, fronteras ni texto crudo. La versión fue congelada con SHA-256 `b10079270b5df316ebbab4ad667df774280ab09f899f5b472f1e09f372bd885b` antes de abrir material externo nuevo.

Validación externa: un holdout general de 30 referencias (UnB, UFSC y una disertación UFES) mostró equivalencia exacta con v0.7 en los campos evaluados: 0 mejoras y 0 regresiones. Un segundo holdout de estrés de 20 referencias (UFT/UFU y UFPB) mostró título fuzzy >= .90 de 35% a 55% (4 mejoras, 0 regresiones), con año y DOI en 100%. La normalización de revista sigue siendo un límite: 87,5% de cobertura pero 0/8 fuzzy >= .90 en ese stress set.


## Parser v0.9 / APP v2.6.8

Parser v0.9 sigue siendo downstream: los 14 módulos de extracción, segmentación, reparación y auditoría son byte a byte idénticos a los de la release de v0.8. La versión quedó congelada con SHA-256 `4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320`.

El diagnóstico que la motiva es que la mayoría de los fallos de revista reportados para v0.8 no eran fallos de revista sino de la frontera del bloque de autores: un nombre de pila con varias iniciales contiene el punto que v0.8 usaba para cerrar el bloque, y el corte arrastraba autor, autores, título y revista de la misma referencia. v0.9 recorre la gramática del bloque en lugar de buscar el primer punto, considera metadatos de periódico posteriores al año, limpia el candidato de revista y agrega una ruta de rescate de revista APA para bloques de volumen no numéricos.

Sobre las 190 referencias de desarrollo y regresión: autor 92,63 % → 99,47 %, autores 86,25 % → 98,75 %, título fuzzy>=.90 92,11 % → 97,89 %, revista fuzzy>=.90 79,73 % → 100 %, sin regresiones. En el barrido estructural de las 29.027 filas históricas cambia el 1,24 % de las filas y se agregan 360 revistas sin eliminar ni reescribir ninguna.

Esta versión **no tiene validación externa**: los dos holdouts de v0.8 se abrieron para diagnosticarla. Para correr un holdout nuevo, congelar y hashear el gold y ejecutar:

```
python3 evaluate_parser_v09_external_holdout.py <gold.csv> <etiqueta>
```

Véase `BIBLIOREF_APP_V268_PARSER_V09_REPORT.md`, `PARSER_V0_9_DEVELOPMENT_EVALUATION.json` y `PARSER_V0_9_HISTORICAL_SWEEP.json`.


## Extractor v0.9.7

Dos clases de caracteres en el motor base, congelado en `8683e68c23773f113b27cb2453b48d7539c1ca9147d470baaf1de306d6d775fa`.

El separador de la numeración de capítulo en un encabezado acepta ahora todo el bloque Unicode de guiones, de modo que `IV–5-BIBLIOGRAFÍA.` se reconoce igual que `IV-5- BIBLIOGRAFÍA.`. Un procesador de texto convierte el guión ASCII en guión medio sin avisar, y con eso desaparecía la bibliografía de un capítulo entero. Y un marcador numérico pegado a un guión (`[1]-Autor`, `[23]- Autor`) cuenta como arranque de referencia numerada; antes exigía espacio, el estilo caía en autor-año y las referencias se fusionaban de a varias por registro.

Los catorce módulos de zonas, segmentación, fronteras, rescates y auditoría son byte a byte idénticos a v0.9.6, dos tesis reales de 300 y 449 páginas dan salida con SHA-256 idéntico entre las dos versiones, y las 752 líneas bibliográficas auténticas de los fixtures dan idéntico perfil de estilo. 491 tests pasan.

Véase `BIBLIOREF_V0_9_7_DEVELOPMENT_REPORT.md` y `EXTRACTION_EQUIVALENCE_V097.json`.


## Extractor v0.9.8 / algoritmo v0.6.4

Se agrega `biblioref/extraction/boundary_reconciliation.py` como segunda pasada entre segmentación y parsing. La reparación sólo se habilita en zonas con sangría francesa bien separada, soporte >=90 % del margen de arranque en la salida base, >=94 % de candidatos geométricos con evidencia bibliográfica local, evidencia bibliográfica >=90 % de los segmentos y una ganancia limitada a 15 % del conteo base (con techo absoluto).

En la tesis de desarrollo que motivó la versión, la segmentación v0.6.1 producía 310 registros. La reconciliación identifica 338 fronteras físicas consistentes: recupera la referencia inicial `5G Américas`, separa autores institucionales y listas de autores cuyo año cae en la línea siguiente, y corrige límites desplazados que comenzaban directamente por `(año)`. El cambio neto es +28 registros porque se recuperan 37 comienzos verdaderos y se eliminan 9 fronteras previas desplazadas/falsas.

Esta tesis es **development set**, no validación externa. La batería completa de la distribución integrada pasa con 515 tests, 3 omitidos y 16 subtests.

Véase `BIBLIOREF_V0_9_8_BOUNDARY_RECONCILIATION_REPORT.md` y `V098_TARGET_THESIS_VALIDATION.json`.

## Parser v0.10 / APP v2.6.9

Congelado en `56993eed5a0c032e9c52495eb721a2cc8ecde73ca3ad0cefd9d1fb0d152d17f2`. Sigue siendo capa downstream y su código no cambia en v0.9.8. El nuevo algoritmo v0.6.4 actúa antes de invocarlo; `biblioref_v0_2.py` continúa congelado.

Dos familias de metadatos iberoamericanos. La revista se recupera cuando la referencia trae número sin volumen (`Comunicar, (38), 51-58`), que era el caso de 44 de las 310 referencias de la tesis de prueba y de ninguna se recuperaba antes. Y la editorial se recupera cuando cierra la referencia después de un país (`Santiago de Chile, Chile: Divergente`), aceptada por el país que la precede y no por figurar en un léxico de editoriales.

Sobre esa tesis: revista 103 → 142, editorial 101 → 125, `sin_clasificar` 42 → 8, sin reescribir ninguna revista. Sobre las 190 referencias de desarrollo de parsers la salida es idéntica, y sobre las 29.027 filas históricas cambia el 0,76 % agregando 165 revistas sin eliminar ni reescribir ninguna.

Véase `BIBLIOREF_PARSER_V0_10_DEVELOPMENT_REPORT.md`, `PARSER_V0_10_TARGET_EVALUATION.json` y `PARSER_V0_10_HISTORICAL_SWEEP.json`.

## Parser v0.11 + StyleProfiler v0.1-shadow

Parser v0.11 incorpora la gramática `v11_legacy_year_final` para bibliografías históricas/iberoamericanas con año final, manteniendo v0.10 intacto fuera de esa ruta.

Se agrega además una capa **separada** `biblioref/styleprofiler/`. StyleProfiler observa el texto crudo y los campos ya parseados para describir morfología bibliográfica a nivel referencia y zona. No modifica extracción, segmentación ni parsing. La primera versión es deliberadamente heurística y se ejecuta en *shadow mode*: `confidence` queda en `null`, `unknown` es una salida válida y el contexto institucional se conserva con `used_in_decision=false`.

Endpoints experimentales:

```
GET /api/documents/{id}/style-profile
GET /api/documents/{id}/style-profile.json
```

Véase `STYLEPROFILER_V0_1_SHADOW_REPORT.md` y `docs/styleprofiler/DEEP_RESEARCH_STYLEPROFILER_2026-09-02.md`.


## APP v2.7.0 — ZIP + Google Drive

La capa de ingestión agrega dos entradas nuevas sin modificar el extractor, parser ni StyleProfiler:

- **ZIP:** acepta `.zip`, busca PDF recursivamente (incluidos ZIP anidados hasta profundidad 2), ignora otros archivos y aplica controles contra path traversal, archivos cifrados, tamaños descomprimidos extremos y relaciones de compresión sospechosas. Cada PDF conserva `ingestion.archive_member`, `archive_chain` y SHA-256.
- **Google Drive:** integración **solo lectura** mediante OAuth 2.0 para aplicación de escritorio. Permite navegar carpetas, seleccionar PDF/ZIP o una carpeta completa e importar sus PDFs al proyecto local. Las carpetas seleccionadas se recorren recursivamente. Los archivos de Drive nunca son modificados.

### Configurar Google Drive

1. Crear un proyecto en Google Cloud y habilitar **Google Drive API**.
2. Configurar la pantalla de consentimiento OAuth.
3. Crear un cliente OAuth de tipo **Desktop app / Aplicación de escritorio**.
4. Descargar `client_secret_....json`.
5. En BiblioRef: **Cargar tesis → Google Drive… → Elegir client_secret.json → Conectar**.
6. Autorizar el alcance `drive.readonly` en el navegador.

Las credenciales y el token se guardan localmente bajo `~/.biblioref/` (o en `BIBLIOREF_CONFIG_DIR`). No se incluyen secretos OAuth en la distribución.
