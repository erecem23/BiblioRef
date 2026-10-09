# BiblioRef MASTER HANDOFF — v0.9.6 + APP v2.6.3 + Parser v0.4

## LEER PRIMERO — autoridad actual

- Software: **0.9.6**
- Algoritmo efectivo de extracción: **0.6.2**
- Stable engine: **0.4.5**
- APP: **2.6.3**
- Parser downstream: **0.4 / schema 4**
- Hash congelado parser v0.4: `f12b43a4670615c9445112052b9714dd11c54f3f10c0889169c3083eb8f2d173`
- Gold externo v0.4: `0db74739ad42c675fda7bc4d9afddc07faec83643a342a39875920b6cd86292d`
- Núcleo extractor: **14/14 archivos idénticos** al release v0.3/v0.9.6.

### Qué añadió v0.4

1. reconstrucción conservadora de títulos multi-oración hasta fuente observada;
2. separación de edición terminal del título;
3. recuperación de nombre de revista completo frente a alias demasiado cortos;
4. `publisher` canónico + nuevo `publisher_observed` literal;
5. recuperación de publisher de una palabra en capítulos bajo evidencia estructural.

### Evaluación externa v0.4

Se congelaron código y 30 referencias antes de ejecutar. Tesis: Sheffield/Rutkauskas 2023, York/Brennan 2024 y USP/Pizzimenti 2024.

Resultado global v0.3→v0.4: título fuzzy **60.0→66.67%**; editorial observada exacta **0→23.08%**; sin regresiones pareadas; año y DOI 100% en la muestra. Revista y tipo quedan iguales globalmente.

El descubrimiento metodológico clave es que **ABNT es una gramática no cubierta**: en 10 referencias USP el título fuzzy es 0%, revista 0/2 y tipo exacto 20%. El código v0.4 no fue modificado después de verlo. Esas referencias quedan quemadas para v0.5.

### Próximo paso correcto

Desarrollar Parser v0.5 con una ruta ABNT general (`AUTOR EM MAIÚSCULAS. Título. Lugar: Editora, ano`; artículos `Revista, v., n., ano`) usando USP sólo como development. Luego congelar v0.5 **antes** de abrir nuevas tesis portuguesas/ABNT.

---

# Handoff histórico preservado — estado v0.3 y anteriores

# BiblioRef — handoff maestro v0.9.6 / APP v2.6.2 / parser v0.3

**Estado canónico actual:** BiblioRef v0.9.6 + APP v2.6.2 + parser bibliográfico v0.3  
**Fecha de freeze:** 2026-09-02

## 0. Override canónico: parser v0.3

Este documento hereda el historial técnico completo de versiones anteriores. Para continuar desarrollo, prevalece este bloque cuando exista una contradicción con el texto histórico inferior.

### Autoridades vigentes

- `SOFTWARE_VERSION = 0.9.6`
- `ALGORITHM_VERSION = 0.6.2`
- `STABLE_ENGINE_VERSION = 0.4.5`
- `APP = 2.6.2`
- `PARSER = biblioref-parser-v0.3`, schema 3
- extractor y parser siguen desacoplados: **el parser jamás escribe fronteras ni modifica el raw**.

### Qué agregó v0.3

- gramática `bare_year` para Harvard/autor-año sin paréntesis;
- gramática `vancouverish`;
- revistas con `:`/subtítulos preservadas completas;
- article-number/página única y colas bibliográficas adicionales;
- rescate conservador de editorial;
- instrumentos/manuales separados de libros ordinarios;
- `parse_style` en parsed/export.

### Corpus y autoridad metodológica

1. Las **29.470 referencias** continúan siendo desarrollo.
2. Las **50 referencias / 5 tesis** que fueron holdout del parser v0.2 quedaron **quemadas** al diagnosticar v0.2 y son desarrollo/regresión para v0.3.
3. Antes de abrir la reserva v0.3 se congeló `biblioref/parsing/v03.py` con SHA-256:
   `f0d62221105c4552c80ad1f6dff6014653070dcc22543fdf06c4239c2fde0b27`.
4. Se creó un gold estricto nuevo de **20 referencias directas / 2 tesis UCL**, SHA-256:
   `7ff4c1c6d8b9ad8b09925ab5b629ad6a61d45842d740e5af7252b0474fcd2d79`.
