# BiblioRef: inicio por proyectos y explorador de carpetas

Base: `erecem23/BiblioRef`, rama `dev`, commit `f03d61cbd448268240b86fc167d8e030f0310f9a`.

## Cambio

- Inicio con creación, búsqueda y apertura de proyectos recientes. No muestra tesis individuales.
- Cada proyecto conserva su nombre, descripción, tesis y preferencias de organización. Guardado automático al cargar y botón Guardar proyecto.
- Carga de PDF, ZIP y carpetas completas. El navegador transmite la ruta relativa; las rutas internas de ZIP y ZIP anidados también aparecen en el explorador derecho.
- Cada tesis pertenece a un proyecto mediante un identificador explícito. Cambiar de proyecto reinicia las selecciones de revisión y exportación. La selección exportada sigue siendo explícita.
- Las tesis guardadas por versiones anteriores se agrupan en Proyecto anterior; la migración añade pertenencia y conserva PDF, referencias, correcciones y metadatos.
- Agrupación opcional y experimental por universidad para archivos sueltos, utilizando el detector de portada ya instalado por el lanzador. Las carpetas originales siempre tienen prioridad. La universidad se corrige en Datos de la tesis.
- Los archivos inválidos generan avisos; una carga parcialmente válida conserva los PDF incorporados. Las rutas inseguras se rechazan.

## Verificación

33 pruebas API pasan: 7 nuevas de proyectos y 26 existentes de carga, revisión y exportación. Incluyen reapertura desde disco, nombres de PDF repetidos entre proyectos, jerarquías de carpetas y ZIP anidados, migración con correcciones y aislamiento de la selección exportada.

`node --check` pasa para ambos scripts. Un ensayo de DOM con jsdom y respuestas API simuladas pasa para inicio, apertura, árbol, creación, limpieza de selecciones, guardado, regreso al inicio, respuesta tardía de actualización y pertenencia durante la lectura de carpetas; no equivale a inspección visual del navegador. Las reglas de extracción y los módulos del parser no se modifican.

La revisión visual en navegador y las pruebas de selección/arrastre nativos quedaron pendientes: el navegador de esta sesión bloqueó las direcciones locales con `ERR_BLOCKED_BY_CLIENT`. No se presenta esta revisión como completada.

## Alcance

Esta propuesta modifica la interfaz y la pertenencia de documentos a proyectos. No elimina tesis existentes ni incluye datos de demostración. Las carpetas vacías o sin PDF/ZIP no se incorporan. La conexión Drive conserva su flujo previo y ahora asigna cada importación al proyecto indicado.

Para probar en la aplicación: iniciar con `python run_biblioref.py`, crear un proyecto, cargar una carpeta/ZIP, volver a Inicio y reabrirlo.

## Continuación (2026-09-09)

Se protege la pertenencia durante la lectura de carpetas y la importación de Drive. Las respuestas de selección/actualización que llegan después de cambiar de proyecto se descartan en la interfaz. El procesamiento de otro proyecto no cambia la vista actual al terminar. Se evita duplicar un proyecto al enviar repetidamente el formulario.

El ensayo DOM reproducible está en `tests_ui/projects_flow.cjs`; ejecutar `cd tests_ui`, `npm install` y `npm test` (Node 20.19 o superior compatible con jsdom 30). Usa datos y respuestas simuladas; no sustituye el selector nativo ni la inspección visual.

## Progreso y legibilidad (2026-09-09)

- Aviso de tarea visible sobre el contenido, con barra y estado de finalización o error. El envío usa los bytes informados por XMLHttpRequest; la lectura/guardado muestra una barra indeterminada, sin porcentaje estimado. El procesamiento por lote usa la cantidad de tesis terminadas. Apertura de proyecto e importación Drive también muestran actividad.
- Tipografía y controles más grandes, contraste de textos secundarios reforzado, nombres directos para los botones de carga y buscador de título/archivo/carpeta/universidad dentro del proyecto. El árbol conserva los antecesores de los resultados.
- Cada PDF reutiliza el título que acaba de detectar la misma capa durante su incorporación. No se conserva una caché entre documentos o migraciones. La respuesta de carga se usa para actualizar la lista, evitando una nueva consulta completa y la reapertura de la tesis seleccionada.
- 40 pruebas locales focalizadas aprobadas, incluido el control de una sola lectura de título con igualdad de resultados. Ensayo DOM con envío simulado, transición a lectura indeterminada, búsqueda, éxito/error e identidad de proyecto aprobado. La inspección visual y el selector nativo corresponden a la prueba del usuario.
- No se cuantifica una mejora de velocidad sobre corpus reales a partir de estas comprobaciones.

