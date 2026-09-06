param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$OutputRoot = "..\mesen\explorer-checkpoints",
    [string]$Frames = '913,1098,1160,1470,1527,1708,2706,3799,4917,5193'
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1'
$aggregate = Join-Path $OutputRoot 'checkpoint_comparison.tsv'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
Set-Content -LiteralPath $aggregate -Value "frame`tframes`tcaptures`tmoved_edges`tblocked_edges`tmap_hashes`tbattles`tstatus"
$frameList = $Frames -split ',' | ForEach-Object { [int]$_.Trim() }
foreach ($frame in $frameList) {
    $output = Join-Path $OutputRoot ("frame-{0:D5}" -f $frame)
    New-Item -ItemType Directory -Force -Path $output | Out-Null
    Set-Content -LiteralPath (Join-Path $output 'explorer_config.txt') `
        -Value @('POKEMON_EXPLORER_START_FRAME=' + $frame, 'POKEMON_EXPLORER_MAX_FRAMES=2000')
    $env:POKEMON_EXPLORER_START_FRAME = [string]$frame
    $env:POKEMON_EXPLORER_MAX_FRAMES = '2000'
    & $runner -RomPath $RomPath -ScriptPath (Join-Path $PSScriptRoot 'mesen_campaign_explorer.lua') `
        -InputPath $InputPath -OutputDirectory $output -TimeoutSeconds 90 `
        -ExpectedMarker POKEMON_MESEN_PASS
    $summary = Join-Path $output 'exploration_summary.tsv'
    if (Test-Path -LiteralPath $summary) {
        $values = @{}
        foreach ($line in Get-Content -LiteralPath $summary) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) { $values[$parts[0]] = $parts[1] }
        }
        $status = if ([int]$values['captures'] -gt 1 -and [int]$values['moved_edges'] -gt 0) { 'usable' } else { 'invalid' }
        $row = "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}" -f $frame,
            $values['frames'], $values['captures'], $values['moved_edges'],
            $values['blocked_edges'], $values['map_hashes'], $values['battles'], $status
        Add-Content -LiteralPath $aggregate -Value $row
        Write-Output $row
    } else {
        Write-Output ("frame={0} summary=missing" -f $frame)
    }
}
Remove-Item Env:POKEMON_EXPLORER_START_FRAME -ErrorAction SilentlyContinue
Remove-Item Env:POKEMON_EXPLORER_MAX_FRAMES -ErrorAction SilentlyContinue
