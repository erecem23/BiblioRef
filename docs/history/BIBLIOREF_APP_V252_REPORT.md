# BiblioRef v0.9.6 — APP v2.5.2

Fecha: 2026-09-02

## Alcance

Esta revisión toma APP v2.5.1 como base e integra la auditoría visual/UX aportada por el usuario, más correcciones funcionales en la capa de aplicación. El núcleo BiblioRef mantiene `SOFTWARE_VERSION=0.9.6`, `ALGORITHM_VERSION=0.6.2` y `STABLE_ENGINE_VERSION=0.4.5`; la revisión efectiva de extracción persistida de la APP se eleva a `v096-app252-alonso-5`.

## 1. Auditoría visual integrada

- `Control de extracción` queda visible antes de los metadatos.
- `Datos de la tesis` pasa a un `<details>` colapsado y navegable por teclado.
- Bordes de página usan prefijos textuales `⚠ revisar` / `✓ ...`, no sólo color.
- `Inicio` y `Final` del visor quedan neutrales; color de éxito/advertencia se reserva para estados.
- `pill.neutral` para sin procesar/procesando y `pillClass()` centralizado.
- `--warn=#8a4f42` y foco `:focus-visible` explícito.
- botones `.xs` con mayor altura/padding.
- referencias a 13.5px / 1.5 de interlineado.
- acciones rápidas de referencias normales aparecen por hover/foco/selección; permanecen visibles en referencias problemáticas y en táctil.
- comparación de bordes usa las líneas reales de `/page/{n}/lines` para centrar una ventana aproximada de 170 pt alrededor del contenido y `minmax(0,1fr)` para evitar grid blowout.
- jerarquía dinámica Inicio: `Cargar tesis` es primario cuando no hay nada pendiente; `Procesar` es primario cuando sí lo hay.

## 2. Primera referencia / Alonso

Se detectó que el problema no era únicamente visual. Una reproducción sintética del patrón `encabezado → línea de autores → año en la línea siguiente → Altieri` mostró que el motor podía devolver la continuación con año como primer registro o saltar el prefijo.

APP v2.5.2 incorpora una guardia acotada y auditable (`_first_reference_guard`) que sólo opera cuando existe un encabezado bibliográfico explícito antes del primer registro devuelto:

1. si la línea de autor quedó fuera y el primer registro comienza como continuación con año diferido, antepone el prefijo físico al primer registro;
2. si entre el encabezado y el primer registro hay una entrada completa con año propio, la inserta como nueva primera referencia;
3. si no hay encabezado explícito o evidencia bibliográfica suficiente, se abstiene.

La guardia no se aplica a regiones sin encabezado inferidas, para no introducir referencias por adivinación. Cuando actúa, se recalcula `CoverageReport`.

## 3. `＋ desde PDF`

- margen vertical por defecto: 42 pt (antes 28);
- la UI envía también la coordenada X;
- si hay una línea alineada con la X del clic, se privilegia esa columna;
- dentro del margen se puntúan comienzos bibliográficos plausibles, incluidos autores cuyo año aparece en la línea siguiente;
- encabezados bibliográficos no pueden ganar el snap;
- se informa el margen y la distancia de ajuste en el modal;
- el modo sigue siendo de un solo uso y `Esc` cancela.

## 4. Migración de proyectos

Editar título, universidad, repositorio u otros metadatos ya no congela una extracción antigua. `_has_manual_work()` distingue trabajo que se perdería al reextraer (referencias editadas/insertadas/eliminadas, límites manuales) de cambios persistentes que sobreviven (metadatos y decisiones de auditoría).

La nueva `EXTRACTION_REVISION` vuelve obsoletas las listas persistidas por APP anteriores. Las tesis antiguas sin trabajo manual bibliográfico pueden actualizarse automáticamente; las que sí tienen trabajo manual muestran actualización explícita con snapshot previo.

## 5. Inicio / dashboard / exportación

Se conserva el flujo v2.5.x:

`Inicio → Proyecto → Referencias por tesis → Exportar`

El procesamiento por lote ahora considera tanto PDF sin procesar como extracciones obsoletas que pueden refrescarse sin riesgo de perder trabajo manual. El dashboard se actualiza al finalizar una reextracción y refleja el nuevo conteo de referencias.

## 6. Validación

Suite completa incluida en el bundle:

```text
346 passed, 3 skipped, 16 subtests passed
```

Adicionalmente:

- `node --check static/app.js` OK;
- `python -m py_compile app.py run_biblioref.py run_biblioref_desktop.py` OK;
- tests focales para snap con año diferido, coordenada X, metadatos que no bloquean actualización, inserción de primera referencia omitida y recomposición de autor diferido.

## 7. Ejecución

Puerto de esta revisión: `http://127.0.0.1:8775`.

El proyecto del usuario continúa en `%USERPROFILE%\.biblioref\projects\default`.
