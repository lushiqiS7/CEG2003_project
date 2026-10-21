param([switch]$ForceImport)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Create .venv and install requirements.txt first. See README.md.' }
if ($ForceImport) { & $projectPython run_project.py --force-import } else { & $projectPython run_project.py }
if ($LASTEXITCODE -ne 0) { throw 'Analysis failed.' }
& $projectPython -m pytest -q --junitxml=results/test_results.xml
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $projectPython scripts/build_report.py
if ($LASTEXITCODE -ne 0) { throw 'Report build failed.' }
& $projectPython scripts/build_support_materials.py
if ($LASTEXITCODE -ne 0) { throw 'Support material build failed.' }
& $projectPython scripts/package_project.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
Write-Output 'Analysis, checks, PDF report and code package complete. Slide rebuild instructions are in docs/BUILD_PROCESS.md.'
