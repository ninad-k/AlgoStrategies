# PineScript Backtester — launch FastAPI + static UI (default http://localhost:8002)
# Run from anywhere:  pwsh -File "D:\path\to\tools\backtester\Run-Backtester.ps1"

param(
    [int]$Port = 8002,
    [string]$HostBind = "0.0.0.0",
    [switch]$InstallDeps,
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$VenvPath = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$ReqFile = Join-Path $Root "requirements.txt"
$RunPy = Join-Path $Root "run.py"

if (-not (Test-Path $RunPy)) {
    Write-Error "Cannot find run.py at $RunPy"
}

function Get-Python {
    if (-not $SkipVenv -and (Test-Path $VenvPython)) {
        return $VenvPython
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $py3 = Get-Command py -ErrorAction SilentlyContinue
    if ($py3) { return "py" }
    Write-Error "Python not found. Install Python 3.10+ or create .venv in $Root"
}

if ($InstallDeps) {
    if (-not (Test-Path $VenvPath)) {
        Write-Host "Creating virtual environment at $VenvPath ..."
        $bootstrap = Get-Python
        if ($bootstrap -eq "py") {
            & py -3 -m venv $VenvPath
        } else {
            & $bootstrap -m venv $VenvPath
        }
    }
    $py = Join-Path $VenvPath "Scripts\python.exe"
    Write-Host "Installing dependencies from requirements.txt ..."
    & $py -m pip install --upgrade pip
    & $py -m pip install -r $ReqFile
}

$python = Get-Python
if ($python -eq "py") {
    $pyExe = "py"
    $pyArgs = @("-3")
} else {
    $pyExe = $python
    $pyArgs = @()
}

$env:BACKTESTER_PORT = "$Port"
$env:BACKTESTER_HOST = $HostBind

Write-Host ""
Write-Host "PineScript Backtester" -ForegroundColor Cyan
Write-Host "  URL:  http://localhost:$Port/" -ForegroundColor Gray
Write-Host "  Host: $HostBind  Port: $Port" -ForegroundColor Gray
Write-Host "  Root: $Root" -ForegroundColor DarkGray
Write-Host ""

Set-Location $Root
if ($pyExe -eq "py") {
    & $pyExe @pyArgs $RunPy
} else {
    & $pyExe $RunPy
}
