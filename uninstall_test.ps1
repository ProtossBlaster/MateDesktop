# Uninstalling, which has to do exactly two things and no more: take the app away, and take the
# start-at-login entry with it — while leaving the driving history completely alone.
#
# The Run entry is the part worth testing. The app writes it itself when "start at login" is on,
# so an uninstaller that ignores it leaves Windows trying to launch a program that is no longer
# there, once per sign-in, silently, for as long as the account exists.
#
# Ends with the machine CLEAN, ready for a real double-click install.
#
#     powershell -ExecutionPolicy Bypass -File .\uninstall_test.ps1
$ErrorActionPreference = "Stop"
$App     = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$Data    = Join-Path $env:LOCALAPPDATA "LeapMotorMate"
$RunKey  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$fail    = 0

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(30), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(30), $detail) -ForegroundColor Red
               $script:fail++ }
}

if (-not (Test-Path $App)) { throw "nothing installed to uninstall" }

# Stand in for a user who had "start at login" switched on, since that is the only state in which
# the entry exists and therefore the only one where forgetting it would show.
Set-ItemProperty $RunKey -Name "LeapMotor Mate" -Value ('"' + (Join-Path $App "LeapMotor Mate.exe") + '"')
Write-Host "==> pretending start-at-login was on"

# Remember what has to survive, so "the data is still there" is a comparison and not a look.
$dbBefore = if (Test-Path (Join-Path $Data "leapmotor_mate.db")) { (Get-Item (Join-Path $Data "leapmotor_mate.db")).Length } else { 0 }

Write-Host "==> uninstalling"
Start-Process -FilePath (Join-Path $App "unins000.exe") `
              -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
Start-Sleep -Seconds 3

Check "app removed" (-not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))) $App
$run = (Get-ItemProperty $RunKey -ErrorAction SilentlyContinue)."LeapMotor Mate"
Check "start-at-login entry gone" (-not $run) $(if ($run) { $run } else { "no value left under Run" })
$arp = Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -like "*LeapMotor*" }
Check "settings > apps entry gone" (-not $arp) $(if ($arp) { $arp.DisplayName } else { "no longer listed" })
$sm = Get-ChildItem (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") `
      -Filter "*LeapMotor*" -Recurse -ErrorAction SilentlyContinue
Check "start menu entry gone" (-not $sm) $(if ($sm) { $sm[0].FullName } else { "no shortcut left" })

$dbAfter = if (Test-Path (Join-Path $Data "leapmotor_mate.db")) { (Get-Item (Join-Path $Data "leapmotor_mate.db")).Length } else { 0 }
Check "driving history untouched" ($dbAfter -gt 0 -and $dbAfter -eq $dbBefore) ("{0:N0} bytes before and after" -f $dbAfter)

Write-Host ""
if ($fail) { Write-Host "$fail check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "uninstall is clean - the machine is ready for a real install" -ForegroundColor Green
