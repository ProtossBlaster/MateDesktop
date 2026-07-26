# The .msi, put through exactly what the .exe was put through.
#
# Same three questions, because a different wrapper around the same folder can still get any of
# them wrong: does it install where it should and carry everything, does a brand-new user get a
# working first run, and does uninstalling take away what it added — and only that.
#
#     powershell -ExecutionPolicy Bypass -File .\test_msi.ps1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Msi  = Get-ChildItem (Join-Path $Here "dist") -Filter "*.msi" | Select-Object -First 1
$App  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$Data  = Join-Path $env:LOCALAPPDATA "LeapMotorMate"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$fail = 0

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(30), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(30), $detail) -ForegroundColor Red
               $script:fail++ }
}

if (-not $Msi) { throw "no .msi in dist\ - run build_win.ps1 first" }
if (Test-Path (Join-Path $App "LeapMotor Mate.exe")) { throw "something is already installed - uninstall it first" }
# The parentheses are load-bearing: without them PowerShell reads -f as Write-Host's own
# -ForegroundColor and tries to turn "28.29" into a colour.
Write-Host ("==> {0}  ({1:N0} MB)`n" -f $Msi.Name, ($Msi.Length / 1MB))

# ── install ─────────────────────────────────────────────────────────────────────────────
# /qn is silent. No /qb, no elevation: if this needed administrator rights it would fail here,
# which is itself the test — the package declares perUser scope and must honour it.
Write-Host "==> installing"
$log = Join-Path $Here "msi-install.log"
$p = Start-Process msiexec.exe -ArgumentList "/i", "`"$($Msi.FullName)`"", "/qn", "/norestart", "/l*v", "`"$log`"" -Wait -PassThru
Check "installs without elevation" ($p.ExitCode -eq 0) "msiexec exit code $($p.ExitCode)"
if ($p.ExitCode -ne 0) {
    Get-Content $log -Tail 25 | Write-Host
    exit 1
}

Check "installed to the user profile" (Test-Path (Join-Path $App "LeapMotor Mate.exe")) $App
Check "payload seed present" (Test-Path (Join-Path $App "_internal\payload_seed\web\main.py")) "web/main.py"
$count = (Get-ChildItem -Recurse $App -File).Count
Check "whole tree copied" ($count -gt 250) "$count files"
$leak = Get-ChildItem -Recurse $App -Include app.crt, app.key -ErrorAction SilentlyContinue
Check "no bundled certificate" (-not $leak) $(if ($leak) { $leak[0].FullName } else { "none under $App" })

# Where an .msi's uninstall entry lands depends on the install CONTEXT, not on us: per-user goes
# to HKCU, per-machine to HKLM. Looking only in HKCU reported "not listed" for a package that was
# plainly listed — so ask all three places, including Windows Installer itself, which is what
# Settings > Apps actually reads.
$hive = "nowhere"
foreach ($h in @("HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
                 "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
                 "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")) {
    $hit = Get-ItemProperty $h -EA SilentlyContinue | Where-Object { $_.DisplayName -like "*LeapMotor*" }
    if ($hit) { $hive = "$($hit[0].DisplayName) $($hit[0].DisplayVersion) in " + $h.Split(':')[0]; break }
}
Check "listed in settings > apps" ($hive -ne "nowhere") $hive

$sm = Get-ChildItem (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") -Filter "*LeapMotor*" -Recurse -EA SilentlyContinue
Check "start menu shortcut" ($sm) $(if ($sm) { $sm[0].Name } else { "not found" })

# What the PACKAGE declares, read straight out of its Property table. This is the part we author
# and can therefore be held to; whether a given machine then elevates is Windows' business, and an
# elevated shell — which an SSH session on Windows is — cannot prove the no-UAC claim either way.
# Only a double-click by a person can do that.
$installer = New-Object -ComObject WindowsInstaller.Installer
$db = $installer.GetType().InvokeMember("OpenDatabase", "InvokeMethod", $null, $installer, @($Msi.FullName, 0))
function Prop($name) {
    $v = $db.GetType().InvokeMember("OpenView", "InvokeMethod", $null, $db, @("SELECT Value FROM Property WHERE Property='$name'"))
    $v.GetType().InvokeMember("Execute", "InvokeMethod", $null, $v, $null)
    $r = $v.GetType().InvokeMember("Fetch", "InvokeMethod", $null, $v, $null)
    if ($r) { $r.GetType().InvokeMember("StringData", "GetProperty", $null, $r, 1) } else { $null }
}
# ALLUSERS is the property that decides it, and its meaning is inverted from what the name
# suggests: 1 is per-machine, 2 is "whatever the privileges allow", and EMPTY is per-user. WiX
# writes empty as a single space, because the Property table cannot hold a zero-length string —
# so a blank here is the per-user declaration, not a missing value. (First version of this check
# looked at MSIINSTALLPERUSER, which is set by the UI at run time, not authored in the package.)
$allUsers = Prop "ALLUSERS"
Check "declares a per-user install" ([string]::IsNullOrWhiteSpace($allUsers)) `
      ("ALLUSERS='$allUsers'  (1=per-machine, 2=depends, blank=per-user)")

# ── first run ───────────────────────────────────────────────────────────────────────────
Write-Host "`n==> first run, on an empty data directory"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Here "firstrun_test.ps1")
Check "first run clean" ($LASTEXITCODE -eq 0) "see the lines above"

# ── uninstall ───────────────────────────────────────────────────────────────────────────
Write-Host "`n==> uninstalling"
# Stand in for a user who had start-at-login switched on: it is the only state in which the entry
# exists, so it is the only one where forgetting to remove it would show.
Set-ItemProperty $RunKey -Name "LeapMotor Mate" -Value ('"' + (Join-Path $App "LeapMotor Mate.exe") + '"')
$dbBefore = if (Test-Path (Join-Path $Data "leapmotor_mate.db")) { (Get-Item (Join-Path $Data "leapmotor_mate.db")).Length } else { 0 }

$p = Start-Process msiexec.exe -ArgumentList "/x", "`"$($Msi.FullName)`"", "/qn", "/norestart" -Wait -PassThru
Check "uninstalls cleanly" ($p.ExitCode -eq 0) "msiexec exit code $($p.ExitCode)"
Start-Sleep -Seconds 2

Check "app removed" (-not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))) $App
$run = (Get-ItemProperty $RunKey -EA SilentlyContinue)."LeapMotor Mate"
Check "start-at-login entry gone" (-not $run) $(if ($run) { $run } else { "no value left under Run" })
$arp = Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -EA SilentlyContinue |
       Where-Object { $_.DisplayName -like "*LeapMotor*" }
Check "delisted from settings" (-not $arp) $(if ($arp) { $arp.DisplayName } else { "no longer listed" })
$sm = Get-ChildItem (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") -Filter "*LeapMotor*" -Recurse -EA SilentlyContinue
Check "shortcut gone" (-not $sm) $(if ($sm) { $sm[0].FullName } else { "no shortcut left" })
$dbAfter = if (Test-Path (Join-Path $Data "leapmotor_mate.db")) { (Get-Item (Join-Path $Data "leapmotor_mate.db")).Length } else { 0 }
Check "driving history untouched" ($dbAfter -gt 0 -and $dbAfter -eq $dbBefore) ("{0:N0} bytes before and after" -f $dbAfter)

Write-Host ""
if ($fail) { Write-Host "$fail check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "the msi is sound - machine left clean" -ForegroundColor Green
