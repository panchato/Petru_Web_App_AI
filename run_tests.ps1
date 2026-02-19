param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TestArgs
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$testRoot = Join-Path $scriptRoot "tests"
$runnerDb = Join-Path $testRoot "test_runner_default.sqlite3"
$appDataRoot = Join-Path $testRoot ".appdata"

New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
New-Item -ItemType Directory -Path $appDataRoot -Force | Out-Null

$runnerDbUri = "sqlite:///" + ($runnerDb -replace "\\", "/")

$env:FLASK_ENV = "testing"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:DATABASE_URL = $runnerDbUri
$env:SECRET_KEY = "test-secret-key"
$env:PETRU_APPDATA_DIR = $appDataRoot

if (-not $TestArgs -or $TestArgs.Count -eq 0) {
    $TestArgs = @("discover", "-s", "tests", "-p", "test_*.py", "-v")
}

& ".\windows_venv\Scripts\python.exe" -m unittest @TestArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}

Write-Output "Tests executed with isolated test environment."
