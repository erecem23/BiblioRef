# BiblioRef — Repository Core + OAI-PMH v0.1
## Informe de implementación

**Repositorio:** `erecem23/BiblioRef`
**Rama:** `feat/repository-core-oai-pmh-v0-1`
**SHA inicial (`dev`):** `217a16091c76e411f4d2e53db38f1deece9c8302`
**SHA final (código):** `8c551fd` — *este informe agrega un commit `docs:` encima.*
**Fecha:** 2026-09-20

---

## 1. Qué se implementó

```text
OAI-PMH endpoint
       ↓
RepositoryRecord
       ↓
metadatos reproducibles
```

`biblioref.repositories` es un módulo independiente que se conecta a cualquier
endpoint **OAI-PMH 2.0**, cosecha Dublin Core y lo representa con objetos
internos estables. No descarga PDFs. No toca el pipeline bibliográfico.

---

## 2. Archivos creados

```text
biblioref/repositories/__init__.py        API pública + REPOSITORY_CORE_VERSION
biblioref/repositories/models.py          RepositorySource, RepositoryRecord,
                                          RepositorySet, RepositoryMetadataFormat,
                                          RepositoryIdentity
biblioref/repositories/connector.py       Protocol RepositoryConnector + errores
biblioref/repositories/oai.py             OaiPmhConnector

tests_core/test_repository_models.py      12 tests (contratos + aislamiento)
tests_core/test_oai_pmh.py                33 tests (protocolo, offline)
tests_core/test_oai_pmh_live.py           3 tests opcionales (red)

tests_support/oai_transport.py            FakeTransport + fixture_bytes
tests_support/repository_fixtures/*.xml   14 fixtures XML
```

## 3. Archivos modificados

**Ninguno.** La fase entera es aditiva: `git diff 217a160..8c551fd --name-only`
devuelve sólo archivos nuevos.

---

## 4. Resultado de la suite

| Suite | Resultado |
|---|---|
| `tests_core/test_repository_models.py` + `test_oai_pmh.py` | **45 passed** |
| `tests_core` (regresión) | **431 passed, 3 skipped, 16 subtests** |
| Suite completa (`pytest -q`) | **1193 passed, 6 skipped, 1 failed** |
| Smoke test live SEDICI | **3 passed** |

La única falla de la suite completa es
`tests_benchmarks/test_human_gold_openalex_candidates.py::test_checked_in_pilot_selection_replays_byte_for_byte`,
**preexistente y ambiental**: el test lanza `bash` por `subprocess` y en esta
máquina resuelve al `bash.exe` de WSL, que responde
`execvpe(/bin/bash) failed: No such file or directory`. No tiene relación con
esta fase (no importa nada de `biblioref.repositories`) y no se modificó ningún
expected output para ocultarla.

---

## 5. Decisiones arquitectónicas

### 5.1. La procedencia es metadato, no heurística

`biblioref.repositories` no importa `extraction`, `detection`, `parsing`,
`styleprofiler`, `adaptive` ni `grammar`. Hay un test que lo verifica en un
intérprete nuevo (`test_importing_repositories_does_not_pull_the_bibliographic_pipeline`),
inspeccionando `sys.modules` después de importar el paquete. No existe ninguna
rama de código que dependa de un repositorio, institución, país o colección.

### 5.2. No destruir información

Dublin Core es repetible y los repositorios reales lo aprovechan. SEDICI
devuelve, por ejemplo, `('1996', '1996', '2009-09-17T03:00:00Z')` en `dc:date`
para una sola tesis. Los tres valores se conservan; **no se decide todavía**
cuál es el año de publicación. Además, `raw_metadata` guarda todos los
elementos enviados, incluidos los que el contrato no nombra (`publisher`,
`contributor`, `format`, `source`…).

### 5.3. Metadatos faltantes no son errores

Título, autor, idioma, derechos, subjects o abstract ausentes producen `None`,
`()` o `{}`. Un `<header status="deleted">` produce un `RepositoryRecord` con
`deleted=True` y sin metadatos, no una excepción.

### 5.4. Namespaces, no prefijos

Todo el parsing usa URI de namespace. El fixture `record_single.xml` usa
deliberadamente los prefijos `z:` / `q:` / `w:` en lugar de `oai:` /
`oai_dc:` / `dc:`, y se parsea igual.

