# BiblioRef — paquete recomendado para depósito DNDA

**Fecha:** 2026-09-09  
**Trámite previsto:** Depósito en custodia de obra inédita — Software (DNDA, Argentina).

Este documento organiza técnicamente el material a presentar. No reemplaza los requisitos oficiales vigentes del trámite.

## Objetivo del paquete

El paquete debe permitir identificar de manera inequívoca la obra BiblioRef que se deposita, conservar evidencia reproducible de su estado y distinguir el código original del proyecto de las dependencias de terceros.

## Contenido recomendado del soporte

Crear una carpeta raíz con el siguiente esquema:

```text
BiblioRef_DNDA_2026-09-09/
├── 00_IDENTIFICACION/
│   ├── VERSION.txt
│   ├── GIT_COMMIT.txt
│   ├── SHA256SUMS.txt
│   └── MANIFEST.txt
├── 01_CODIGO_FUENTE/
│   └── biblioref_source/
├── 02_DOCUMENTACION/
│   ├── README.md
│   ├── IP_RELEASE_CHECKLIST.md
│   ├── IP_SNAPSHOT_2026_09_09.md
│   ├── PYMUPDF_DECISION.md
│   └── THIRD_PARTY_NOTICES.md
└── 03_PRUEBAS/
    └── TEST_RESULTS.txt
```

## Qué incluir

- código fuente original necesario para identificar BiblioRef;
- interfaz y recursos propios del proyecto;
- documentación técnica relevante;
- versión y commit Git exactos;
- resultados de la suite de pruebas correspondiente al snapshot;
- manifiesto de archivos;
- SHA-256 del contenido o del archivo fuente congelado;
- avisos de dependencias de terceros.

## Qué excluir del paquete de autoría

Salvo que exista una razón documental específica, no incorporar como si fueran código propio:

- el paquete/binarios de PyMuPDF o MuPDF;
- el contenido instalado de `site-packages`;
- dependencias Python completas de terceros;
- entornos virtuales (`venv`, `.venv`, `.buildvenv`);
- build de PyInstaller (`build/`, `dist/`) como sustituto del fuente;
- modelos de terceros cuya licencia no se haya auditado;
- PDFs/tesis del corpus que BiblioRef procesa;
- credenciales OAuth, tokens, claves, secretos o archivos personales;
- caches, temporales y resultados locales no necesarios para identificar la obra.

Las dependencias se documentan mediante sus nombres, versiones/requisitos y licencias en `THIRD_PARTY_NOTICES.md`. Su exclusión del paquete fuente no modifica ni evita las obligaciones de licencia que correspondan cuando BiblioRef sea ejecutado o distribuido con ellas.

## PyMuPDF

PyMuPDF debe figurar como dependencia de terceros, no como autoría de BiblioRef. El snapshot fuente puede conservar las líneas `import pymupdf` y el requisito de instalación porque forman parte de la arquitectura del proyecto, pero no debe presentar el código/binarios upstream de PyMuPDF como creación propia.

La cuestión de licencia de PyMuPDF se resuelve separadamente antes de distribuir el ejecutable o desplegar un servicio público.

## Reproducibilidad

Antes de grabar el soporte:

1. congelar el commit elegido;
2. exportar únicamente los archivos admitidos por el manifiesto;
3. generar `MANIFEST.txt` con las rutas incluidas;
4. calcular SHA-256;
5. ejecutar tests desde el snapshot;
6. guardar el resultado de tests;
7. verificar manualmente que no haya secretos ni archivos de terceros no previstos;
8. conservar localmente una copia idéntica al soporte presentado.

## Requisitos administrativos a completar fuera del repositorio

Según la página oficial de DNDA para software inédito, el trámite se inicia por TAD y requiere, entre otros elementos, comprobante de pago, datos de autores/coordinadores/titulares y una copia de la obra en soporte dentro de un sobre cerrado firmado en los puntos de cierre. El expediente genera carátulas que deben acompañar el soporte presentado o enviado a DNDA.

Los datos personales requeridos para el trámite no deben almacenarse en este repositorio.