5. Recién después del freeze se ejecutaron parser v0.2 y v0.3.
6. La tesis Surrey/Petker permanece sin usar por no poder garantizar texto exacto de referencia en este entorno.

### Reserva externa v0.3

- autor exacto: 100% → 100%;
- año: 100% → 100%;
- título exacto/fuzzy90: 90% → 90%;
- revista fuzzy90: **73,33% → 93,33%**;
- cobertura revista: **93,33% → 100%**;
- tipo exacto: **95% → 100%**;
- editorial exacta: **20% → 40%**;
- cobertura editorial: **60% → 80%**;
- DOI: 100% → 100% (n=14).

Pareado: revista 3 mejoras/0 regresiones; tipo 1/0; editorial 1/0; cero regresiones en autor/título/DOI.

### Fallas abiertas que NO deben parchearse dentro de v0.3

- `The British Journal of Criminology` → `Criminology`;
- capítulo `Haley ... Willan` sin editorial;
- edición `(2nd ed.)` pegada al título de Kirkwood;
- títulos de dos oraciones separados por `?` (Kounali);
- equivalencia/canonicalización editorial (`Blackwell` vs `Blackwell Publishing`, `Guilford Press` vs `Guilford Publications`).

Si se usan estas fallas para desarrollar una futura v0.4, el gold de 20 deja de ser holdout para esa versión. v0.4 deberá evaluarse sobre material externo nuevo.

### Próximo paso recomendado

No tocar el extractor. Si se trabaja parser v0.4, hacerlo en una rama separada y buscar **nuevo holdout** antes de evaluar. La prioridad técnica es título multi-oración + política de equivalencia de editoriales + último colapso de alias de revista.

---

## Historial heredado hasta APP v2.6.1 / parser v0.2
# BiblioRef — handoff maestro de desarrollo

**Estado canónico actual:** BiblioRef v0.9.6 + APP v2.6.1 + parser bibliográfico v0.2  
**Fecha de consolidación:** 2026-09-02  

## 0. Override canónico: parser v0.2

Este documento conserva debajo el historial completo que llegó hasta APP v2.6.0/parser v0.1. Desde esta release, la autoridad downstream es `biblioref-parser-v0.2`; el extractor sigue siendo `SOFTWARE=0.9.6`, `ALGORITHM=0.6.2`, `STABLE_ENGINE=0.4.5`.

Arquitectura vigente:

```text
PDF → segmentación v0.9.6 → referencia cruda → parser v0.2 → campos estructurados
```

Invariantes: el parser no puede cambiar fronteras; la referencia cruda es autoridad; año/título/DOI se heredan exactamente de v0.1.

Resultados de desarrollo (N=29.470): revista fuzzy≥.90 39,26→76,79%; tipo grueso 68,71→82,93%; autor 71,33→72,10%; editorial v0.2 exacta 93,59% sobre 7.814 targets aceptados de la pipeline v2. Todas estas cifras son **development**, no holdout.

Validación de release: 359 passed, 3 skipped, 16 subtests; 14/14 hashes del núcleo de extracción idénticos.

Siguiente paso recomendado: **holdout del parser con anotación humana**, antes de más tuning.

---

# Historial consolidado hasta parser v0.1


**Estado canónico:** BiblioRef v0.9.6 + APP v2.6.0 + parser bibliográfico v0.1  
**Fecha de consolidación:** 2026-09-02  
**Propósito:** permitir continuar el desarrollo en otro chat, otra sesión o con otra persona sin reconstruir el historial del parser ni confundir corpus de desarrollo con validación externa.

---

## 1. Autoridades actuales

