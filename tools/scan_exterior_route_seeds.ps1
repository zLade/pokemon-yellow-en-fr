param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$OutputRoot = '..\mesen\route-seeds',
    [int]$Seed = -1,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$aggregate = Join-Path $OutputRoot 'seed_comparison.tsv'
Set-Content -LiteralPath $aggregate -Value "seed`tframes`tcaptures`tmap_hashes`tbattles`texterior_reached`tbuilding_seen`tstatus"
$seeds = if ($Seed -ge 0 -and $Seed -le 3) { @($Seed) } else { 0..3 }
foreach ($seed in $seeds) {
    $output = Join-Path $OutputRoot ("seed-{0}" -f $seed)
    New-Item -ItemType Directory -Force -Path $output | Out-Null
    Set-Content -LiteralPath (Join-Path $output 'explorer_config.txt') -Value @(
        'POKEMON_EXPLORER_START_FRAME=4917',
        'POKEMON_EXPLORER_MAX_FRAMES=18000',
        'POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60',
        'POKEMON_EXPLORER_SETTLE_FRAMES=12',
        'POKEMON_EXPLORER_DIRECT_TRANSITION=1',
        'POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1',
        'POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3',
        'POKEMON_EXPLORER_GUIDE_EXTERIOR=1',
        'POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD=900',
        'POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD=30',
        ('POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET={0}' -f $seed),
        'POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=0',
        'POKEMON_EXPLORER_GENERIC_ACTION_PERIOD=30'
    )
    if ($DryRun) { continue }
    try {
        & $runner -RomPath $RomPath -ScriptPath (Join-Path $PSScriptRoot 'mesen_campaign_explorer.lua') `
            -InputPath $InputPath -OutputDirectory $output -TimeoutSeconds 900 -ExpectedMarker POKEMON_MESEN_PASS
    } catch {
        Write-Warning ("Seed {0} runner ended before its marker: {1}" -f $seed, $_.Exception.Message)
    }
    $summary = Join-Path $output 'exploration_summary.tsv'
    if (Test-Path -LiteralPath $summary) {
        $values = @{}
        foreach ($line in Get-Content -LiteralPath $summary) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $values[$parts[0]] = $parts[1] }
        }
        $status = if ([int]$values['battles'] -gt 0) { 'battle' } elseif ([int]$values['map_hashes'] -gt 10) { 'broad' } else { 'limited' }
        Add-Content -LiteralPath $aggregate -Value ("{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}" -f $seed,
            $values['frames'], $values['captures'], $values['map_hashes'], $values['battles'],
            $values['exterior_reached'], $values['building_seen'], $status)
    }
}
