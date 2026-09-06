param(
    [Parameter(Mandatory = $true)]
    [string]$RomPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [ValidateSet('Ntsc', 'Pal', 'Dendy')]
    [string]$Region = 'Dendy',
    [string]$MesenPath,
    [string]$SettingsPath,
    [string]$PortableMesenDirectory,
    [int]$TimeoutSeconds = 120,
    [bool]$StrictHardware = $true,
    [bool]$FullDebug = $true,
    [string]$ExpectedMesenSha256 =
        '8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7'
)

$ErrorActionPreference = 'Stop'
$RomRoot = Split-Path -Parent $PSScriptRoot
$ScenarioRunner = Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1'
$ControlProbe = Join-Path $PSScriptRoot 'mesen_battery_control_probe.lua'
$CreateProbe = Join-Path $PSScriptRoot 'mesen_battery_create_probe.lua'
$LoadProbe = Join-Path $PSScriptRoot 'mesen_battery_load_probe.lua'
$CorruptionProbe = Join-Path `
    $PSScriptRoot `
    'mesen_battery_corruption_probe.lua'

$RomPath = [System.IO.Path]::GetFullPath($RomPath)
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
foreach ($Path in @(
    $RomPath,
    $ScenarioRunner,
    $ControlProbe,
    $CreateProbe,
    $LoadProbe,
    $CorruptionProbe
)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}
if ($TimeoutSeconds -lt 30) {
    throw 'TimeoutSeconds must be at least 30.'
}

[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$RunName = (
    'run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' +
    [Guid]::NewGuid().ToString('N').Substring(0, 8)
)
$RunDirectory = Join-Path $OutputDirectory $RunName
$ControlOutput = Join-Path $RunDirectory '01-fresh-control'
$ControlIsolation = Join-Path $RunDirectory 'isolation-fresh-control'
$CreateOutput = Join-Path $RunDirectory '02-create-save'
$LoadOutput = Join-Path $RunDirectory '03-reload-save'
$PrimaryCorruptOutput = Join-Path $RunDirectory '04-primary-corrupt'
$BackupCorruptOutput = Join-Path $RunDirectory '05-backup-corrupt'
$SharedIsolation = Join-Path $RunDirectory 'isolation-shared'
$PrimaryCorruptIsolation = Join-Path `
    $RunDirectory `
    'isolation-primary-corrupt'
$BackupCorruptIsolation = Join-Path `
    $RunDirectory `
    'isolation-backup-corrupt'
$EvidenceDirectory = Join-Path $RunDirectory 'evidence'
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
[System.IO.Directory]::CreateDirectory($EvidenceDirectory) | Out-Null

function Invoke-MesenBatteryPhase {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$PhaseOutput,
        [Parameter(Mandatory = $true)]
        [string]$IsolationDirectory,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedMarker
    )

    $Arguments = @{
        RomPath = $RomPath
        ScriptPath = $ScriptPath
        OutputDirectory = $PhaseOutput
        SharedIsolationDirectory = $IsolationDirectory
        Region = $Region
        ExpectedEffectiveRegion = $Region
        ExpectedMarker = $ExpectedMarker
        TimeoutSeconds = $TimeoutSeconds
        ExpectedMesenSha256 = $ExpectedMesenSha256
    }
    if ($MesenPath) {
        $Arguments.MesenPath = $MesenPath
    }
    if ($SettingsPath) {
        $Arguments.SettingsPath = $SettingsPath
    }
    if ($PortableMesenDirectory) {
        $Arguments.PortableMesenDirectory = $PortableMesenDirectory
    }
    if ($StrictHardware) {
        $Arguments.StrictHardware = $true
    }
    if ($FullDebug) {
        $Arguments.FullDebug = $true
    }

    & $ScenarioRunner @Arguments
}

function Assert-FileBytesEqual {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedPath,
        [Parameter(Mandatory = $true)]
        [string]$ActualPath,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $Expected = [System.IO.File]::ReadAllBytes($ExpectedPath)
    $Actual = [System.IO.File]::ReadAllBytes($ActualPath)
    if ($Expected.Length -ne $Actual.Length) {
        throw (
            "$Description length mismatch: " +
            "$($Expected.Length) != $($Actual.Length)"
        )
    }
    for ($Index = 0; $Index -lt $Expected.Length; $Index++) {
        if ($Expected[$Index] -ne $Actual[$Index]) {
            throw (
                "$Description differs at byte ${Index}: " +
                "$($Expected[$Index]) != $($Actual[$Index])"
            )
        }
    }
}

