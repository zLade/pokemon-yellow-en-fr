param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$FrontierPath = '',
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [int]$MaxCycles = 8,
    [int]$InitialRouteOffset = 2,
    [string]$ProfileTemplatePath = '',
    [string]$ContextPath = '',
    [switch]$StopOnBattle,
    [switch]$StopOnInterior,
    [switch]$StopOnMenuTimeout,
    [switch]$StopOnNoGrowth,
    [switch]$Resume,
    [ValidateRange(1, 16)][int]$NoGrowthLimit = 1,
    [int]$ProfileTimeoutSeconds = 1800,
    [ValidateRange(0,255)][int]$BattleButton = 1,
    [ValidateRange(0,255)][int]$BattleAlternateButton = 0,
    [ValidateRange(1,100000)][int]$BattlePeriod = 45,
    [ValidateRange(0,100000)][int]$BattleHold = 8
)

$ErrorActionPreference = 'Stop'
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
if ($ContextPath) {
    if (-not (Test-Path -LiteralPath $ContextPath -PathType Leaf)) { throw "Context not found: $ContextPath" }
    $context = @{}
    foreach ($line in Get-Content -LiteralPath $ContextPath) {
        $parts = $line -split "`t", 2
        if ($parts.Count -eq 2) { $context[$parts[0]] = $parts[1] }
    }
    if (-not $FrontierPath) { $FrontierPath = $context['frontier'] }
    if (-not $ProfileTemplatePath) { $ProfileTemplatePath = $context['profile_template'] }
    if ($ProfileTemplatePath -eq '<generated-profile>') { $ProfileTemplatePath = '' }
    if ($context['route_offset']) { $InitialRouteOffset = [int]$context['route_offset'] }
}
if ($Resume -and -not $FrontierPath) {
    $latestFrontier = @(Get-ChildItem -LiteralPath $OutputRoot -Directory -Filter 'cycle-*' -ErrorAction SilentlyContinue |
        Sort-Object @{Expression={
                if ($_.Name -match '^cycle-(\d+)$') { [int]$Matches[1] } else { -1 }
            }; Descending=$true} |
        ForEach-Object {
            $candidate = Join-Path $_.FullName 'exploration_frontier.tsv'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { Get-Item -LiteralPath $candidate }
        } | Select-Object -First 1)
    if ($latestFrontier) { $FrontierPath = $latestFrontier.FullName }
}
if (-not $FrontierPath) { throw 'FrontierPath or ContextPath is required.' }
$currentFrontier = [System.IO.Path]::GetFullPath($FrontierPath)
$cycleScript = Join-Path $PSScriptRoot 'run_frontier_cycle.ps1'
$history = Join-Path $OutputRoot 'campaign_history.tsv'
$startCycle = 1
if ($Resume) {
    $existingCycles = @(Get-ChildItem -LiteralPath $OutputRoot -Directory -Filter 'cycle-*' -ErrorAction SilentlyContinue |
        ForEach-Object { if ($_.Name -match '^cycle-(\d+)$') { [int]$Matches[1] } })
    if ($existingCycles.Count -gt 0) { $startCycle = (($existingCycles | Measure-Object -Maximum).Maximum + 1) }
}
if (-not $Resume -or -not (Test-Path -LiteralPath $history -PathType Leaf)) {
    Set-Content -LiteralPath $history -Value "cycle`tstatus`troute_offset`tmaps`tbattles`tinterior_seen`tfrontier"
}
$seenFrontiers = [System.Collections.Generic.HashSet[string]]::new()
$previousMaps = -1
$noGrowthCount = 0
if ($Resume -and $StopOnNoGrowth -and (Test-Path -LiteralPath $history -PathType Leaf)) {
    $lastHistory = @(Get-Content -LiteralPath $history | Where-Object { $_ -and $_ -notmatch '^cycle\t' } | Select-Object -Last 1)
    if ($lastHistory) {
        $historyFields = $lastHistory[0] -split "`t"
        if ($historyFields.Count -ge 4 -and $historyFields[3] -match '^\d+$') {
            $previousMaps = [int]$historyFields[3]
        }
    }
}

