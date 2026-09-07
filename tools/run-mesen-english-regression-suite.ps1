param(
    [Parameter(Mandatory = $true)]
    [string]$RomPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedRomSha256,
    [string]$CriticalRestorationTargetsPath,
    [int]$TimeoutSeconds = 180,
    [bool]$StrictHardware = $true,
    [bool]$FullDebug = $true,
    [string]$MesenPath,
    [string]$SettingsPath,
    [string]$PortableMesenDirectory,
    [string]$ExpectedMesenSha256 =
        '8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7'
)

# Runtime suite for NJ046 English Fidelity 2.0.
#
# Targeted checks only: no automated playthrough or recorded route replay.
# Every scenario creates evidence tied to the English candidate SHA.
# Critical restoration coverage uses an assisted transient loaded-PRG pointer patch.

$ErrorActionPreference = 'Stop'
$StartedUtc = [DateTime]::UtcNow
$ToolsRoot = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ToolsRoot
$ScenarioRunner = Join-Path $ToolsRoot 'run-mesen-pokemon-scenario.ps1'
$BatteryRunner = Join-Path $ToolsRoot 'run-mesen-battery-persistence.ps1'
$BootProbe = Join-Path $ToolsRoot 'mesen_mapper163_boot_probe.lua'
$RuntimeProbe = Join-Path $ToolsRoot 'mesen_mapper163_runtime_probe.lua'
$IntroProbe = Join-Path $ToolsRoot 'mesen_pokemon_intro_probe.lua'
$PromptProbe = Join-Path `
    $ToolsRoot `
    'mesen_pokemon_intro_prompt_en_probe.lua'
$EnglishCharsetProbe = Join-Path $ToolsRoot 'mesen_english_charset_probe.lua'
$TitleMenuProbe = Join-Path $ToolsRoot 'mesen_title_yellow_version_probe.lua'
$PlayerMenuProbe = Join-Path $ToolsRoot 'mesen_player_menu_en_probe.lua'
$CriticalPair6Probe = Join-Path `
    $ToolsRoot `
    'mesen_critical_restorations_pair6_probe.lua'
if (-not $CriticalRestorationTargetsPath) {
    $CriticalRestorationTargetsPath = Join-Path `
        $ProjectRoot `
        'build\critical_restoration_runtime_targets.tsv'
}

$RomPath = [System.IO.Path]::GetFullPath($RomPath)
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$CriticalRestorationTargetsPath = [System.IO.Path]::GetFullPath(
    $CriticalRestorationTargetsPath
)
if ($MesenPath) {
    $MesenPath = [System.IO.Path]::GetFullPath($MesenPath)
}
if ($SettingsPath) {
    $SettingsPath = [System.IO.Path]::GetFullPath($SettingsPath)
}
if ($PortableMesenDirectory) {
    $PortableMesenDirectory = [System.IO.Path]::GetFullPath(
        $PortableMesenDirectory
    )
}

if ($TimeoutSeconds -lt 30) {
    throw 'TimeoutSeconds must be at least 30.'
}

