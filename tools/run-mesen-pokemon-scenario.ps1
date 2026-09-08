param(
    [Parameter(Mandatory = $true)]
    [string]$RomPath,
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$InputPath,
    [ValidateSet('Auto', 'Ntsc', 'Pal', 'Dendy')]
    [string]$Region = 'Ntsc',
    [string]$MesenPath,
    [string]$SettingsPath,
    [int]$TimeoutSeconds = 60,
    [string]$ExpectedMarker = 'POKEMON_MESEN_PASS',
    [switch]$StrictHardware,
    [switch]$FullDebug,
    [bool]$PortableIsolation = $true,
    [string]$PortableMesenDirectory,
    [string]$SharedIsolationDirectory,
    [switch]$EnableGameDatabase,
    [string]$ExpectedEffectiveRegion = '',
    [string]$ExpectedMesenSha256 =
        '8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7'
)

$ErrorActionPreference = 'Stop'
$RomRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent $RomRoot
$SharedMesenDirectory = Join-Path $WorkspaceRoot 'mesen\portable-2.2.1'

function Get-LowerSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    return (
        Get-FileHash -LiteralPath $Path -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

function Get-LowerSha256OrMissing {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return '<missing>'
    }
    try {
        return Get-LowerSha256 -Path $Path
    } catch {
        return '<unreadable>'
    }
}

function Convert-ToSingleLine {
    param(
        [AllowEmptyString()]
        [string]$Text
    )
    return (($Text -replace '\r?\n', ' ') -replace '\s+', ' ').Trim()
}

function Get-LocalLuaDependencyPaths {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootScriptPath
    )

    $RootScriptPath = [System.IO.Path]::GetFullPath($RootScriptPath)
    $Pending = [System.Collections.Generic.Queue[string]]::new()
    $Seen = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    $Dependencies = [System.Collections.Generic.List[string]]::new()
    $DependencyPattern = [regex]::new(
        '(?:loadModule|dofile|require)\s*\(\s*["'']' +
        '(?<path>[^"'']+\.lua)["'']\s*\)',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $Pending.Enqueue($RootScriptPath)
    $Seen.Add($RootScriptPath) | Out-Null
    while ($Pending.Count -gt 0) {
        $CurrentPath = $Pending.Dequeue()
        $CurrentSource = [System.IO.File]::ReadAllText($CurrentPath)
        foreach ($Match in $DependencyPattern.Matches($CurrentSource)) {
            $Reference = $Match.Groups['path'].Value
            $ResolvedPath = if (
                [System.IO.Path]::IsPathRooted($Reference)
            ) {
                [System.IO.Path]::GetFullPath($Reference)
            } else {
                [System.IO.Path]::GetFullPath(
                    (Join-Path `
                        (Split-Path -Parent $CurrentPath) `
                        $Reference)
                )
            }
            if (-not (
                Test-Path -LiteralPath $ResolvedPath -PathType Leaf
            )) {
                throw (
                    "Local Lua dependency not found: $Reference " +
                    "(referenced by $CurrentPath)"
                )
            }
            if ($Seen.Add($ResolvedPath)) {
                $Dependencies.Add($ResolvedPath) | Out-Null
                $Pending.Enqueue($ResolvedPath)
            }
        }
    }
    return @($Dependencies | Sort-Object)
}

if (-not $MesenPath) {
    $MesenPath = Join-Path $SharedMesenDirectory 'Mesen.exe'
}
if (-not $SettingsPath) {
    $SharedSettingsPath = Join-Path $SharedMesenDirectory 'settings.json'
    if (Test-Path -LiteralPath $SharedSettingsPath -PathType Leaf) {
        $SettingsPath = $SharedSettingsPath
    } else {
        $MyDocuments = [Environment]::GetFolderPath(
            [Environment+SpecialFolder]::MyDocuments
        )
        $SettingsPath = Join-Path $MyDocuments 'Mesen2\settings.json'
    }
}

