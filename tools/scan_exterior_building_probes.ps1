param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$OutputRoot = '..\mesen\building-probes',
    [int]$Direction = -1
)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$aggregate = Join-Path $OutputRoot 'probe_comparison.tsv'
Set-Content -LiteralPath $aggregate -Value "direction`tframes`tcaptures`tmap_hashes`tbattles`texterior_reached`tbuilding_seen`tbuilding_entered`tinterior_seen`tstatus"
$directions = if ($Direction -ge 0 -and $Direction -le 4) { @($Direction) } else { 0..4 }
foreach ($direction in $directions) {
    $output = Join-Path $OutputRoot ("direction-{0}" -f $direction)
    New-Item -ItemType Directory -Force -Path $output | Out-Null
    Set-Content -LiteralPath (Join-Path $output 'explorer_config.txt') -Value @(
        'POKEMON_EXPLORER_START_FRAME=4917',
        'POKEMON_EXPLORER_MAX_FRAMES=7000',
        'POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60',
        'POKEMON_EXPLORER_SETTLE_FRAMES=12',
        'POKEMON_EXPLORER_EDGE_HOLD_FRAMES=180',
        'POKEMON_EXPLORER_DIRECT_TRANSITION=1',
        'POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1',
        'POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3',
        'POKEMON_EXPLORER_GUIDE_EXTERIOR=1',
        'POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=1',
        ('POKEMON_EXPLORER_BUILDING_PROBE_DIRECTION=' + $direction)
    )
    $runnerArgs = @('-NoProfile', '-File', $runner,
        '-RomPath', $RomPath,
        '-ScriptPath', (Join-Path $PSScriptRoot 'mesen_campaign_explorer.lua'),
        '-InputPath', $InputPath,
        '-OutputDirectory', $output,
        '-TimeoutSeconds', '600',
        '-ExpectedMarker', 'POKEMON_MESEN_PASS')
    $child = Start-Process -FilePath 'powershell.exe' -ArgumentList $runnerArgs -Wait -PassThru -NoNewWindow
    if ($child.ExitCode -ne 0) {
        Write-Warning ("Probe direction {0} exited with code {1}" -f $direction, $child.ExitCode)
    }
    $summary = Join-Path $output 'exploration_summary.tsv'
    if (Test-Path -LiteralPath $summary) {
        $values = @{}
        foreach ($line in Get-Content -LiteralPath $summary) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $values[$parts[0]] = $parts[1] }
        }
        $status = if ([int]$values['battles'] -gt 0) { 'battle' }
            elseif ($values['interior_seen'] -eq 'true') { 'interior' }
            elseif ($values['building_entered'] -eq 'true') { 'entered' }
            elseif ($values['building_seen'] -eq 'true') { 'building' }
            elseif ($values['exterior_reached'] -eq 'true') { 'exterior' } else { 'incomplete' }
        Add-Content -LiteralPath $aggregate -Value ("{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}`t{9}" -f $direction,
            $values['frames'], $values['captures'], $values['map_hashes'], $values['battles'],
            $values['exterior_reached'], $values['building_seen'], $values['building_entered'], $values['interior_seen'], $status)
    }
}
