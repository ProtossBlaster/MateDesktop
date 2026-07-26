# Build LeapMotor Mate.exe for Windows.
#
# The twin of build_mac.sh, and deliberately its mirror image: same seed payload, same
# collect-alls, same reasons. Read that file for why any of this is here — the notes are not
# duplicated, only the syntax changes.
#
# Run from the repo root inside Windows:
#     powershell -ExecutionPolicy Bypass -File .\build_win.ps1
#
# The Mac source tree is reachable from the VM as \\Mac\Home\leapmotor-mate, so the payload can
# be staged straight from it — no second checkout to keep in step.
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
# Three ways to find Mate's source, tried in order. The share is the convenient one when building
# by hand inside Windows, but it is NOT there over SSH: Parallels mounts it into the interactive
# desktop session, and a remote shell is a different logon session that has never seen it. That
# cost a build, so the script now falls back to a plain copy in repo\ rather than insisting.
$Repo = if ($env:MATE_REPO)                                 { $env:MATE_REPO }
        elseif (Test-Path "\\Mac\Home\leapmotor-mate\web")  { "\\Mac\Home\leapmotor-mate" }
        else                                                { Join-Path $Here "repo" }
$BuildPy = Join-Path $Here "buildenv\Scripts\python.exe"
$Out = Join-Path $Here "dist"

if (-not (Test-Path $BuildPy)) { throw "build venv missing - see the notes in STATO.md" }
if (-not (Test-Path (Join-Path $Repo "web"))) { throw "Mate source not found at $Repo" }

