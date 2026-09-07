[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('Export', 'Verify', 'Diff', 'Roundtrip', 'Compile')]
    [string]$Action = 'Verify',

    [string]$RomPath,
    [string]$IpsBasePath,
    [string]$ManifestPath,
    [string]$PackPath,
    [string]$OutputDirectory,
    [string]$OutRomPath,
    [string]$OutIpsPath,
    [string]$ReportPath,
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..')
)
$PipelinePath = Join-Path $PSScriptRoot 'chr_asset_pipeline.py'
$DefaultSnapshotId = '22210785'
$DefaultSnapshotSha256 = (
    '22210785ca066222b47cb255c5beeeeff7f0276439e57d65ff884c9bc9cd6298'
)
$DefaultSnapshotRomPath = (
    'build\final-readable-dialogues-20260729\release\Pokemon_Jaune_FR.nes'
)

function Resolve-ProjectPath {
    param(
        [AllowEmptyString()]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$DefaultRelativePath
    )

    $Selected = if ($Value) {
        $Value
    } else {
        $DefaultRelativePath
    }
    if ([System.IO.Path]::IsPathRooted($Selected)) {
        return [System.IO.Path]::GetFullPath($Selected)
    }
    return [System.IO.Path]::GetFullPath(
        (Join-Path $RepositoryRoot $Selected)
    )
}

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
}

function Get-FileSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ChrSnapshotBinding {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Rom,
        [Parameter(Mandatory = $true)]
        [string]$Manifest,
        [AllowEmptyString()]
        [string]$PinnedSha256 = ''
    )

    $ManifestObject = Get-Content `
        -LiteralPath $Manifest `
        -Raw `
        -Encoding UTF8 | ConvertFrom-Json
    $ExpectedSha256 = [string]$ManifestObject.source_sha256
    if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "Invalid source_sha256 in manifest: $Manifest"
    }
    $ExpectedSha256 = $ExpectedSha256.ToLowerInvariant()
    $ActualSha256 = Get-FileSha256 -Path $Rom
    if ($ActualSha256 -ne $ExpectedSha256) {
        throw (
            'CHR manifest and ROM do not describe the same snapshot: ' +
            "$ActualSha256 instead of $ExpectedSha256"
        )
    }
    if ($PinnedSha256 -and $ActualSha256 -ne $PinnedSha256) {
        throw (
            "Default CHR snapshot $DefaultSnapshotId has changed: " +
            "$ActualSha256 instead of $PinnedSha256"
        )
    }
}

function Assert-ChrPackBinding {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Rom,
        [Parameter(Mandatory = $true)]
        [string]$Manifest,
        [Parameter(Mandatory = $true)]
        [string]$Pack
    )

    $LockPath = Join-Path $Pack 'pack.lock.json'
    Assert-FileExists -Path $LockPath -Label 'CHR pack lock'
    $Lock = Get-Content `
        -LiteralPath $LockPath `
        -Raw `
        -Encoding UTF8 | ConvertFrom-Json
    $RomSha256 = Get-FileSha256 -Path $Rom
    $ManifestSha256 = Get-FileSha256 -Path $Manifest
    if ([string]$Lock.source_sha256 -ne $RomSha256) {
        throw 'The CHR pack lock does not match the source ROM.'
    }
    if ([string]$Lock.manifest_sha256 -ne $ManifestSha256) {
        throw 'The CHR pack lock does not match the manifest.'
    }
}

