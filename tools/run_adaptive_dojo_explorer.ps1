param(
    [string]$RomPath = 'build/restored/en/Pokemon_Yellow_EN_Chinese_Dojo.nes',
    [string]$InputPath = 'build/campaign-reference/LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin',
    [string]$OutputDirectory = '../mesen/adaptive-dojo-run',
    [int]$TimeoutSeconds = 900
)
$ErrorActionPreference = 'Stop'
$profile = Join-Path $PSScriptRoot 'campaign/explorer_adaptive_dojo_profile.txt'
$runner = Join-Path $PSScriptRoot 'run_mesen_explorer_profile.ps1'
$runStarted = Get-Date
& $runner -RomPath $RomPath -InputPath $InputPath -OutputDirectory $OutputDirectory `
    -ProfilePath $profile -TimeoutSeconds $TimeoutSeconds

$summary = Join-Path $OutputDirectory 'exploration_summary.tsv'
if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
    throw "Adaptive dojo run did not produce $summary."
}
if ((Get-Item -LiteralPath $summary).LastWriteTime -lt $runStarted) {
    throw "Adaptive dojo run returned a stale summary: $summary."
}
$values = @{}
foreach ($line in Get-Content -LiteralPath $summary) {
    $parts = $line -split "`t", 2
    if ($parts.Count -eq 2) { $values[$parts[0]] = $parts[1] }
}
if ($values['interior_seen'] -ne 'true' -or $values['interior_visual_seen'] -ne 'true') {
    throw 'Adaptive dojo run did not confirm a visually validated interior.'
}
$termination = Join-Path $OutputDirectory 'termination_reason.tsv'
if (-not (Test-Path -LiteralPath $termination -PathType Leaf) -or
    (Get-Content -LiteralPath $termination | Select-Object -Last 1) -ne 'interior') {
    throw 'Adaptive dojo run did not terminate on the confirmed interior.'
}
$verifier = Join-Path $PSScriptRoot 'verify_explorer_artifacts.py'
python.exe $verifier $OutputDirectory
if (-not $?) { throw 'Adaptive dojo artifact verification failed.' }
Write-Host "adaptive-dojo=PASS output=$OutputDirectory"
