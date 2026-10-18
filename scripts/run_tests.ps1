<#
.SYNOPSIS
  Run every automated check and print an honest summary (a failing or skipped stage is never hidden).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
  powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1 -SkipFrontend
#>
param([switch]$SkipBackend, [switch]$SkipFrontend)
. "$PSScriptRoot\_common.ps1"
$ErrorActionPreference = "Continue"
$results = [ordered]@{}

function Run-Stage([string]$Name, [scriptblock]$Block) {
    Write-Step $Name
    & $Block
    $results[$Name] = if ($LASTEXITCODE -eq 0) { "PASSED" } else { "FAILED (exit $LASTEXITCODE)" }
}

if (-not $SkipBackend) {
    $py = Get-VenvPython
    & $py -c "import pytest" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "pytest missing - installing dev requirements"; & $py -m pip install --disable-pip-version-check -q -r requirements-dev.txt }
    Run-Stage "Backend: pytest (unit + integration)" { & $py -m pytest -q -p no:cacheprovider }
}

if (-not $SkipFrontend) {
    if (-not (Test-Command "npm")) { $results["Frontend"] = "NOT RUN (Node.js/npm not found)" }
    else {
        Push-Location frontend
        if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund | Out-Null }
        Run-Stage "Frontend: TypeScript"  { npm run typecheck }
        Run-Stage "Frontend: ESLint"      { npm run lint }
        Run-Stage "Frontend: Vitest"      { npm test }
        Run-Stage "Frontend: production build" { npm run build }
        Pop-Location
    }
}

Write-Host "`n==================== SUMMARY ====================" -ForegroundColor Cyan
$failed = $false
foreach ($k in $results.Keys) {
    $ok = $results[$k] -eq "PASSED"
    if (-not $ok) { $failed = $true }
    Write-Host ("{0,-42} {1}" -f $k, $results[$k]) -ForegroundColor $(if ($ok) { "Green" } else { "Red" })
}
if ($failed) { exit 1 }
