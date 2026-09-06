param(
    [Parameter(Mandatory = $true)]
    [string]$RomPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [int]$TimeoutSeconds = 120,
    [switch]$SkipBattery,
    [switch]$BootstrapCompletionGate,
    [switch]$IncludeExperimentalRoute1Viridian,
    [bool]$StrictHardware = $true,
    [bool]$FullDebug = $true,
    [string]$MesenPath,
    [string]$SettingsPath,
    [string]$PortableMesenDirectory,
    [string]$ChineseRomPath,
    [string]$FinalIpsPath,
    [string]$TranslationBaseRomPath,
    [string]$CanonicalEnglishRomPath,
    [string]$EnglishIpsPath,
    [string]$TranslationScriptPath,
    [string]$CanonicalCsvPath,
    [string]$FixedOverflowPath,
    [string]$Route1InputPath,
    [string]$ExpectedMesenSha256 =
        '8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7'
)

$ErrorActionPreference = 'Stop'
$StartedUtc = [DateTime]::UtcNow
$RomRoot = Split-Path -Parent $PSScriptRoot
$ScenarioRunner = Join-Path $PSScriptRoot 'run-mesen-pokemon-scenario.ps1'
$BatteryRunner = Join-Path $PSScriptRoot 'run-mesen-battery-persistence.ps1'
$BootProbe = Join-Path $PSScriptRoot 'mesen_mapper163_boot_probe.lua'
$RuntimeProbe = Join-Path $PSScriptRoot 'mesen_mapper163_runtime_probe.lua'
$IntroProbe = Join-Path $PSScriptRoot 'mesen_pokemon_intro_probe.lua'
$PromptProbe = Join-Path $PSScriptRoot 'mesen_pokemon_intro_prompt_probe.lua'
$AccentProbe = Join-Path `
    $PSScriptRoot `
    'mesen_intro_french_accents_probe.lua'
$ChrExportProbe = Join-Path $PSScriptRoot 'mesen_chr_export_probe.lua'
$PlayerMenuProbe = Join-Path `
    $PSScriptRoot `
    'mesen_player_menu_french_probe.lua'
$CampaignProbe = Join-Path `
    $PSScriptRoot `
    'campaign\mesen_campaign_prototype.lua'
$Route1Probe = Join-Path `
    $PSScriptRoot `
    'mesen_fm3_route1_viridian_after_prototype.lua'

if (-not $ChineseRomPath) {
    $ChineseRomPath = Join-Path $RomRoot (
        'Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes'
    )
}
if (-not $FinalIpsPath) {
    $FinalIpsPath = Join-Path $RomRoot 'Pokemon_Jaune_FR_repacked_title.ips'
}
if (-not $TranslationBaseRomPath) {
    $TranslationBaseRomPath = Join-Path `
        $RomRoot `
        'Pokemon Yellow English 9-23-2015.nes'
}
if (-not $CanonicalEnglishRomPath) {
    $CanonicalEnglishRomPath = Join-Path $RomRoot 'yellow.nes'
}
if (-not $EnglishIpsPath) {
    $EnglishIpsPath = Join-Path `
        $RomRoot `
        'Pokemon Yellow English 9-23-2015.ips'
}
if (-not $TranslationScriptPath) {
    $TranslationScriptPath = Join-Path $RomRoot 'script.py'
}
if (-not $CanonicalCsvPath) {
    $CanonicalCsvPath = Join-Path $RomRoot 'traduction_base.csv'
}
if (-not $FixedOverflowPath) {
    $FixedOverflowPath = Join-Path $RomRoot 'textes_fixes_trop_longs.csv'
}
if (-not $Route1InputPath) {
    $Route1InputPath = Join-Path `
        $RomRoot `
        'build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin'
}