$RequiredFiles = @(
    $RomPath,
    $ScenarioRunner,
    $BatteryRunner,
    $BootProbe,
    $RuntimeProbe,
    $IntroProbe,
    $PromptProbe,
    $EnglishCharsetProbe,
    $TitleMenuProbe,
    $PlayerMenuProbe,
    $CriticalPair6Probe,
    $CriticalRestorationTargetsPath
)
foreach ($Path in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required English regression file not found: $Path"
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

$ActualRomSha256 = Get-LowerSha256 -Path $RomPath
if ($ActualRomSha256 -ne $ExpectedRomSha256.ToLowerInvariant()) {
    throw (
        "English candidate SHA-256 mismatch: expected " +
        "$ExpectedRomSha256, got $ActualRomSha256"
    )
}

$Header = [System.IO.File]::ReadAllBytes($RomPath)[0..15]
if ([System.Text.Encoding]::ASCII.GetString($Header, 0, 3) -ne 'NES' -or
    $Header[3] -ne 0x1A) {
    throw "Not an iNES ROM: $RomPath"
}
$Mapper = (($Header[6] -shr 4) -bor ($Header[7] -band 0xF0))
$PrgBytes = [int64]$Header[4] * 16384
$ChrBytes = [int64]$Header[5] * 8192
if ($Mapper -ne 163 -or $PrgBytes -ne 2097152 -or $ChrBytes -ne 0) {
    throw (
        "Unexpected cartridge layout: mapper=$Mapper " +
        "PRG=$PrgBytes CHR=$ChrBytes"
    )
}

[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$RunName = (
    'run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' +
    [Guid]::NewGuid().ToString('N').Substring(0, 8)
)
$RunDirectory = Join-Path $OutputDirectory $RunName
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
$ManifestPath = Join-Path $RunDirectory 'english_runtime_manifest.txt'
$script:StepResults = [System.Collections.Generic.List[object]]::new()

function Invoke-EnglishStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )
    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Action
        $Stopwatch.Stop()
        $script:StepResults.Add([pscustomobject]@{
            Name = $Name
            Result = 'PASS'
            Seconds = [Math]::Round($Stopwatch.Elapsed.TotalSeconds, 3)
        }) | Out-Null
    } catch {
        $Stopwatch.Stop()
        $script:StepResults.Add([pscustomobject]@{
            Name = $Name
            Result = 'FAIL'
            Seconds = [Math]::Round($Stopwatch.Elapsed.TotalSeconds, 3)
        }) | Out-Null
        throw
    }
}

function Invoke-EnglishScenario {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Region,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedMarker,
        [string]$InputPath
    )
    $ScenarioOutput = Join-Path `
        (Join-Path $RunDirectory $Region.ToLowerInvariant()) `
        $Name
    $Arguments = @{
        RomPath = $RomPath
        ScriptPath = $ScriptPath
        OutputDirectory = $ScenarioOutput
        Region = $Region
        ExpectedEffectiveRegion = $Region
        ExpectedMarker = $ExpectedMarker
        TimeoutSeconds = $TimeoutSeconds
        ExpectedMesenSha256 = $ExpectedMesenSha256
        StrictHardware = $StrictHardware
        FullDebug = $FullDebug
    }
    if ($InputPath) {
        $Arguments.InputPath = $InputPath
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
    & $ScenarioRunner @Arguments
}

function Invoke-EnglishBattery {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Region
    )
    $Arguments = @{
        RomPath = $RomPath
        OutputDirectory = Join-Path `
            (Join-Path $RunDirectory $Region.ToLowerInvariant()) `
            '09-battery-primary-backup-corruption'
        Region = $Region
        TimeoutSeconds = $TimeoutSeconds
        StrictHardware = $StrictHardware
        FullDebug = $FullDebug
        ExpectedMesenSha256 = $ExpectedMesenSha256
        IsolationRootDirectory = Join-Path `
            $ProjectRoot `
            'build\emulator-runs\en2-battery-isolation'
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
    & $BatteryRunner @Arguments
}