$RomPath = [System.IO.Path]::GetFullPath($RomPath)
$ScriptPath = [System.IO.Path]::GetFullPath($ScriptPath)
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$InputPath = if ($InputPath) {
    [System.IO.Path]::GetFullPath($InputPath)
} else {
    ''
}
$MesenPath = if ($MesenPath) {
    [System.IO.Path]::GetFullPath($MesenPath)
} else {
    ''
}
$SettingsPath = [System.IO.Path]::GetFullPath($SettingsPath)
if ($SharedIsolationDirectory) {
    $SharedIsolationDirectory = [System.IO.Path]::GetFullPath(
        $SharedIsolationDirectory
    )
}

foreach ($Path in @($RomPath, $ScriptPath, $MesenPath, $SettingsPath)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}
if ($InputPath -and
    -not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
    throw "Input file not found: $InputPath"
}
if ($TimeoutSeconds -lt 5) {
    throw 'TimeoutSeconds must be at least 5.'
}

$SourceMesenPath = $MesenPath
$TemplateSettingsPath = $SettingsPath
$SourceMesenHash = (
    Get-FileHash -LiteralPath $SourceMesenPath -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($ExpectedMesenSha256 -and
    $SourceMesenHash -ne $ExpectedMesenSha256.ToLowerInvariant()) {
    throw (
        "Mesen SHA-256 mismatch: expected $ExpectedMesenSha256, " +
        "got $SourceMesenHash"
    )
}
if ($PortableIsolation) {
    if (-not $PortableMesenDirectory) {
        $PortableMesenDirectory = $SharedMesenDirectory
    }
    $PortableMesenDirectory = [System.IO.Path]::GetFullPath(
        $PortableMesenDirectory
    )
    [System.IO.Directory]::CreateDirectory($PortableMesenDirectory) | Out-Null
    $PortableExecutable = Join-Path $PortableMesenDirectory 'Mesen.exe'
    $PortableSettings = Join-Path $PortableMesenDirectory 'settings.json'
    if (-not (Test-Path -LiteralPath $PortableExecutable -PathType Leaf)) {
        [System.IO.File]::Copy(
            $SourceMesenPath,
            $PortableExecutable,
            $false
        )
    }
    $PortableMesenHash = (
        Get-FileHash -LiteralPath $PortableExecutable -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($PortableMesenHash -ne $SourceMesenHash) {
        throw (
            "Portable Mesen binary differs from source: " +
            "$SourceMesenHash -> $PortableMesenHash"
        )
    }
    [System.IO.File]::WriteAllBytes(
        $PortableSettings,
        [System.IO.File]::ReadAllBytes($TemplateSettingsPath)
    )
    $MesenPath = $PortableExecutable
    $SettingsPath = $PortableSettings
}

$Header = [System.IO.File]::ReadAllBytes($RomPath)[0..15]
if ([System.Text.Encoding]::ASCII.GetString($Header, 0, 3) -ne 'NES' -or
    $Header[3] -ne 0x1A) {
    throw "Not an iNES ROM: $RomPath"
}
$Mapper = (($Header[6] -shr 4) -bor ($Header[7] -band 0xF0))
$PrgBytes = [int64]$Header[4] * 16384
$ChrBytes = [int64]$Header[5] * 8192
if ($Mapper -ne 163) {
    throw "This runner is for mapper 163, ROM header reports mapper $Mapper."
}
if ($PrgBytes -ne 2097152 -or $ChrBytes -ne 0) {
    throw "Unexpected mapper 163 layout: PRG=$PrgBytes CHR=$ChrBytes."
}

$Config = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
if ($Config.Version -ne '2.2.1') {
    throw "Mesen 2.2.1 settings required, found version '$($Config.Version)'."
}

[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$IsolationRoot = if ($SharedIsolationDirectory) {
    $SharedIsolationDirectory
} else {
    Join-Path $OutputDirectory (
        'isolated-' + [Guid]::NewGuid().ToString('N')
    )
}
$IsolationSaveData = Join-Path $IsolationRoot 'save-data'
$IsolationSaveStates = Join-Path $IsolationRoot 'save-states'
[System.IO.Directory]::CreateDirectory($IsolationSaveData) | Out-Null
[System.IO.Directory]::CreateDirectory($IsolationSaveStates) | Out-Null
$StdoutPath = Join-Path $OutputDirectory 'mesen.stdout.txt'
$StderrPath = Join-Path $OutputDirectory 'mesen.stderr.txt'
$ManifestPath = Join-Path $OutputDirectory 'mesen_run_manifest.txt'
$OriginalSettings = [System.IO.File]::ReadAllBytes($SettingsPath)
$SettingsHashBefore = Get-LowerSha256 -Path $SettingsPath
$RomHashBefore = Get-LowerSha256 -Path $RomPath
$InputHashBefore = if ($InputPath) {
    Get-LowerSha256 -Path $InputPath
} else {
    ''
}
$MesenHash = Get-LowerSha256 -Path $MesenPath
$LuaScriptHashBefore = Get-LowerSha256 -Path $ScriptPath
$LuaScriptHashAfter = ''
$LuaModules = @()
$PreviousOutput = $env:POKEMON_YELLOW_MESEN_OUTPUT
$PreviousRom = $env:POKEMON_YELLOW_MESEN_ROM
$PreviousRegion = $env:POKEMON_YELLOW_MESEN_REGION
$PreviousInput = $env:POKEMON_YELLOW_MESEN_INPUT
$StartedUtc = [DateTime]::UtcNow

$FailureMessages = [System.Collections.Generic.List[string]]::new()
$CapturedError = $null
$ProcessExitCode = $null
$Stdout = ''
$Stderr = ''
$Screenshots = @()
$ExpectedMarkerObserved = -not [bool]$ExpectedMarker
$ExpectedRegionObservation = if ($ExpectedEffectiveRegion) {
    'False'
} else {
    'NotRequested'
}

try {
    $LuaModules = @(
        Get-LocalLuaDependencyPaths -RootScriptPath $ScriptPath |
            ForEach-Object {
                [pscustomobject]@{
                    Path = $_
                    HashBefore = Get-LowerSha256 -Path $_
                    HashAfter = ''
                }
            }
    )

    $Config.Nes.Region = $Region
    $Config.Nes.DisableGameDatabase = -not $EnableGameDatabase
    $Config.Nes.RemoveSpriteLimit = $false
    $Config.Nes.AdaptiveSpriteLimit = $false
    $Config.Nes.EnablePalBorders = $true
    if ($StrictHardware) {
        $Config.Nes.EnableOamDecay = $true
        $Config.Nes.EnablePpuOamRowCorruption = $true
        $Config.Nes.EnablePpu2000ScrollGlitch = $true
        $Config.Nes.EnablePpu2006ScrollGlitch = $true
        $Config.Nes.RestrictPpuAccessOnFirstFrame = $true
        $Config.Nes.RandomizeMapperPowerOnState = $true
        $Config.Nes.RandomizeCpuPpuAlignment = $true
        $Config.Nes.RamPowerOnState = 'Random'
    } else {
        $Config.Nes.RandomizeMapperPowerOnState = $false
        $Config.Nes.RandomizeCpuPpuAlignment = $false
        $Config.Nes.RamPowerOnState = 'AllZeros'
    }
    $Config.Preferences.SingleInstance = $false
    $Config.Preferences.AutoLoadPatches = $false
    $Config.Preferences.EnableAutoSaveState = $false
    $Config.Preferences.OverrideSaveDataFolder = $true
    $Config.Preferences.OverrideSaveStateFolder = $true
    $Config.Preferences.SaveDataFolder = $IsolationSaveData
    $Config.Preferences.SaveStateFolder = $IsolationSaveStates
    $Config.Debug.ScriptWindow.AllowIoOsAccess = $true
    $Config.Debug.ScriptWindow.AllowNetworkAccess = $false
    $Config.Debug.ScriptWindow.AutoRestartScriptAfterPowerCycle = $false
    if ($FullDebug) {
        $Config.Debug.Debugger.Nes.BreakOnBrk = $true
        $Config.Debug.Debugger.Nes.BreakOnUnofficialOpCode = $true
        $Config.Debug.Debugger.Nes.BreakOnUnstableOpCode = $true
        $Config.Debug.Debugger.Nes.BreakOnCpuCrash = $true
        $Config.Debug.Debugger.Nes.BreakOnBusConflict = $true
        $Config.Debug.Debugger.Nes.BreakOnDecayedOamRead = $true
        $Config.Debug.Debugger.Nes.BreakOnPpuScrollGlitch = $true
        $Config.Debug.Debugger.Nes.BreakOnExtOutputMode = $true
        $Config.Debug.Debugger.Nes.BreakOnInvalidVramAccess = $true
        $Config.Debug.Debugger.Nes.BreakOnInvalidOamWrite = $true
        $Config.Debug.Debugger.Nes.BreakOnDmaInputRead = $true
        $Config.Debug.Debugger.BreakOnUninitRead = $true
    }
    [System.IO.File]::WriteAllText(
        $SettingsPath,
        ($Config | ConvertTo-Json -Depth 100),
        [System.Text.UTF8Encoding]::new($true)
    )

    $env:POKEMON_YELLOW_MESEN_OUTPUT = $OutputDirectory
    $env:POKEMON_YELLOW_MESEN_ROM = $RomPath
    $env:POKEMON_YELLOW_MESEN_REGION = $Region
    $env:POKEMON_YELLOW_MESEN_INPUT = $InputPath
    $Arguments = @(
        '--testRunner',
        ('--timeout={0}' -f $TimeoutSeconds),
        '--noAudio',
        ('"{0}"' -f $ScriptPath),
        ('"{0}"' -f $RomPath)
    )
    $Process = Start-Process `
        -FilePath $MesenPath `
        -ArgumentList $Arguments `
        -Wait `
        -PassThru `
        -WindowStyle Hidden `
        -WorkingDirectory $OutputDirectory `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath

    $ProcessExitCode = $Process.ExitCode
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
    if ($Stdout) {
        $Stdout.TrimEnd() | Write-Host
    }
    if ($Stderr) {
        $Stderr.TrimEnd() | Write-Host
    }
    $ExpectedMarkerObserved = (
        -not $ExpectedMarker -or
        $Stdout -match [regex]::Escape($ExpectedMarker)
    )
    if ($ExpectedEffectiveRegion) {
        $ExpectedRegionObservation = [string](
            $Stdout -match (
                'region=' +
                [regex]::Escape($ExpectedEffectiveRegion) +
                '(?:\s|$)'
            )
        )
    }
    if ($Process.ExitCode -ne 0) {
        throw "Mesen scenario failed with exit code $($Process.ExitCode)."
    }
    if (-not $ExpectedMarkerObserved) {
        throw "Mesen output is missing expected marker '$ExpectedMarker'."
    }
    if ($ExpectedEffectiveRegion -and
        $ExpectedRegionObservation -ne 'True') {
        throw (
            "Mesen output does not report expected effective region " +
            "'$ExpectedEffectiveRegion'."
        )
    }

    Add-Type -AssemblyName System.Drawing
    $Screenshots = @(Get-ChildItem -LiteralPath $OutputDirectory -File -Filter '*.png')
    foreach ($Png in $Screenshots) {
        $Bitmap = [System.Drawing.Bitmap]::new($Png.FullName)
        try {
            if ($Bitmap.Width -ne 256 -or
                $Bitmap.Height -lt 224 -or
                $Bitmap.Height -gt 240) {
                throw (
                    "Unexpected screenshot size for $($Png.Name): " +
                    "$($Bitmap.Width)x$($Bitmap.Height)"
                )
            }
            $NonBlackSamples = 0
            for ($Y = 0; $Y -lt $Bitmap.Height; $Y += 8) {
                for ($X = 0; $X -lt $Bitmap.Width; $X += 8) {
                    $Pixel = $Bitmap.GetPixel($X, $Y)
                    if (($Pixel.R + $Pixel.G + $Pixel.B) -gt 24) {
                        $NonBlackSamples++
                    }
                }
            }
            if ($NonBlackSamples -lt 4) {
                throw "Screenshot is blank or nearly blank: $($Png.Name)"
            }
        } finally {
            $Bitmap.Dispose()
        }
    }
} catch {
    $CapturedError = $_
    $FailureMessages.Add(
        (Convert-ToSingleLine -Text $_.Exception.Message)
    ) | Out-Null
} finally {
    try {
        [System.IO.File]::WriteAllBytes($SettingsPath, $OriginalSettings)
    } catch {
        if ($null -eq $CapturedError) {
            $CapturedError = $_
        }
        $FailureMessages.Add(
            "Failed to restore Mesen settings: " +
            (Convert-ToSingleLine -Text $_.Exception.Message)
        ) | Out-Null
    }
    try {
        $env:POKEMON_YELLOW_MESEN_OUTPUT = $PreviousOutput
        $env:POKEMON_YELLOW_MESEN_ROM = $PreviousRom
        $env:POKEMON_YELLOW_MESEN_REGION = $PreviousRegion
        $env:POKEMON_YELLOW_MESEN_INPUT = $PreviousInput
    } catch {
        if ($null -eq $CapturedError) {
            $CapturedError = $_
        }
        $FailureMessages.Add(
            "Failed to restore scenario environment: " +
            (Convert-ToSingleLine -Text $_.Exception.Message)
        ) | Out-Null
    }
}

if (-not $Stdout -and (Test-Path -LiteralPath $StdoutPath -PathType Leaf)) {
    $Stdout = Get-Content -LiteralPath $StdoutPath -Raw
}
if (-not $Stderr -and (Test-Path -LiteralPath $StderrPath -PathType Leaf)) {
    $Stderr = Get-Content -LiteralPath $StderrPath -Raw
}
$ExpectedMarkerObserved = (
    -not $ExpectedMarker -or
    $Stdout -match [regex]::Escape($ExpectedMarker)
)
if ($ExpectedEffectiveRegion) {
    $ExpectedRegionObservation = [string](
        $Stdout -match (
            'region=' +
            [regex]::Escape($ExpectedEffectiveRegion) +
            '(?:\s|$)'
        )
    )
}
$StdoutHash = Get-LowerSha256OrMissing -Path $StdoutPath
$StderrHash = Get-LowerSha256OrMissing -Path $StderrPath
$TerminalOutput = ''
$OutputLines = @(
    ($Stdout + "`n" + $Stderr) -split '\r?\n' |
        Where-Object { $_.Trim() }
)
if ($OutputLines.Count -gt 0) {
    $TerminalOutput = Convert-ToSingleLine -Text $OutputLines[-1]
}
$Screenshots = @(
    Get-ChildItem -LiteralPath $OutputDirectory -File -Filter '*.png'
)

$SettingsHashAfter = Get-LowerSha256OrMissing -Path $SettingsPath
$RomHashAfter = Get-LowerSha256OrMissing -Path $RomPath
$InputHashAfter = if ($InputPath) {
    Get-LowerSha256OrMissing -Path $InputPath
} else {
    ''
}
$LuaScriptHashAfter = Get-LowerSha256OrMissing -Path $ScriptPath
foreach ($Module in $LuaModules) {
    $Module.HashAfter = Get-LowerSha256OrMissing -Path $Module.Path
}

if ($SettingsHashAfter -ne $SettingsHashBefore) {
    $FailureMessages.Add(
        "Mesen settings were not restored: " +
        "$SettingsHashBefore -> $SettingsHashAfter"
    ) | Out-Null
}
if ($RomHashAfter -ne $RomHashBefore) {
    $FailureMessages.Add(
        "ROM changed during Mesen scenario: " +
        "$RomHashBefore -> $RomHashAfter"
    ) | Out-Null
}
if ($InputHashAfter -ne $InputHashBefore) {
    $FailureMessages.Add(
        "Scenario input changed during Mesen scenario: " +
        "$InputHashBefore -> $InputHashAfter"
    ) | Out-Null
}
if ($LuaScriptHashAfter -ne $LuaScriptHashBefore) {
    $FailureMessages.Add(
        "Lua scenario changed during Mesen scenario: " +
        "$LuaScriptHashBefore -> $LuaScriptHashAfter"
    ) | Out-Null
}
foreach ($Module in $LuaModules) {
    if ($Module.HashAfter -ne $Module.HashBefore) {
        $FailureMessages.Add(
            "Lua module changed during Mesen scenario: $($Module.Path) " +
            "$($Module.HashBefore) -> $($Module.HashAfter)"
        ) | Out-Null
    }
}

$ScenarioResult = if ($FailureMessages.Count -eq 0) {
    'PASS'
} else {
    'FAIL'
}
$FailureSummary = $FailureMessages -join ' | '
$TimedOut = (
    $ScenarioResult -eq 'FAIL' -and
    ($FailureSummary + ' ' + $Stdout + ' ' + $Stderr) -match
    '(?:timed?\s*out|timeout)'
)

$ManifestLines = [System.Collections.Generic.List[string]]::new()
foreach ($Line in @(
    'Pokemon Yellow NES - Mesen 2.2.1 scenario manifest'
    "Started UTC: $($StartedUtc.ToString('o'))"
    "Finished UTC: $([DateTime]::UtcNow.ToString('o'))"
    "Mesen executable: $MesenPath"
    "Mesen source executable: $SourceMesenPath"
    "Mesen executable SHA-256: $MesenHash"
    "Portable Mesen isolation: $PortableIsolation"
    "Shared isolation directory: $SharedIsolationDirectory"
    "ROM: $RomPath"
    "ROM SHA-256 before: $RomHashBefore"
    "ROM SHA-256 after: $RomHashAfter"
    "iNES mapper: $Mapper"
    "PRG bytes: $PrgBytes"
    "CHR bytes: $ChrBytes (CHR-RAM cartridge)"
    "Region: $Region"
    "Expected effective region: $ExpectedEffectiveRegion"
    "Mesen game database enabled: $([bool]$EnableGameDatabase)"
    "Strict hardware profile: $([bool]$StrictHardware)"
    "Full NES debug-stop profile: $([bool]$FullDebug)"
    "Mesen test-runner timeout seconds: $TimeoutSeconds"
    "Isolated save-data folder: $IsolationSaveData"
    "Isolated save-state folder: $IsolationSaveStates"
    'Automatic patch loading: disabled'
    "Lua scenario: $ScriptPath"
    "Lua scenario SHA-256 before: $LuaScriptHashBefore"
    "Lua scenario SHA-256 after: $LuaScriptHashAfter"
    (
        'Lua local module discovery: recursive literal ' +
        'loadModule/dofile/require .lua calls'
    )
    "Lua local module count: $($LuaModules.Count)"
)) {
    $ManifestLines.Add($Line) | Out-Null
}
for ($Index = 0; $Index -lt $LuaModules.Count; $Index++) {
    $Module = $LuaModules[$Index]
    $Number = $Index + 1
    $ManifestLines.Add(
        "Lua local module $Number path: $($Module.Path)"
    ) | Out-Null
    $ManifestLines.Add(
        "Lua local module $Number SHA-256 before: $($Module.HashBefore)"
    ) | Out-Null
    $ManifestLines.Add(
        "Lua local module $Number SHA-256 after: $($Module.HashAfter)"
    ) | Out-Null
}
foreach ($Line in @(
    "Scenario input: $InputPath"
    "Scenario input SHA-256 before: $InputHashBefore"
    "Scenario input SHA-256 after: $InputHashAfter"
    "Expected marker: $ExpectedMarker"
    "Expected marker observed: $([bool]$ExpectedMarkerObserved)"
    "Expected effective region observed: $ExpectedRegionObservation"
    "Mesen process exit code: $ProcessExitCode"
    "Mesen stdout SHA-256: $StdoutHash"
    "Mesen stderr SHA-256: $StderrHash"
    "Mesen terminal output: $TerminalOutput"
    "Timed out: $([bool]$TimedOut)"
    "Settings SHA-256 before: $SettingsHashBefore"
    "Settings SHA-256 after: $SettingsHashAfter"
    "Screenshots: $($Screenshots.Count)"
)) {
    $ManifestLines.Add($Line) | Out-Null
}
for ($Index = 0; $Index -lt $FailureMessages.Count; $Index++) {
    $ManifestLines.Add(
        "Failure $($Index + 1): $($FailureMessages[$Index])"
    ) | Out-Null
}
$ManifestLines.Add("Result: $ScenarioResult") | Out-Null
$ManifestLines |
    Set-Content -LiteralPath $ManifestPath -Encoding UTF8

Write-Host (
    "Mesen 2.2.1 mapper 163 scenario: $ScenarioResult ($Region)"
)
Write-Host "Manifest: $ManifestPath"
if ($ScenarioResult -ne 'PASS') {
    if ($null -ne $CapturedError) {
        throw $CapturedError
    }
    throw $FailureSummary
}
