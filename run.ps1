<#
.SYNOPSIS
  One command to run the whole project. Prepares anything that is missing, starts the server,
  prints the localhost URL and opens it in the browser. Safe to run repeatedly (only does missing work).

.EXAMPLE
  .\run.cmd
  powershell -ExecutionPolicy Bypass -File run.ps1
  powershell -ExecutionPolicy Bypass -File run.ps1 -Port 8765 -NoBrowser
#>
param(
    [int]$Port = 0,          # 0 = first free port starting at 8000
    [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root
. "$Root\scripts\_common.ps1"

function Get-EnvValue([string]$Key) {
    if (-not (Test-Path ".env")) { return "" }
    $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
    if (-not $line) { return "" }
    return ($line -replace "^\s*$Key=", "").Trim().Trim('"').Trim("'")
}
function Set-EnvValue([string]$Key, [string]$Value) {
    $lines = @(Get-Content ".env")
    $found = $false
    $lines = $lines | ForEach-Object { if ($_ -match "^\s*$Key=") { $found = $true; "$Key=$Value" } else { $_ } }
    if (-not $found) { $lines += "$Key=$Value" }
    Set-Content ".env" $lines -Encoding utf8
}
function Get-Status {
    $json = & $py main.py status 2>$null
    try { return ($json -join "`n" | ConvertFrom-Json) } catch { return $null }
}

# ---- 1. environment ---------------------------------------------------------------------------
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Step "First run: installing dependencies (a few minutes)"
    & "$Root\scripts\setup.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Setup failed." }
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# ---- 2. database ------------------------------------------------------------------------------
$dbUrl = Get-EnvValue "DATABASE_URL"
$useLocalDb = (-not $dbUrl) -or ($dbUrl -match "127\.0\.0\.1:54329")
if ($useLocalDb) {
    Write-Step "Starting the project-local PostgreSQL"
    & $py -c "import pgserver" 2>$null
    if ($LASTEXITCODE -ne 0) { Invoke-Checked $py @("-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements-localdb.txt") "Installing pgserver" }
    Invoke-Checked $py @("scripts\dev_postgres.py", "start") "Local PostgreSQL"
    if (-not $dbUrl) { Set-EnvValue "DATABASE_URL" (& $py scripts\dev_postgres.py url).Trim(); Write-Ok "DATABASE_URL set in .env" }
}

Write-Step "Checking what is ready"
$s = Get-Status
$dbReady = $s -and $s.database.connected -and $s.database.schema_ready -and ($s.database.fact_rows -gt 0)
$needRole = $useLocalDb -and -not (Get-EnvValue "DATABASE_READONLY_URL")

if (-not $dbReady -or $needRole) {
    $setupArgs = @("scripts\setup_database.py", "--create-database")
    if ($needRole) {
        $chars = (48..57) + (65..90) + (97..122)
        $pw = -join ((1..24) | ForEach-Object { [char]($chars | Get-Random) })
        $env:READONLY_DB_PASSWORD = $pw
        $setupArgs += "--create-readonly-role"
    }
    try { Invoke-Checked $py $setupArgs "Database setup" } finally { Remove-Item Env:\READONLY_DB_PASSWORD -ErrorAction SilentlyContinue }
    if ($needRole) {
        $base = (Get-EnvValue "DATABASE_URL") -replace "^(postgres(?:ql)?(?:\+\w+)?://)[^@/]*@", "`$1retailiq_readonly:$pw@"
        Set-EnvValue "DATABASE_READONLY_URL" $base
        Write-Ok "created a SELECT-only database role and saved it to .env"
    }
}
if (-not $dbReady) {
    Write-Step "Loading the dataset (validated, idempotent)"
    Invoke-Checked $py @("scripts\run_etl.py") "ETL"
    Invoke-Checked $py @("scripts\generate_docs.py") "Generating documentation from the data"
}

# ---- 3. model, index, frontend ----------------------------------------------------------------
$s = Get-Status
if (-not ($s -and $s.model.ready)) {
    Write-Step "Training and evaluating the models (about 30 seconds)"
    Invoke-Checked $py @("scripts\train_model.py") "Model training"
}
if (-not ($s -and $s.vector_store.state -ne "not_indexed" -and -not $s.vector_store.stale)) {
    Write-Step "Building the knowledge-base index"
    Invoke-Checked $py @("scripts\index_rag.py") "Indexing"
}
if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Step "Building the dashboard"
    & "$Root\scripts\build_frontend.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
}

# ---- 4. start the server ----------------------------------------------------------------------
if ($Port -eq 0) {
    $Port = 8000
    while (-not (Test-PortFree $Port)) { $Port++; if ($Port -gt 8100) { throw "No free port found between 8000 and 8100." } }
} elseif (-not (Test-PortFree $Port)) { throw "Port $Port is already in use. Omit -Port to pick a free one automatically." }

Write-Step "Starting RetailIQ"
$server = Start-Process -FilePath $py -ArgumentList @("main.py", "serve", "--port", "$Port") -WorkingDirectory $Root -NoNewWindow -PassThru
$url = "http://127.0.0.1:$Port"
$up = $false
for ($i = 0; $i -lt 90 -and -not $server.HasExited; $i++) {
    try { if ((Invoke-WebRequest "$url/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $up = $true; break } } catch { Start-Sleep -Milliseconds 700 }
}
if (-not $up) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "The server did not start. Scroll up for the error message."
}

Write-Host ""
Write-Host "  RetailIQ is running" -ForegroundColor Green
Write-Host "  Open:      $url" -ForegroundColor Green
Write-Host "  API docs:  $url/docs"
Write-Host "  Status:    $url/status"
Write-Host "  Press Ctrl+C in this window to stop." -ForegroundColor DarkGray
Write-Host ""
if (-not $NoBrowser) { Start-Process $url }

try { $server.WaitForExit() }
finally { if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force } }
