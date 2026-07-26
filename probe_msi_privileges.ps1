# Why does a per-user .msi still ask for administrator rights?
#
# Two separate things have to agree, and only one of them is the ALLUSERS property. The other
# lives in the package's Summary Information Stream: field 15 (Word Count) carries a bit that
# says "this package does not need elevated privileges". Windows Installer reads that bit BEFORE
# it reads any property, to decide whether to raise a UAC prompt at all — so a package can be
# per-user in every other respect and still be elevated on principle.
#
#   bit 0 (1) = short file names
#   bit 1 (2) = compressed / no admin sequences
#   bit 2 (4) = Administrative image
#   bit 3 (8) = ELEVATED PRIVILEGES ARE NOT REQUIRED   <-- the one that matters here
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Msi  = Get-ChildItem (Join-Path $Here "dist") -Filter "*.msi" | Select-Object -First 1
if (-not $Msi) { throw "no .msi in dist\" }
Write-Host "reading $($Msi.Name)`n"

$installer = New-Object -ComObject WindowsInstaller.Installer

# --- summary information -----------------------------------------------------------------
$si = $installer.GetType().InvokeMember("SummaryInformation", "GetProperty", $null, $installer, @($Msi.FullName, 0))
function SI($n) { $si.GetType().InvokeMember("Property", "GetProperty", $null, $si, @($n)) }
$words = SI 15
$template = SI 7
Write-Host "Template (platform;language) : $template"
Write-Host "Word Count                   : $words"
$noElevation = ($words -band 8) -eq 8
Write-Host ("  bit 3 'no elevation needed': {0}" -f $(if ($noElevation) { "SET" } else { "NOT SET  <-- this is why UAC appears" }))

# --- the properties ----------------------------------------------------------------------
$db = $installer.GetType().InvokeMember("OpenDatabase", "InvokeMethod", $null, $installer, @($Msi.FullName, 0))
function Prop($name) {
    $v = $db.GetType().InvokeMember("OpenView", "InvokeMethod", $null, $db, @("SELECT Value FROM Property WHERE Property='$name'"))
    $v.GetType().InvokeMember("Execute", "InvokeMethod", $null, $v, $null)
    $r = $v.GetType().InvokeMember("Fetch", "InvokeMethod", $null, $v, $null)
    if ($r) { $r.GetType().InvokeMember("StringData", "GetProperty", $null, $r, 1) } else { "<absent>" }
}
Write-Host "`nProperties:"
foreach ($p in @("ALLUSERS", "MSIINSTALLPERUSER", "Privileged", "MSIRESTARTMANAGERCONTROL", "InstallScope")) {
    Write-Host ("  {0,-24} = '{1}'" -f $p, (Prop $p))
}