function Get-LowerSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    return (
        Get-FileHash -LiteralPath $Path -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

function Assert-ByteSegmentsEqual {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,
        [Parameter(Mandatory = $true)]
        [int]$FirstOffset,
        [Parameter(Mandatory = $true)]
        [int]$SecondOffset,
        [Parameter(Mandatory = $true)]
        [int]$Length,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (
        $FirstOffset -lt 0 -or
        $SecondOffset -lt 0 -or
        $Length -lt 0 -or
        $FirstOffset + $Length -gt $Bytes.Length -or
        $SecondOffset + $Length -gt $Bytes.Length
    ) {
        throw "$Description segment lies outside the byte array."
    }
    for ($Index = 0; $Index -lt $Length; $Index++) {
        if (
            $Bytes[$FirstOffset + $Index] -ne
            $Bytes[$SecondOffset + $Index]
        ) {
            throw (
                "$Description differs at relative byte ${Index}: " +
                "$($Bytes[$FirstOffset + $Index]) != " +
                "$($Bytes[$SecondOffset + $Index])"
            )
        }
    }
}

function New-CorruptSaveIsolation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$IsolationDirectory,
        [Parameter(Mandatory = $true)]
        [string]$SaveName,
        [Parameter(Mandatory = $true)]
        [byte[]]$Baseline,
        [Parameter(Mandatory = $true)]
        [int]$MutationOffset,
        [Parameter(Mandatory = $true)]
        [string]$EvidencePath
    )

    if ($MutationOffset -lt 0 -or $MutationOffset -ge $Baseline.Length) {
        throw "Corruption offset outside save: $MutationOffset"
    }
    $SaveDataDirectory = Join-Path $IsolationDirectory 'save-data'
    [System.IO.Directory]::CreateDirectory($SaveDataDirectory) | Out-Null
    $Corrupted = [byte[]]$Baseline.Clone()
    $Corrupted[$MutationOffset] = $Corrupted[$MutationOffset] -bxor 0x01
    $Differences = 0
    for ($Index = 0; $Index -lt $Baseline.Length; $Index++) {
        if ($Baseline[$Index] -ne $Corrupted[$Index]) {
            $Differences++
        }
    }
    if ($Differences -ne 1) {
        throw "Corruption fixture must differ by exactly one byte."
    }
    $RuntimeSave = Join-Path $SaveDataDirectory $SaveName
    [System.IO.File]::WriteAllBytes($RuntimeSave, $Corrupted)
    [System.IO.File]::WriteAllBytes($EvidencePath, $Corrupted)
    return $RuntimeSave
}

$StartedUtc = [DateTime]::UtcNow
if (Test-Path -LiteralPath $ControlIsolation) {
    throw "Fresh-control isolation unexpectedly exists: $ControlIsolation"
}
Invoke-MesenBatteryPhase `
    -ScriptPath $ControlProbe `
    -PhaseOutput $ControlOutput `
    -IsolationDirectory $ControlIsolation `
    -ExpectedMarker 'POKEMON_BATTERY_CONTROL_PASS'

if (Test-Path -LiteralPath $SharedIsolation) {
    throw "Shared isolation unexpectedly exists before creation: $SharedIsolation"
}
Invoke-MesenBatteryPhase `
    -ScriptPath $CreateProbe `
    -PhaseOutput $CreateOutput `
    -IsolationDirectory $SharedIsolation `
    -ExpectedMarker 'POKEMON_BATTERY_CREATE_PASS'

