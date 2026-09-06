param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$FrontierPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [int]$RouteOffset = 2,
    [string]$ProfileTemplatePath = '',
    [int]$ProfileTimeoutSeconds = 1800,
    [ValidateRange(0,255)][int]$BattleButton = 1,
    [ValidateRange(0,255)][int]$BattleAlternateButton = 0,
    [ValidateRange(1,100000)][int]$BattlePeriod = 45,
    [ValidateRange(0,100000)][int]$BattleHold = 8,
    [switch]$StopOnBattle,
    [switch]$StopOnInterior,
    [switch]$StopOnMenuTimeout
)
$ErrorActionPreference = 'Stop'
if ($ProfileTimeoutSeconds -lt 5) { throw 'ProfileTimeoutSeconds must be at least 5.' }
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$frontierProfile = Join-Path $PSScriptRoot 'campaign\auto_frontier_profile.txt'
$statusPath = Join-Path $OutputDirectory 'cycle_status.txt'
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) { throw 'wsl.exe not found.' }
$toWslPath = { param([string]$Path) ($Path -replace '^C:', '/mnt/c' -replace '\\', '/') }
$scriptWsl = & $toWslPath (Join-Path $PSScriptRoot 'analyze_explorer_frontier.py')
$frontierWsl = & $toWslPath ([System.IO.Path]::GetFullPath($FrontierPath))
$profileWsl = & $toWslPath $frontierProfile
    & $wsl.Source python3 $scriptWsl $frontierWsl '--route-offset' ($RouteOffset % 4) '--write-profile' $profileWsl `
        '--battle-button' $BattleButton '--battle-alternate-button' $BattleAlternateButton `
        '--battle-period' $BattlePeriod '--battle-hold' $BattleHold
$analysisExitCode = if ($null -eq $LASTEXITCODE -or $LASTEXITCODE -eq '') { 0 } else { [int]$LASTEXITCODE }
if ($analysisExitCode -eq 2) {
    Set-Content -LiteralPath $statusPath -Value 'frontier-exhausted'
    Write-Host 'frontier-exhausted'
    exit 0
}
if ($analysisExitCode -ne 0) { throw "Frontier analysis failed with exit code $analysisExitCode." }
 $profileContent = @(Get-Content -LiteralPath $frontierProfile)
if ($ProfileTemplatePath) {
    if (-not (Test-Path -LiteralPath $ProfileTemplatePath -PathType Leaf)) {
        throw "Profile template not found: $ProfileTemplatePath"
    }
    $profileContent += @(Get-Content -LiteralPath $ProfileTemplatePath)
}
if ($StopOnBattle) { $profileContent += 'POKEMON_EXPLORER_STOP_ON_BATTLE=1' }
if ($StopOnInterior) { $profileContent += 'POKEMON_EXPLORER_STOP_ON_INTERIOR=1' }
if ($StopOnMenuTimeout) { $profileContent += 'POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1' }
Set-Content -LiteralPath $statusPath -Value 'running'
$profileContent | Set-Content -LiteralPath (Join-Path $OutputDirectory 'explorer_config.txt')
try {
    $runner = Join-Path $PSScriptRoot 'run_mesen_explorer_profile.ps1'
    $before = @(Get-Process -Name Mesen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$runner,
        '-RomPath',$RomPath,'-InputPath',$InputPath,'-OutputDirectory',$OutputDirectory)
    $child = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($ProfileTimeoutSeconds)
    while (-not $child.HasExited -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $child.Refresh()
    }
    if (-not $child.HasExited) {
        Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
        $old = @{}; $before | ForEach-Object { $old[[int]$_] = $true }
        @(Get-Process -Name Mesen -ErrorAction SilentlyContinue) |
            Where-Object { -not $old.ContainsKey([int]$_.Id) } |
            Stop-Process -Force -ErrorAction SilentlyContinue
        Set-Content -LiteralPath $statusPath -Value 'timeout'
        throw "Explorer profile timed out after $ProfileTimeoutSeconds seconds."
    }
} catch {
    if ((Get-Content -LiteralPath $statusPath -Raw).Trim() -ne 'timeout') {
        Set-Content -LiteralPath $statusPath -Value 'failed'
    }
    throw
}
Set-Content -LiteralPath $statusPath -Value 'completed'
$contextPath = Join-Path $OutputDirectory 'cycle_context.tsv'
$summaryPath = Join-Path $OutputDirectory 'exploration_summary.tsv'
$templateRecord = if ($ProfileTemplatePath) { $ProfileTemplatePath } else { '<generated-profile>' }
$summaryRows = @{}
if (Test-Path -LiteralPath $summaryPath) {
    foreach ($line in Get-Content -LiteralPath $summaryPath) {
        $parts = $line -split "`t", 2
        if ($parts.Count -eq 2) { $summaryRows[$parts[0]] = $parts[1] }
    }
}
@(
    "route_offset`t$($RouteOffset % 4)",
    "profile_template`t$templateRecord",
    "map_hashes`t$($summaryRows['map_hashes'])",
    "battles`t$($summaryRows['battles'])",
    "frontier`t$(Join-Path $OutputDirectory 'exploration_frontier.tsv')"
) | Set-Content -LiteralPath $contextPath