### 5.5. `noRecordsMatch` es un resultado vacío, no una falla

OAI-PMH lo modela como `<error>`, pero semánticamente significa "los filtros no
coincidieron con nada". `harvest()` termina la iteración sin registros. El
resto de los códigos (`idDoesNotExist`, `badArgument`,
`cannotDisseminateFormat`, `badResumptionToken`…) se propagan como
`RepositoryOaiError`, preservando `.code` y `.message`.

### 5.6. Paginación en *todos* los verbos de lista, no sólo `ListRecords`

Hallazgo del smoke test live: `ListSets` de SEDICI devuelve 100 sets y sigue con
`resumptionToken`. Cortar ahí habría perdido silenciosamente el 98 % de las
colecciones. La paginación se extrajo a `_paginated()` y la comparten
`list_sets()` y `harvest()`. Cosecha real verificada: **6767 sets en 68
páginas**, sin registros perdidos ni duplicados.

### 5.7. Ritmo de pedidos y reintentos acotados *(agregado sobre la especificación)*

El smoke test live descubrió que SEDICI responde **HTTP 429 Too Many Requests**
a un cosechador sin pausa: la conexión se caía en la segunda página de
`ListSets`. La taxonomía de errores lo representaba bien, pero un conector que
no puede pasar de la página 2 no establece una frontera usable, así que se
agregó:

* `min_request_interval` — 1 s entre pedidos **sólo con el transporte de red
  real**; un transporte inyectado (test o caché) no se frena, así la suite
  offline sigue corriendo en menos de un segundo;
* reintento acotado de 429/503 respetando `Retry-After`, con backoff
  exponencial si el servidor no lo envía, tope de 60 s y `max_retries=3`.

Es la única adición fuera del alcance literal de la especificación. Es stdlib,
está cubierta por cuatro tests y se documenta acá para que se pueda revertir si
se considera fuera de lugar.

### 5.8. Transporte inyectable

```python
connector = OaiPmhConnector(source, transport=fake_transport)
```

Firma: `(url, headers, timeout) -> bytes`. Los 45 tests obligatorios corren
**100 % offline**.

---

## 6. Límites y defensas

| Defensa | Default | Configurable |
|---|---|---|
| Timeout de red | 30 s | `timeout` |
| Tamaño máximo de respuesta | 8 MiB | `max_response_bytes` |
| Páginas por verbo de lista | 500 | `max_pages` |
| Token repetido | error | — |
| Scheme de `base_url` | sólo `http`/`https` | — |
| Intervalo mínimo entre pedidos | 1 s (sólo red real) | `min_request_interval` |
| Reintentos 429/503 | 3, tope 60 s | `max_retries` |

El límite de tamaño se aplica dos veces: en el transporte por defecto lee un
byte más que el presupuesto (para detectar el exceso en vez de truncar en
silencio) y el conector revalida el payload devuelto por cualquier transporte.

El contenido recibido no se ejecuta ni se interpreta. No se descargan PDFs.

---

## 7. Taxonomía de errores

```text
RepositoryError
├── RepositoryTransportError      red, timeout, HTTP 4xx/5xx (.status)
├── RepositoryResponseTooLarge    presupuesto de bytes excedido (.limit)
├── RepositoryMalformedResponse   XML inválido o documento que no es OAI-PMH
└── RepositoryProtocolError       token repetido, presupuesto de páginas
    └── RepositoryOaiError        <error code="..."> (.code, .message)
```

---

## 8. Smoke test live (SEDICI)

```bash
BIBLIOREF_TEST_LIVE_OAI=1 pytest tests_core/test_oai_pmh_live.py
```

Fuera de la suite obligatoria. Si el endpoint falla, la suite normal sigue
verde. Resultado del 2026-09-20: **3 passed**.

Observado en vivo (nada de esto se convirtió en lógica específica):

```text
repositoryName     SEDICI - Repositorio de la UNLP
protocolVersion    2.0
granularity        YYYY-MM-DDThh:mm:ssZ
deletedRecord      transient
earliestDatestamp  2003-11-21T03:00:00Z
sets               6767 (68 páginas) — 33 con "Tesis" en el nombre
```