$RomPath = [System.IO.Path]::GetFullPath($RomPath)
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$ChineseRomPath = [System.IO.Path]::GetFullPath($ChineseRomPath)
$FinalIpsPath = [System.IO.Path]::GetFullPath($FinalIpsPath)
$TranslationBaseRomPath = [System.IO.Path]::GetFullPath(
    $TranslationBaseRomPath
)
$CanonicalEnglishRomPath = [System.IO.Path]::GetFullPath(
    $CanonicalEnglishRomPath
)
$EnglishIpsPath = [System.IO.Path]::GetFullPath($EnglishIpsPath)
$TranslationScriptPath = [System.IO.Path]::GetFullPath(
    $TranslationScriptPath
)
$CanonicalCsvPath = [System.IO.Path]::GetFullPath($CanonicalCsvPath)
$FixedOverflowPath = [System.IO.Path]::GetFullPath($FixedOverflowPath)
$Route1InputPath = [System.IO.Path]::GetFullPath($Route1InputPath)
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

$PythonTestFiles = @(
    Get-ChildItem `
        -LiteralPath $PSScriptRoot `
        -File `
        -Filter 'test_*.py' |
        Sort-Object Name
)
if ($PythonTestFiles.Count -eq 0) {
    throw "No Python test module discovered in $PSScriptRoot"
}

$RequiredFiles = @(
    $RomPath,
    $ChineseRomPath,
    $FinalIpsPath,
    $TranslationBaseRomPath,
    $CanonicalEnglishRomPath,
    $EnglishIpsPath,
    $TranslationScriptPath,
    $CanonicalCsvPath,
    $FixedOverflowPath,
    $ScenarioRunner,
    $BatteryRunner,
    $BootProbe,
    $RuntimeProbe,
    $IntroProbe,
    $PromptProbe,
    $AccentProbe,
    $ChrExportProbe,
    $PlayerMenuProbe,
    $CampaignProbe,
    $Route1Probe,
    (Join-Path $RomRoot 'rom_traduction_assistant.py'),
    (Join-Path $PSScriptRoot 'audit_quality_ambitious.py'),
    (Join-Path $PSScriptRoot 'audit_translation_coverage.py'),
    (Join-Path $PSScriptRoot 'dialogue_layout.py'),
    (Join-Path $PSScriptRoot 'dialogue_inventory.py'),
    (Join-Path $PSScriptRoot 'validate_mapper163.py'),
    (Join-Path $PSScriptRoot 'validate_repacked.py'),
    (Join-Path $PSScriptRoot 'validate_dialogue_layout.py'),
    (Join-Path $PSScriptRoot 'validate_pokedex_layout.py'),
    (Join-Path $PSScriptRoot 'validate_final_pokedex_runtime.py'),
    (Join-Path $PSScriptRoot 'data\dialogue_boundary_inventory.json'),
    (
        Join-Path `
            $PSScriptRoot `
            'data\mesen_french_charset_probe_expected.json'
    )
) + @($PythonTestFiles.FullName)
if ($IncludeExperimentalRoute1Viridian) {
    $RequiredFiles += $Route1InputPath
}
foreach ($Path in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required regression-suite file not found: $Path"
    }
}

$WslCommand = Get-Command 'wsl.exe' -ErrorAction SilentlyContinue
if (-not $WslCommand) {
    throw (
        'wsl.exe is required to run the project Python validators from ' +
        'this Windows PowerShell Mesen suite.'
    )
}
$WslExecutable = $WslCommand.Source

[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$RunName = (
    'run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' +
    [Guid]::NewGuid().ToString('N').Substring(0, 8)
)
$RunDirectory = Join-Path $OutputDirectory $RunName
$StaticOutput = Join-Path $RunDirectory 'static'
$MesenOutput = Join-Path $RunDirectory 'mesen'
[System.IO.Directory]::CreateDirectory($StaticOutput) | Out-Null
[System.IO.Directory]::CreateDirectory($MesenOutput) | Out-Null
$ManifestPath = Join-Path $RunDirectory 'regression_suite_manifest.txt'

$script:RegressionStepResults = [System.Collections.Generic.List[object]]::new()

function Get-LowerSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    return (
        Get-FileHash -LiteralPath $Path -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

function Convert-ToSingleLine {
    param(
        [AllowEmptyString()]
        [string]$Text
    )
    return (($Text -replace '\r?\n', ' ') -replace '\s+', ' ').Trim()
}

function Convert-ToNativeArgument {
    param(
        [AllowEmptyString()]
        [string]$Argument
    )
    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }
    return '"' + ($Argument -replace '"', '\"') + '"'
}

function Convert-ToWslPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WindowsPath
    )

    $Token = [Guid]::NewGuid().ToString('N')
    $StdoutPath = Join-Path $StaticOutput "wslpath-$Token.stdout.txt"
    $StderrPath = Join-Path $StaticOutput "wslpath-$Token.stderr.txt"
    try {
        $Arguments = @(
            '--exec',
            'wslpath',
            '-a',
            $WindowsPath
        ) | ForEach-Object {
            Convert-ToNativeArgument -Argument $_
        }
        $Process = Start-Process `
            -FilePath $WslExecutable `
            -ArgumentList $Arguments `
            -Wait `
            -PassThru `
            -NoNewWindow `
            -RedirectStandardOutput $StdoutPath `
            -RedirectStandardError $StderrPath
        $Stdout = if (Test-Path -LiteralPath $StdoutPath) {
            Get-Content -LiteralPath $StdoutPath -Raw
        } else {
            ''
        }
        $Stderr = if (Test-Path -LiteralPath $StderrPath) {
            Get-Content -LiteralPath $StderrPath -Raw
        } else {
            ''
        }
        if ($Process.ExitCode -ne 0) {
            throw (
                "wslpath failed for '$WindowsPath' " +
                "(exit $($Process.ExitCode)): " +
                (Convert-ToSingleLine -Text ($Stderr + ' ' + $Stdout))
            )
        }
        $Converted = ($Stdout -split '\r?\n')[0].Trim()
        if (-not $Converted) {
            throw "wslpath returned an empty path for '$WindowsPath'."
        }
        return $Converted
    } finally {
        foreach ($TemporaryPath in @($StdoutPath, $StderrPath)) {
            if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
                [System.IO.File]::Delete($TemporaryPath)
            }
        }
    }
}

