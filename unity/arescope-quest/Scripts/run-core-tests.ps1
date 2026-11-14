param([string]$CscPath)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $CscPath) {
    $candidate = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if (Test-Path -LiteralPath $candidate) { $CscPath = $candidate }
    else { $CscPath = (Get-Command csc.exe -ErrorAction Stop).Source }
}
$outputDir = Join-Path $PSScriptRoot '.verification'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$outputFile = Join-Path $outputDir 'Arescope.Core.Tests.exe'
$sources = @((Join-Path $projectRoot 'Assets/Arescope/Math/CoreMath.cs'))
$sources += Get-ChildItem -LiteralPath (Join-Path $projectRoot 'Assets/Tests') -Filter '*.cs' -File | ForEach-Object FullName
& $CscPath /nologo /target:exe /optimize+ /define:ARESCOPE_STANDALONE "/out:$outputFile" @sources
if ($LASTEXITCODE -ne 0) { throw 'Core test compilation failed' }
& $outputFile
if ($LASTEXITCODE -ne 0) { throw 'Core tests failed' }