function Test-SamePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Left,
        [Parameter(Mandatory = $true)]
        [string]$Right
    )

    return [string]::Equals(
        [System.IO.Path]::GetFullPath($Left),
        [System.IO.Path]::GetFullPath($Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Test-PathInside {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Candidate,
        [Parameter(Mandatory = $true)]
        [string]$Directory
    )

    $CandidateFull = [System.IO.Path]::GetFullPath($Candidate)
    $DirectoryFull = [System.IO.Path]::GetFullPath($Directory)
    $DirectoryPrefix = $DirectoryFull.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    return $CandidateFull.StartsWith(
        $DirectoryPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Assert-SafeOutputPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    foreach ($Protected in @(
        @{ Path = $RomPath; Label = 'the source ROM' },
        @{ Path = $IpsBasePath; Label = 'the IPS base' },
        @{ Path = $ManifestPath; Label = 'the manifest' },
        @{ Path = $PipelinePath; Label = 'the Python pipeline' }
    )) {
        if (Test-SamePath -Left $Path -Right $Protected.Path) {
            throw "$Label cannot overwrite $($Protected.Label): $Path"
        }
    }
    if (Test-PathInside -Candidate $Path -Directory $PackPath) {
        throw "$Label cannot be written inside the pack: $Path"
    }
    if (Test-SamePath -Left $Path -Right $PackPath) {
        throw "$Label cannot replace the pack directory: $Path"
    }
}

function Resolve-PythonRunner {
    if ($PythonPath) {
        $PythonCommand = $null
        if (
            [System.IO.Path]::IsPathRooted($PythonPath) -or
            $PythonPath.Contains('\') -or
            $PythonPath.Contains('/')
        ) {
            $ResolvedPython = Resolve-ProjectPath `
                -Value $PythonPath `
                -DefaultRelativePath $PythonPath
            Assert-FileExists `
                -Path $ResolvedPython `
                -Label 'Python interpreter'
            $PythonCommand = $ResolvedPython
        } else {
            $Command = Get-Command $PythonPath -ErrorAction SilentlyContinue
            if (-not $Command) {
                throw "Python interpreter not found: $PythonPath"
            }
            $PythonCommand = $Command.Source
        }
        return [pscustomobject]@{
            Mode = 'Native'
            Command = $PythonCommand
            Prefix = @()
        }
    }

    foreach ($Candidate in @(
        'python.exe',
        'python3.exe',
        'python',
        'python3'
    )) {
        $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
        if (
            $Command -and
            $Command.Source -and
            $Command.Source -notmatch '[\\/]WindowsApps[\\/]python3?\.exe$'
        ) {
            return [pscustomobject]@{
                Mode = 'Native'
                Command = $Command.Source
                Prefix = @()
            }
        }
    }

    $Launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (
        $Launcher -and
        $Launcher.Source -and
        $Launcher.Source -notmatch '[\\/]WindowsApps[\\/]py\.exe$'
    ) {
        return [pscustomobject]@{
            Mode = 'Native'
            Command = $Launcher.Source
            Prefix = @('-3')
        }
    }

    $Wsl = Get-Command 'wsl.exe' -ErrorAction SilentlyContinue
    if ($Wsl) {
        return [pscustomobject]@{
            Mode = 'Wsl'
            Command = $Wsl.Source
            Prefix = @()
        }
    }

    throw (
        'Python 3 was not found. Install Python, enable WSL, or ' +
        'specify -PythonPath.'
    )
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
        [string]$WindowsPath,
        [Parameter(Mandatory = $true)]
        [string]$WslExecutable
    )

    $Token = [Guid]::NewGuid().ToString('N')
    $TemporaryRoot = [System.IO.Path]::GetTempPath()
    $StdoutPath = Join-Path $TemporaryRoot "chr-wslpath-$Token.stdout.txt"
    $StderrPath = Join-Path $TemporaryRoot "chr-wslpath-$Token.stderr.txt"
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
                "(code $($Process.ExitCode)) : " +
                (Convert-ToSingleLine -Text ($Stderr + ' ' + $Stdout))
            )
        }
        $Result = ($Stdout -split '\r?\n')[0].Trim()
        if (-not $Result) {
            throw "wslpath returned an empty path for: $WindowsPath"
        }
        return $Result
    } finally {
        foreach ($TemporaryPath in @($StdoutPath, $StderrPath)) {
            if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
                [System.IO.File]::Delete($TemporaryPath)
            }
        }
    }
}

function Convert-ArgumentsToWsl {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$WslExecutable
    )

    $PathFlags = @(
        '--manifest',
        '--pack',
        '--rom',
        '--ips-base',
        '--out',
        '--out-rom',
        '--out-ips',
        '--report'
    )
    $Converted = [System.Collections.Generic.List[string]]::new()
    for ($Index = 0; $Index -lt $Arguments.Count; $Index++) {
        $Value = $Arguments[$Index]
        if ($Index -gt 0 -and $PathFlags -contains $Arguments[$Index - 1]) {
            $Value = Convert-ToWslPath `
                -WindowsPath $Value `
                -WslExecutable $WslExecutable
        }
        $Converted.Add($Value)
    }
    return $Converted.ToArray()
}