| Capa | Versión canónica | Significado |
|---|---|---|
| Software / paquete | **0.9.6** | release pública del núcleo modular |
| Algoritmo efectivo | **0.6.2** | decisiones efectivas de extracción vigentes |
| Motor estable | **0.4.5** | segmentador histórico que fue modificado deliberadamente en v0.9.6 |
| Adaptive analysis | **0.8.10-shadow23** | capa diagnóstica sin autoridad automática general |
| Rescue router | **0.9.4-selective-router3-plausibility** | selector de rescates explícitos |
| APP integrada | **v2.6.0** | aplicación local FastAPI/HTML/JS con parser downstream |
| Parser bibliográfico | **legacy-v3.2.2-adapted-v0.1** | baseline recuperado del extractor V3.2.2; separa campos internos sin modificar segmentación |
| Revisión persistida APP | **v096-app252-alonso-5** | invalida snapshots viejos cuando pueden reextraerse sin perder trabajo manual |

No volver a describir el motor estable como 0.4.4: v0.9.6 cambió reglas dentro de `biblioref_v0_4.py`. No volver a describir el algoritmo efectivo como 0.6.1: la autoridad actual es 0.6.2.

---

## 2. Principio rector que debe sobrevivir a toda versión

BiblioRef no busca una regex universal ni un extractor que "nunca falle". La arquitectura debe distinguir entre:

```text
sé segmentar esto
creo que puedo reparar esto
hay varias interpretaciones posibles
no debería decidir automáticamente
```

Reglas de diseño obligatorias:

1. **Si lo estable funciona, no intervenir.**
2. Aumentar automatización sólo cuando aumenta la evidencia.
3. La incertidumbre debe producir **abstención/revisión**, no éxito silencioso.
4. No aceptar una alternativa sólo porque devuelve más registros.
5. Separar evidencia local de frontera de la evaluación global de la segmentación.
6. Mantener trazabilidad de por qué se abrió/cerró una zona o frontera.
7. Una corrección humana sobre una tesis **no** se convierte automáticamente en una regla global.
8. El contexto positivo no basta por sí solo para verificar bibliografía.
9. La geometría aporta evidencia; por sí sola no debe crear registros arbitrariamente.
10. Evitar probabilidades decorativas o scores presentados como accuracy si no están calibrados.

---

## 2A. Parser bibliográfico downstream recuperado en APP v2.6.0

El handoff del 2026-09-01 contenía una segunda pieza que no debe confundirse con el segmentador: `biblioref_parser_legacy_v0_1.py`, derivado del viejo extractor V3.2.2. Su arquitectura correcta es:

```text
PDF
  ↓
BiblioRef v0.9.6 detecta zonas y segmenta referencias
  ↓
texto completo de cada referencia (autoridad)
  ↓
parser bibliográfico v0.1
  ↓
author / authors / year / publication_type / title / journal / source_publisher / doi
```

Reglas de integración:

1. El parser **no participa** en `process_pdf()` ni decide fronteras.
2. La referencia cruda permanece siempre disponible y es la autoridad.
3. El resultado parseado se guarda bajo `reference["parsed"]`.
4. Ediciones, divisiones, uniones e inserciones humanas recalculan sólo la capa `parsed`.
5. CSV, XLSX y JSON exportan tanto el texto crudo como los campos parseados.
6. La CLI ofrece `--parsed-csv` como salida opcional y no altera el CSV de extracción tradicional.
7. El parser conserva `parser_status = development_baseline`: no presentar sus campos como ground truth.

Baseline recuperado del handoff:

- N=29.470, corpus previamente curado de desarrollo: autor 71,33% acuerdo estricto; año 93,81%; título 92,37% fuzzy ≥ .90; revista 39,18%; DOI 97,26% recall / 99,61% precisión; tipo documental 68,71%.
- La salida de Agrazar del baseline contiene 432 ocurrencias. El port stdlib integrado en v2.6.0 reproduce esas **432/432 filas exactamente campo por campo** respecto de la implementación legacy.
- La muestra estratificada de 120 sigue siendo seed de desarrollo pendiente de confirmación humana; no llamarla gold publicable.

Orden recomendado de mejora, preservando no-regresión de año/título/DOI:

```text
revista → tipo documental → editorial/fuente → autor(es)
```

Los artefactos recuperados quedan en `docs/parser/` y `parser_baseline/`.

---

## 3. Evolución del parser: mapa corto

