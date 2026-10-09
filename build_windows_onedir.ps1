$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3 -m venv .buildvenv
.\.buildvenv\Scripts\python.exe -m pip install --upgrade pip
.\.buildvenv\Scripts\python.exe -m pip install -r requirements-app.txt pyinstaller
.\.buildvenv\Scripts\pyinstaller.exe --noconfirm --clean --onedir --name BiblioRef --add-data "static;static" --collect-all pymupdf --collect-all googleapiclient --collect-all google_auth_oauthlib run_biblioref.py
Write-Host "Build listo en dist\BiblioRef\BiblioRef.exe"