$SaveFiles = @(
    Get-ChildItem `
        -LiteralPath (Join-Path $SharedIsolation 'save-data') `
        -File `
        -Filter '*.sav'
)
if ($SaveFiles.Count -ne 1) {
    throw "Expected exactly one Mesen .sav file, found $($SaveFiles.Count)."
}
$SaveFile = $SaveFiles[0]
if ($SaveFile.Length -ne 8192) {
    throw "Mapper 163 save must be 8192 bytes, got $($SaveFile.Length)."
}
$SaveSnapshot = Join-Path $EvidenceDirectory 'created-save-before-reload.sav'
[System.IO.File]::WriteAllBytes(
    $SaveSnapshot,
    [System.IO.File]::ReadAllBytes($SaveFile.FullName)
)
$SaveHashBeforeReload = Get-LowerSha256 -Path $SaveSnapshot
$BaselineSave = [System.IO.File]::ReadAllBytes($SaveSnapshot)
$PrimarySize = 0x0800
$BackupOffset = 0x0C00
$MutationRelativeOffset = 0x0050
Assert-ByteSegmentsEqual `
    -Bytes $BaselineSave `
    -FirstOffset 0 `
    -SecondOffset $BackupOffset `
    -Length $PrimarySize `
    -Description 'valid primary/backup baseline'

$PrimaryCorruptEvidence = Join-Path `
    $EvidenceDirectory `
    'primary-corrupt-before-launch.sav'
$BackupCorruptEvidence = Join-Path `
    $EvidenceDirectory `
    'backup-corrupt-before-launch.sav'
$PrimaryCorruptSave = New-CorruptSaveIsolation `
    -IsolationDirectory $PrimaryCorruptIsolation `
    -SaveName $SaveFile.Name `
    -Baseline $BaselineSave `
    -MutationOffset $MutationRelativeOffset `
    -EvidencePath $PrimaryCorruptEvidence
$BackupCorruptSave = New-CorruptSaveIsolation `
    -IsolationDirectory $BackupCorruptIsolation `
    -SaveName $SaveFile.Name `
    -Baseline $BaselineSave `
    -MutationOffset ($BackupOffset + $MutationRelativeOffset) `
    -EvidencePath $BackupCorruptEvidence

Invoke-MesenBatteryPhase `
    -ScriptPath $LoadProbe `
    -PhaseOutput $LoadOutput `
    -IsolationDirectory $SharedIsolation `
    -ExpectedMarker 'POKEMON_BATTERY_LOAD_PASS'

Invoke-MesenBatteryPhase `
    -ScriptPath $CorruptionProbe `
    -PhaseOutput $PrimaryCorruptOutput `
    -IsolationDirectory $PrimaryCorruptIsolation `
    -ExpectedMarker 'POKEMON_BATTERY_CORRUPTION_OBSERVED'

Invoke-MesenBatteryPhase `
    -ScriptPath $CorruptionProbe `
    -PhaseOutput $BackupCorruptOutput `
    -IsolationDirectory $BackupCorruptIsolation `
    -ExpectedMarker 'POKEMON_BATTERY_CORRUPTION_OBSERVED'

$LoadInitialSram = Join-Path $LoadOutput 'battery_load_initial_sram.bin'
$CreateRoom = Join-Path $CreateOutput 'battery_create_4000.png'
$LoadedRoom = Join-Path $LoadOutput 'battery_load_resumed_room.png'
$ControlFallback = Join-Path $ControlOutput 'battery_control_final.png'
$PrimaryCorruptInitial = Join-Path `
    $PrimaryCorruptOutput `
    'battery_corruption_initial_sram.bin'
$PrimaryCorruptFinal = Join-Path `
    $PrimaryCorruptOutput `
    'battery_corruption_final_sram.bin'
$PrimaryCorruptScreen = Join-Path `
    $PrimaryCorruptOutput `
    'battery_corruption_final.png'
$BackupCorruptInitial = Join-Path `
    $BackupCorruptOutput `
    'battery_corruption_initial_sram.bin'
$BackupCorruptFinal = Join-Path `
    $BackupCorruptOutput `
    'battery_corruption_final_sram.bin'
$BackupCorruptScreen = Join-Path `
    $BackupCorruptOutput `
    'battery_corruption_final.png'
foreach ($Path in @(
    $LoadInitialSram,
    $CreateRoom,
    $LoadedRoom,
    $ControlFallback,
    $PrimaryCorruptInitial,
    $PrimaryCorruptFinal,
    $PrimaryCorruptScreen,
    $BackupCorruptInitial,
    $BackupCorruptFinal,
    $BackupCorruptScreen
)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Expected battery-suite artifact not found: $Path"
    }
}

Assert-FileBytesEqual `
    -ExpectedPath $SaveSnapshot `
    -ActualPath $LoadInitialSram `
    -Description 'closed .sav vs second-process initial SRAM'
Assert-FileBytesEqual `
    -ExpectedPath $CreateRoom `
    -ActualPath $LoadedRoom `
    -Description 'created-game room vs CONT-resumed room'
