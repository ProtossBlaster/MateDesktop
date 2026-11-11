# Installing the setup .exe over an older one must not leave the older libraries behind.
#
# MateDesktop #12. Inno copies the new build over the old folder and, unless told otherwise,
# deletes nothing. From 1.2.2 to 1.2.3 the bundled libraries changed version, so _internal\ ended
# up with BOTH fastapi-0.115.0.dist-info and fastapi-0.162.2.dist-info (and jinja2, Pillow,
# cryptography, paho-mqtt). The code that runs is the new one, but the updater's guard asks
# importlib.metadata for the version, gets the OLD record, and refuses every Mate after the one
# the installer seeded: "fastapi ==0.162.2 (this app carries 0.115.0)". The red badge, forever.
#
# So: install a real older release, install the new setup on top, and count the records. One
# distribution, one .dist-info.
#
# Never runs an uninstaller: Inno's would delete %LOCALAPPDATA%\LeapMotorMate, the user's data.
# The test folder and its Settings > Apps entry are removed by hand. Inno also rewrites the Start
# menu shortcut whatever folder it installs to; if the machine has a Mate of its own, the shortcut
# is put back as it was.
#
# PURE ASCII on purpose (see test_uninstall_removes_data.ps1).
#
#     powershell -ExecutionPolicy Bypass -File .\test_exe_upgrade_leaves_no_old_libraries.ps1
#     ... -NewSetup <path to a setup .exe>     (default: the one in dist\)
param(
    [string]$NewSetup = "",
    [string]$OldVersion = "1.2.2"
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $NewSetup) {
    $NewSetup = (Get-ChildItem (Join-Path $Here "dist") -Filter "*Setup*.exe" | Select-Object -First 1).FullName
}
if (-not $NewSetup -or -not (Test-Path $NewSetup)) { throw "no setup .exe to test" }

$Work = Join-Path $env:TEMP "mate-exe-upgrade-test"
$Dir  = Join-Path $Work "app"
$Key  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{2E199589-62CA-404E-B3FF-71CBC04AD285}_is1"
$Lnk  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\LeapMotor Mate\LeapMotor Mate.lnk"

function Wipe($path) {
    # A file Windows Defender is still scanning refuses deletion for a moment: try again.
    for ($i = 0; $i -lt 15 -and (Test-Path $path); $i++) {
        Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    if (Test-Path $path) { throw "could not remove $path" }
}
function Install($setup) {
    $p = Start-Process $setup -Wait -PassThru -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=`"`"", "/DIR=`"$Dir`"")
    if ($p.ExitCode -ne 0) { throw "$setup exited with $($p.ExitCode)" }
}
function DuplicateRecords {
    # "fastapi-0.115.0.dist-info" -> "fastapi". Names are normalised the way pip does (PEP 503).
    Get-ChildItem (Join-Path $Dir "_internal") -Directory -Filter "*.dist-info" |
        Group-Object { ($_.Name -replace '-[^-]+\.dist-info$', '').ToLower() -replace '[-_.]+', '-' } |
        Where-Object Count -gt 1 |
        ForEach-Object { "{0}: {1}" -f $_.Name, (($_.Group | ForEach-Object Name) -join ", ") }
}

# The machine's own Start menu shortcut, if there is one, as it is now.
$saved = $null
if (Test-Path $Lnk) {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk)
    $saved = @{ Target = $s.TargetPath; Dir = $s.WorkingDirectory; Icon = $s.IconLocation; Args = $s.Arguments }
}
$hadKey = Test-Path $Key
if ($hadKey) { throw "a setup .exe install of Mate already exists on this machine: run this elsewhere" }

$fail = 0
try {
    Wipe $Work
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    $zip = Join-Path $Work "old.zip"
    $url = "https://github.com/ProtossBlaster/MateDesktop/releases/download/v$OldVersion/LeapMotor-Mate-Setup-$OldVersion-x64.exe.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath (Join-Path $Work "old") -Force
    $OldSetup = (Get-ChildItem (Join-Path $Work "old") -Filter "*Setup*.exe" | Select-Object -First 1).FullName

    Install $OldSetup
    $before = @(Get-ChildItem (Join-Path $Dir "_internal") -Directory -Filter "fastapi-*.dist-info" | ForEach-Object Name)
    Install $NewSetup
    $dups = @(DuplicateRecords)

    Write-Host "  installed $OldVersion, then $(Split-Path -Leaf $NewSetup) on top"
    Write-Host "  fastapi record after $OldVersion : $($before -join ', ')"
    if ($dups.Count -eq 0) {
        Write-Host "  PASS  one record per library after the upgrade"
    } else {
        Write-Host "  FAIL  the older libraries are still recorded after the upgrade:" -ForegroundColor Red
        $dups | ForEach-Object { Write-Host "          $_" -ForegroundColor Red }
        $fail = 1
    }
} finally {
    Wipe $Work
    if (Test-Path $Key) { Remove-Item -Recurse -Force $Key }
    if ($saved) {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk)
        $s.TargetPath = $saved.Target; $s.WorkingDirectory = $saved.Dir
        $s.IconLocation = $saved.Icon; $s.Arguments = $saved.Args
        $s.Save()
    } elseif (Test-Path (Split-Path $Lnk)) {
        Remove-Item -Recurse -Force (Split-Path $Lnk)
    }
}
exit $fail
