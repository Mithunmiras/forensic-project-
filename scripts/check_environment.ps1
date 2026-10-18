<#
.SYNOPSIS
  Report what is installed/running and what is still missing. Exit code 1 if a REQUIRED item is missing.
#>
. "$PSScriptRoot\_common.ps1"
$ErrorActionPreference = "Continue"
$missing = 0

function Check([string]$Name, [bool]$Ok, [string]$Detail, [bool]$Required = $true, [string]$Fix = "") {
    if ($Ok) { Write-Ok "$Name - $Detail" }
    elseif ($Required) { Write-Fail "$Name - $Detail"; if ($Fix) { Write-Host "         fix: $Fix" -ForegroundColor DarkGray }; $script:missing++ }
    else { Write-Warn2 "$Name (optional) - $Detail"; if ($Fix) { Write-Host "         fix: $Fix" -ForegroundColor DarkGray } }
}

Write-Step "Tools"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
Check "Python venv" (Test-Path $venvPy) $(if (Test-Path $venvPy) { (& $venvPy --version) } else { "not created" }) $true "scripts\setup.ps1"
Check "Node.js" (Test-Command "node") $(if (Test-Command "node") { (node --version) } else { "not found" }) $true "install Node 18+ from https://nodejs.org"
Check "npm" (Test-Command "npm") $(if (Test-Command "npm") { (npm --version) } else { "not found" }) $true "comes with Node.js"
Check "PostgreSQL client (psql)" (Test-Command "psql") $(if (Test-Command "psql") { "found" } else { "not on PATH (not required - the app uses a Python driver)" }) $false

Write-Step "Project files"
Check ".env" (Test-Path ".env") $(if (Test-Path ".env") { "present" } else { "missing" }) $true "scripts\setup.ps1 (copies .env.example; never overwrites)"
Check "dataset" (Test-Path "data\raw\superstore.csv") "data\raw\superstore.csv" $true
Check "trained model" (Test-Path "models\sales_model.joblib") $(if (Test-Path "models\sales_model.joblib") { "present" } else { "not trained" }) $false "python scripts\train_model.py"
Check "frontend build" (Test-Path "frontend\dist\index.html") $(if (Test-Path "frontend\dist\index.html") { "present" } else { "not built" }) $false "scripts\build_frontend.ps1"

if (Test-Path $venvPy) {
    Write-Step "Live system status (database, model, vector index, LLM)"
    & $venvPy main.py status 2>$null | ConvertFrom-Json | ForEach-Object {
        $s = $_
        Check "PostgreSQL" ($s.database.connected -and $s.database.schema_ready -and $s.database.fact_rows -gt 0) $(if ($s.database.connected) { "connected, $($s.database.fact_rows) rows, read-only role: $($s.database.readonly_role)" } else { "$($s.database.error)" }) $true "set DATABASE_URL in .env, then scripts\run_etl.ps1 -CreateDatabase"
        Check "Model" $s.model.ready $(if ($s.model.ready) { "loaded" } else { "$($s.model.error)" }) $true "python scripts\train_model.py"
        Check "Vector index" ($s.vector_store.state -ne "not_indexed") "$($s.vector_store.state), mode: $($s.vector_store.retrieval_mode)" $true "python scripts\index_rag.py"
        Check "LLM (Ollama)" $s.llm.available $(if ($s.llm.available) { "model $($s.llm.model) ready" } else { "$($s.llm.error)" }) $false "install Ollama, then: ollama pull llama3.2"
    }
    if ($LASTEXITCODE -gt 1) { Write-Fail "Could not read the system status" }
}

Write-Host ""
if ($missing -gt 0) { Write-Host "$missing required item(s) missing." -ForegroundColor Red; exit 1 }
Write-Host "All required components are in place." -ForegroundColor Green
