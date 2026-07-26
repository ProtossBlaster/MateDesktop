# The desktop shortcut: created on install, gone on uninstall, and suppressible for a fleet.
#
# PURE ASCII, for the reason written at the top of test_uninstall_removes_data.ps1.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Msi  = (Get-ChildItem (Join-Path $Here "dist") -Filter "*.msi" | Select-Object -First 1).FullName
$Exe  = (Get-ChildItem (Join-Path $Here "dist") -Filter "*Setup*.exe" | Select-Object -First 1).FullName
$App  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$fail = 0

function Check($n, $ok, $d) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $n.PadRight(40), $d) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $n.PadRight(40), $d) -ForegroundColor Red; $script:fail++ }
}
function RunMsi($a) { (Start-Process msiexec.exe -ArgumentList $a -Wait -PassThru).ExitCode }
# The shortcut can land on the user's own desktop or the all-users one; look in both.
function Lnk {
    @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory")) |
        ForEach-Object { Join-Path $_ "LeapMotor Mate.lnk" } | Where-Object { Test-Path $_ } | Select-Object -First 1
}
function Cleanup {
    if (Test-Path (Join-Path $App "unins000.exe")) {
        Start-Process (Join-Path $App "unins000.exe") -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
    } elseif (Test-Path $App) { RunMsi @("/x", "`"$Msi`"", "/qn", "/norestart") | Out-Null }
    Start-Sleep -Seconds 3
}

Cleanup
Write-Host ""
Write-Host "=== 1. MSI: il collegamento si crea ==="
Check "installazione" ((RunMsi @("/i", "`"$Msi`"", "/qn", "/norestart")) -eq 0) "msiexec 0"
$l = Lnk
Check "collegamento sul desktop" ($null -ne $l) $(if ($l) { $l } else { "NON creato" })
if ($l) {
    $sh = (New-Object -ComObject WScript.Shell).CreateShortcut($l)
    Check "punta all'app giusta" ($sh.TargetPath -eq (Join-Path $App "LeapMotor Mate.exe")) $sh.TargetPath
}

Write-Host ""
Write-Host "=== 2. MSI: sparisce disinstallando ==="
RunMsi @("/x", "`"$Msi`"", "/qn", "/norestart") | Out-Null
Start-Sleep -Seconds 3
Check "collegamento rimosso" ($null -eq (Lnk)) $(if (Lnk) { "ANCORA PRESENTE" } else { "via" })

Write-Host ""
Write-Host "=== 3. MSI: si puo' sopprimere per una flotta ==="
Check "installazione con DESKTOPSHORTCUT=0" ((RunMsi @("/i", "`"$Msi`"", "/qn", "/norestart", "DESKTOPSHORTCUT=0")) -eq 0) "msiexec 0"
Check "nessun collegamento creato" ($null -eq (Lnk)) $(if (Lnk) { "CREATO LO STESSO" } else { "assente, come chiesto" })
Check "app comunque installata" (Test-Path (Join-Path $App "LeapMotor Mate.exe")) $App
RunMsi @("/x", "`"$Msi`"", "/qn", "/norestart") | Out-Null
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== 4. Installer Inno: stesso comportamento ==="
Start-Process $Exe -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
Start-Sleep -Seconds 3
Check "collegamento sul desktop" ($null -ne (Lnk)) $(if (Lnk) { Lnk } else { "NON creato" })
Cleanup
Check "collegamento rimosso" ($null -eq (Lnk)) $(if (Lnk) { "ANCORA PRESENTE" } else { "via" })

Write-Host ""
if ($fail) { Write-Host "$fail controlli FALLITI" -ForegroundColor Red; exit 1 }
Write-Host "collegamento sul desktop: creato, rimosso, e disattivabile" -ForegroundColor Green
