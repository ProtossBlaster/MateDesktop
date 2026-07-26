# Uninstalling must take the data with it - and an UPGRADE must not.
#
# Two behaviours that come out of the same Windows Installer step and are easy to conflate, which
# is exactly why they are tested together. A cleanup wired to "uninstall" alone looks correct
# until the day someone updates and finds Mate empty, with nothing in the logs to explain it.
#
# PURE ASCII on purpose. PowerShell reads a .ps1 in the system code page unless it carries a BOM,
# and the first version of this file - written with em-dashes and box-drawing rules - arrived
# mangled and failed to parse. Same trap as the arrows in Mate's own logs.
#
#     powershell -ExecutionPolicy Bypass -File .\test_uninstall_removes_data.ps1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Msi  = (Get-ChildItem (Join-Path $Here "dist") -Filter "*.msi" | Select-Object -First 1).FullName
$Exe  = (Get-ChildItem (Join-Path $Here "dist") -Filter "*Setup*.exe" | Select-Object -First 1).FullName
$App  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$Data = Join-Path $env:LOCALAPPDATA "LeapMotorMate"
$Canary = Join-Path $Data "canary.txt"
$fail = 0

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(38), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(38), $detail) -ForegroundColor Red
               $script:fail++ }
}
function RunMsi($a) { (Start-Process msiexec.exe -ArgumentList $a -Wait -PassThru).ExitCode }
function Seed {
    New-Item -ItemType Directory -Force -Path $Data | Out-Null
    "fake history: must survive an upgrade, must vanish on uninstall" | Set-Content $Canary
}

# Start from nothing, whatever state the machine was left in.
if (Test-Path (Join-Path $App "unins000.exe")) {
    Start-Process (Join-Path $App "unins000.exe") -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
} elseif (Test-Path $App) {
    RunMsi @("/x", "`"$Msi`"", "/qn", "/norestart") | Out-Null
}
Remove-Item -Recurse -Force $Data -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== 1. Aggiornamento: i dati NON si toccano ==="
Check "prima installazione" ((RunMsi @("/i", "`"$Msi`"", "/qn", "/norestart")) -eq 0) "msiexec 0"
Seed
Check "storico finto creato" (Test-Path $Canary) $Canary
# Reinstalling the same package takes the same road an upgrade does: Windows removes the installed
# product and lays the new one down. Unconditioned, the cleanup would kill the canary right here.
$rc = RunMsi @("/i", "`"$Msi`"", "/qn", "/norestart", "REINSTALL=ALL", "REINSTALLMODE=vomus")
Check "reinstallazione riuscita" ($rc -eq 0) "msiexec $rc"
$alive = Test-Path $Canary
Check "STORICO SOPRAVVISSUTO" $alive $(if ($alive) { "canary.txt ancora presente" } else { "CANCELLATO: un update distruggerebbe i dati" })

Write-Host ""
Write-Host "=== 2. Disinstallazione vera, pacchetto MSI ==="
$rc = RunMsi @("/x", "`"$Msi`"", "/qn", "/norestart")
Start-Sleep -Seconds 3
Check "disinstallazione riuscita" ($rc -eq 0) "msiexec $rc"
Check "app rimossa" (-not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))) $App
$gone = -not (Test-Path $Data)
Check "DATI RIMOSSI" $gone $(if ($gone) { "la cartella non esiste piu" } else { "ANCORA PRESENTI: $Data" })

Write-Host ""
Write-Host "=== 3. Disinstallazione vera, installer Inno ==="
Start-Process $Exe -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
Start-Sleep -Seconds 3
Check "installato" (Test-Path (Join-Path $App "unins000.exe")) "unins000.exe"
Seed
Start-Process (Join-Path $App "unins000.exe") -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
Start-Sleep -Seconds 5
Check "app rimossa" (-not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))) $App
$gone = -not (Test-Path $Data)
Check "DATI RIMOSSI" $gone $(if ($gone) { "la cartella non esiste piu" } else { "ANCORA PRESENTI: $Data" })

Write-Host ""
if ($fail) { Write-Host "$fail controlli FALLITI" -ForegroundColor Red; exit 1 }
Write-Host "disinstallare pulisce tutto, aggiornare non tocca niente" -ForegroundColor Green
