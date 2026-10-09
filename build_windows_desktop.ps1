$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Test-Path .buildvenv) { Remove-Item -Recurse -Force .buildvenv }
py -3 -m venv .buildvenv
.\.buildvenv\Scripts\python.exe -m pip install --upgrade pip
.\.buildvenv\Scripts\python.exe -m pip install -r requirements-desktop-windows.txt pyinstaller
.\.buildvenv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onedir --name BiblioRef --add-data "static;static" --collect-all pymupdf --collect-all googleapiclient --collect-all google_auth_oauthlib --collect-all webview run_biblioref_desktop.py
Write-Host "Desktop build listo en dist\BiblioRef\BiblioRef.exe"
Write-Host "Para distribuirlo, empaquete la carpeta dist\BiblioRef en un instalador (Inno Setup/NSIS) y firme el instalador."
