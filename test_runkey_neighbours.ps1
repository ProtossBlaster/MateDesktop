# Does uninstalling Mate take other applications' start-at-login entries with it?
#
# HKCU\...\Run is a SHARED key: every app that starts at sign-in has a value in it. After the MSI
# test the whole key had vanished from this machine — not our value, the key. If one of our two
# uninstallers does that on a real machine it silently stops OneDrive, Teams, the user's password
# manager and everything else from starting, and nothing about the symptom points back at us.
#
# So: put two neighbours in the key, run each uninstaller, and see who is still standing. Nothing
# here reasons about what the flags are documented to mean — it measures what they do.
#
#     powershell -ExecutionPolicy Bypass -File .\test_runkey_neighbours.ps1
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Run  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$App  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$fail = 0

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(34), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(34), $detail) -ForegroundColor Red
               $script:fail++ }
}

function Seed-Neighbours {
    if (-not (Test-Path $Run)) { New-Item -Path $Run -Force | Out-Null }
    Set-ItemProperty $Run -Name "PretendOneDrive" -Value "C:\fake\onedrive.exe"
    Set-ItemProperty $Run -Name "PretendPasswordManager" -Value "C:\fake\pwmgr.exe"
    Set-ItemProperty $Run -Name "LeapMotor Mate" -Value ('"' + (Join-Path $App "LeapMotor Mate.exe") + '"')
}

function Report-Neighbours($label) {
    $exists = Test-Path $Run
    Check "$label - key still exists" $exists $Run
    if (-not $exists) { return }
    $props = (Get-Item $Run).Property
    Check "$label - neighbours survived" (($props -contains "PretendOneDrive") -and ($props -contains "PretendPasswordManager")) `
          ("left: " + ($props -join ", "))
    Check "$label - our value removed" (-not ($props -contains "LeapMotor Mate")) "LeapMotor Mate entry"
}

Write-Host "=== who am I running as ==="
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "  user: $($id.Name)   elevated: $admin"
if ($admin) {
    Write-Host "  NB: an elevated shell means 'installs without elevation' cannot be proven here." -ForegroundColor Yellow
}

# ── the MSI, which is currently installed ───────────────────────────────────────────────
$msi = Get-ChildItem (Join-Path $Here "dist") -Filter "*.msi" -EA SilentlyContinue | Select-Object -First 1
if ((Test-Path (Join-Path $App "LeapMotor Mate.exe")) -and $msi) {
    Write-Host "`n=== uninstalling the MSI, with neighbours watching ==="
    Seed-Neighbours
    Start-Process msiexec.exe -ArgumentList "/x", "`"$($msi.FullName)`"", "/qn", "/norestart" -Wait
    Start-Sleep -Seconds 2
    Report-Neighbours "msi"
}

# ── the Inno .exe ───────────────────────────────────────────────────────────────────────
$exe = Get-ChildItem (Join-Path $Here "dist") -Filter "*Setup*.exe" -EA SilentlyContinue | Select-Object -First 1
if ($exe) {
    Write-Host "`n=== installing the Inno .exe ==="
    Start-Process $exe.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
    Start-Sleep -Seconds 2
    if (-not (Test-Path (Join-Path $App "unins000.exe"))) { Write-Host "  (inno install failed)" -ForegroundColor Red; exit 1 }

    Write-Host "=== uninstalling it, with neighbours watching ==="
    Seed-Neighbours
    Start-Process (Join-Path $App "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
    Start-Sleep -Seconds 3
    Report-Neighbours "inno"
}

# Leave the key as we found it conceptually: our test neighbours are not real apps.
if (Test-Path $Run) {
    Remove-ItemProperty $Run -Name "PretendOneDrive", "PretendPasswordManager" -EA SilentlyContinue
}

Write-Host ""
if ($fail) { Write-Host "$fail check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "both uninstallers leave the neighbours alone" -ForegroundColor Green