```text
v0.4/v0.5  motor estable de zonas + segmentación
    ↓
v0.6       stable-first; fallback sólo si falla la salida estable
    ↓
v0.6.1     reparación de subsegmentación condicionada por evidencia
    ↓
v0.7.0     modularización sin cambiar la extracción efectiva
    ↓
v0.7.1     infraestructura de benchmark y separación development/holdout
    ↓
v0.7.2     arquitectura adaptativa ensayada sobre fallas reales; cierre de desarrollo
    ↓
v0.8.x     shadow mode, verificación de región, contexto documental, geometría,
           continuidad/orden e higiene de entrada sin autoridad de escritura general
    ↓
v0.9.x     two-pass/rescue routers/plausibility + cambios efectivos acotados
    ↓
v0.9.5     vocabulario de headings y prefijos de capítulo con fullmatch anclado
    ↓
v0.9.6     fronteras físicas, párrafo, decoración, expansión de región y CoverageReport
    ↓
APP 2.5.2  integra 0.9.6 + auditoría visual + guardia acotada de primera referencia
    ↓
APP 2.6.0  agrega parser bibliográfico downstream v0.1 sin tocar fronteras
```

---

## 4. Qué dejó establecido el handoff histórico v0.7.0

El diagnóstico acumulado de v0.7.0 mostró que los errores no eran una sola regex defectuosa sino una **estratigrafía de heurísticas**: reglas razonables creadas para un patrón podían interactuar mal con otro.

Mapa histórico de fallos:

| Capa | Familia de error | Casos que lo mostraron |
|---|---|---|
| Zona | falso positivo | Marder, Fierro, Tello temprano |
| Zona | heading verdadero suprimido | Tello |
| Zona | TOC convertido en zonas | Gabini |
| Estilo | clasificación dominante incorrecta | Tello |
| Segmentación | fronteras omitidas / fusiones | Viguera, Daher, Labin, Gabini, Bogetti, Fierro |
| Reparación | sobresegmentación | Simkin |
| Auditoría | confianza no representaba calidad final | Viguera, Marder |

Lección metodológica: no responder a cada tesis con `if <caso> → excepción`. Formalizar evidencia a favor **y en contra** de cada frontera y de cada zona.

### Casos históricos de regresión prioritaria

- Gabini
- Marder
- Viguera
- Simkin
- Tello
- Bogetti
- Fierro
- Daher
- Labin

Baselines históricos documentados para reproducir familias de error (no son la autoridad de conteo actual):

| Caso | Baseline del handoff v0.7.0 | Familia |
|---|---|---|
| Tello | histórico 241; v0.7 = 5; heading real desde p.285 | heading suprimido / estilo |
| Viguera | histórico 236; v0.7 = 102; candidato = 114 | subsegmentación no activada |
| Simkin | histórico 1381; base 1387; repair 1422 | sobresegmentación / DOI |
| Marder | histórico 227; v0.7 = 225; zona falsa de 6 + real 219 | falso positivo de zona |
| Fierro | 3 zonas: vacía + narrativa 4 + real 740 | falso heading + contaminación |
| Gabini | 30 headings; 28 zonas; 13 TOC vacías + 15 reales | TOC / bibliografías por capítulo |

El detalle recuperado queda en `BIBLIOREF_V0_7_0_HANDOFF_RECOVERED_SUMMARY.md`.

### Controles históricos que no deben degradarse

- Canal
- Ramírez
- Rubiales
- Demagistri
- Aydmune
- Trógolo
- Poó
- Cosentino
- Andrés
- Peltzer
- Benítez

---

## 5. v0.6.1: reparación conservadora que sigue siendo parte del ADN del sistema

v0.6.1 introdujo señales generales para problemas reales de PDF:

- márgenes iniciales distintos por página / márgenes espejados;
- autor-año sin paréntesis;
- versalitas y caracteres espaciados;
- raya/guion como autor repetido;
- autor heredado con comienzo por fecha;
- agrupación lógica de encabezados corridos y numeración continua.

La reparación sólo se aceptaba con controles adicionales de incremento, ausencia de segmentos gigantes, longitud mediana razonable y suficiente evidencia bibliográfica. Los controles focales del challenge sirvieron para desarrollo, **no** como estimación independiente de efectividad.

Casos que deben seguir protegidos conceptualmente:

- PUCP: autor heredado;
- USP: versalitas / autor repetido;
- White Rose: márgenes espejados;
- Cambridge: año sin paréntesis;
- TU Delft: continuidad de zona y secuencia numérica.

