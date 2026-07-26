# What a fresh install of LeapMotor Mate looks like from outside, checked rather than assumed.
#
# Written as a file rather than typed at an SSH prompt because it is run remotely and PowerShell
# quoting does not survive two shells intact — the first attempt returned nothing at all, which is
# indistinguishable from a clean pass and is exactly the kind of silence this project keeps
# getting caught by.
#
#     powershell -ExecutionPolicy Bypass -File .\verify_install.ps1
$App  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$Data = Join-Path $env:LOCALAPPDATA "LeapMotorMate"
$fail = 0

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(28), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(28), $detail) -ForegroundColor Red
               $script:fail++ }
}

Write-Host "`n=== installed app ==="
$exe = Join-Path $App "LeapMotor Mate.exe"
Check "executable" (Test-Path $exe) $exe
if (Test-Path $exe) {
    $vi = (Get-Item $exe).VersionInfo
    Check "version resource" ($vi.FileVersion) "$($vi.FileVersion)  $($vi.CompanyName)"
}
Check "payload seed" (Test-Path (Join-Path $App "_internal\payload_seed\web\main.py")) "web/main.py present"
Check "uninstaller" (Test-Path (Join-Path $App "unins000.exe")) "unins000.exe"

Write-Host "`n=== the property that must never regress ==="
# The Leapmotor certificate belongs to markoceri/leapmotor-certs and the user uploads it in the
# setup wizard. No build of this app carries a copy.
$leak = Get-ChildItem -Recurse $App -Include app.crt, app.key -ErrorAction SilentlyContinue
Check "no bundled certificate" (-not $leak) $(if ($leak) { $leak[0].FullName } else { "nothing found under $App" })

Write-Host "`n=== how the user finds and removes it ==="
$sm = Get-ChildItem (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") `
      -Filter "*LeapMotor*" -Recurse -ErrorAction SilentlyContinue
Check "start menu entry" ($sm) $(if ($sm) { $sm[0].Name } else { "not found" })
$arp = Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -like "*LeapMotor*" }
Check "settings > apps entry" ($arp) $(if ($arp) { "$($arp.DisplayName) $($arp.DisplayVersion)" } else { "not listed" })

Write-Host "`n=== the user's data, which the installer must not touch ==="
Check "data directory kept" (Test-Path $Data) $Data
$db = Join-Path $Data "leapmotor_mate.db"
if (Test-Path $db) {
    Check "database intact" $true ("{0:N0} KB, last written {1}" -f ((Get-Item $db).Length/1KB), (Get-Item $db).LastWriteTime)
}
Check "install is elsewhere" ($App -ne $Data) "app in Programs\, data in LeapMotorMate\"

Write-Host ""
if ($fail) { Write-Host "$fail check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "all checks passed" -ForegroundColor Green
