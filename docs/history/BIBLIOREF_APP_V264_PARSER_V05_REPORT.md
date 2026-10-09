# BiblioRef APP v2.6.4 — Parser bibliográfico v0.5

**Fecha:** 2026-09-02  
**Software:** BiblioRef 0.9.6  
**Algoritmo de extracción:** 0.6.2  
**Stable engine:** 0.4.5  
**APP:** 2.6.4  
**Parser downstream:** biblioref-parser-v0.5 · schema 5

## 1. Alcance

Parser v0.5 agrega una ruta explícita y conservadora para referencias **ABNT-like con autor en mayúsculas, iniciales y año terminal**. La capa sigue siendo downstream y no destructiva: no modifica zonas, fronteras ni texto crudo.

Familias soportadas por la nueva ruta:

- `AUTOR, A. Título. Lugar: Editora, ano.`
- `AUTOR, A. Título. Revista, v., n., p., ano.`
- `AUTOR, A. Título do capítulo. In: ... Lugar: Editora, ano.`

La activación requiere simultáneamente autor compatible al inicio, ausencia de año parentético, año bibliográfico cerca del final y una frontera título/fuente independiente. No se utilizan nombres de universidades, países ni documentos.

## 2. Desarrollo ABNT ya consumido

Las 10 referencias USP/Pizzimenti que revelaron el problema en el holdout de v0.4 pasan formalmente a development/regression de v0.5. Sobre esas 10, la nueva ruta recupera:

- autor: **10/10**;
- año: **10/10**;
- título: **10/10**;
- tipo documental: **10/10**;
- revista: **2/2**;
- editorial canónica: **8/8**;
- editorial observada: **8/8**.

Estas cifras no son validación externa.

## 3. No regresión sobre el corpus histórico

El CSV histórico empaquetado contiene **29.027 referencias**. Antes del nuevo holdout se escaneó qué filas activarían la ruta ABNT v0.5: **0/29.027**.

Por lo tanto, las métricas de desarrollo de v0.4 se conservan exactamente:

- revista fuzzy ≥ .90: **79,13%**;
- cobertura de revista: **84,88%**;
- tipo documental de clase alta: **83,84%**;
- editorial canónica exacta: **93,67%**;
- cobertura editorial: **95,45%**.

## 4. Holdout ABNT externo congelado

Antes de ejecutar v0.5 sobre las nuevas citas se congelaron:

- código `biblioref/parsing/v05.py`: `5be695aeb585e02b4eb1b20b96904fb513be87e36950c98487f2572feb8be1d8`;
- gold de 30 referencias: `5773422499c42fbd866b69d457cbaf849310a498f7e2c8ecf6e129960fc3d70c`.

El conjunto contiene 10 referencias por tesis:

1. PUC-Rio, Taveira 2012, tesis doctoral en Letras;
2. PUC-SP, Miyagui 2014, tesis doctoral en Psicología Social;
3. UFBA, Lima 2022, tesis doctoral en Cultura e Sociedade.

### Resultado global v0.4 → v0.5

| Campo | v0.4 | v0.5 |
|---|---:|---:|
| Autor exacto | 63,33% | **90,00%** |
| Año exacto | 96,67% | **100,00%** |
| Título exacto | 0,00% | **56,67%** |
| Título fuzzy ≥ .90 | 0,00% | **60,00%** |
| Revista fuzzy ≥ .90 | 0,00% | **20,00%** |
| Cobertura revista | 0,00% | **40,00%** |
| Tipo documental exacto | 33,33% | **53,33%** |
| Editorial canónica exacta | 5,88% | **70,59%** |
| Editorial observada exacta | 0,00% | **70,59%** |
| Cobertura editorial canónica | 5,88% | **70,59%** |

La ruta ABNT se activó en **20/30** referencias.

### Comparación pareada

- autor: **8 mejoras / 0 regresiones**;
- año: **1 / 0**;
- título fuzzy: **18 / 0**;
- revista fuzzy: **2 / 0**;
- editorial canónica: **11 / 0**;
- editorial observada: **12 / 0**;
- tipo documental: **8 mejoras / 2 regresiones**.

Las dos regresiones de tipo son referencias donde `In:` introduce una **revista**, no un capítulo (`Revista Teias` y `Journal of the Theory of Social Behaviour`). v0.5 interpreta `In:` demasiado fuertemente como marcador de capítulo.

## 5. Nuevo límite descubierto

La tesis UFBA usa repetidamente autor ABNT con **apellido + nombre desarrollado**, por ejemplo `ADICHIE, Chimamanda Ngozi`, no sólo iniciales. La ruta v0.5 fue deliberadamente congelada con una gramática de iniciales y sólo se activa en **1/10** referencias UFBA de la muestra. En ese subconjunto, el título fuzzy de v0.5 queda en **10%** y el tipo exacto en **30%**.

No se amplió la ruta después de observar este resultado. Es el frente correcto para v0.6.

También permanecen abiertos:

1. `In:` antes de un título de revista no debe implicar automáticamente capítulo;
2. reconocimiento explícito de `Tese`/`Dissertação` como tipo documental;
3. revistas ABNT sin secuencia canónica `v./n./p.`;
4. variantes con nombres propios completos y partículas de apellido;
5. editoriales expresadas sin `Lugar: Editora`.

## 6. Estado metodológico

El hash de `v05.py` posterior al holdout es idéntico al freeze previo: `5be695aeb585e02b4eb1b20b96904fb513be87e36950c98487f2572feb8be1d8`. El holdout de 30 queda desde ahora **quemado** para cualquier desarrollo de v0.6.

v0.5 debe leerse como una mejora sustancial para una familia ABNT concreta, no como cobertura completa de ABNT.
