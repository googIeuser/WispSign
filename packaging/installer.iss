; Inno Setup script for WispSign. Build with: iscc /DAppVersion=0.1.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6E0B5C1A-3F4D-4C7B-9A52-7D1E8B2F4A90}
AppName=WispSign
AppVersion={#AppVersion}
AppPublisher=WispSign
DefaultDirName={autopf}\WispSign
DefaultGroupName=WispSign
UninstallDisplayIcon={app}\WispSign.exe
SetupIconFile=assets\wispsign.ico
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=WispSign-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Files]
Source: "..\dist\WispSign\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\WispSign"; Filename: "{app}\WispSign.exe"
Name: "{autodesktop}\WispSign"; Filename: "{app}\WispSign.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\WispSign.exe"; Description: "Launch WispSign"; Flags: nowait postinstall skipifsilent