---

## 6. v0.7.1–v0.7.2: pasar de anécdotas a corpus y taxonomías

v0.7.1 consolidó la idea de dos corpus distintos:

1. **development/regression/challenge**: documentos ya vistos, útiles para reproducir fallos y evitar regresiones;
2. **external holdout**: documentos congelados antes de inspeccionarlos, necesarios para estimar desempeño.

Los conteos históricos no deben tratarse como ground truth perfecto. Una coincidencia de conteos puede ocultar fusiones, splits o contaminación.

v0.7.2 mostró que una arquitectura adaptativa podía ayudar, pero también que debía medirse contra PDFs reales y ground truth corregido. El resultado de desarrollo llegó a 1.211/1.211 anclas y 10/10 zonas en ese corpus; sigue siendo evidencia de desarrollo, no generalización externa.

Taxonomía que debe mantenerse disponible para anotar errores:

```text
ZONE_FALSE_POSITIVE
ZONE_FALSE_NEGATIVE
ZONE_TOC_NOISE
ZONE_EMPTY
HEADING_DEDUP_FALSE_POSITIVE
STYLE_MISCLASSIFICATION
BOUNDARY_FALSE_NEGATIVE
BOUNDARY_FALSE_POSITIVE
MERGED_REFERENCES
SPLIT_REFERENCE
URL_FRAGMENT
DOI_FRAGMENT
TABLE_FRAGMENT
PROSE_FRAGMENT
REPAIR_HELPFUL
REPAIR_HARMFUL
REPAIR_NOT_TRIGGERED
CONFIDENCE_FALSE_NEGATIVE
CONFIDENCE_FALSE_POSITIVE
```

---

## 7. v0.8.x: arquitectura adaptativa en shadow

La capa adaptativa se construyó con una regla de autoridad clara: **observar y explicar antes de escribir**.

Elementos que quedaron incorporados al árbol actual:

- gramática documental (`cover`, `front_matter`, `toc`, `publications`, `chapter_open`, `body`, `bibliography_heading`, `back_matter`);
- verificación independiente de regiones descubiertas;
- conflictos de contexto que fuerzan revisión;
- detección de headers/footers recurrentes;
- clustering interpretable de sangría;
- gaps verticales robustos con mediana/MAD;
- densidad bibliográfica local;
- perfiles de orden/continuidad;
- vigilancia/higiene de decoraciones;
- generación de hipótesis y validación global;
- stable-conflict diagnostics.

Invariante: `auto_apply = false` para estas capas experimentales salvo promociones explícitas y verificadas en versiones posteriores.

---

## 8. v0.9.5: headings sin relajar el anclaje

La 0.9.5 fue el primer release reciente que volvió a tocar la extracción efectiva al ampliar el vocabulario de encabezados legítimos:

- catalán: `Referències`, `Referències bibliogràfiques`, `Obres citades`, `Fonts consultades`;
- inglés: `List of references`, `Reference list`;
- prefijos `Chapter N: References` / equivalentes.

La protección central fue **agregar alternativas sin relajar el `fullmatch`**. Se corrigieron regresiones por headers corridos y entradas del índice mediante una banda geométrica para el prefijo de capítulo.

Pendientes que v0.9.5 dejó explícitos:

- vocabulario todavía incompleto para otros idiomas;
- un heading de capítulo a media página del índice podría exigir reconciliación estructural;
- AERC necesitaba además gramática numérica;
- los 37 suplentes usados para verificar el cambio dejaron de ser holdout para cambios futuros.

---

## 9. v0.9.6: cambio efectivo actual

La v0.9.6 modificó deliberadamente tres reglas dentro del motor estable; por eso las autoridades actuales son:

```text
SOFTWARE_VERSION      0.9.6
ALGORITHM_VERSION     0.6.2
STABLE_ENGINE_VERSION 0.4.5
```

### Problema que reveló RIEA

El caso `riea_v21_n1_01.pdf` no tenía cuatro errores aislados: la anotación completa mostró 75 referencias y nueve omisiones en la salida anterior de 66.

Causas raíz:

