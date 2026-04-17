# ═══════════════════════════════════════════════════════════════════════════════
#  Rey Capital - Gemma Trader Launcher
#  Start the AI trading bot with Flask dashboard
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [ValidateSet("paper", "live")]
    [string]$Mode = "paper",

    [int]$Port = 8050,

    [string]$Config = "config.yaml",

    [string[]]$Symbols,

    [string]$Interval,

    [switch]$DashboardOnly,

    [switch]$SkipChecks,

    [switch]$Verbose
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir = Join-Path $AppDir "venv"
$VenvActivate = Join-Path $VenvDir "Scripts\Activate.ps1"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $AppDir "requirements.txt"
$ConfigFile = Join-Path $AppDir $Config
$LogsDir = Join-Path $AppDir "logs"
$ProcessFile = Join-Path $AppDir ".trader_pid.txt"

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

function Write-Banner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        REY CAPITAL - GEMMA TRADER LAUNCHER            ║" -ForegroundColor Cyan
    Write-Host "  ║        AI-Powered Trading Engine                      ║" -ForegroundColor Cyan
    Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Status {
    param([string]$Label, [string]$Status, [string]$Detail)
    $color = switch ($Status) {
        "OK"      { "Green"  }
        "WARN"    { "Yellow" }
        "FAIL"    { "Red"    }
        "INFO"    { "Cyan"   }
        default   { "White"  }
    }
    $icon = switch ($Status) {
        "OK"   { "[✓]" }
        "WARN" { "[!]" }
        "FAIL" { "[✗]" }
        "INFO" { "[i]" }
        default{ "   " }
    }
    Write-Host "  $icon " -ForegroundColor $color -NoNewline
    Write-Host "$Label " -NoNewline
    if ($Detail) { Write-Host "- $Detail" -ForegroundColor DarkGray } else { Write-Host "" }
}

function Test-Port {
    param([int]$PortNum)
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return $listener.Port -contains $PortNum
    } catch {
        return $false
    }
}

function Invoke-ApiCall {
    param([string]$Url)
    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 2 -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  1. PREFLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────────────────

Write-Banner

if (-not $SkipChecks) {
    Write-Host "  PREFLIGHT CHECKS" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    # Check Python
    try {
        $pyVer = & python --version 2>&1
        Write-Status "Python" "OK" "$pyVer"
    } catch {
        Write-Status "Python" "FAIL" "Not found or not in PATH"
        exit 1
    }

    # Check config file
    if (Test-Path $ConfigFile) {
        Write-Status "Config" "OK" $Config
    } else {
        Write-Status "Config" "FAIL" "$Config not found"
        exit 1
    }

    # Check virtual environment
    if (Test-Path $VenvPython) {
        Write-Status "Venv" "OK" $VenvDir
    } else {
        Write-Status "Venv" "FAIL" "Run Setup-GemmaTrader.ps1 first"
        exit 1
    }

    # Check Ollama
    $ollamaRunning = Invoke-ApiCall "http://localhost:11434/api/tags"
    if ($ollamaRunning) {
        Write-Status "Ollama" "OK" "Service running"
    } else {
        Write-Status "Ollama" "WARN" "Not running. Starting now..."
        if (Get-Command ollama -ErrorAction SilentlyContinue) {
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
            Start-Sleep -Seconds 3
            if (Invoke-ApiCall "http://localhost:11434/api/tags") {
                Write-Status "Ollama" "OK" "Started successfully"
            } else {
                Write-Status "Ollama" "WARN" "Failed to start. Manual launch may be required"
            }
        } else {
            Write-Status "Ollama" "WARN" "Not installed. Download: https://ollama.com"
        }
    }

    # Check MT5 (for live mode)
    if ($Mode -eq "live") {
        $mt5Proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
        if ($mt5Proc) {
            Write-Status "MT5" "OK" "Running"
        } else {
            Write-Status "MT5" "WARN" "Not running. Required for live trading"
        }
    }

    # Check port availability
    if (Test-Port $Port) {
        Write-Status "Port $Port" "WARN" "Already in use"
    } else {
        Write-Status "Port $Port" "OK" "Available"
    }

    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
#  2. ACTIVATE VIRTUAL ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  ENVIRONMENT ACTIVATION" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Write-Status "Venv" "INFO" "Activating virtual environment..."

if (-not (Test-Path $VenvActivate)) {
    Write-Status "Venv" "FAIL" "Activation script not found"
    Write-Host "  Please run: Setup-GemmaTrader.ps1" -ForegroundColor Yellow
    exit 1
}

try {
    & $VenvActivate
    Write-Status "Venv" "OK" "Activated"
} catch {
    Write-Status "Venv" "FAIL" "Could not activate: $_"
    exit 1
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  3. SAVE PID FOR STOP SCRIPT
# ─────────────────────────────────────────────────────────────────────────────

$CurrentPID = $PID
$CurrentPID | Out-File -FilePath $ProcessFile -Encoding UTF8 -Force

# ─────────────────────────────────────────────────────────────────────────────
#  4. CREATE LOGS DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────

if (-not (Test-Path $LogsDir)) {
    New-Item -Path $LogsDir -ItemType Directory -Force | Out-Null
}

# ─────────────────────────────────────────────────────────────────────────────
#  5. DISPLAY STARTUP CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  LAUNCH CONFIGURATION" -ForegroundColor White
Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Cyan

$modeColor = if ($Mode -eq "live") { "Red" } else { "Green" }
Write-Host "  Mode              : $Mode" -ForegroundColor $modeColor
Write-Host "  Dashboard URL     : http://localhost:$Port" -ForegroundColor Green
Write-Host "  Config File       : $Config" -ForegroundColor White
Write-Host "  Trading Enabled   : $(if ($DashboardOnly) { 'No (dashboard only)' } else { 'Yes' })" -ForegroundColor White

if ($Symbols) {
    Write-Host "  Trading Symbols   : $($Symbols -join ', ')" -ForegroundColor White
}

if ($Interval) {
    Write-Host "  Timeframe         : $Interval" -ForegroundColor White
}

Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($Mode -eq "live") {
    Write-Host ""
    Write-Host "  ⚠️  LIVE TRADING MODE - REAL MONEY AT RISK ⚠️" -ForegroundColor Red
    Write-Host "  Press Ctrl+C to stop at any time" -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 3
}

# ─────────────────────────────────────────────────────────────────────────────
#  6. BUILD AND EXECUTE RUN COMMAND
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  STARTING APPLICATION" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

$runArgs = @("run.py", "--config", $Config, "--port", $Port.ToString(), "--mode", $Mode)

if ($DashboardOnly) {
    $runArgs += "--no-trade"
}

if ($Symbols) {
    $runArgs += "--symbols"
    $runArgs += $Symbols
}

if ($Interval) {
    $runArgs += "--interval"
    $runArgs += $Interval
}

# Change to app directory
Set-Location $AppDir

Write-Host "  Command: $VenvPython $($runArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

# Run the application
try {
    Write-Host "  ✓ Application started. Press Ctrl+C to stop." -ForegroundColor Green
    Write-Host ""
    & $VenvPython @runArgs
} catch {
    Write-Host ""
    Write-Status "Error" "FAIL" "Application crashed: $_"
} finally {
    Write-Host ""
    Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "  Application stopped" -ForegroundColor Yellow
    Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""

    # Clean up PID file
    if (Test-Path $ProcessFile) {
        Remove-Item $ProcessFile -Force -ErrorAction SilentlyContinue
    }
}
