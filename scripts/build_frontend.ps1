<#
.SYNOPSIS
  Type-check and build the production frontend into frontend\dist (served by the backend).
#>
. "$PSScriptRoot\_common.ps1"
if (-not (Test-Command "npm")) { throw "Node.js 18+ is required. Install it from https://nodejs.org" }
Push-Location frontend
try {
    if (-not (Test-Path "node_modules")) { Invoke-Checked "npm" @("install", "--no-audit", "--no-fund") "npm install" }
    Invoke-Checked "npm" @("run", "build") "Frontend build"
} finally { Pop-Location }
Write-Ok "built frontend\dist"
