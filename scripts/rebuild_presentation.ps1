$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$runtimeNode = Join-Path $runtimeRoot 'node\bin\node.exe'
$runtimeModules = Join-Path $runtimeRoot 'node\node_modules'
if (-not (Test-Path -LiteralPath $runtimeNode)) { throw 'Bundled presentation runtime unavailable. Use the supplied editable PPTX or Presentation.html.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'node_modules'))) {
    New-Item -ItemType Junction -Path (Join-Path $projectRoot 'node_modules') -Target $runtimeModules | Out-Null
}
& $runtimeNode scripts/build_presentation.mjs
if ($LASTEXITCODE -ne 0) { throw 'Slide build or validation failed.' }
