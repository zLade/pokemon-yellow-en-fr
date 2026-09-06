param(
    [string]$RomPath = 'build/restored/en/Pokemon_Yellow_EN_Chinese_Dojo.nes',
    [string]$InputPath = 'build/campaign-reference/LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin',
    [string]$ProfilePath = 'tools/campaign/recovery_action_sweep_smoke_profile.txt',
    [string]$OutputDirectory = '../mesen/explorer-smoke-test',
    [int]$TimeoutSeconds = 60,
    [string]$MesenPath = '',
    [switch]$ExpectBattle,
    [switch]$ExpectAlternateBattle,
    [switch]$ExpectInterior,
    [switch]$ExpectMenuTimeout
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_mesen_explorer_profile.ps1'
$runStarted = Get-Date
& $runner -RomPath $RomPath -InputPath $InputPath `
    -OutputDirectory $OutputDirectory -ProfilePath $ProfilePath `
    -TimeoutSeconds $TimeoutSeconds -MesenPath $MesenPath

$summary = Join-Path $OutputDirectory 'exploration_summary.tsv'
if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
    throw "Explorer smoke test did not produce $summary."
}
if ((Get-Item -LiteralPath $summary).LastWriteTime -lt $runStarted) {
    throw "Explorer smoke test returned a stale summary: $summary."
}

$verifier = Join-Path $PSScriptRoot 'verify_explorer_artifacts.py'
python.exe $verifier $OutputDirectory
if (-not $?) { throw 'Explorer artifact verification failed.' }
$manifest = Join-Path $OutputDirectory 'explorer_run_manifest.tsv'
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw "Explorer smoke test did not produce $manifest."
}
if ($ExpectBattle -or $ExpectAlternateBattle -or $ExpectInterior -or $ExpectMenuTimeout) {
    $summaryRows = @{}
    foreach ($line in Get-Content -LiteralPath $summary) {
        $parts = $line -split "`t", 2
        if ($parts.Count -eq 2) { $summaryRows[$parts[0]] = $parts[1] }
    }
    if ($ExpectBattle -or $ExpectAlternateBattle) {
        $battleConfig = Join-Path $OutputDirectory 'battle_config.tsv'
        if (-not (Test-Path -LiteralPath $battleConfig -PathType Leaf)) {
            throw "Expected battle configuration at $battleConfig."
        }
        if ([int]($summaryRows['battles'] -as [int]) -ne 1) {
            throw 'Expected exactly one detected battle.'
        }
        $battleScreens = @(Get-ChildItem -LiteralPath $OutputDirectory -Filter 'battle_*.png' -File)
        if ($battleScreens.Count -ne 1 -or $battleScreens[0].Name -notlike 'battle_001_*.png') {
            throw 'Expected exactly one battle_001 screenshot.'
        }
    }
    if ($ExpectAlternateBattle) {
        $battleConfig = Join-Path $OutputDirectory 'battle_config.tsv'
        if (-not (Test-Path -LiteralPath $battleConfig -PathType Leaf)) {
            throw "Expected battle configuration at $battleConfig."
        }
        $battleValues = @{}
        foreach ($line in Get-Content -LiteralPath $battleConfig) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $battleValues[$parts[0]] = $parts[1] }
        }
        if (-not $battleValues.ContainsKey('alternate_button') -or
            [int]::Parse($battleValues['alternate_button'], [Globalization.NumberStyles]::HexNumber) -eq 0) {
            throw 'Expected a non-zero alternate battle button.'
        }
    }
}
if ($ExpectMenuTimeout) {
    $termination = Join-Path $OutputDirectory 'termination_reason.tsv'
    if (-not (Test-Path -LiteralPath $termination -PathType Leaf) -or
        (Get-Content -LiteralPath $termination | Select-Object -Last 1) -ne 'menu-timeout') {
        throw 'Expected termination_reason=menu-timeout.'
    }
    $timeoutTrace = Join-Path $OutputDirectory 'menu_recovery_timeout.tsv'
    if (-not (Test-Path -LiteralPath $timeoutTrace -PathType Leaf)) {
        throw "Expected menu timeout evidence at $timeoutTrace."
    }
    $timeoutScreen = Join-Path $OutputDirectory 'menu_timeout_screen.png'
    if (-not (Test-Path -LiteralPath $timeoutScreen -PathType Leaf)) {
        throw "Expected menu timeout screenshot at $timeoutScreen."
    }
}
if ($ExpectInterior) {
    if ($summaryRows['interior_seen'] -ne 'true' -or
        $summaryRows['interior_visual_seen'] -ne 'true') {
        throw 'Expected a confirmed interior with visual evidence.'
    }
    $interiorStop = Join-Path $OutputDirectory 'interior_stop.tsv'
    if (-not (Test-Path -LiteralPath $interiorStop -PathType Leaf)) {
        throw "Expected interior stop evidence at $interiorStop."
    }
}
Write-Host "explorer-smoke=PASS output=$OutputDirectory"
