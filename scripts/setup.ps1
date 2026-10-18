<#
.SYNOPSIS
  One-time setup: Python venv, backend dependencies, .env (never overwritten), frontend dependencies.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SkipFrontend
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Dev     # also installs pytest + the embedded PostgreSQL
#>
param(
    [switch]$SkipFrontend,
    [switch]$Dev,
    [switch]$LocalDb
)
. "$PSScriptRoot\_common.ps1"

Write-Step "Python virtual environment"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $sysPy = if (Test-Command "py") { "py" } elseif (Test-Command "python") { "python" } else { throw "Python 3.11+ was not found. Install it from https://www.python.org/downloads/ and re-run." }
    $venvArgs = if ($sysPy -eq "py") { @("-3.11", "-m", "venv", ".venv") } else { @("-m", "venv", ".venv") }
    try { Invoke-Checked $sysPy $venvArgs "Creating the virtual environment" }
    catch { if ($sysPy -eq "py") { Invoke-Checked "py" @("-3", "-m", "venv", ".venv") "Creating the virtual environment" } else { throw } }
    Write-Ok "created .venv"
} else { Write-Ok ".venv already exists (kept)" }

$ver = & $venvPy -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.11") { throw "Python $ver found in .venv; 3.11 or newer is required." }
Write-Ok "Python $ver"

Write-Step "Backend dependencies"
Invoke-Checked $venvPy @("-m", "pip", "install", "--disable-pip-version-check", "--quiet", "--upgrade", "pip") "Upgrading pip"
$req = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }
Invoke-Checked $venvPy @("-m", "pip", "install", "--disable-pip-version-check", "-r", $req) "Installing $req"
if ($LocalDb -and -not $Dev) { Invoke-Checked $venvPy @("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements-localdb.txt") "Installing the local database package" }
Write-Ok "installed $req"

Write-Step "Configuration (.env)"
if (Test-Path ".env") {
    Write-Ok ".env already exists - left untouched"
} else {
    Copy-Item ".env.example" ".env"
    Write-Ok "created .env from .env.example - edit DATABASE_URL before running the ETL"
}

if (-not $SkipFrontend) {
    Write-Step "Frontend dependencies"
    if (-not (Test-Command "node") -or -not (Test-Command "npm")) {
        Write-Warn2 "Node.js / npm not found - skipping the frontend. Install Node 18+ from https://nodejs.org and re-run."
    } else {
        $nodeMajor = [int](node -p "process.versions.node.split('.')[0]")
        if ($nodeMajor -lt 18) { throw "Node $nodeMajor found; Node 18 or newer is required." }
        Push-Location frontend
        try {
            Invoke-Checked "npm" @("install", "--no-audit", "--no-fund") "npm install"
            Invoke-Checked "npm" @("run", "build") "Building the frontend"
        } finally { Pop-Location }
        Write-Ok "frontend installed and built (frontend\dist is served by the API)"
    }
}

Write-Host "`nSetup finished. Next steps:" -ForegroundColor Green
Write-Host "  1. Set DATABASE_URL in .env  (or run scripts\start_local_postgres.ps1 for a project-local dev database)"
Write-Host "  2. scripts\run_etl.ps1 -CreateDatabase -CreateReadonlyRole"
Write-Host "  3. scripts\start_backend.ps1     (and scripts\start_frontend.ps1 in a second terminal for hot reload)"
