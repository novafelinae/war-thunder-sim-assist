; Inno Setup betiği. GitHub Actions bunu otomatik derler; elle derlemek için:
;   ISCC.exe /DAppVersion=1.0.0 installer\installer.iss
; Önce PyInstaller ile dist\WarThunderSimAssist klasörü oluşturulmuş olmalı (build.bat).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "War Thunder Sim Assist"
#define AppExe "WarThunderSimAssist.exe"

[Setup]
; Bu AppId'yi DEĞİŞTİRME: Windows güncellemeleri aynı program olarak tanısın diye sabit kalmalı.
AppId={{8F3B2C71-4D5A-4E9B-A1C6-7D2E94B05F38}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=WarThunderSimAssist-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Yönetici izni istemeden, kullanıcının kendi klasörüne kurulabilir.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Program çalışırken güncelleme/kaldırma yapılırsa kullanıcıyı uyarır
; (uygulamadaki MUTEX_ADI ile aynı olmalı).
AppMutex=WarThunderSimAssist_SingleInstance

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#define TurkishIsl AddBackslash(CompilerPath) + "Languages\Turkish.isl"
#if FileExists(TurkishIsl)
Name: "turkish"; MessagesFile: "{#TurkishIsl}"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\WarThunderSimAssist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
