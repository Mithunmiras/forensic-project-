<#
.SYNOPSIS
  Development launcher: starts the backend and the frontend dev server in two windows and waits until both answer.
  It reports a failure explicitly instead of pretending everything started.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -ApiPort 8765
#>
param([int]$ApiPort = 8000, [int]$WebPort = 5173)
. "$PSScriptRoot\_common.ps1"
Get-VenvPython | Out-Null

foreach ($p in @($ApiPort, $WebPort)) {
    if (-not (Test-PortFree $p)) { throw "Port $p is already in use. Re-run with -ApiPort / -WebPort set to free ports." }
}

$ps = (Get-Process -Id $PID).Path
$api = Start-Process $ps -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\start_backend.ps1", "-Port", $ApiPort, "-Reload") -PassThru
$web = Start-Process $ps -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\start_frontend.ps1", "-Port", $WebPort, "-ApiPort", $ApiPort) -PassThru

function Wait-Url([string]$Url, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try { if ((Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 3).StatusCode -lt 500) { return $true } } catch { Start-Sleep -Milliseconds 800 }
    }
    return $false
}

Write-Step "Waiting for the services"
$apiUp = Wait-Url "http://127.0.0.1:$ApiPort/health" 60
$webUp = Wait-Url "http://localhost:$WebPort" 60
if ($apiUp) { Write-Ok "backend  http://127.0.0.1:$ApiPort  (docs: /docs)" } else { Write-Fail "backend did not answer within 60 s - see its window for the error" }
if ($webUp) { Write-Ok "frontend http://localhost:$WebPort" } else { Write-Fail "frontend did not answer within 60 s - see its window for the error" }
if (-not ($apiUp -and $webUp)) { exit 1 }
Start-Process "http://localhost:$WebPort"
Write-Host "`nClose the two new windows to stop." -ForegroundColor DarkGray