## Lectura incremental y procesos paralelos (2026-09-09)

La importación local ahora opta por una respuesta NDJSON. Después del envío, identifica los PDF del lote y comunica el número total, los archivos en curso, el tiempo transcurrido y la cantidad terminada. Cada tesis se guarda y aparece en la lista y el árbol antes de que termine el lote. Un error posterior conserva las tesis ya guardadas; un fallo al guardar no se anuncia como éxito. Si se cierra la pestaña, el servidor continúa el lote mientras la aplicación siga abierta.

La lectura de PDF, títulos y portadas se distribuye entre procesos independientes con `spawn`, también compatible con Windows. El análisis de referencias desde la interfaz utiliza el mismo conjunto de procesos, con resultados aplicados y guardados por la aplicación principal. Se mantienen los algoritmos de extracción, parser y guardia de primera referencia. El valor automático es hasta cuatro procesos, dejando un procesador lógico libre cuando es posible. Para equipos con poca RAM se puede iniciar con `BIBLIOREF_WORKERS=1`; el ajuste explícito permite hasta ocho, limitado por los procesadores disponibles. El límite es común a importación y análisis. La unidad paralela es la tesis, no las páginas de una única tesis. La descarga desde Google Drive conserva su ruta previa.

También se corrige una contradicción entre la revisión de títulos de la app base y la capa de metadatos: las consultas de documentos actuales ya no vuelven a leer el título y la portada. Las migraciones de revisiones anteriores siguen ejecutándose, conservando la protección de datos humanos.

Medición reproducible: `python benchmark_pdf_workers.py --synthetic 24 --workers 4`. En este entorno, 24 PDF sintéticos de 40 páginas: 35,804 s de preparación secuencial frente a 13,565 s con cuatro procesos, incluido su arranque en frío (2,64×); resultados idénticos de preflight, título y metadatos. No mide la transferencia, el análisis bibliográfico completo ni el corpus del usuario, y no garantiza la misma aceleración en otro equipo.

Pruebas adicionales: dos procesos reales distintos con resultados equivalentes; transmisión por HTTP real antes de finalizar el último archivo; respuesta de la API durante una lectura demorada; persistencia y jerarquía de ZIP anidados; error de PDF y error de guardado; ausencia de relecturas en GET; equivalencia del análisis bibliográfico con la ruta anterior. El ensayo DOM incluye fragmentos NDJSON partidos, aparición de tesis antes de terminar, fallo posterior sin pérdida de las incorporadas y límite de solicitudes paralelas.

## Espacio de trabajo ajustable (2026-09-09)

- Carga compacta arriba: PDF/ZIP, carpeta completa, Google Drive y zona de arrastre. Los mensajes y el progreso de la carga siguen visibles.
- Explorador a la izquierda por defecto; las tesis ocupan el panel central. Puede moverse a la derecha o arriba, a todo el ancho, arrastrando su título o desde Disposición.
- Separador ajustable con mouse, entrada de puntero o flechas del teclado. Se puede ocultar el explorador y recuperarlo desde la barra; Restablecer disposición devuelve la configuración inicial.
- Las preferencias de ubicación, visibilidad y tamaño se guardan en este navegador, sin modificar el proyecto ni las tesis. La pantalla angosta apila los paneles y conserva la preferencia de escritorio.
- Un clic en el archivo lo ubica y resalta en la lista; un doble clic abre la revisión. Los nombres largos ocupan una línea en el árbol y se leen completos al pasar el mouse. La agrupación por universidad queda plegada inicialmente.

Verificación: ensayo DOM del flujo existente y controles de movimiento/tamaño/selección; reapertura de preferencias, disposición angosta, almacenamiento bloqueado o JSON inválido. Comando: `cd tests_ui && npm test` (requiere instalar las dependencias de tests_ui). La vista en el navegador de esta sesión está bloqueada por `ERR_BLOCKED_BY_CLIENT`: no se presenta como revisión visual completada. El ajuste alcanza a los paneles de la colección; no incorpora ventanas flotantes ni redistribuye los paneles de auditoría.
