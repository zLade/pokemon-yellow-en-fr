param(
    [string]$RomPath = 'build/restored/en/Pokemon_Yellow_EN_Chinese_Dojo.nes',
    [string]$InputPath = 'build/campaign-reference/LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin',
    [string]$OutputDirectory = '../mesen/alternate-battle-smoke',
    [ValidateRange(5, 86400)][int]$TimeoutSeconds = 120,
    [string]$MesenPath = '',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$smoke = Join-Path $PSScriptRoot 'test_explorer_smoke.ps1'
$profile = Join-Path $PSScriptRoot 'campaign/battle_action_alternate_smoke_profile.txt'
if ($ValidateOnly) {
    if (-not (Test-Path -LiteralPath $profile -PathType Leaf)) {
        throw "Alternate battle profile not found: $profile"
    }
    if (-not (Test-Path -LiteralPath $RomPath -PathType Leaf)) {
        throw "ROM not found: $RomPath"
    }
    if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
        throw "Input stream not found: $InputPath"
    }
    $alternateLine = Get-Content -LiteralPath $profile |
        Where-Object { $_ -match '^POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x([0-9A-Fa-f]{2})$' } |
        Select-Object -First 1
    if (-not $alternateLine -or $alternateLine -match '=0x00$') {
        throw 'Alternate battle profile does not enable a secondary button.'
    }
    $primaryLine = Get-Content -LiteralPath $profile |
        Where-Object { $_ -match '^POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0x([0-9A-Fa-f]{2})$' } |
        Select-Object -First 1
    if (-not $primaryLine -or $primaryLine -match '=0x00$') {
        throw 'Alternate battle profile does not enable a primary button.'
    }
    $periodLine = Get-Content -LiteralPath $profile | Where-Object { $_ -match '^POKEMON_EXPLORER_BATTLE_ACTION_PERIOD=(\d+)$' } | Select-Object -First 1
    $holdLine = Get-Content -LiteralPath $profile | Where-Object { $_ -match '^POKEMON_EXPLORER_BATTLE_ACTION_HOLD=(\d+)$' } | Select-Object -First 1
    if (-not $periodLine -or [int]($periodLine -replace '^[^=]+=','') -lt 1) {
        throw 'Alternate battle profile has an invalid action period.'
    }
    if (-not $holdLine -or [int]($holdLine -replace '^[^=]+=','') -lt 0) {
        throw 'Alternate battle profile has an invalid action hold.'
    }
    Write-Host "alternate-battle-smoke=VALID profile=$profile"
    exit 0
}
& $smoke -RomPath $RomPath -InputPath $InputPath -ProfilePath $profile `
    -OutputDirectory $OutputDirectory -TimeoutSeconds $TimeoutSeconds `
    -MesenPath $MesenPath `
    -ExpectBattle -ExpectAlternateBattle
if (-not $?) { throw 'Alternate battle smoke test failed.' }
Write-Host "alternate-battle-smoke=PASS output=$OutputDirectory"