function Invoke-RegressionStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "==> $Name"
    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Action
        $Stopwatch.Stop()
        $script:RegressionStepResults.Add([pscustomobject]@{
            Name = $Name
            Result = 'PASS'
            Seconds = [Math]::Round($Stopwatch.Elapsed.TotalSeconds, 3)
            Detail = ''
        }) | Out-Null
        Write-Host "<== PASS $Name"
    } catch {
        $Stopwatch.Stop()
        $Detail = Convert-ToSingleLine -Text $_.Exception.Message
        $script:RegressionStepResults.Add([pscustomobject]@{
            Name = $Name
            Result = 'FAIL'
            Seconds = [Math]::Round($Stopwatch.Elapsed.TotalSeconds, 3)
            Detail = $Detail
        }) | Out-Null
        Write-Host "<== FAIL $Name"
        throw
    }
}

function Invoke-WslPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$LogPath,
        [switch]$BootstrapCompletionGateEnvironment
    )

    $StderrPath = $LogPath + '.stderr.txt'
    $PythonCommand = if ($BootstrapCompletionGateEnvironment) {
        @('env', 'POKEMON_MESEN_BOOTSTRAP=1', 'python3')
    } else {
        @('python3')
    }
    $WslArguments = @(
        '--cd',
        $script:LinuxRomRoot,
        '--exec'
    ) + $PythonCommand + $Arguments
    $NativeArguments = @($WslArguments | ForEach-Object {
        Convert-ToNativeArgument -Argument $_
    })
    $Process = Start-Process `
        -FilePath $WslExecutable `
        -ArgumentList $NativeArguments `
        -Wait `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $StderrPath
    $Stdout = if (Test-Path -LiteralPath $LogPath) {
        Get-Content -LiteralPath $LogPath -Raw
    } else {
        ''
    }
    $Stderr = if (Test-Path -LiteralPath $StderrPath) {
        Get-Content -LiteralPath $StderrPath -Raw
    } else {
        ''
    }
    if ($Stdout) {
        $Stdout.TrimEnd() | Write-Host
    }
    if ($Stderr) {
        $Stderr.TrimEnd() | Write-Host
    }
    if ($Process.ExitCode -ne 0) {
        throw (
            "Python validation exited with code $($Process.ExitCode); " +
            "see $LogPath and $StderrPath"
        )
    }
}

