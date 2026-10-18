<#
.SYNOPSIS
  Create the schema and load the dataset into PostgreSQL (idempotent - safe to re-run; never drops anything).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_etl.ps1 -CreateDatabase -CreateReadonlyRole
  powershell -ExecutionPolicy Bypass -File scripts\run_etl.ps1 -DryRun        # validate only, no database needed
#>
param(
    [switch]$DryRun,
    [switch]$CreateDatabase,
    [switch]$CreateReadonlyRole,
    [switch]$UpdateExisting,
    [switch]$SkipDocs        # skip regenerating docs/generated/* after loading
)
. "$PSScriptRoot\_common.ps1"
$py = Get-VenvPython

if ($DryRun) {
    Write-Step "Validating the dataset (dry run - the database is not touched)"
    Invoke-Checked $py @("scripts\run_etl.py", "--dry-run") "ETL dry run"
    exit 0
}

Write-Step "Database schema"
$setupArgs = @("scripts\setup_database.py")
if ($CreateDatabase) { $setupArgs += "--create-database" }
if ($CreateReadonlyRole) {
    $setupArgs += "--create-readonly-role"
    if (-not $env:READONLY_DB_PASSWORD) {
        $secure = Read-Host "Password for the new read-only role (input hidden)" -AsSecureString
        $env:READONLY_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    }
}
try { Invoke-Checked $py $setupArgs "Database setup" } finally { if ($CreateReadonlyRole) { Remove-Item Env:\READONLY_DB_PASSWORD -ErrorAction SilentlyContinue } }

Write-Step "ETL"
$etlArgs = @("scripts\run_etl.py")
if ($UpdateExisting) { $etlArgs += "--update-existing" }
Invoke-Checked $py $etlArgs "ETL"

if (-not $SkipDocs) {
    Write-Step "Regenerating data-driven documentation"
    Invoke-Checked $py @("scripts\generate_docs.py") "generate_docs"
}
Write-Host "`nETL finished. Train the model next:  python scripts\train_model.py   then index docs:  python scripts\index_rag.py" -ForegroundColor Green
