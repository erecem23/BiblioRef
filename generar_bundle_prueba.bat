@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Arrastra sobre este archivo el CSV exportado por BiblioRef.
  echo.
  pause
  exit /b 1
)
python field_test_bundle.py "%~1" --out field_test_output
if errorlevel 1 (
  echo.
  echo No se pudo generar el bundle.
  pause
  exit /b 1
)
echo.
echo Bundle generado en: %CD%\field_test_output
pause
