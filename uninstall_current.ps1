# Remove whatever copy of Mate is installed, whichever installer put it there, and prove the
# driving history survived. Written as a file rather than typed at an SSH prompt for the reason
# this project has now learned twice: PowerShell quoting does not survive two shells, and the
# failure prints nothing at all — indistinguishable from success.
$ErrorActionPreference = "Continue"
$App = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate"
$Data = Join-Path $env:LOCALAPPDATA "LeapMotorMate"
$db = Join-Path $Data "leapmotor_mate.db"

$before = if (Test-Path $db) { (Get-Item $db).Length } else { 0 }
Write-Host ("database prima : {0:N0} byte" -f $before)

if (-not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))) {
    Write-Host "niente da disinstallare"
} else {
    $inno = Join-Path $App "unins000.exe"
    if (Test-Path $inno) {
        Write-Host "disinstallo (Inno Setup)"
        Start-Process $inno -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
    } else {
        $p = Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,
                              HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -EA SilentlyContinue |
             Where-Object { $_.DisplayName -like "*LeapMotor*" } | Select-Object -First 1
        if ($p) {
            Write-Host "disinstallo (Windows Installer) $($p.PSChildName)"
            Start-Process msiexec.exe -ArgumentList "/x", $p.PSChildName, "/qn", "/norestart" -Wait
        } else {
            Write-Host "app presente ma non registrata da nessun installer - la rimuovo a mano"
            Remove-Item -Recurse -Force $App -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 3
}

$gone = -not (Test-Path (Join-Path $App "LeapMotor Mate.exe"))
$after = if (Test-Path $db) { (Get-Item $db).Length } else { 0 }
Write-Host ("app rimossa    : {0}" -f $gone)
Write-Host ("database dopo  : {0:N0} byte" -f $after)
Write-Host ("storico intatto: {0}" -f ($after -gt 0 -and $after -eq $before))
if (-not $gone) { exit 1 }
