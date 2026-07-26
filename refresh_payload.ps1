# Replace the local copy of Mate's source that build_win.ps1 seeds from.
#
# The Mac's shared folder is not visible over SSH (Parallels mounts it into the interactive
# desktop session only), and there is no git in the VM, so the payload arrives as a tarball and
# is unpacked here. Ten seconds, and it removes the one thing that would otherwise go unnoticed:
# a package built today carrying last week's Mate.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tgz  = Join-Path $Here "payload.tgz"
$Repo = Join-Path $Here "repo"

if (-not (Test-Path $Tgz)) { throw "payload.tgz not found - copy it over first" }

$before = if (Test-Path "$Repo\web\main.py") {
    (Select-String -Path "$Repo\web\main.py" -Pattern 'MATE_VERSION' | Select-Object -First 1).Line.Split('"')[1]
} else { "(none)" }

# certs\ is deliberately left alone: it is not part of the payload and nothing should put it there.
Remove-Item -Recurse -Force "$Repo\web", "$Repo\poller" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Repo | Out-Null
tar -xzf $Tgz -C $Repo
if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE" }

$after = (Select-String -Path "$Repo\web\main.py" -Pattern 'MATE_VERSION' | Select-Object -First 1).Line.Split('"')[1]
Write-Host "payload: $before -> $after"
Remove-Item $Tgz -Force