function Invoke-ChrPipeline {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $Runner = Resolve-PythonRunner
    $PipelineExitCode = $null
    if ($Runner.Mode -eq 'Native') {
        $PrefixArguments = @($Runner.Prefix)
        & $Runner.Command @PrefixArguments $PipelinePath @Arguments
        $PipelineExitCode = $LASTEXITCODE
    } else {
        $LinuxRepositoryRoot = Convert-ToWslPath `
            -WindowsPath $RepositoryRoot `
            -WslExecutable $Runner.Command
        $LinuxPipelinePath = Convert-ToWslPath `
            -WindowsPath $PipelinePath `
            -WslExecutable $Runner.Command
        $LinuxArguments = Convert-ArgumentsToWsl `
            -Arguments $Arguments `
            -WslExecutable $Runner.Command
        $Token = [Guid]::NewGuid().ToString('N')
        $TemporaryRoot = [System.IO.Path]::GetTempPath()
        $StdoutPath = Join-Path `
            $TemporaryRoot `
            "chr-pipeline-$Token.stdout.txt"
        $StderrPath = Join-Path `
            $TemporaryRoot `
            "chr-pipeline-$Token.stderr.txt"
        try {
            $WslArguments = @(
                '--cd',
                $LinuxRepositoryRoot,
                '--exec',
                'python3',
                $LinuxPipelinePath
            ) + @($LinuxArguments)
            $NativeArguments = $WslArguments | ForEach-Object {
                Convert-ToNativeArgument -Argument $_
            }
            $Process = Start-Process `
                -FilePath $Runner.Command `
                -ArgumentList $NativeArguments `
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
            if ($Stdout) {
                Write-Host $Stdout.TrimEnd()
            }
            if ($Stderr) {
                Write-Error `
                    (Convert-ToSingleLine -Text $Stderr) `
                    -ErrorAction Continue
            }
            $PipelineExitCode = $Process.ExitCode
        } finally {
            foreach ($TemporaryPath in @($StdoutPath, $StderrPath)) {
                if (
                    Test-Path `
                        -LiteralPath $TemporaryPath `
                        -PathType Leaf
                ) {
                    [System.IO.File]::Delete($TemporaryPath)
                }
            }
        }
    }
    if ($null -eq $PipelineExitCode -or $PipelineExitCode -ne 0) {
        $ExitLabel = if ($null -eq $PipelineExitCode) {
            'unavailable'
        } else {
            [string]$PipelineExitCode
        }
        throw (
            "The CHR pipeline failed with code $ExitLabel " +
            "during action $Action."
        )
    }
}

$UsesDefaultRom = [string]::IsNullOrWhiteSpace($RomPath)
$UsesDefaultManifest = [string]::IsNullOrWhiteSpace($ManifestPath)
$UsesDefaultPack = [string]::IsNullOrWhiteSpace($PackPath)

$RomPath = Resolve-ProjectPath `
    -Value $RomPath `
    -DefaultRelativePath $DefaultSnapshotRomPath
$IpsBasePath = Resolve-ProjectPath `
    -Value $IpsBasePath `
    -DefaultRelativePath 'yellow.nes'
$ManifestPath = Resolve-ProjectPath `
    -Value $ManifestPath `
    -DefaultRelativePath "graphics\chr_modular\manifest-$DefaultSnapshotId.json"
$PackPath = Resolve-ProjectPath `
    -Value $PackPath `
    -DefaultRelativePath "graphics\chr_modular\pack-$DefaultSnapshotId"
$OutputDirectory = Resolve-ProjectPath `
    -Value $OutputDirectory `
    -DefaultRelativePath "build\chr-modular-$DefaultSnapshotId"

Assert-FileExists -Path $PipelinePath -Label 'Python pipeline'
Assert-FileExists -Path $RomPath -Label 'Source ROM'
Assert-FileExists -Path $ManifestPath -Label 'CHR manifest'
$PinnedSnapshotSha256 = if (
    $UsesDefaultRom -or $UsesDefaultManifest -or $UsesDefaultPack
) {
    $DefaultSnapshotSha256
} else {
    ''
}
Assert-ChrSnapshotBinding `
    -Rom $RomPath `
    -Manifest $ManifestPath `
    -PinnedSha256 $PinnedSnapshotSha256

$Command = $Action.ToLowerInvariant()
$Arguments = [System.Collections.Generic.List[string]]::new()

if ($Action -eq 'Export') {
    if (Test-Path -LiteralPath $PackPath) {
        throw (
            'The pack directory already exists. Export cancelled to preserve ' +
            "edited files: $PackPath"
        )
    }
    $Arguments.Add('export')
    $Arguments.Add('--manifest')
    $Arguments.Add($ManifestPath)
    $Arguments.Add('--rom')
    $Arguments.Add($RomPath)
    $Arguments.Add('--out')
    $Arguments.Add($PackPath)
} else {
    if (-not (Test-Path -LiteralPath $PackPath -PathType Container)) {
        throw (
            "CHR pack not found: $PackPath. " +
            "Run the Export action explicitly first."
        )
    }
    Assert-ChrPackBinding `
        -Rom $RomPath `
        -Manifest $ManifestPath `
        -Pack $PackPath

    [System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
    $Arguments.Add($Command)
    $Arguments.Add('--manifest')
    $Arguments.Add($ManifestPath)
    $Arguments.Add('--pack')
    $Arguments.Add($PackPath)
    $Arguments.Add('--rom')
    $Arguments.Add($RomPath)

    if ($Action -eq 'Compile') {
        Assert-FileExists -Path $IpsBasePath -Label 'IPS base'
        $OutRomPath = Resolve-ProjectPath `
            -Value $OutRomPath `
            -DefaultRelativePath (
                Join-Path $OutputDirectory 'Pokemon_Jaune_FR_CHR_mod.nes'
            )
        $OutIpsPath = Resolve-ProjectPath `
            -Value $OutIpsPath `
            -DefaultRelativePath (
                Join-Path $OutputDirectory 'Pokemon_Jaune_FR_CHR_mod.ips'
            )
        $ReportPath = Resolve-ProjectPath `
            -Value $ReportPath `
            -DefaultRelativePath (
                Join-Path $OutputDirectory 'compile-report.json'
            )

        foreach ($Output in @(
            @{ Path = $OutRomPath; Label = 'The compiled ROM' },
            @{ Path = $OutIpsPath; Label = 'The compiled IPS patch' },
            @{ Path = $ReportPath; Label = 'The compilation report' }
        )) {
            Assert-SafeOutputPath `
                -Path $Output.Path `
                -Label $Output.Label
            [System.IO.Directory]::CreateDirectory(
                (Split-Path -Parent $Output.Path)
            ) | Out-Null
        }
        if (
            (Test-SamePath -Left $OutRomPath -Right $OutIpsPath) -or
            (Test-SamePath -Left $OutRomPath -Right $ReportPath) -or
            (Test-SamePath -Left $OutIpsPath -Right $ReportPath)
        ) {
            throw 'The three compilation outputs must be distinct.'
        }

        $Arguments.Add('--ips-base')
        $Arguments.Add($IpsBasePath)
        $Arguments.Add('--out-rom')
        $Arguments.Add($OutRomPath)
        $Arguments.Add('--out-ips')
        $Arguments.Add($OutIpsPath)
        $Arguments.Add('--report')
        $Arguments.Add($ReportPath)
    } else {
        $DefaultReportName = switch ($Action) {
            'Verify' { 'verify-report.json' }
            'Diff' { 'diff-report.json' }
            'Roundtrip' { 'roundtrip-report.json' }
        }
        $ReportPath = Resolve-ProjectPath `
            -Value $ReportPath `
            -DefaultRelativePath (
                Join-Path $OutputDirectory $DefaultReportName
            )
        Assert-SafeOutputPath `
            -Path $ReportPath `
            -Label "The $Action report"
        [System.IO.Directory]::CreateDirectory(
            (Split-Path -Parent $ReportPath)
        ) | Out-Null

        if ($Action -eq 'Roundtrip') {
            Assert-FileExists -Path $IpsBasePath -Label 'IPS base'
            $Arguments.Add('--ips-base')
            $Arguments.Add($IpsBasePath)
        }
        $Arguments.Add('--report')
        $Arguments.Add($ReportPath)
    }
}

Write-Host "Modular CHR pipeline - $Action"
Write-Host "- Source ROM: $RomPath"
Write-Host "- Manifest: $ManifestPath"
Write-Host "- Pack        : $PackPath"
if ($Action -ne 'Export') {
    Write-Host "- Outputs: $OutputDirectory"
}

Invoke-ChrPipeline -Arguments $Arguments.ToArray()

Write-Host "Action $Action completed successfully."
if ($Action -eq 'Compile') {
    Write-Host "- Compiled ROM: $OutRomPath"
    Write-Host "- Patch IPS     : $OutIpsPath"
    Write-Host "- Report: $ReportPath"
} elseif ($Action -ne 'Export') {
    Write-Host "- Report: $ReportPath"
}
