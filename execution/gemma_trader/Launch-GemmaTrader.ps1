# ═══════════════════════════════════════════════════════════════════
#  Rey Capital - Gemma Trader Launcher
#  One-click PowerShell script to run the Gemma Trader app
# ═══════════════════════════════════════════════════════════════════

param(
    [ValidateSet("paper", "live")]
    [string]$Mode = "paper",

    [int]$Port = 8050,

    [string]$Config = "config.yaml",

    [string[]]$Symbols,

    [string]$Interval,

    [switch]$DashboardOnly,

    [switch]$SkipChecks,

    [switch]$InstallDeps
)

# ── Paths ──────────────────────────────────────────────────────────
$AppDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir      = Join-Path $AppDir "venv"
$VenvActivate = Join-Path $VenvDir "Scripts\Activate.ps1"
$VenvPython   = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile      = Join-Path $AppDir "requirements.txt"
$ConfigFile   = Join-Path $AppDir $Config
$LogsDir      = Join-Path $AppDir "logs"

# ── Helpers ────────────────────────────────────────────────────────
function Write-Banner {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        REY CAPITAL - GEMMA TRADER            ║" -ForegroundColor Cyan
    Write-Host "  ║        AI-Powered Scalping Engine             ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Check([string]$Label, [string]$Status, [string]$Detail) {
    $color = switch ($Status) {
        "OK"      { "Green"  }
        "WARN"    { "Yellow" }
        "FAIL"    { "Red"    }
        "INFO"    { "Cyan"   }
        default   { "White"  }
    }
    $icon = switch ($Status) {
        "OK"   { "[OK]  " }
        "WARN" { "[!!]  " }
        "FAIL" { "[XX]  " }
        "INFO" { "[--]  " }
        default{ "      " }
    }
    Write-Host "  $icon" -ForegroundColor $color -NoNewline
    Write-Host "$Label " -NoNewline
    if ($Detail) { Write-Host "- $Detail" -ForegroundColor DarkGray } else { Write-Host "" }
}

function Test-Port([int]$PortNum) {
    $listener = Get-NetTCPConnection -LocalPort $PortNum -ErrorAction SilentlyContinue
    return ($null -ne $listener)
}

# ── Start ──────────────────────────────────────────────────────────
Write-Banner

# ── 1. Preflight Checks ───────────────────────────────────────────
if (-not $SkipChecks) {
    Write-Host "  PREFLIGHT CHECKS" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────" -ForegroundColor DarkGray

    # Python
    try {
        $pyVer = & python --version 2>&1
        if ($pyVer -match "Python (\d+\.\d+)") {
            $ver = [version]$Matches[1]
            if ($ver -ge [version]"3.8") {
                Write-Check "Python" "OK" "$pyVer"
            } else {
                Write-Check "Python" "WARN" "$pyVer (3.8+ recommended)"
            }
        }
    } catch {
        Write-Check "Python" "FAIL" "Not found. Install from https://python.org"
        Write-Host ""
        exit 1
    }

    # Config file
    if (Test-Path $ConfigFile) {
        Write-Check "Config" "OK" $Config
    } else {
        Write-Check "Config" "FAIL" "$Config not found at $ConfigFile"
        Write-Host ""
        exit 1
    }

    # Ollama service
    $ollamaRunning = $false
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
        $ollamaRunning = $true

        # Check if gemma4 model is pulled
        $hasGemma = $false
        if ($response.models) {
            foreach ($m in $response.models) {
                if ($m.name -match "gemma") { $hasGemma = $true; break }
            }
        }
        if ($hasGemma) {
            Write-Check "Ollama" "OK" "Running, gemma model available"
        } else {
            Write-Check "Ollama" "WARN" "Running but gemma model not found. Run: ollama pull gemma4"
        }
    } catch {
        # Check if ollama is installed but not running
        $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaCmd) {
            Write-Check "Ollama" "WARN" "Installed but not running. Starting it now..."
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
            Start-Sleep -Seconds 3
            # Re-check
            try {
                Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop | Out-Null
                $ollamaRunning = $true
                Write-Check "Ollama" "OK" "Started successfully"
            } catch {
                Write-Check "Ollama" "WARN" "Failed to auto-start. Please run 'ollama serve' manually"
            }
        } else {
            Write-Check "Ollama" "WARN" "Not installed. Download: https://ollama.com/download"
        }
    }

    # MetaTrader 5 process
    $mt5Proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    if ($mt5Proc) {
        Write-Check "MetaTrader 5" "OK" "Running (PID $($mt5Proc.Id))"
    } else {
        # Try to find and launch MT5
        $mt5Paths = @(
            "C:\Program Files\MetaTrader 5\terminal64.exe",
            "C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
            "$env:APPDATA\..\Local\Programs\MetaTrader 5\terminal64.exe"
        )
        $mt5Found = $false
        foreach ($p in $mt5Paths) {
            if (Test-Path $p) { $mt5Found = $true; break }
        }
        if ($mt5Found) {
            Write-Check "MetaTrader 5" "WARN" "Installed but not running. Please open MT5 and log in"
        } else {
            if ($Mode -eq "paper") {
                Write-Check "MetaTrader 5" "INFO" "Not found (OK for paper mode if using synthetic data)"
            } else {
                Write-Check "MetaTrader 5" "WARN" "Not found. Required for live MT5 trading"
            }
        }
    }

    # Port availability
    if (Test-Port $Port) {
        Write-Check "Port $Port" "WARN" "Already in use. Dashboard may fail to bind"
    } else {
        Write-Check "Port $Port" "OK" "Available"
    }

    Write-Host ""
}