Write-Host "==> staging the seed payload from $Repo"
$Seed = Join-Path $Here "payload_seed"
Remove-Item -Recurse -Force $Seed -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Seed | Out-Null
foreach ($part in @("web", "poller")) {
    Copy-Item -Recurse (Join-Path $Repo $part) (Join-Path $Seed $part)
    # Ship what the app runs, and nothing else.
    Get-ChildItem -Path (Join-Path $Seed $part) -Recurse -Include "__pycache__" -Directory |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
# NB: the app certificate is deliberately NOT bundled - see the note above --add-data below.
$PayloadVersion = (Select-String -Path (Join-Path $Seed "web\main.py") -Pattern 'MATE_VERSION' |
                   Select-Object -First 1).Line.Split('"')[1]
Write-Host "    payload $PayloadVersion"

$ShellVersion = (Select-String -Path (Join-Path $Here "mate_desktop\launcher.py") `
                 -Pattern '^SHELL_VERSION' | Select-Object -First 1).Line.Split('"')[1]

Write-Host "==> building the executable (shell $ShellVersion)"
Remove-Item -Recurse -Force $Out, (Join-Path $Here "build") -ErrorAction SilentlyContinue

# The version resource Windows shows in the file's Properties tab. PyInstaller wants it as a
# file, and Explorer is where people look when they want to know what they downloaded.
$VersionFile = Join-Path $Here "build\version_info.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $VersionFile) | Out-Null
$v = $ShellVersion.Split(".")
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($($v[0]), $($v[1]), $($v[2]), 0), prodvers=($($v[0]), $($v[1]), $($v[2]), 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'ProtossBlaster'),
      StringStruct('FileDescription', 'LeapMotor Mate'),
      StringStruct('FileVersion', '$ShellVersion'),
      StringStruct('InternalName', 'LeapMotor Mate'),
      StringStruct('OriginalFilename', 'LeapMotor Mate.exe'),
      StringStruct('ProductName', 'LeapMotor Mate'),
      StringStruct('ProductVersion', '$ShellVersion')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"@ | Set-Content -Encoding ASCII $VersionFile

# UTF-8 mode, set HERE because it cannot be set later. Mate's logs are full of arrows
# ("State: unknown -> parked_active"), Python on Windows defaults to the system code page, and
# logging's FILE handler raised on every such line — the line never reached the log at all.
# Setting PYTHONUTF8 for the children does NOT work: the variable arrives and a frozen
# interpreter ignores it (measured — utf8_mode stayed 0 with it plainly set). The bootloader
# reads this build option instead, and the children are this same binary re-run, so they
# inherit it.
# NO certs/ in --add-data, and it is not an omission. app.crt/app.key are NOT Mate's to
# redistribute: they are the Leapmotor APP's TLS certificate - the same one for every user, not
# anybody's account - published at markoceri/leapmotor-certs, and the setup wizard asks the user
# to upload them once on first run, exactly as under Docker and Home Assistant. Bundling the build
# machine's copy would make this the one channel handing out a third party's certificate and
# private key on Mate's behalf, and would freeze every install onto whatever copy was on this disk
# that day - invisible the moment it is rotated.
& $BuildPy -m PyInstaller `
  --name "LeapMotor Mate" `
  --python-option "X utf8=1" `
  --windowed `
  --icon (Join-Path $Here "Mate.ico") `
  --version-file $VersionFile `
  --noconfirm `
  --distpath $Out `
  --workpath (Join-Path $Here "build") `
  --specpath (Join-Path $Here "build") `
  --add-data "$Seed;payload_seed" `
  --collect-all webview `
  --collect-all uvicorn `
  --collect-all fastapi `
  --collect-all leapmotor_api `
  --collect-all cryptography `
  --collect-all paho `
  --collect-all jinja2 `
  --collect-all PIL `
  --collect-all multipart `
  --collect-all certifi `
  --collect-all tzdata `
  --collect-submodules sqlite3 `
  (Join-Path $Here "mate_desktop\launcher.py")

# $ErrorActionPreference does NOT cover the exit code of an external program: PyInstaller can
# fail outright and the script sails on to print "done". It did — a build stopped halfway by a
# locked file (the app was still running, so its own files could not be replaced) was announced
# as finished, and the only clue was the size being smaller than usual.
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

# …and a check the size alone would not have caught either. The two things the shell cannot work
# without are the seed payload and the certificates, both added with --add-data: if either is
# missing the app builds, starts, and fails at the worst possible moment — on someone's first run.
$Internal = "$Out\LeapMotor Mate\_internal"
foreach ($must in @("payload_seed\web\main.py", "payload_seed\poller\main.py")) {
    if (-not (Test-Path (Join-Path $Internal $must))) { throw "incomplete build: $must is missing" }
}

# Asserted rather than trusted, because a recipe above already got this wrong once and shipped
# the certificate without anyone noticing. What it guards is a property, not a secret: no build
# of this app redistributes the Leapmotor certificate - the user brings their own copy.
$Leaked = Get-ChildItem -Recurse "$Out\LeapMotor Mate" -Include "app.crt", "app.key" -ErrorAction SilentlyContinue
if ($Leaked) { throw "REFUSING TO PACKAGE: an app certificate is inside the build ($($Leaked[0].FullName))" }

Write-Host "==> done: $Out\LeapMotor Mate\LeapMotor Mate.exe"
"{0:N0} MB" -f ((Get-ChildItem -Recurse "$Out\LeapMotor Mate" | Measure-Object Length -Sum).Sum / 1MB)

# ── the installer ───────────────────────────────────────────────────────────────────────
# What a user actually downloads. See installer.iss for why a folder of 300 files is not it.
# All three places it lands, because which one you get depends on how it was installed rather than
# on anything about the machine: winget without administrator rights — which is what you have over
# SSH — installs it per-user under LOCALAPPDATA, and a build that only looked in Program Files
# quietly skipped the installer and said so in a warning that is easy to scroll past.
$Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) { $Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source }
if (-not $Iscc) {
    Write-Warning "Inno Setup not found - app built, installer skipped."
    Write-Warning "  winget install --id JRSoftware.InnoSetup --exact"
    return
}

Write-Host "==> building the installer"
& $Iscc "/DAppVersion=$ShellVersion" (Join-Path $Here "installer.iss") | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$Setup = "$Out\LeapMotor-Mate-Setup-$ShellVersion-x64.exe"
if (-not (Test-Path $Setup)) { throw "ISCC reported success but $Setup is not there" }
Write-Host "==> done: $Setup"
"{0:N0} MB" -f ((Get-Item $Setup).Length / 1MB)

# ── the .msi ────────────────────────────────────────────────────────────────────────────
# Same folder, same install location, different wrapper. The one thing an .msi can do that the
# .exe cannot is be pushed by a company through group policy or Intune. See installer.wxs.
# WiX **5**, deliberately, and installed as a dotnet tool rather than from winget.
#
# From version 6 onwards WiX refuses to build until you accept the Open Source Maintenance Fee
# licence — "error WIX7015: You must accept the Open Source Maintenance Fee (OSMF) EULA". That is
# a licence with terms about who may use it free of charge, so accepting it is a statement about
# this project that only its owner can make. Version 5 speaks the same language as installer.wxs
# and asks for nothing, so the question does not arise.
#
#     winget install --id Microsoft.DotNet.SDK.8 --exact
#     dotnet tool install --global wix --version 5.0.2
#
# The explicit path first: a winget-installed WiX 6/7 also puts a wix.exe on PATH, and if one is
# left over on the machine it would win the lookup and fail the build with that same licence
# error — for a version we are deliberately not using.
$Wix = @("$env:USERPROFILE\.dotnet\tools\wix.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Wix) { $Wix = (Get-Command wix.exe -ErrorAction SilentlyContinue).Source }
if (-not $Wix) {
    Write-Warning "WiX not found - .msi skipped.  dotnet tool install --global wix --version 5.0.2"
    return
}

Write-Host "==> building the msi"
# The UI dialogs (welcome, licence, install location) live in an extension, not in wix itself.
# Adding it is idempotent, so it can run on every build rather than being a setup step someone has
# to remember on a fresh machine or a CI runner. The version is PINNED to match wix itself: left
# open it resolves to the newest published, which WiX 5 declines to load — with a warning, not an
# error, so the build appears to succeed and the wizard simply has no dialogs.
& $Wix extension add -g WixToolset.UI.wixext/5.0.2 2>&1 | Out-Null

# From the project root, because every path inside installer.wxs — the icon, the licence, the
# payload folder — is written relative to it, and wix resolves them against the CURRENT directory
# rather than the .wxs file's own. Run from anywhere else and it fails on the icon; run it over
# SSH, where you land in the home directory, and it fails every time.
#
# -arch x64 because the payload is: the shell, the interpreter and every bundled library are
# 64-bit. Left at the default the package would declare itself x86 while carrying x64 binaries.
$Msi = "$Out\LeapMotor-Mate-$ShellVersion-x64.msi"
Push-Location $Here
try {
    & $Wix build -arch x64 -d AppVersion=$ShellVersion -ext WixToolset.UI.wixext `
        installer.wxs -o $Msi
} finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "wix build failed with exit code $LASTEXITCODE" }
if (-not (Test-Path $Msi)) { throw "wix reported success but $Msi is not there" }
Write-Host "==> done: $Msi"
"{0:N0} MB" -f ((Get-Item $Msi).Length / 1MB)
