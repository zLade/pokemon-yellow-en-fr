param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string[]]$ProfilePath,
    [string]$ProfileListPath = '',
    [int]$ProfileTimeoutSeconds = 1800,
    [switch]$StopOnBattle,
    [switch]$StopOnInterior
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$rows = @()
# PowerShell -File receives comma-separated values as one string from some
# callers (notably bash/WSL), so accept both native arrays and that form.
$profilePaths = @($ProfilePath | ForEach-Object {
    $_ -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
})
if ($ProfileListPath) {
    if (-not (Test-Path -LiteralPath $ProfileListPath -PathType Leaf)) {
        throw "Profile list not found: $ProfileListPath"
    }
    $profilePaths += @(Get-Content -LiteralPath $ProfileListPath |
        Where-Object { $_ -and -not $_.Trim().StartsWith('#') } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ })
}
if ($profilePaths.Count -eq 0) { throw 'At least one explorer profile is required.' }
if ($ProfileTimeoutSeconds -lt 5) { throw 'ProfileTimeoutSeconds must be at least 5.' }

foreach ($profile in $profilePaths) {
    $profileName = [IO.Path]::GetFileNameWithoutExtension($profile)
    $runDirectory = Join-Path $OutputDirectory $profileName
    Write-Host "[explorer-matrix] $profileName"
    $profileRunner = Join-Path $PSScriptRoot 'run_mesen_explorer_profile.ps1'
    $effectiveProfile = $profile
    if ($StopOnBattle) {
        New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null
        $effectiveProfile = Join-Path $runDirectory 'explorer_config_stop_on_battle.txt'
        Copy-Item -LiteralPath $profile -Destination $effectiveProfile -Force
        Add-Content -LiteralPath $effectiveProfile -Value 'POKEMON_EXPLORER_STOP_ON_BATTLE=1'
    }
    $mesenBefore = @(Get-Process -Name Mesen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $childArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $profileRunner,
        '-RomPath', $RomPath, '-InputPath', $InputPath,
        '-OutputDirectory', $runDirectory, '-ProfilePath', $effectiveProfile,
        '-TimeoutSeconds', $ProfileTimeoutSeconds)
    $child = Start-Process -FilePath 'powershell.exe' -ArgumentList $childArgs `
        -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($ProfileTimeoutSeconds)
    $timedOut = $false
    while (-not $child.HasExited -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $child.Refresh()
    }
    if (-not $child.HasExited) {
        $timedOut = $true
        Write-Warning "Profile timed out after $ProfileTimeoutSeconds seconds: $profileName"
        Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
        # The runner can leave Mesen alive after its own termination. Only
        # remove emulator instances created after this profile started.
        $mesenBeforeSet = @{}; $mesenBefore | ForEach-Object { $mesenBeforeSet[[int]$_] = $true }
        @(Get-Process -Name Mesen -ErrorAction SilentlyContinue) |
            Where-Object { -not $mesenBeforeSet.ContainsKey([int]$_.Id) } |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    $summaryPath = Join-Path $runDirectory 'exploration_summary.tsv'
    $summaryExists = Test-Path -LiteralPath $summaryPath
    if (-not $summaryExists) {
        Write-Warning "Missing exploration summary: $summaryPath"
    }
    $summary = @{}
    if ($summaryExists) {
        foreach ($line in Get-Content -LiteralPath $summaryPath) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $summary[$parts[0]] = $parts[1] }
        }
    }
    $diagnosticCount = 0
    $diagnosticPath = Join-Path $runDirectory 'interior_diagnostics.tsv'
    if (Test-Path -LiteralPath $diagnosticPath) {
        $diagnosticCount = [Math]::Max(0, @(Get-Content -LiteralPath $diagnosticPath).Count - 1)
    }
    $rows += [pscustomobject]@{
        profile = $profileName
        frames = $summary['frames']
        captures = $summary['captures']
        moved_edges = $summary['moved_edges']
        blocked_edges = $summary['blocked_edges']
        map_hashes = $summary['map_hashes']
        battles = $summary['battles']
        recoveries = $summary['recoveries']
        detour_y = $summary['detour_y']
        interior_diagnostics = $diagnosticCount
        building_entered = $summary['building_entered']
        interior_seen = $summary['interior_seen']
        frontier_exhausted = $summary['frontier_exhausted']
        status = if ($timedOut) { 'timeout' } elseif ($summaryExists) { 'completed' } else { 'failed' }
    }
    if ($StopOnBattle -and ([int]($summary['battles'] -as [int])) -gt 0) {
        Write-Host "[explorer-matrix] battle detected; stopping after $profileName"
        break
    }
    if ($StopOnInterior -and $summary['interior_seen'] -eq 'true') {
        Write-Host "[explorer-matrix] interior detected; stopping after $profileName"
        break
    }
}

$aggregatePath = Join-Path $OutputDirectory 'matrix_summary.tsv'
$rows | ConvertTo-Csv -Delimiter "`t" -NoTypeInformation | Set-Content -LiteralPath $aggregatePath -Encoding utf8
Write-Host "[explorer-matrix] summary: $aggregatePath"
