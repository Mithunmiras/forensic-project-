<#
.SYNOPSIS
  Start the FastAPI backend (also serves the built dashboard from frontend\dist when present).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1 -Port 8765 -Reload
#>
param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reload
)
. "$PSScriptRoot\_common.ps1"
$py = Get-VenvPython

if (-not (Test-Path ".env")) { Write-Warn2 ".env not found - using defaults (no database). Run scripts\setup.ps1 first." }
if (-not (Test-Path "models\sales_model.joblib")) {
    Write-Warn2 "No trained model yet - the Prediction page will ask for it. Train it with:  python scripts\train_model.py"
}
if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Warn2 "frontend\dist not built - the API runs but the dashboard needs:  scripts\build_frontend.ps1  (or run scripts\start_frontend.ps1 for the dev server)"
}
if (-not (Test-PortFree $Port)) {
    throw "Port $Port is already in use by another program. Choose another one:  scripts\start_backend.ps1 -Port $($Port + 1)"
}

Write-Step "Starting RetailIQ API on http://${BindHost}:$Port  (API docs: /docs, status: /api/v1/system/status)"
$cliArgs = @("main.py", "serve", "--host", $BindHost, "--port", "$Port")
if ($Reload) { $cliArgs += "--reload" }
& $py @cliArgs
if ($LASTEXITCODE -ne 0) { throw "The backend exited with code $LASTEXITCODE." }