function Invoke-MesenScenario {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScenarioRom,
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$ScenarioOutput,
        [Parameter(Mandatory = $true)]
        [ValidateSet('Auto', 'Ntsc', 'Pal', 'Dendy')]
        [string]$Region,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedRegion,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedMarker,
        [string]$ScenarioInput,
        [switch]$EnableGameDatabase
    )

    $Arguments = @{
        RomPath = $ScenarioRom
        ScriptPath = $ScriptPath
        OutputDirectory = $ScenarioOutput
        Region = $Region
        ExpectedEffectiveRegion = $ExpectedRegion
        ExpectedMarker = $ExpectedMarker
        TimeoutSeconds = $TimeoutSeconds
        ExpectedMesenSha256 = $ExpectedMesenSha256
    }
    if ($StrictHardware) {
        $Arguments.StrictHardware = $true
    }
    if ($FullDebug) {
        $Arguments.FullDebug = $true
    }
    if ($EnableGameDatabase) {
        $Arguments.EnableGameDatabase = $true
    }
    if ($ScenarioInput) {
        $Arguments.InputPath = $ScenarioInput
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

function Invoke-BatterySuite {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Region,
        [Parameter(Mandatory = $true)]
        [string]$BatteryOutput
    )

    $Arguments = @{
        RomPath = $RomPath
        OutputDirectory = $BatteryOutput
        Region = $Region
        TimeoutSeconds = $TimeoutSeconds
        StrictHardware = $StrictHardware
        FullDebug = $FullDebug
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

    & $BatteryRunner @Arguments
}

function Write-RegressionManifest {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('PASS', 'FAIL')]
        [string]$Result,
        [AllowEmptyString()]
        [string]$Failure
    )

    $Lines = [System.Collections.Generic.List[string]]::new()
    $Lines.Add(
        'Pokemon Yellow NES - Mesen 2.2.1 complete regression suite'
    ) | Out-Null
    $Lines.Add("Started UTC: $($StartedUtc.ToString('o'))") | Out-Null
    $Lines.Add(
        "Finished UTC: $([DateTime]::UtcNow.ToString('o'))"
    ) | Out-Null
    $Lines.Add("Run directory: $RunDirectory") | Out-Null
    $Lines.Add("ROM: $RomPath") | Out-Null
    $Lines.Add("ROM SHA-256: $(Get-LowerSha256 -Path $RomPath)") | Out-Null
    $Lines.Add("Final IPS: $FinalIpsPath") | Out-Null
    $Lines.Add(
        "Final IPS SHA-256: $(Get-LowerSha256 -Path $FinalIpsPath)"
    ) | Out-Null
    $Lines.Add("Chinese reference ROM: $ChineseRomPath") | Out-Null
    $Lines.Add(
        "Chinese reference SHA-256: " +
        (Get-LowerSha256 -Path $ChineseRomPath)
    ) | Out-Null
    $Lines.Add("Canonical CSV: $CanonicalCsvPath") | Out-Null
    $Lines.Add(
        "Canonical CSV SHA-256: " +
        (Get-LowerSha256 -Path $CanonicalCsvPath)
    ) | Out-Null
    $Lines.Add(
        "Python test modules discovered: $($PythonTestFiles.Count)"
    ) | Out-Null
    $Lines.Add("Expected Mesen SHA-256: $ExpectedMesenSha256") | Out-Null
    $Lines.Add(
        "Mesen path: $(if ($MesenPath) { $MesenPath } else { '<runner discovery>' })"
    ) | Out-Null
    $Lines.Add("Timeout seconds per scenario: $TimeoutSeconds") | Out-Null
    $Lines.Add("Strict hardware profile: $StrictHardware") | Out-Null
    $Lines.Add("Full NES debug-stop profile: $FullDebug") | Out-Null
    $Lines.Add("Skip battery: $([bool]$SkipBattery)") | Out-Null
    $Lines.Add(
        "Bootstrap completion gate: $([bool]$BootstrapCompletionGate)"
    ) | Out-Null
    $Lines.Add("Campaign prototype by region: True") | Out-Null
    $Lines.Add(
        "Experimental Route 1/Viridian gallery: " +
        "$([bool]$IncludeExperimentalRoute1Viridian)"
    ) | Out-Null
    $Lines.Add(
        "Route 1 qualification: opt-in because its FM3 stream was frozen " +
        "under NTSC; historical identical runs also exposed transient " +
        "blank screenshots and route-alignment timeouts."
    ) | Out-Null
    if ($IncludeExperimentalRoute1Viridian) {
        $Lines.Add("Route 1 input: $Route1InputPath") | Out-Null
        $Lines.Add(
            "Route 1 input SHA-256: " +
            (Get-LowerSha256 -Path $Route1InputPath)
        ) | Out-Null
    }
    $Lines.Add("Static output: $StaticOutput") | Out-Null
    $Lines.Add("Mesen output: $MesenOutput") | Out-Null
    $Lines.Add(
        "Executed steps: $($script:RegressionStepResults.Count)"
    ) | Out-Null
    for (
        $Index = 0;
        $Index -lt $script:RegressionStepResults.Count;
        $Index++
    ) {
        $Step = $script:RegressionStepResults[$Index]
        $Line = (
            "Step {0:D2}: {1} | {2} | {3}s" -f
            ($Index + 1),
            $Step.Result,
            $Step.Name,
            $Step.Seconds
        )
        if ($Step.Detail) {
            $Line += " | $($Step.Detail)"
        }
        $Lines.Add($Line) | Out-Null
    }
    if ($Failure) {
        $Lines.Add("Failure: $Failure") | Out-Null
    }
    $Lines.Add("Result: $Result") | Out-Null
    $Lines | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