Cosecha de ejemplo (`set=col_10915_31`, `from=2024-01-01`), 6 registros:

```text
oai:sedici.unlp.edu.ar:10915/2810
  title     Problemas sobre el poder político en las behetrías
  creators  ('Da Graca, Laura Cecilia',)
  dates     ('1996', '1996', '2009-09-17T03:00:00Z')
  types     ('Tesis', 'Tesis de grado')
  rights    ('http://creativecommons.org/licenses/by-nc-sa/4.0/',)
  raw keys  creator, date, description, identifier, language, rights,
            subject, title, type
```

Unicode verificado sobre el dato, no sobre la consola: los `í` de ese título
son `0xed` en el objeto devuelto.

---

## 9. Dependencias

**Ninguna nueva.** Todo es stdlib: `urllib.request`, `urllib.parse`,
`urllib.error`, `xml.etree.ElementTree`, `functools`, `time`.

---

## 10. Límites conocidos

1. **Entidades XML.** `ElementTree` no expande entidades externas y rechaza las
   no definidas, así que XXE y las bombas de entidades clásicas no aplican. No
   hay, en cambio, límite de profundidad de anidamiento; el tope de 8 MiB es la
   defensa efectiva contra un documento hostil.
2. **`deleted_record_policy`** se lee y se conserva, pero todavía nada consume
   esa política — corresponde a la capa de catálogo.
3. **Sólo `oai_dc`** está mapeado a campos nombrados. Otros `metadataPrefix`
   funcionan y caen enteros en `raw_metadata` por nombre local de elemento.
4. **`setDescription`** se aplana a texto: el elemento admite XML arbitrario y
   es lo único prometible entre repositorios.
5. **Sin persistencia.** No hay catálogo SQLite, ni deduplicación, ni estado de
   cosecha incremental: `from_date` hay que pasarlo desde afuera.
6. **`min_request_interval` es por conector**, no global. Varios conectores
   simultáneos contra el mismo host pueden volver a provocar 429.

---

## 11. Fuera de alcance (no implementado, según especificación)

```text
descarga de PDFs · DSpace bitstreams · Invenio files · EPrints full text
scraping HTML · selección automática de PDF · SQLite repository catalog
Corpus Builder UI · búsqueda textual local · sincronización persistente
deduplicación SHA-256 · importación al proyecto · procesamiento automático
cambios de extractor / parser / StyleProfiler
```

---

## 12. Criterios de aceptación

```text
✓ existe biblioref.repositories como módulo independiente
✓ RepositorySource tiene contrato estable
✓ RepositoryRecord preserva metadata Dublin Core
✓ Identify funciona
✓ ListMetadataFormats funciona
✓ ListSets funciona (con paginación)
✓ GetRecord funciona
✓ ListRecords funciona
✓ resumptionToken funciona en múltiples páginas
✓ from/until/set funcionan
✓ deleted records se representan correctamente
✓ raw metadata se conserva
✓ Unicode se conserva
✓ errores OAI se modelan
✓ errores HTTP/XML no rompen silenciosamente
✓ existen límites de red/tamaño/paginación
✓ tests funcionan offline
✓ no se modifica extraction
✓ no se modifica parsing
✓ no se modifica StyleProfiler
✓ no se modifica detection/adaptive/grammar
✓ smoke test SEDICI opcional documentado
✓ suite relevante verde
```

---

## 13. Siguiente fase

La frontera quedó establecida. Lo que sigue es `dspace-fulltext-0.1`:

```text
RepositoryRecord
       ↓
FullTextResolver        FULLTEXT_CONFIRMED / PROBABLE / MULTIPLE_CANDIDATES
       ↓                RESTRICTED / EMBARGOED / NOT_FOUND / UNSUPPORTED / ERROR
RepositoryFile
       ↓
PDF confirmado → SHA-256 → pdf_preflight() → pipeline actual
```

`RepositoryRecord.identifiers` ya trae el handle (`http://sedici.unlp.edu.ar/handle/10915/2810`),
que es el punto de partida del resolver. `RepositoryRecord` no obliga a devolver
una sola URL de archivo: abstenerse sigue siendo preferible a elegir el PDF
equivocado.
