# Shared helpers for the RetailIQ PowerShell scripts (dot-sourced; not run directly).

$ErrorActionPreference = "Stop"
$script:Root = Split-Path -Parent $PSScriptRoot
Set-Location $script:Root

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text)   { Write-Host "  [ok]   $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text){ Write-Host "  [warn] $Text" -ForegroundColor Yellow }
function Write-Fail([string]$Text) { Write-Host "  [FAIL] $Text" -ForegroundColor Red }

function Get-VenvPython {
    $py = Join-Path $script:Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        throw "Python virtual environment not found. Run:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1"
    }
    return $py
}

# Run a native command and stop the script if it fails (PowerShell does not do this by itself).
function Invoke-Checked {
    param([Parameter(Mandatory)][string]$Exe, [string[]]$Arguments = @(), [string]$What = $Exe)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE." }
}

function Test-PortFree([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $Port)
        $listener.Start()
        return $true
    } catch { return $false } finally { if ($listener) { $listener.Stop() } }
}

function Test-Command([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