1. `_has_bare_author_year` dependía del estilo global de la zona;
2. `_weak_boundary_supported` exigía sangría francesa y fallaba en bibliografía compuesta en bloque;
3. faltaba una regla para comienzo con editor + año diferido en continuación/página siguiente;
4. decoraciones corridas entraban en `bibliographic_lines` y contaminaban contenido y geometría.

### Implementaciones efectivas

- `biblioref_page_decorations.py`: saneamiento de decoraciones por similitud y posición extrema;
- `biblioref_paragraph_flow.py`: perfil de separación vertical sólo cuando existen dos poblaciones reales;
- autoridad **local** para fronteras de año simple;
- regla de párrafo para evitar split en la línea que contiene el año diferido;
- expansión de región hacia atrás, párrafo a párrafo;
- `biblioref_page_boundary.py`: `split` / `continue` / `review`, nunca cortar por cambio de página solo;
- `biblioref/audit/coverage.py`: verificador independiente y más permisivo que el segmentador.

### Resultado de desarrollo RIEA

```text
v0.9.5: 66 / 75
v0.9.6: 75 / 75
recall fronteras: 0.880 → 1.000
falsos positivos: 0
contaminación por decoración: 4 → 0
```

Las nueve recuperadas: Alonso Mielgo, Buttel, Collier, Hann, Motín, Ottmann, Shanin, Shiva y Wolf.

### Límites deliberados actuales

- `mixed_tight` sigue absteniéndose parcialmente cuando no hay separación tipográfica;
- el perfil de párrafo requiere suficiente material (aprox. ocho saltos en una página);
- `heading_recognition_shadow` para headings OCR espaciados sigue con `auto_apply: False`;
- una decoración de una sola página no se confirma automáticamente.

---

## 10. APP v2.5.2: qué está integrado y qué autoridad tiene

La aplicación actual no reemplaza la lógica del núcleo: la envuelve con persistencia, revisión visual, correcciones manuales y exportación.

Flujo:

```text
Inicio → Proyecto → Referencias por tesis → Exportar
```

Funciones de seguridad que deben preservarse:

- control visual de extracción antes de metadatos;
- panel de bordes con `Nueva referencia` / `Continúa anterior` / `Dejar pendiente`;
- `＋ desde PDF` como intervención humana local;
- dividir/unir referencias;
- delimitación manual;
- snapshots antes de reemplazar trabajo bibliográfico manual;
- reextracción automática sólo cuando los cambios persistidos no se perderán;
- texto original preservado en proyecto/exportación aunque la UI use `vista limpia`.

### Guardia de primera referencia

APP v2.5.2 agrega `_first_reference_guard`, limitada a casos donde existe **encabezado bibliográfico explícito** antes del primer registro devuelto. Puede:

1. recomponer un prefijo de autor cuyo año quedó en la siguiente línea;
2. insertar una entrada completa omitida entre heading y primer registro;
3. abstenerse cuando no hay evidencia suficiente.

No se aplica a regiones sin heading inferidas. Cuando actúa, recalcula `CoverageReport`.

Esta guardia es de **capa APP**, no una autorización para añadir heurísticas generales equivalentes al núcleo sin evaluación.

---

## 11. Ruta efectiva del código actual

No asumir que todo caso atraviesa primero la capa adaptativa. La lección de v0.9.6 fue que los cambios deben implementarse en la **ruta que realmente ejecuta el documento**.

Puntos de entrada principales:

```text
app.py                           aplicación local
biblioref/pipeline.py            pipeline modular
biblioref/detection/fallback.py  stable/fallback routing
biblioref_v0_4.py                motor estable efectivo
biblioref/audit/manual.py        zonas/correcciones manuales
biblioref/audit/coverage.py      verificación de cobertura
biblioref_page_boundary.py       decisión de frontera física de página
biblioref_paragraph_flow.py      evidencia de párrafo/gap
biblioref_page_decorations.py    saneamiento de decoraciones
biblioref/adaptive/*             análisis contextual/geométrico/shadow
```

Antes de diseñar un arreglo: reproducir el caso y confirmar qué función tomó la decisión que falló.

---

## 12. Corpus: roles que NO deben mezclarse

### Development / regression

