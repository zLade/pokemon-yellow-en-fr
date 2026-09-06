param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$OutputRoot = '..\mesen\explorer-profiles',
    [string]$Holds = '60,90,120,180',
    [int]$TimeoutSeconds = 120,
    [int]$DirectionSeed = 0,
    [ValidateRange(0,255)][int]$BattleButton = 1,
    [ValidateRange(0,255)][int]$BattleAlternateButton = 0,
    [ValidateRange(1,100000)][int]$BattlePeriod = 45,
    [ValidateRange(0,100000)][int]$BattleHold = 8,
    [switch]$CaptureAllTransitions,
    [switch]$TracePc,
    [switch]$StopOnBattle,
    [switch]$StopOnInterior,
    [switch]$StopOnMenuTimeout
)
$ErrorActionPreference = 'Stop'
if ($TimeoutSeconds -lt 5) { throw 'TimeoutSeconds must be at least 5.' }
$runner = Join-Path $PSScriptRoot 'run_mesen_explorer_profile.ps1'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$aggregate = Join-Path $OutputRoot 'profile_comparison.tsv'
Set-Content -LiteralPath $aggregate -Value "hold`tdirection_seed`tframes`tcaptures`tmoved_edges`tblocked_edges`tmap_hashes`ttermination_reason`tstatus"
$holdList = $Holds -split ',' | ForEach-Object { [int]$_.Trim() }
foreach ($hold in $holdList) {
    $output = Join-Path $OutputRoot ("hold-{0:D3}" -f $hold)
    New-Item -ItemType Directory -Force -Path $output | Out-Null
    $profile = Join-Path $OutputRoot ("hold-{0:D3}.profile.txt" -f $hold)
    Set-Content -LiteralPath $profile -Value @(
        'POKEMON_EXPLORER_START_FRAME=4917',
        'POKEMON_EXPLORER_MAX_FRAMES=3000',
        ('POKEMON_EXPLORER_MOVE_HOLD_FRAMES=' + $hold),
        'POKEMON_EXPLORER_SETTLE_FRAMES=12',
        ('POKEMON_EXPLORER_DIRECTION_SEED=' + $DirectionSeed),
        ('POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0x{0:X2}' -f $BattleButton),
        ('POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x{0:X2}' -f $BattleAlternateButton),
        ('POKEMON_EXPLORER_BATTLE_ACTION_PERIOD=' + $BattlePeriod),
        ('POKEMON_EXPLORER_BATTLE_ACTION_HOLD=' + $BattleHold),
        ('POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=' + ($(if ($CaptureAllTransitions) { '1' } else { '0' }))),
        ('POKEMON_EXPLORER_TRACE_PC=' + ($(if ($TracePc) { '1' } else { '0' }))),
        ('POKEMON_EXPLORER_STOP_ON_BATTLE=' + ($(if ($StopOnBattle) { '1' } else { '0' }))),
        ('POKEMON_EXPLORER_STOP_ON_INTERIOR=' + ($(if ($StopOnInterior) { '1' } else { '0' }))),
        ('POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=' + ($(if ($StopOnMenuTimeout) { '1' } else { '0' })))
    )
    $runError = $null
    $runStarted = Get-Date
    try {
        & $runner -RomPath $RomPath -InputPath $InputPath -OutputDirectory $output `
            -ProfilePath $profile -TimeoutSeconds $TimeoutSeconds
    } catch {
        $runError = $_
    }
    $summary = Join-Path $output 'exploration_summary.tsv'
    if ($runError -or -not (Test-Path -LiteralPath $summary) -or
        (Get-Item -LiteralPath $summary).LastWriteTime -lt $runStarted) {
        Add-Content -LiteralPath $aggregate -Value ("{0}`t{1}`t0`t0`t0`t0`t0`t`tfailed" -f $hold, $DirectionSeed)
    } else {
        $values = @{}
        foreach ($line in Get-Content -LiteralPath $summary) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $values[$parts[0]] = $parts[1] }
        }
        $status = if ([int]$values['moved_edges'] -gt 0) { 'usable' } else { 'invalid' }
        $termination = ''
        $terminationPath = Join-Path $output 'termination_reason.tsv'
        if (Test-Path -LiteralPath $terminationPath) {
            $termination = (Get-Content -LiteralPath $terminationPath | Select-Object -Last 1)
        }
        if ($termination -and $termination -notin @('budget', 'battle', 'interior', 'menu-timeout')) {
            Add-Content -LiteralPath $aggregate -Value ("{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`tfailed" -f $hold, $DirectionSeed,
                $values['frames'], $values['captures'], $values['moved_edges'],
                $values['blocked_edges'], $values['map_hashes'], $termination)
            continue
        }
        Add-Content -LiteralPath $aggregate -Value ("{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}" -f $hold, $DirectionSeed,
            $values['frames'], $values['captures'], $values['moved_edges'],
            $values['blocked_edges'], $values['map_hashes'], $termination, $status)
    }
}
$rows = Import-Csv -Delimiter "`t" -LiteralPath $aggregate
$best = $rows | Where-Object { $_.status -eq 'usable' } |
    Sort-Object @{Expression={
            switch ($_.termination_reason) {
                'interior' { 3; break }
                'battle' { 2; break }
                'menu-timeout' { 1; break }
                default { 0 }
            }
        }; Descending=$true},
        @{Expression={[int]$_.moved_edges}; Descending=$true},
        @{Expression={[int]$_.blocked_edges}; Descending=$false} | Select-Object -First 1
if ($best) {
    Set-Content -LiteralPath (Join-Path $OutputRoot 'recommended_profile.txt') -Value @(
        ('POKEMON_EXPLORER_MOVE_HOLD_FRAMES=' + $best.hold),
        'POKEMON_EXPLORER_SETTLE_FRAMES=12',
        ('POKEMON_EXPLORER_DIRECTION_SEED=' + $best.direction_seed)
    )
}
