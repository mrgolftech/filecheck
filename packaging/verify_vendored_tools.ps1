param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('x64', 'x86')]
    [string]$Arch
)

$ErrorActionPreference = 'Stop'

$expected = @{
    x64 = @{
        Machine = 0x8664
        EverythingSha256 = 'F191F756996A14A11E5445FA7103D302EFD510CF2FBF920E6C0C8ED51D512E36'
        EsSha256 = '3BE7185707E8023CD9295DBCB7A3FA4092A3D8F52B7FA92A0B84243AB40D12F3'
    }
    x86 = @{
        Machine = 0x014C
        EverythingSha256 = 'D38F48DD60DE6B10F9A132718CCBFDDC171A7A7D1CC88EF2E4CE73C0C43DCD5F'
        EsSha256 = '1C805F71B19AED9680A20E04443E4205506FB8032DDB650AE1414A86CDC4D38D'
    }
}

function Get-PeMachine([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Path))
    if ($bytes.Length -lt 64) { throw "Invalid PE file: $Path" }
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    return [BitConverter]::ToUInt16($bytes, $peOffset + 4)
}

$root = Join-Path 'vendor\everything' $Arch
$everything = Join-Path $root 'Everything.exe'
$es = Join-Path $root 'es.exe'

foreach ($path in @($everything, $es)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Vendored tool missing: $path"
    }
}

$cfg = $expected[$Arch]
$everythingHash = (Get-FileHash $everything -Algorithm SHA256).Hash
$esHash = (Get-FileHash $es -Algorithm SHA256).Hash
if ($everythingHash -ne $cfg.EverythingSha256) {
    throw "Vendored Everything.exe SHA-256 mismatch for $Arch. expected=$($cfg.EverythingSha256) actual=$everythingHash"
}
if ($esHash -ne $cfg.EsSha256) {
    throw "Vendored es.exe SHA-256 mismatch for $Arch. expected=$($cfg.EsSha256) actual=$esHash"
}

$everythingMachine = Get-PeMachine $everything
$esMachine = Get-PeMachine $es
if ($everythingMachine -ne $cfg.Machine) {
    throw ('Everything.exe PE machine mismatch for {0}: 0x{1:X4}' -f $Arch, $everythingMachine)
}
if ($esMachine -ne $cfg.Machine) {
    throw ('es.exe PE machine mismatch for {0}: 0x{1:X4}' -f $Arch, $esMachine)
}

$everythingVersion = (Get-Item $everything).VersionInfo.ProductVersion
if (-not $everythingVersion) {
    $everythingVersion = (Get-Item $everything).VersionInfo.FileVersion
}
Write-Host "Everything $Arch version: $everythingVersion"
if ($everythingVersion -notmatch '^1\.4\.1\.1032') {
    throw "Unexpected Everything version for ${Arch}: $everythingVersion"
}

$esVersion = (& $es -version | Out-String).Trim()
Write-Host "ES $Arch version: $esVersion"
if ($esVersion -notmatch '1\.1\.0\.37') {
    throw "Unexpected ES version for ${Arch}: $esVersion"
}

Write-Host "Vendored Everything/ES verification passed for $Arch."
