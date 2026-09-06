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
        throw "$Label introuvable : $Path"
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
        throw "source_sha256 invalide dans le manifeste : $Manifest"
    }
    $ExpectedSha256 = $ExpectedSha256.ToLowerInvariant()
    $ActualSha256 = Get-FileSha256 -Path $Rom
    if ($ActualSha256 -ne $ExpectedSha256) {
        throw (
            'Le manifeste CHR et la ROM ne forment pas le meme snapshot : ' +
            "$ActualSha256 au lieu de $ExpectedSha256"
        )
    }
    if ($PinnedSha256 -and $ActualSha256 -ne $PinnedSha256) {
        throw (
            "Le snapshot CHR par defaut $DefaultSnapshotId a derive : " +
            "$ActualSha256 au lieu de $PinnedSha256"
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
    Assert-FileExists -Path $LockPath -Label 'Lock du pack CHR'
    $Lock = Get-Content `
        -LiteralPath $LockPath `
        -Raw `
        -Encoding UTF8 | ConvertFrom-Json
    $RomSha256 = Get-FileSha256 -Path $Rom
    $ManifestSha256 = Get-FileSha256 -Path $Manifest
    if ([string]$Lock.source_sha256 -ne $RomSha256) {
        throw 'Le lock du pack CHR ne correspond pas a la ROM source.'
    }
    if ([string]$Lock.manifest_sha256 -ne $ManifestSha256) {
        throw 'Le lock du pack CHR ne correspond pas au manifeste.'
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
        @{ Path = $RomPath; Label = 'la ROM source' },
        @{ Path = $IpsBasePath; Label = 'la base IPS' },
        @{ Path = $ManifestPath; Label = 'le manifeste' },
        @{ Path = $PipelinePath; Label = 'le pipeline Python' }
    )) {
        if (Test-SamePath -Left $Path -Right $Protected.Path) {
            throw "$Label ne peut pas ecraser $($Protected.Label) : $Path"
        }
    }
    if (Test-PathInside -Candidate $Path -Directory $PackPath) {
        throw "$Label ne peut pas etre ecrit dans le pack : $Path"
    }
    if (Test-SamePath -Left $Path -Right $PackPath) {
        throw "$Label ne peut pas remplacer le dossier du pack : $Path"
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
                -Label 'Interpreteur Python'
            $PythonCommand = $ResolvedPython
        } else {
            $Command = Get-Command $PythonPath -ErrorAction SilentlyContinue
            if (-not $Command) {
                throw "Interpreteur Python introuvable : $PythonPath"
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
        'Python 3 est introuvable. Installez Python, activez WSL, ou ' +
        'indiquez -PythonPath.'
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
                "wslpath a echoue pour '$WindowsPath' " +
                "(code $($Process.ExitCode)) : " +
                (Convert-ToSingleLine -Text ($Stderr + ' ' + $Stdout))
            )
        }
        $Result = ($Stdout -split '\r?\n')[0].Trim()
        if (-not $Result) {
            throw "wslpath a renvoye un chemin vide pour : $WindowsPath"
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
            'indisponible'
        } else {
            [string]$PipelineExitCode
        }
        throw (
            "Le pipeline CHR a echoue avec le code $ExitLabel " +
            "pendant l'action $Action."
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

Assert-FileExists -Path $PipelinePath -Label 'Pipeline Python'
Assert-FileExists -Path $RomPath -Label 'ROM source'
Assert-FileExists -Path $ManifestPath -Label 'Manifeste CHR'
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
            'Le dossier du pack existe deja. Export annule pour preserver ' +
            "les fichiers edites : $PackPath"
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
            "Pack CHR introuvable : $PackPath. " +
            "Lancez d'abord explicitement l'action Export."
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
        Assert-FileExists -Path $IpsBasePath -Label 'Base IPS'
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
            @{ Path = $OutRomPath; Label = 'La ROM compilee' },
            @{ Path = $OutIpsPath; Label = 'Le patch IPS compile' },
            @{ Path = $ReportPath; Label = 'Le rapport de compilation' }
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
            throw 'Les trois sorties de compilation doivent etre distinctes.'
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
            -Label "Le rapport $Action"
        [System.IO.Directory]::CreateDirectory(
            (Split-Path -Parent $ReportPath)
        ) | Out-Null

        if ($Action -eq 'Roundtrip') {
            Assert-FileExists -Path $IpsBasePath -Label 'Base IPS'
            $Arguments.Add('--ips-base')
            $Arguments.Add($IpsBasePath)
        }
        $Arguments.Add('--report')
        $Arguments.Add($ReportPath)
    }
}

Write-Host "Pipeline CHR modulaire - $Action"
Write-Host "- ROM source : $RomPath"
Write-Host "- Manifeste  : $ManifestPath"
Write-Host "- Pack        : $PackPath"
if ($Action -ne 'Export') {
    Write-Host "- Sorties     : $OutputDirectory"
}

Invoke-ChrPipeline -Arguments $Arguments.ToArray()

Write-Host "Action $Action terminee avec succes."
if ($Action -eq 'Compile') {
    Write-Host "- ROM compilee : $OutRomPath"
    Write-Host "- Patch IPS     : $OutIpsPath"
    Write-Host "- Rapport       : $ReportPath"
} elseif ($Action -ne 'Export') {
    Write-Host "- Rapport       : $ReportPath"
}