$script:LinuxRomRoot = ''
$script:LinuxRomPath = ''
$script:LinuxFinalIpsPath = ''
$script:LinuxTranslationBaseRomPath = ''
$script:LinuxCanonicalEnglishRomPath = ''
$script:LinuxEnglishIpsPath = ''
$script:LinuxTranslationScriptPath = ''
$script:LinuxCanonicalCsvPath = ''
$script:LinuxFixedOverflowPath = ''
$script:LinuxChineseRomPath = ''
$script:LinuxAuditOutput = ''
$script:LinuxAsciiCoverageOutput = ''
$script:LinuxGlyphCoverageOutput = ''
$script:LinuxDialogueLayoutOutput = ''
$script:LinuxPokedexLayoutOutput = ''
$script:LinuxFinalPokedexRuntimeOutput = ''
$SuiteResult = 'FAIL'
$FailureMessage = ''
$CapturedError = $null
try {
    Invoke-RegressionStep -Name 'setup/wsl-paths' -Action {
        $script:LinuxRomRoot = Convert-ToWslPath -WindowsPath $RomRoot
        $script:LinuxRomPath = Convert-ToWslPath -WindowsPath $RomPath
        $script:LinuxFinalIpsPath = Convert-ToWslPath `
            -WindowsPath $FinalIpsPath
        $script:LinuxTranslationBaseRomPath = Convert-ToWslPath `
            -WindowsPath $TranslationBaseRomPath
        $script:LinuxCanonicalEnglishRomPath = Convert-ToWslPath `
            -WindowsPath $CanonicalEnglishRomPath
        $script:LinuxEnglishIpsPath = Convert-ToWslPath `
            -WindowsPath $EnglishIpsPath
        $script:LinuxTranslationScriptPath = Convert-ToWslPath `
            -WindowsPath $TranslationScriptPath
        $script:LinuxCanonicalCsvPath = Convert-ToWslPath `
            -WindowsPath $CanonicalCsvPath
        $script:LinuxFixedOverflowPath = Convert-ToWslPath `
            -WindowsPath $FixedOverflowPath
        $script:LinuxChineseRomPath = Convert-ToWslPath `
            -WindowsPath $ChineseRomPath
        $script:LinuxAuditOutput = Convert-ToWslPath -WindowsPath (
            Join-Path $StaticOutput 'audit_qualite_ambitieux.csv'
        )
        $script:LinuxAsciiCoverageOutput = Convert-ToWslPath -WindowsPath (
            Join-Path $StaticOutput 'translation_ascii_coverage.csv'
        )
        $script:LinuxGlyphCoverageOutput = Convert-ToWslPath -WindowsPath (
            Join-Path $StaticOutput 'translation_glyph_records.csv'
        )
        $script:LinuxDialogueLayoutOutput = Convert-ToWslPath -WindowsPath (
            Join-Path $StaticOutput 'dialogue_layout_validation.json'
        )
        $script:LinuxPokedexLayoutOutput = Convert-ToWslPath -WindowsPath (
            Join-Path $StaticOutput 'pokedex_layout_validation.json'
        )
        $script:LinuxFinalPokedexRuntimeOutput = Convert-ToWslPath `
            -WindowsPath (
                Join-Path `
                    $StaticOutput `
                    'final_pokedex_runtime_validation.json'
            )
    }
    Invoke-RegressionStep -Name 'static/provenance-english-ips' -Action {
        Invoke-WslPython `
            -Arguments @(
                'rom_traduction_assistant.py',
                'check',
                '--chinese-rom',
                $script:LinuxChineseRomPath,
                '--english-ips',
                $script:LinuxEnglishIpsPath,
                '--english-rom',
                $script:LinuxCanonicalEnglishRomPath
            ) `
            -LogPath (Join-Path $StaticOutput '01-provenance.log')
    }
    Invoke-RegressionStep -Name 'static/final-ips-roundtrip' -Action {
        Invoke-WslPython `
            -Arguments @(
                'rom_traduction_assistant.py',
                'check-ips',
                '--base-rom',
                $script:LinuxCanonicalEnglishRomPath,
                '--ips',
                $script:LinuxFinalIpsPath,
                '--target-rom',
                $script:LinuxRomPath
            ) `
            -LogPath (Join-Path $StaticOutput '02-check-ips.log')
    }
    Invoke-RegressionStep -Name 'static/audit-quality-rule-tests' -Action {
        Invoke-WslPython `
            -Arguments @('tools/test_audit_quality_ambitious.py') `
            -LogPath (Join-Path $StaticOutput '03-audit-tests.log')
    }
    Invoke-RegressionStep -Name 'static/graphics-rule-tests' -Action {
        Invoke-WslPython `
            -Arguments @('tools/test_title_screen_tools.py') `
            -LogPath (Join-Path $StaticOutput '04-graphics-tests.log')
    }
    Invoke-RegressionStep -Name 'static/full-python-test-suite' -Action {
        Invoke-WslPython `
            -Arguments @(
                '-m',
                'unittest',
                'discover',
                '-s',
                'tools',
                '-p',
                'test_*.py',
                '-v'
            ) `
            -LogPath (
                Join-Path $StaticOutput '04a-full-python-test-suite.log'
            ) `
            -BootstrapCompletionGateEnvironment:$BootstrapCompletionGate
    }
    Invoke-RegressionStep -Name 'static/dialogue-layout-validation' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/validate_dialogue_layout.py',
                '--script',
                $script:LinuxTranslationScriptPath,
                '--output',
                $script:LinuxDialogueLayoutOutput
            ) `
            -LogPath (
                Join-Path $StaticOutput '04b-dialogue-layout-validation.log'
            )
    }
    Invoke-RegressionStep -Name 'static/pokedex-layout-validation' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/validate_pokedex_layout.py',
                '--script',
                $script:LinuxTranslationScriptPath,
                '--rom',
                $script:LinuxTranslationBaseRomPath,
                '--output',
                $script:LinuxPokedexLayoutOutput
            ) `
            -LogPath (
                Join-Path $StaticOutput '04c-pokedex-layout-validation.log'
            )
    }
    Invoke-RegressionStep `
        -Name 'static/final-pokedex-runtime-validation' `
        -Action {
            Invoke-WslPython `
                -Arguments @(
                    'tools/validate_final_pokedex_runtime.py',
                    '--rom',
                    $script:LinuxRomPath,
                    '--script',
                    $script:LinuxTranslationScriptPath,
                    '--pointer-rom',
                    $script:LinuxTranslationBaseRomPath,
                    '--output',
                    $script:LinuxFinalPokedexRuntimeOutput
                ) `
                -LogPath (
                    Join-Path `
                        $StaticOutput `
                        '04d-final-pokedex-runtime-validation.log'
                )
        }
    Invoke-RegressionStep -Name 'static/audit-quality' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/audit_quality_ambitious.py',
                '--csv',
                $script:LinuxCanonicalCsvPath,
                '--output',
                $script:LinuxAuditOutput,
                '--fail-on-high'
            ) `
            -LogPath (Join-Path $StaticOutput '05-audit-quality.log')
    }
    Invoke-RegressionStep -Name 'static/mapper163-contract' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/validate_mapper163.py',
                '--rom',
                $script:LinuxRomPath,
                '--base-rom',
                $script:LinuxTranslationBaseRomPath,
                '--title-logo',
                'english',
                '--title-credits-mode',
                'shared'
            ) `
            -LogPath (Join-Path $StaticOutput '06-mapper163.log')
    }
    Invoke-RegressionStep -Name 'static/repacked-pointers' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/validate_repacked.py',
                '--rom',
                $script:LinuxRomPath,
                '--csv',
                $script:LinuxCanonicalCsvPath,
                '--input-rom',
                $script:LinuxTranslationBaseRomPath,
                '--fixed-overflow',
                $script:LinuxFixedOverflowPath
            ) `
            -LogPath (Join-Path $StaticOutput '07-repacked.log')
    }
    Invoke-RegressionStep -Name 'static/repacked-allocator-tests' -Action {
        Invoke-WslPython `
            -Arguments @('tools/test_repacked_allocator.py') `
            -LogPath (
                Join-Path $StaticOutput '08-repacked-allocator-tests.log'
            )
    }
    Invoke-RegressionStep -Name 'static/repacked-safety-tests' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/test_repacked_safety.py',
                '--final-rom',
                $script:LinuxRomPath
            ) `
            -LogPath (
                Join-Path $StaticOutput '09-repacked-safety-tests.log'
            )
    }
    Invoke-RegressionStep -Name 'static/translation-coverage-tests' -Action {
        Invoke-WslPython `
            -Arguments @('tools/test_translation_coverage.py') `
            -LogPath (
                Join-Path $StaticOutput '10-translation-coverage-tests.log'
            )
    }
    Invoke-RegressionStep -Name 'static/translation-coverage' -Action {
        Invoke-WslPython `
            -Arguments @(
                'tools/audit_translation_coverage.py',
                '--rom',
                $script:LinuxRomPath,
                '--csv',
                $script:LinuxCanonicalCsvPath,
                '--english-rom',
                $script:LinuxTranslationBaseRomPath,
                '--chinese-rom',
                $script:LinuxChineseRomPath,
                '--ascii-report',
                $script:LinuxAsciiCoverageOutput,
                '--glyph-report',
                $script:LinuxGlyphCoverageOutput
            ) `
            -LogPath (
                Join-Path $StaticOutput '11-translation-coverage.log'
            )
    }

    Invoke-RegressionStep -Name 'mesen/auto-db-final-expected-ntsc' -Action {
        Invoke-MesenScenario `
            -ScenarioRom $RomPath `
            -ScriptPath $BootProbe `
            -ScenarioOutput (
                Join-Path $MesenOutput 'auto-db-final-expected-ntsc'
            ) `
            -Region 'Auto' `
            -ExpectedRegion 'Ntsc' `
            -ExpectedMarker 'POKEMON_MESEN_PASS' `
            -EnableGameDatabase
    }
    Invoke-RegressionStep -Name 'mesen/auto-db-chinese-expected-dendy' -Action {
        Invoke-MesenScenario `
            -ScenarioRom $ChineseRomPath `
            -ScriptPath $BootProbe `
            -ScenarioOutput (
                Join-Path $MesenOutput 'auto-db-chinese-expected-dendy'
            ) `
            -Region 'Auto' `
            -ExpectedRegion 'Dendy' `
            -ExpectedMarker 'POKEMON_MESEN_PASS' `
            -EnableGameDatabase
    }

    foreach ($TestRegion in @('Dendy', 'Ntsc', 'Pal')) {
        $RegionDirectory = Join-Path `
            $MesenOutput `
            ($TestRegion.ToLowerInvariant())
        Invoke-RegressionStep -Name "mesen/$TestRegion/boot" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $BootProbe `
                -ScenarioOutput (Join-Path $RegionDirectory '01-boot') `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'POKEMON_MESEN_PASS'
        }
        Invoke-RegressionStep -Name "mesen/$TestRegion/runtime-passive" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $RuntimeProbe `
                -ScenarioOutput (Join-Path $RegionDirectory '02-runtime-passive') `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'MAPPER163_PASS'
        }
        Invoke-RegressionStep -Name "mesen/$TestRegion/intro-broad" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $IntroProbe `
                -ScenarioOutput (Join-Path $RegionDirectory '03-intro-broad') `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'POKEMON_INTRO_PASS'
        }
        Invoke-RegressionStep -Name "mesen/$TestRegion/intro-prompts" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $PromptProbe `
                -ScenarioOutput (Join-Path $RegionDirectory '04-intro-prompts') `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'POKEMON_INTRO_PROMPTS_PASS'
        }
        Invoke-RegressionStep `
            -Name "mesen/$TestRegion/french-charset-exhaustive" `
            -Action {
                Invoke-MesenScenario `
                    -ScenarioRom $RomPath `
                    -ScriptPath $AccentProbe `
                    -ScenarioOutput (
                        Join-Path `
                            $RegionDirectory `
                            '04a-french-charset-exhaustive'
                    ) `
                    -Region $TestRegion `
                    -ExpectedRegion $TestRegion `
                    -ExpectedMarker `
                        'POKEMON_FRENCH_CHARSET_EXHAUSTIVE_PASS'
            }
        Invoke-RegressionStep -Name "mesen/$TestRegion/chr-same-frame" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $ChrExportProbe `
                -ScenarioOutput (Join-Path $RegionDirectory '05-chr-same-frame') `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'POKEMON_CHR_EXPORT_PASS'
        }
        Invoke-RegressionStep -Name "mesen/$TestRegion/player-menu-fr" -Action {
            Invoke-MesenScenario `
                -ScenarioRom $RomPath `
                -ScriptPath $PlayerMenuProbe `
                -ScenarioOutput (
                    Join-Path $RegionDirectory '06-player-menu-fr'
                ) `
                -Region $TestRegion `
                -ExpectedRegion $TestRegion `
                -ExpectedMarker 'POKEMON_PLAYER_MENU_FR_PASS'
        }
        Invoke-RegressionStep `
            -Name "mesen/$TestRegion/campaign-prototype" `
            -Action {
                Invoke-MesenScenario `
                    -ScenarioRom $RomPath `
                    -ScriptPath $CampaignProbe `
                    -ScenarioOutput (
                        Join-Path $RegionDirectory '07-campaign-prototype'
                    ) `
                    -Region $TestRegion `
                    -ExpectedRegion $TestRegion `
                    -ExpectedMarker 'POKEMON_CAMPAIGN_PROTOTYPE_PASS'
            }
        if ($IncludeExperimentalRoute1Viridian) {
            Invoke-RegressionStep `
                -Name "mesen/$TestRegion/route1-viridian-experimental" `
                -Action {
                    Invoke-MesenScenario `
                        -ScenarioRom $RomPath `
                        -ScriptPath $Route1Probe `
                        -ScenarioInput $Route1InputPath `
                        -ScenarioOutput (
                            Join-Path `
                                $RegionDirectory `
                                '08-route1-viridian-experimental'
                        ) `
                        -Region $TestRegion `
                        -ExpectedRegion $TestRegion `
                        -ExpectedMarker `
                            'POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS'
                }
        }
        if (-not $SkipBattery) {
            Invoke-RegressionStep -Name "mesen/$TestRegion/battery" -Action {
                Invoke-BatterySuite `
                    -Region $TestRegion `
                    -BatteryOutput (Join-Path $RegionDirectory '09-battery')
            }
        }
    }
    $SuiteResult = 'PASS'
} catch {
    $CapturedError = $_
    $FailureMessage = Convert-ToSingleLine -Text $_.Exception.Message
} finally {
    Write-RegressionManifest `
        -Result $SuiteResult `
        -Failure $FailureMessage
}

if ($CapturedError) {
    Write-Host "Pokemon mapper 163 regression suite: FAIL"
    Write-Host "Manifest: $ManifestPath"
    throw $CapturedError
}

Write-Host 'Pokemon mapper 163 regression suite: PASS'
Write-Host "Run directory: $RunDirectory"
Write-Host "Manifest: $ManifestPath"
