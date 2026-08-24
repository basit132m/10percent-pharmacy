; Inno Setup script — turns the PyInstaller folder into a normal Windows installer.
; Compile with:  ISCC.exe packaging\installer.iss
; The compiled setup lands in packaging\output\.

#define AppName "Ten Percent Discount Pharmacy"
#define AppVersion "1.0.0"
#define AppExe "TenPercentPharmacy.exe"

[Setup]
AppId={{8F3C4C2E-6A71-4C0E-9F1D-10PERCENTPHARM}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Ten Percent Discount Pharmacy, Kahror Pakka
DefaultDirName={autopf}\TenPercentPharmacy
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=TenPercentPharmacy-Setup-{#AppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; No internet connection is needed at any point, during setup or after it.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a shortcut on the desktop"; \
    GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\TenPercentPharmacy\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\USER-MANUAL.md"; DestDir: "{app}"; \
    DestName: "User manual.txt"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Messages]
; The database lives in %LOCALAPPDATA%\TenPercentPharmacy and is deliberately
; left alone by the uninstaller, so removing the program never loses the shop's
; records.