function Write-EnglishRuntimeManifest {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('PASS', 'FAIL')]
        [string]$Result,
        [AllowEmptyString()]
        [string]$Failure
    )
    $Lines = [System.Collections.Generic.List[string]]::new()
    $Lines.Add('Suite: NJ046 English Fidelity 2.0 runtime') | Out-Null
    $Lines.Add("Started UTC: $($StartedUtc.ToString('o'))") | Out-Null
    $Lines.Add("Finished UTC: $([DateTime]::UtcNow.ToString('o'))") | Out-Null
    $Lines.Add("Candidate SHA-256: $ActualRomSha256") | Out-Null
    $Lines.Add("Mapper: $Mapper") | Out-Null
    $Lines.Add("PRG bytes: $PrgBytes") | Out-Null
    $Lines.Add("CHR-ROM bytes: $ChrBytes") | Out-Null
    $Lines.Add('Expected CHR-RAM bytes: 8192') | Out-Null
    $Lines.Add('Regions: Dendy,Ntsc,Pal') | Out-Null
    $Lines.Add('Scope: targeted checks only; no automated playthrough') |
        Out-Null
    $Lines.Add(
        'Critical restoration qualification: assisted transient loaded-PRG ' +
        'pointer patch; pointers restored; no game RAM writes'
    ) | Out-Null
    $Lines.Add(
        'Critical restoration target map SHA-256: ' +
        (Get-LowerSha256 -Path $CriticalRestorationTargetsPath)
    ) | Out-Null
    $Lines.Add(
        'Coverage split: controller/runtime evidence is not static ' +
        'exhaustive text coverage'
    ) | Out-Null
    $Lines.Add("Executed steps: $($script:StepResults.Count)") | Out-Null
    for ($Index = 0; $Index -lt $script:StepResults.Count; $Index++) {
        $Step = $script:StepResults[$Index]
        $Lines.Add((
            'Step {0:D2}: {1} | {2} | {3}s' -f
            ($Index + 1),
            $Step.Result,
            $Step.Name,
            $Step.Seconds
        )) | Out-Null
    }
    if ($Failure) {
        $Lines.Add("Failure: $Failure") | Out-Null
    }
    $Lines.Add("Result: $Result") | Out-Null
    $Lines | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

$Result = 'FAIL'
$FailureMessage = ''
try {
    foreach ($Region in @('Dendy', 'Ntsc', 'Pal')) {
        $Scenarios = @(
            @('01-boot', $BootProbe, 'POKEMON_MESEN_PASS', ''),
            @('02-mapper-runtime', $RuntimeProbe, 'MAPPER163_PASS', ''),
            @('03-intro-broad', $IntroProbe, 'POKEMON_INTRO_PASS', ''),
            @(
                '04-intro-prompts',
                $PromptProbe,
                'POKEMON_ENGLISH_INTRO_PROMPTS_PASS',
                ''
            ),
            @(
                '05-english-charset',
                $EnglishCharsetProbe,
                'POKEMON_ENGLISH_CHARSET_PASS',
                ''
            ),
            @(
                '06-title-and-new-load',
                $TitleMenuProbe,
                'TITLE_YELLOW_VERSION_PASS',
                ''
            ),
            @(
                '07-player-menu-exact',
                $PlayerMenuProbe,
                'POKEMON_PLAYER_MENU_EN_PASS',
                ''
            ),
            @(
                '08-critical-restorations-pair6-assisted',
                $CriticalPair6Probe,
                'POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS',
                $CriticalRestorationTargetsPath
            )
        )
        foreach ($Scenario in $Scenarios) {
            $Name = [string]$Scenario[0]
            Invoke-EnglishStep -Name "$Region/$Name" -Action {
                Invoke-EnglishScenario `
                    -Region $Region `
                    -Name $Name `
                    -ScriptPath ([string]$Scenario[1]) `
                    -ExpectedMarker ([string]$Scenario[2]) `
                    -InputPath ([string]$Scenario[3])
            }
        }
        Invoke-EnglishStep -Name "$Region/battery" -Action {
            Invoke-EnglishBattery -Region $Region
        }
    }
    $Result = 'PASS'
} catch {
    $FailureMessage = $_.Exception.Message
    throw
} finally {
    Write-EnglishRuntimeManifest `
        -Result $Result `
        -Failure $FailureMessage
}

Write-Host (
    "NJ046 English Fidelity 2.0 Mesen runtime: PASS " +
    "($($script:StepResults.Count) steps; SHA-256=$ActualRomSha256)"
)
Write-Host "Evidence: $RunDirectory"
