# Put WiX 5 on this machine and take WiX 7 off it.
#
# WiX 6 and later refuse to build until the Open Source Maintenance Fee licence is accepted
# (error WIX7015). Accepting it is a statement about the project, not a build step, so this uses
# version 5 — same language as installer.wxs, nothing to agree to.
#
# The removal matters as much as the install: a winget WiX 7 also puts wix.exe on PATH, and left
# in place it would win a plain lookup and fail every build with a licence error for a version we
# are deliberately not using.
$ErrorActionPreference = "Continue"

Write-Host "==> removing WiX 7 (if present)"
winget uninstall --id WiXToolset.WiXCLI --silent --disable-interactivity 2>&1 | Select-Object -Last 2

Write-Host "==> installing WiX 5 as a dotnet tool"
$dotnet = (Get-Command dotnet -EA SilentlyContinue).Source
if (-not $dotnet) { $dotnet = "C:\Program Files\dotnet\dotnet.exe" }
& $dotnet tool install --global wix --version 5.0.2 2>&1 | Select-Object -Last 4

$wix = "$env:USERPROFILE\.dotnet\tools\wix.exe"
Write-Host ""
if (Test-Path $wix) {
    Write-Host "wix at: $wix"
    & $wix --version
    # PINNED to 5.0.2. Without the version the extension resolves to the newest published — 7.0.0 —
    # which WiX 5 then declines to load ("Could not find expected package root folder wixext5").
    # It is a warning, not an error, so the build carries on and fails later somewhere less
    # obvious: the dialogs simply are not there.
    Write-Host "==> adding the UI extension (welcome / licence / install-location dialogs)"
    & $wix extension add -g WixToolset.UI.wixext/5.0.2 2>&1 | Select-Object -Last 2
    Write-Host "installed extensions:"
    & $wix extension list -g
} else {
    Write-Host "wix.exe NOT found at $wix" -ForegroundColor Red
}
