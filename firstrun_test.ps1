# First run, as a brand-new user gets it: no database, no certificate, nothing configured.
#
# This is the path that CHANGED when the bundled certificate came out of the package, so it is
# the one that has to be exercised rather than reasoned about. It runs against a throwaway data
# directory (MATE_APP_DIR) so it never touches the real install's history, and in browser mode so
# it needs no desktop — the shell starts the services and we ask them questions over HTTP.
#
#     powershell -ExecutionPolicy Bypass -File .\firstrun_test.ps1
$ErrorActionPreference = "Stop"
$Exe  = Join-Path $env:LOCALAPPDATA "Programs\LeapMotor Mate\LeapMotor Mate.exe"
$Sand = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "firstrun"

if (-not (Test-Path $Exe)) { throw "not installed: $Exe" }
Remove-Item -Recurse -Force $Sand -ErrorAction SilentlyContinue

Write-Host "==> starting the installed app on an empty data directory"
$env:MATE_APP_DIR = $Sand
$env:MATE_BROWSER = "1"          # no window: there is no desktop in an SSH session
$env:MATE_SKIP_UPDATE = "1"      # test the SEEDED payload, not whatever GitHub has today
$p = Start-Process -FilePath $Exe -PassThru

# The shell seeds the payload, then starts two services and waits for the port. 25s of grace in
# the launcher plus room for a cold first extraction.
$deadline = (Get-Date).AddSeconds(75)
$port = $null
while ((Get-Date) -lt $deadline -and -not $port) {
    Start-Sleep -Seconds 3
    if ($p.HasExited) { break }
    $log = Join-Path $Sand "desktop.log"
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "serving on http://127.0.0.1:(\d+)" | Select-Object -Last 1
        if ($m) { $port = $m.Matches[0].Groups[1].Value }
    }
}

if (-not $port) {
    Write-Host "`n--- it never served. desktop.log: ---" -ForegroundColor Red
    Get-Content (Join-Path $Sand "desktop.log") -ErrorAction SilentlyContinue | Select-Object -Last 30
    foreach ($c in @("mate-web-console.log", "mate-poller-console.log")) {
        Write-Host "`n--- $c ---" -ForegroundColor Red
        Get-Content (Join-Path $Sand $c) -ErrorAction SilentlyContinue | Select-Object -Last 20
    }
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
    exit 1
}

Write-Host "==> serving on port $port"
$base = "http://127.0.0.1:$port"
$fail = 0
function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("  PASS  {0}  {1}" -f $name.PadRight(30), $detail) }
    else     { Write-Host ("  FAIL  {0}  {1}" -f $name.PadRight(30), $detail) -ForegroundColor Red
               $script:fail++ }
}

# The certificate is NOT in the package, so a first run must report it missing and the wizard must
# be the thing the user lands on. If this ever says present:true, a build has started carrying one.
$cert = Invoke-RestMethod "$base/api/setup/cert-status" -TimeoutSec 15
Check "certificate absent" (-not $cert.present) "cert-status present=$($cert.present)"

$home_ = Invoke-WebRequest $base -TimeoutSec 20 -UseBasicParsing
Check "app answers" ($home_.StatusCode -eq 200) "HTTP $($home_.StatusCode), $($home_.Content.Length) bytes"

# The wizard is the whole point of a first run: it is where the user uploads app.crt/app.key.
$setup = Invoke-WebRequest "$base/setup" -TimeoutSec 20 -UseBasicParsing
$hasUpload = $setup.Content -match 'id="file-crt"' -and $setup.Content -match 'id="file-key"'
Check "wizard offers cert upload" $hasUpload "file-crt + file-key inputs present"
Check "wizard names the source" ($setup.Content -match 'markoceri/leapmotor-certs') "links markoceri/leapmotor-certs"

# -Encoding UTF8 is not decoration. The launcher writes UTF-8 on purpose; Get-Content without this
# decodes with the system code page, and the em-dash in "first run — installed bundled payload"
# arrives as three replacement characters. The first version of this check failed on that and
# reported a defect in the app that did not exist — the same encoding trap the app itself fell
# into four times, this time hidden inside the thing meant to catch it.
$log = Get-Content (Join-Path $Sand "desktop.log") -Encoding UTF8
Check "seeded from the bundle" ($log -match "installed bundled payload") `
      (($log | Where-Object { $_ -match "first run" }) -join "")
Check "no fatal errors" (-not ($log -match "FATAL")) "desktop.log has no FATAL line"
Check "data went to the sandbox" (Test-Path (Join-Path $Sand "leapmotor_mate.db")) "$Sand\leapmotor_mate.db"

Write-Host "`n==> stopping"
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
Start-Sleep -Seconds 2
# The shell was killed rather than closed, so its children outlive it — mop them up by name, but
# only the ones running out of the sandbox, never a real instance the user has open.
Get-CimInstance Win32_Process -Filter "Name='LeapMotor Mate.exe'" |
    Where-Object { $_.CommandLine -like "*mate-child*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item -Recurse -Force $Sand -ErrorAction SilentlyContinue

Write-Host ""
if ($fail) { Write-Host "$fail check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "first run is clean" -ForegroundColor Green