for ($cycle = $startCycle; $cycle -lt ($startCycle + $MaxCycles); $cycle++) {
    $cycleOffset = ($InitialRouteOffset + $cycle - 1) % 4
    $frontierHash = (Get-FileHash -LiteralPath $currentFrontier -Algorithm SHA256).Hash
    if (-not $seenFrontiers.Add($frontierHash)) {
        Add-Content -LiteralPath $history -Value ("{0}`tloop-detected`t{1}`t-`t-`t-`t{2}" -f $cycle, $cycleOffset, $currentFrontier)
        break
    }
    $cycleDir = Join-Path $OutputRoot ('cycle-{0:D2}' -f $cycle)
    try {
        & $cycleScript -RomPath $RomPath -InputPath $InputPath `
            -FrontierPath $currentFrontier -OutputDirectory $cycleDir `
            -RouteOffset $cycleOffset `
            -ProfileTemplatePath $ProfileTemplatePath `
            -ProfileTimeoutSeconds $ProfileTimeoutSeconds `
            -BattleButton $BattleButton -BattleAlternateButton $BattleAlternateButton `
            -BattlePeriod $BattlePeriod -BattleHold $BattleHold `
            -StopOnBattle:$StopOnBattle `
            -StopOnInterior:$StopOnInterior `
            -StopOnMenuTimeout:$StopOnMenuTimeout
    } catch {
        $cycleStatusPath = Join-Path $cycleDir 'cycle_status.txt'
        $cycleStatus = if (Test-Path -LiteralPath $cycleStatusPath) {
            (Get-Content -LiteralPath $cycleStatusPath -Raw).Trim()
        } else { 'failed' }
        if ($cycleStatus -eq 'timeout') {
            Add-Content -LiteralPath $history -Value ("{0}`ttimeout`t{1}`t-`t-`t-`t{2}" -f $cycle, $cycleOffset, $currentFrontier)
            # A timeout did not consume or transform the frontier. Permit a
            # retry with the next route offset instead of misclassifying it as
            # a frontier loop.
            [void]$seenFrontiers.Remove($frontierHash)
            continue
        }
        throw
    }
    $status = (Get-Content -LiteralPath (Join-Path $cycleDir 'cycle_status.txt') -Raw).Trim()
    $summaryPath = Join-Path $cycleDir 'exploration_summary.tsv'
    if ($status -eq 'running' -and -not (Test-Path -LiteralPath $summaryPath)) {
        # A runner that vanished before finalization must not poison the
        # campaign with a permanently "running" cycle.
        $status = 'timeout'
        Set-Content -LiteralPath (Join-Path $cycleDir 'cycle_status.txt') -Value $status
        Add-Content -LiteralPath $history -Value ("{0}`ttimeout`t{1}`t-`t-`t-`t{2}" -f $cycle, $cycleOffset, $currentFrontier)
        [void]$seenFrontiers.Remove($frontierHash)
        continue
    }
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        $status = 'failed'
        Set-Content -LiteralPath (Join-Path $cycleDir 'cycle_status.txt') -Value $status
        Add-Content -LiteralPath $history -Value ("{0}`tfailed-missing-summary`t{1}`t-`t-`t-`t{2}" -f $cycle, $cycleOffset, $currentFrontier)
        break
    }
    $summary = @{}
    if (Test-Path -LiteralPath $summaryPath) {
        foreach ($line in Get-Content -LiteralPath $summaryPath) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $summary[$parts[0]] = $parts[1] }
        }
    }
    $nextFrontier = Join-Path $cycleDir 'exploration_frontier.tsv'
    Add-Content -LiteralPath $history -Value (
        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}" -f $cycle, $status, $cycleOffset,
        $summary['map_hashes'], $summary['battles'], $summary['interior_seen'], $nextFrontier)
    $terminationPath = Join-Path $cycleDir 'termination_reason.tsv'
    $terminationReason = if (Test-Path -LiteralPath $terminationPath) {
        (Get-Content -LiteralPath $terminationPath | Select-Object -Last 1).Trim()
    } else { '' }
    if ($StopOnMenuTimeout -and $terminationReason -eq 'menu-timeout') {
        Add-Content -LiteralPath $history -Value ("{0}`tmenu-timeout`t{1}`t{2}`t{3}`t{4}`t{5}" -f $cycle, $cycleOffset,
            $summary['map_hashes'], $summary['battles'], $summary['interior_seen'], $nextFrontier)
        break
    }
    $currentMaps = [int]($summary['map_hashes'] -as [int])
    if ($StopOnNoGrowth -and $previousMaps -ge 0 -and $currentMaps -le $previousMaps) {
        $noGrowthCount++
        Add-Content -LiteralPath $history -Value ("{0}`tno-growth`t{1}`t{2}`t{3}`t{4}`t{5}" -f $cycle, $cycleOffset,
            $summary['map_hashes'], $summary['battles'], $summary['interior_seen'], $nextFrontier)
        if ($noGrowthCount -ge $NoGrowthLimit) { break }
    } else {
        $noGrowthCount = 0
    }
    $previousMaps = $currentMaps
    if ($StopOnBattle -and ([int]($summary['battles'] -as [int])) -gt 0) {
        Add-Content -LiteralPath $history -Value ("{0}`tbattle-detected`t{1}`t{2}`t{3}`t{4}`t{5}" -f $cycle, $cycleOffset,
            $summary['map_hashes'], $summary['battles'], $summary['interior_seen'], $nextFrontier)
        break
    }
    if ($StopOnInterior -and $summary['interior_seen'] -eq 'true') {
        Add-Content -LiteralPath $history -Value ("{0}`tinterior-detected`t{1}`t{2}`t{3}`t{4}`t{5}" -f $cycle, $cycleOffset,
            $summary['map_hashes'], $summary['battles'], $summary['interior_seen'], $nextFrontier)
        break
    }
    if ($status -eq 'frontier-exhausted' -or
        -not (Test-Path -LiteralPath $nextFrontier -PathType Leaf)) { break }
    $currentFrontier = $nextFrontier
}

Write-Host "campaign-history=$history"
