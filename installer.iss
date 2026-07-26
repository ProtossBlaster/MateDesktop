; LeapMotor Mate — Windows installer (Inno Setup 6.3+)
;
; Compiled by build_win.ps1 straight after PyInstaller, which passes the version in:
;     ISCC.exe /DAppVersion=1.0.0 installer.iss
;
; WHY an installer and not a zip. PyInstaller's output is a folder of some three hundred files
; with one .exe at the top, and that is exactly the shape that goes wrong for the audience this
; app exists for — people who asked how to install Mate without knowing what Docker is. Silvio,
; who wrote Mate, already double-clicked the wrong executable once: the leftover copy inside
; build\. A folder cannot say which file to open; an installer does not have to.
;
; It also settles three smaller things a zip leaves to the user: a Start-menu entry so the app can
; be found by name, a proper entry in Settings ▸ Apps so it can be removed the ordinary way, and
; somewhere to install to that isn't the Downloads folder.
;
; WHY NOT --onefile, which would have made the zip question moot: the shell re-runs its own binary
; to start the poller and the web server (see spawn() in launcher.py). Under onefile each of those
; children would unpack the whole bundle again into a temporary folder — three copies extracted on
; every launch, on a machine we are trying to be light on.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName      "LeapMotor Mate"
#define AppPublisher "ProtossBlaster"
#define AppURL       "https://github.com/ProtossBlaster/leapmotor-mate"
#define AppExeName   "LeapMotor Mate.exe"

[Setup]
; Never change this GUID: Windows recognises an upgrade by it. A new one would make every release
; install alongside the last instead of replacing it.
AppId={{2E199589-62CA-404E-B3FF-71CBC04AD285}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; Per-user, and deliberately so. Asking for administrator rights would mean a UAC prompt on an
; app nobody has signed — precisely the prompt people should be refusing. Installing under the
; user's own profile needs no elevation at all, and Mate is a personal app: one account, one car,
; one driving history. With PrivilegesRequired=lowest, {autopf} resolves to
; %LOCALAPPDATA%\Programs, which is where per-user apps belong on Windows.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; The build is x64. "x64compatible" rather than plain "x64" so it also installs on Windows on ARM,
; which runs x64 through emulation — that is the only machine this was ever tested on, and turning
; away the developer's own laptop would be a poor way to find that out.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; If Mate is open, say so instead of failing halfway through replacing files it is holding. This
; is the same named mutex the app takes to keep two copies from running (plat_win.py); Inno looks
; for it in the user's own session, which is where the app creates it.
AppMutex=LeapMotorMate

OutputDir=dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}-x64
SetupIconFile=Mate.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Nothing here is confidential, but the installer is a single file people will download and pass
; around, and a checksum in the release notes is only useful if the file it names is stable.
DisableWelcomePage=no
LicenseFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian";  MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller folder, as it comes. recursesubdirs+createallsubdirs keeps _internal's
; own tree intact — the app will not start if any of it is flattened.
;
; There is no certs\ in here, and that is not an oversight: app.crt and app.key are the Leapmotor
; app's TLS certificate — the same for everyone, published at markoceri/leapmotor-certs — which
; the setup wizard asks the user to upload on first run, exactly as under Docker. This build does
; not redistribute them, and build_win.ps1 refuses to package if one ever turns up in dist\.
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Do nothing on install, remove on uninstall. The app writes this value itself when "start at
; login" is on, and without this the entry would outlive the app: Windows would go on trying to
; launch a program that is no longer there, once per sign-in, silently. ValueType none plus
; dontcreatekey is Inno's idiom for delete-only.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: none; ValueName: "LeapMotor Mate"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

; NOTE — what uninstalling does NOT remove: %LOCALAPPDATA%\LeapMotorMate, which holds the
; database, the certificates and the log. That is the user's driving history, sometimes years of
; it, and an uninstaller is no place to be asked a question whose wrong answer cannot be undone.
; Reinstalling finds it again exactly where it was. The readme says where it lives for anyone who
; does want it gone.