# ── 2. Virtual Environment ────────────────────────────────────────
Write-Host "  ENVIRONMENT SETUP" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────" -ForegroundColor DarkGray

if (-not (Test-Path $VenvDir)) {
    Write-Check "Venv" "INFO" "Creating virtual environment..."
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Check "Venv" "FAIL" "Could not create virtual environment"
        exit 1
    }
    Write-Check "Venv" "OK" "Created at $VenvDir"
    $InstallDeps = $true   # force install on first run
} else {
    Write-Check "Venv" "OK" "Found"
}

# Activate
& $VenvActivate

# ── 3. Install Dependencies ───────────────────────────────────────
if ($InstallDeps) {
    Write-Host ""
    Write-Host "  INSTALLING DEPENDENCIES" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────" -ForegroundColor DarkGray

    if (Test-Path $ReqFile) {
        Write-Check "pip" "INFO" "Installing from requirements.txt..."
        & $VenvPython -m pip install --upgrade pip --quiet 2>$null
        & $VenvPython -m pip install -r $ReqFile --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Check "Deps" "OK" "Core dependencies installed"
        } else {
            Write-Check "Deps" "WARN" "Some packages may have failed"
        }
    }

    # Install MetaTrader5 (Windows-only, optional)
    Write-Check "MT5 lib" "INFO" "Installing MetaTrader5 Python package..."
    & $VenvPython -m pip install MetaTrader5 --quiet 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Check "MT5 lib" "OK" "MetaTrader5 package installed"
    } else {
        Write-Check "MT5 lib" "WARN" "MetaTrader5 package failed (OK if not using MT5)"
    }

    Write-Host ""
}

# ── 4. Ensure logs directory ──────────────────────────────────────
if (-not (Test-Path $LogsDir)) {
    New-Item -Path $LogsDir -ItemType Directory -Force | Out-Null
}

# ── 5. Launch ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "  LAUNCHING" -ForegroundColor White
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Mode          :  $Mode" -ForegroundColor $(if ($Mode -eq "live") { "Red" } else { "Green" })
Write-Host "  Dashboard     :  http://localhost:$Port" -ForegroundColor Green
Write-Host "  Config        :  $Config" -ForegroundColor White
Write-Host "  Trading       :  $(if ($DashboardOnly) { 'Disabled (dashboard only)' } else { 'Enabled' })" -ForegroundColor White
if ($Symbols) {
    Write-Host "  Symbols       :  $($Symbols -join ', ')" -ForegroundColor White
}
if ($Interval) {
    Write-Host "  Interval      :  $Interval" -ForegroundColor White
}
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Cyan

if ($Mode -eq "live") {
    Write-Host ""
    Write-Host "  ** LIVE TRADING MODE **" -ForegroundColor Red
    Write-Host "  Real money is at risk. Press Ctrl+C to stop at any time." -ForegroundColor Yellow
    Write-Host ""
}

# Build command arguments
$runArgs = @("run.py", "--config", $Config, "--port", $Port, "--mode", $Mode)

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

# Change to app directory and run
Set-Location $AppDir

try {
    & $VenvPython @runArgs
} catch {
    Write-Host ""
    Write-Host "  [ERROR] Application crashed: $_" -ForegroundColor Red
} finally {
    Write-Host ""
    Write-Host "  Gemma Trader stopped." -ForegroundColor Yellow
    Write-Host ""
}
