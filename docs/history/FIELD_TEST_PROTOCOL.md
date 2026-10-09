# BiblioRef — protocolo de prueba real

## Estado congelado

Este paquete mantiene separadas tres capas:

1. **Extractor BiblioRef v0.9.8**: decide zona y fronteras de referencias.
2. **Parser v0.11 candidate**: interpreta campos bibliográficos; no modifica fronteras.
3. **StyleProfiler v0.1-shadow**: describe morfología/consistencia después del parser; no modifica extracción ni parseo.

El helper `field_test_bundle.py` es una herramienta de diagnóstico externa a las tres capas. **No reextrae, no reparsea y no corrige registros.**

## Flujo recomendado

1. Usar BiblioRef normalmente con una tesis nueva.
2. Revisar visualmente si la zona y el número de referencias parecen correctos.
3. Exportar el CSV normal desde la aplicación.
4. En Windows, arrastrar ese CSV sobre `generar_bundle_prueba.bat`.
5. Se crea `field_test_output/*_FIELD_TEST_BUNDLE.zip`.
6. Si encontraste un problema, enviar el PDF + ese bundle + una frase breve, por ejemplo:
   - `falta la primera referencia`;
   - `34 y 35 quedaron juntas`;
   - `fila 88: artículo etiquetado como libro`;
   - `autor y año bien, revista mal`.

No es obligatorio completar la plantilla de revisión. Está incluida sólo para auditorías sistemáticas.

## Qué contiene el bundle

- copia exacta del CSV usado como entrada;
- `manifest.json`: hashes, versiones, distribuciones de rutas del parser, tipos y cobertura de campos;
- `style_profile.json`: salida completa de StyleProfiler shadow;
- `parser_profiler_diagnostics.csv`: una fila por referencia con campos parseados + features estructurales + perfil local;
- `optional_review_template.csv`: la misma referencia con columnas vacías para marcar problemas manuales.

## Regla de desarrollo

Una tesis nueva no cambia automáticamente ninguna capa. Primero se clasifica el error:

- zona/delimitación;
- frontera faltante o multireferencia;
- sobresegmentación;
- parser (autor, año, título, tipo, revista/editorial, DOI);
- profiler (familia/estilo probable/variante/consistencia);
- clase nueva.

Sólo se modifica una capa cuando la causa sea generalizable y pueda añadirse con controles negativos y no regresión.
