# BiblioRef APP v2.7.0 — Google Drive v0.2

La integración es deliberadamente **solo lectura**. BiblioRef puede buscar, listar y descargar PDF/ZIP autorizados por el usuario, pero no puede modificar, mover, borrar ni subir archivos a Google Drive.

## Configuración inicial

La configuración se realiza una sola vez por equipo:

1. En Google Cloud Console, crear o elegir un proyecto.
2. Habilitar **Google Drive API**.
3. Configurar la pantalla de consentimiento OAuth.
4. Crear credenciales **OAuth client ID → Desktop app / Aplicación de escritorio**.
5. Descargar el JSON del cliente.
6. Abrir BiblioRef y elegir **Cargar tesis → Google Drive…**.
7. Seleccionar el JSON cuando la aplicación lo solicite.
8. Pulsar **Conectar**. Se abrirá el navegador de sistema para autorizar `drive.readonly`.

BiblioRef muestra estos pasos también dentro de la interfaz. No se incluyen credenciales OAuth dentro del repositorio ni de los paquetes de la aplicación.

## Privacidad

- El JSON OAuth se guarda en `~/.biblioref/google_drive_client_secret.json`.
- El token OAuth se guarda en `~/.biblioref/google_drive_token.json`.
- Ambos permanecen en el equipo del usuario y no se incluyen en exports ni bundles de prueba.
- **Desconectar** elimina el token local. No borra el `client_secret.json`.
- BiblioRef solicita únicamente `https://www.googleapis.com/auth/drive.readonly`.
- La cuenta conectada se muestra en el selector para que el usuario pueda verificar con qué identidad está trabajando.
- La integración no contiene operaciones de escritura contra Drive.

## Navegación y búsqueda

v0.2 conserva la navegación por carpetas y agrega **Buscar en todo Drive**.

La búsqueda:

- consulta únicamente nombres de archivos y carpetas accesibles para la cuenta autorizada;
- devuelve sólo carpetas, PDF y ZIP compatibles con BiblioRef;
- no indexa ni analiza el contenido de Google Docs/Sheets/Slides;
- admite elementos de unidades compartidas cuando la cuenta tenga acceso;
- limita la cantidad de resultados devueltos por una consulta.

Desde los resultados se puede abrir una carpeta o seleccionar PDF/ZIP/carpetas para importarlos.

## Qué se puede importar

- PDF individuales.
- ZIP que contengan uno o varios PDF.
- Carpetas completas, recorridas recursivamente.
- Accesos directos de Drive cuyo destino sea PDF o carpeta compatible.
- Elementos de unidades compartidas cuando la cuenta autorizada tenga acceso.

Los Google Docs/Sheets/Slides nativos no se convierten automáticamente a PDF en esta versión: el objetivo es importar tesis ya existentes como PDF o lotes ZIP.

## ZIP

BiblioRef no ejecuta ni interpreta otros contenidos del ZIP. Sólo materializa PDF y ZIP anidados. Se bloquean rutas `../`, rutas absolutas, archivos cifrados y patrones de tamaño/compresión compatibles con zip bombs. El PDF extraído pasa luego por el mismo `pdf_preflight()` que un PDF cargado manualmente.

## Contrato de v0.2

`google-drive-readonly-0.2` agrega búsqueda y metadatos de capacidades, pero no amplía permisos. El contrato sigue siendo:

`Google Drive → lectura autorizada → copia al proyecto BiblioRef`

Nunca:

`BiblioRef → modificar Google Drive`.
