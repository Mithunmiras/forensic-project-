<#
.SYNOPSIS
  Start/stop a project-local PostgreSQL 16 (no install, no admin rights) for development.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start_local_postgres.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start_local_postgres.ps1 -Action stop
#>
param(
    [ValidateSet("start", "stop", "status")][string]$Action = "start",
    [switch]$UpdateEnv   # set DATABASE_URL in .env, only if it is currently empty
)
. "$PSScriptRoot\_common.ps1"
$py = Get-VenvPython

& $py -c "import pgserver" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing the embedded PostgreSQL package (pgserver)"
    Invoke-Checked $py @("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements-localdb.txt") "Installing pgserver"
}

Invoke-Checked $py @("scripts\dev_postgres.py", $Action) "dev_postgres $Action"

if ($Action -eq "start" -and $UpdateEnv) {
    $url = (& $py scripts\dev_postgres.py url).Trim()
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
    $lines = Get-Content ".env"
    $current = $lines | Where-Object { $_ -match '^DATABASE_URL=(.+)$' }
    if ($current) { Write-Warn2 "DATABASE_URL in .env already has a value - not changing it." }
    else {
        $lines = $lines | ForEach-Object { if ($_ -match '^DATABASE_URL=\s*$') { "DATABASE_URL=$url" } else { $_ } }
        Set-Content ".env" $lines -Encoding utf8
        Write-Ok "set DATABASE_URL in .env"
    }
}
