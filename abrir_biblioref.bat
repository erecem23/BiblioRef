@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primera ejecucion: creando entorno local de BiblioRef...
  py -3 -m venv .venv || goto :error
  .venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
  .venv\Scripts\python.exe -m pip install -r requirements-app.txt || goto :error
) else (
  .venv\Scripts\python.exe -c "import fastapi, fitz, googleapiclient, google_auth_oauthlib" >nul 2>&1
  if errorlevel 1 (
    echo Actualizando dependencias de BiblioRef APP v2.7.0...
    .venv\Scripts\python.exe -m pip install -r requirements-app.txt || goto :error
  )
)
echo.
echo Abriendo BiblioRef APP v2.7.0 en http://127.0.0.1:8775
echo.
.venv\Scripts\python.exe run_biblioref.py
goto :eof
:error
echo.
echo No se pudo preparar BiblioRef. Verifique que Python 3.10 o superior este instalado y que haya conexion a Internet para instalar dependencias.
pause
