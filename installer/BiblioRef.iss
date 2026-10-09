#define MyAppName "BiblioRef"
#define MyAppVersion "0.9.8-app-v2.7.0-parser-v0.11"
#define MyAppExeName "BiblioRef.exe"
[Setup]
AppId={{0A8E5E1E-8B02-4F21-9EAC-58CB0F2D4B41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\BiblioRef
DefaultGroupName=BiblioRef
OutputBaseFilename=BiblioRef_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\BiblioRef\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\BiblioRef"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\BiblioRef"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir BiblioRef"; Flags: nowait postinstall skipifsilent
