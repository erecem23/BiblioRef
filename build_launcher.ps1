$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Preparando launcher de BiblioRef..." -ForegroundColor Cyan

$venv = Join-Path $PSScriptRoot ".launcher-venv"
$dist = Join-Path $PSScriptRoot ".launcher"
$work = Join-Path $PSScriptRoot ".launcher-build"

if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
if (Test-Path $work) { Remove-Item -Recurse -Force $work }

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -3 -m venv $venv
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "No se encontro Python 3 en PATH."
    }
    & python -m venv $venv
}

$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install pyinstaller

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name BiblioRef `
    --distpath $dist `
    --workpath $work `
    --specpath $work `
    (Join-Path $PSScriptRoot "biblioref_launcher.py")

$exe = Join-Path $dist "BiblioRef.exe"
if (-not (Test-Path $exe)) {
    throw "No se genero BiblioRef.exe."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "BiblioRef.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.IconLocation = "$exe,0"
$shortcut.Description = "Abrir BiblioRef"
$shortcut.Save()

Write-Host ""
Write-Host "Listo." -ForegroundColor Green
Write-Host "Ejecutable: $exe"
Write-Host "Acceso directo: $shortcutPath"
Write-Host ""
Write-Host "Desde ahora podes abrir BiblioRef con doble clic desde el Escritorio."
