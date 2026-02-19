$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot 'windows_venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment Python not found at $venvPython"
    exit 1
}

Set-Location $projectRoot
& $venvPython 'run.py'
