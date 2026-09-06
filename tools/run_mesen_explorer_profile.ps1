param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$ProfilePath = '',
    [int]$TimeoutSeconds = 1800,
    [string]$MesenPath = ''
)
$ErrorActionPreference = 'Stop'
if ($TimeoutSeconds -lt 5) { throw 'TimeoutSeconds must be at least 5.' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$profileHash = ''
if ($ProfilePath) {
    Copy-Item -LiteralPath $ProfilePath -Destination (Join-Path $OutputDirectory 'explorer_config.txt') -Force
    $profileHash = (Get-FileHash -LiteralPath $ProfilePath -Algorithm SHA256).Hash
}
$romHash = (Get-FileHash -LiteralPath $RomPath -Algorithm SHA256).Hash
$inputHash = (Get-FileHash -LiteralPath $InputPath -Algorithm SHA256).Hash
$scriptPath = Join-Path $PSScriptRoot 'mesen_campaign_explorer.lua'
$scriptHash = (Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash
@(
    "field`tvalue"
    "rom_path`t$RomPath"
    "rom_sha256`t$romHash"
    "input_path`t$InputPath"
    "input_sha256`t$inputHash"
    "script_path`t$scriptPath"
    "script_sha256`t$scriptHash"
    "profile_path`t$ProfilePath"
    "profile_sha256`t$profileHash"
    "timeout_seconds`t$TimeoutSeconds"
) | Set-Content -LiteralPath (Join-Path $OutputDirectory 'explorer_run_manifest.tsv') -Encoding UTF8
& (Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1') `
    -RomPath $RomPath `
    -ScriptPath $scriptPath `
    -InputPath $InputPath `
    -OutputDirectory $OutputDirectory `
    -TimeoutSeconds $TimeoutSeconds `
    -MesenPath $MesenPath `
    -ExpectedMarker POKEMON_MESEN_PASS
