<#
.SYNOPSIS
  Start the React dev server (hot reload) at http://localhost:5173, proxying /api to the backend.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1 -ApiPort 8765
#>
param(
    [int]$Port = 5173,
    [int]$ApiPort = 8000
)
. "$PSScriptRoot\_common.ps1"

if (-not (Test-Command "node") -or -not (Test-Command "npm")) { throw "Node.js 18+ is required. Install it from https://nodejs.org" }
if (-not (Test-PortFree $Port)) { throw "Port $Port is already in use. Choose another one:  scripts\start_frontend.ps1 -Port $($Port + 1)" }

Push-Location frontend
try {
    if (-not (Test-Path "node_modules")) {
        Write-Step "Installing frontend dependencies"
        Invoke-Checked "npm" @("install", "--no-audit", "--no-fund") "npm install"
    }
    $env:VITE_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
    Write-Step "Starting the dev server on http://localhost:$Port  (API proxied to port $ApiPort)"
    Write-Host "  If the CORS origin differs from http://localhost:5173, set FRONTEND_ORIGIN in .env." -ForegroundColor DarkGray
    Invoke-Checked "npm" @("run", "dev", "--", "--port", "$Port", "--strictPort") "Vite dev server"
} finally { Pop-Location }