Todo documento usado para diagnosticar, diseñar, ajustar o verificar una heurística deja de ser independiente para esa heurística.

Incluye, entre otros:

- challenge internacional v0.6.1;
- diagnóstico Oke / Al-Shareef / UNAM / Castignani / Machado / Núñez / Roth;
- `master_tesis` y casos históricos;
- RIEA;
- corpus/holdouts que ya hayan sido abiertos para decidir cambios de v0.9.5 o v0.9.6.

### External holdout

Debe:

1. seleccionarse con semilla nueva;
2. congelarse antes de mirar PDFs;
3. guardar SHA-256;
4. tener ground truth de zona y fronteras/referencias;
5. permanecer fuera del ajuste de reglas hasta cerrar la evaluación.

### Métricas mínimas

**Zona**
- precision/recall de región bibliográfica;
- inicio/final correctos;
- falsos headings;
- contaminación por `toc`, `publications`, CV, anexos, etc.

**Frontera**
- precision;
- recall;
- F1.

**Referencia**
- exact match normalizado;
- omitidas;
- fusionadas;
- partidas;
- fragmentos no bibliográficos.

**Documento**
- perfecto;
- usable con auditoría;
- fallido;
- número de correcciones manuales;
- tasa de abstención útil.

---

## 13. Qué NO debe afirmarse a partir del corpus de desarrollo

No convertir en estimación de efectividad frases como:

```text
101/101 challenge
1.211/1.211 anclas de desarrollo
75/75 RIEA
correlaciones altas de conteos
```

Esas cifras demuestran reproducción/corrección de casos conocidos y ausencia de ciertas regresiones, no accuracy externa del producto.

---

## 14. Próximo paso correcto

**Prioridad 1: holdout externo nuevo.**

No seguir agregando heurísticas porque exista una nueva lista de casos ya vistos. Primero medir v0.9.6 + APP v2.5.2 tal como está.

Orden recomendado:

1. congelar esta release;
2. seleccionar muestra nueva con semilla;
3. anotar ground truth sin mirar la salida de BiblioRef;
4. ejecutar núcleo y APP en modo reproducible;
5. medir zona, frontera, referencia, documento y abstención por separado;
6. clasificar errores por taxonomía;
7. sólo después abrir una nueva rama de desarrollo.

Hipótesis registrada antes del test: la mejora de v0.9.6 debería concentrarse en bibliografías en bloque y estilos mixtos de año, con poco o ningún cambio en sangría francesa uniforme. El holdout debe poder refutar esta hipótesis.

---

## 15. Regla de aceptación para una futura versión

Una versión nueva sólo debería promoverse si:

1. mejora una familia de error claramente definida;
2. conserva regresiones exactas de casos previamente estables;
3. no oculta recuperaciones parciales bajo estados de éxito;
4. mantiene evidencia/provenance de decisiones;
5. no usa el mismo corpus para inventar la regla y luego presentarlo como validación externa;
6. aumenta automatización sólo cuando la evidencia lo justifica.

---

## 16. Estado de tests al congelar esta integración

La APP v2.5.2 recibida se verificó antes de integrar este handoff:

```text
346 passed, 3 skipped, 16 subtests passed
```

La integración documental y de empaquetado debe volver a ejecutar la suite completa y `node --check static/app.js` antes de distribuir el ZIP final.

---

## 17. Mini-handoff para pegar en un chat futuro

```text
Continuar BiblioRef desde v0.9.6 + APP v2.5.2.
Autoridades: SOFTWARE=0.9.6, ALGORITHM=0.6.2, STABLE_ENGINE=0.4.5.
No degradar la red de seguridad manual de la APP.
No convertir casos de development en holdout.
No añadir excepciones por tesis: reproducir, identificar la ruta efectiva y clasificar la familia de error.
CoverageReport es verificador más permisivo; segmentación efectiva debe seguir siendo conservadora.
heading_recognition_shadow continúa auto_apply=False.
El próximo trabajo metodológicamente correcto es un external holdout nuevo y congelado, con métricas separadas de zona, frontera, referencia, documento y abstención.
Leer primero docs/handoff/BIBLIOREF_MASTER_HANDOFF_V0_9_6_APP_V2_5_2.md.
```