Assert-FileBytesEqual `
    -ExpectedPath $PrimaryCorruptEvidence `
    -ActualPath $PrimaryCorruptInitial `
    -Description 'primary-corrupt fixture vs initial SRAM'
Assert-FileBytesEqual `
    -ExpectedPath $BackupCorruptEvidence `
    -ActualPath $BackupCorruptInitial `
    -Description 'backup-corrupt fixture vs initial SRAM'
Assert-FileBytesEqual `
    -ExpectedPath $CreateRoom `
    -ActualPath $PrimaryCorruptScreen `
    -Description 'primary-corrupt recovery vs valid resumed room'
Assert-FileBytesEqual `
    -ExpectedPath $ControlFallback `
    -ActualPath $BackupCorruptScreen `
    -Description 'backup-corrupt rejection vs fresh fallback'

$PrimaryRecoveredBytes = [System.IO.File]::ReadAllBytes(
    $PrimaryCorruptFinal
)
Assert-ByteSegmentsEqual `
    -Bytes $PrimaryRecoveredBytes `
    -FirstOffset 0 `
    -SecondOffset $BackupOffset `
    -Length $PrimarySize `
    -Description 'primary-corrupt runtime recovery'
if (
    $PrimaryRecoveredBytes[$MutationRelativeOffset] -ne
    $BaselineSave[$MutationRelativeOffset]
) {
    throw 'Primary-corrupt byte was not restored from the valid backup.'
}

$ControlHash = Get-LowerSha256 -Path $ControlFallback
$LoadedRoomHash = Get-LowerSha256 -Path $LoadedRoom
if ($ControlHash -eq $LoadedRoomHash) {
    throw 'Fresh CONT control unexpectedly matches the loaded room.'
}

$SaveHashAfterReload = Get-LowerSha256 -Path $SaveFile.FullName
$ManifestPath = Join-Path $RunDirectory 'battery_persistence_manifest.txt'
@(
    'Pokemon Yellow NES - Mesen 2.2.1 battery persistence suite'
    "Started UTC: $($StartedUtc.ToString('o'))"
    "Finished UTC: $([DateTime]::UtcNow.ToString('o'))"
    "ROM: $RomPath"
    "ROM SHA-256: $(Get-LowerSha256 -Path $RomPath)"
    'iNES mapper: 163'
    'Battery/save-RAM bytes: 8192'
    "Region: $Region"
    "Strict hardware profile: $StrictHardware"
    "Full NES debug-stop profile: $FullDebug"
    "Fresh-control isolation absent before launch: true"
    "Fresh control output: $ControlOutput"
    "Create output: $CreateOutput"
    "Reload output: $LoadOutput"
    "Primary-corrupt output: $PrimaryCorruptOutput"
    "Backup-corrupt output: $BackupCorruptOutput"
    "Shared isolation: $SharedIsolation"
    "Created save file: $($SaveFile.FullName)"
    "Created save SHA-256 before reload: $SaveHashBeforeReload"
    "Save SHA-256 after reload: $SaveHashAfterReload"
    "Second-process initial SRAM SHA-256: $(Get-LowerSha256 -Path $LoadInitialSram)"
    'Closed .sav equals second-process initial SRAM: true'
    "Created room SHA-256: $(Get-LowerSha256 -Path $CreateRoom)"
    "CONT-resumed room SHA-256: $LoadedRoomHash"
    'Created room equals CONT-resumed room: true'
    "Fresh CONT fallback SHA-256: $ControlHash"
    'Fresh CONT fallback differs from resumed room: true'
    "Corruption relative offset: 0x$($MutationRelativeOffset.ToString('X4'))"
    'Corruption fixture changed bytes per case: 1'
    "Primary-corrupt fixture SHA-256: $(Get-LowerSha256 -Path $PrimaryCorruptEvidence)"
    "Backup-corrupt fixture SHA-256: $(Get-LowerSha256 -Path $BackupCorruptEvidence)"
    'Primary-corrupt initial SRAM equals fixture: true'
    'Backup-corrupt initial SRAM equals fixture: true'
    'Primary corruption restored from valid backup: true'
    'Primary-corrupt CONT equals valid resumed room: true'
    'Backup-corrupt CONT equals fresh fallback: true'
    'Corruption scenarios use memory injection: false'
    'Result: PASS'
) | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

Write-Host "Mesen 2.2.1 mapper 163 battery persistence: PASS ($Region)"
Write-Host "Run directory: $RunDirectory"
Write-Host "Manifest: $ManifestPath"
