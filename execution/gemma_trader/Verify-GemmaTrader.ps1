# ═══════════════════════════════════════════════════════════════════════════════
#  Rey Capital - Gemma Trader Verification Script
#  Verify that all components are properly installed and configured
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [switch]$Detailed,
    [switch]$FixIssues
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir = Join-Path $AppDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $AppDir "requirements.txt"
$ConfigFile = Join-Path $AppDir "config.yaml"
$LogsDir = Join-Path $AppDir "logs"

$checks = @()
$allPass = $true

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

function Write-Banner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║     REY CAPITAL - GEMMA TRADER VERIFICATION           ║" -ForegroundColor Cyan
    Write-Host "  ║     System & Component Status Check                   ║" -ForegroundColor Cyan
    Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Add-Check {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Message,
        [string]$Details
    )

    $color = switch ($Status) {
        "PASS" { "Green"  }
        "WARN" { "Yellow" }
        "FAIL" { "Red"    }
        "INFO" { "Cyan"   }
    }

    $icon = switch ($Status) {
        "PASS" { "✓" }
        "WARN" { "!" }
        "FAIL" { "✗" }
        "INFO" { "i" }
    }

    Write-Host "  [$icon] " -ForegroundColor $color -NoNewline
    Write-Host "$Name" -ForegroundColor $color -NoNewline
    Write-Host " - $Message" -ForegroundColor White

    if ($Details) {
        Write-Host "      $Details" -ForegroundColor DarkGray
    }

    if ($Status -eq "FAIL") {
        $allPass = $false
    }

    $checks += @{
        Name = $Name
        Status = $Status
        Message = $Message
        Details = $Details
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  1. SYSTEM CHECKS
# ─────────────────────────────────────────────────────────────────────────────

Write-Banner

Write-Host "  SYSTEM ENVIRONMENT" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Python
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "Python (\d+\.\d+\.\d+)") {
        $ver = [version]$Matches[1]
        if ($ver -ge [version]"3.8.0") {
            Add-Check "Python" "PASS" "Installed and compatible" "$pyVer"
        } else {
            Add-Check "Python" "WARN" "Version too old" "$pyVer (3.8+ required)"
        }
    }
} catch {
    Add-Check "Python" "FAIL" "Not found or not in PATH" "Install Python 3.8+ and add to PATH"
}

# PowerShell
$psVer = $PSVersionTable.PSVersion
Add-Check "PowerShell" "PASS" "Running version" "$($psVer.Major).$($psVer.Minor)"

# Operating System
$osInfo = Get-WmiObject Win32_OperatingSystem
$osName = "$($osInfo.Caption) ($($osInfo.OSArchitecture))"
Add-Check "OS" "PASS" "Detected" $osName

# RAM
$totalRAM = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($totalRAM -ge 8) {
    Add-Check "System RAM" "PASS" "Sufficient" "${totalRAM}GB (8GB+ recommended)"
} else {
    Add-Check "System RAM" "WARN" "May be insufficient" "${totalRAM}GB (8GB+ recommended)"
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  2. APPLICATION STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  APPLICATION STRUCTURE" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# App directory
if (Test-Path $AppDir) {
    Add-Check "App Directory" "PASS" "Located" $AppDir
} else {
    Add-Check "App Directory" "FAIL" "Not found" $AppDir
}

# Config file
if (Test-Path $ConfigFile) {
    Add-Check "Config File" "PASS" "Found" "config.yaml"
} else {
    Add-Check "Config File" "FAIL" "Not found" "config.yaml"
}

# Virtual environment
if (Test-Path $VenvDir) {
    Add-Check "Virtual Env" "PASS" "Exists" "venv/"
} else {
    Add-Check "Virtual Env" "WARN" "Not found" "Run: .\Setup-GemmaTrader.ps1"
}

# Logs directory
if (Test-Path $LogsDir) {
    $logCount = @(Get-ChildItem $LogsDir -ErrorAction SilentlyContinue).Count
    Add-Check "Logs Directory" "PASS" "Created" "logs/ ($logCount files)"
} else {
    Add-Check "Logs Directory" "WARN" "Not created yet" "Will be created on first run"
}

# Python executable
if (Test-Path $VenvPython) {
    Add-Check "Venv Python" "PASS" "Found" $VenvPython
} else {
    Add-Check "Venv Python" "WARN" "Not found" "Run: .\Setup-GemmaTrader.ps1"
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  3. DEPENDENCIES CHECK
# ─────────────────────────────────────────────────────────────────────────────

if (Test-Path $VenvPython) {
    Write-Host "  PYTHON DEPENDENCIES" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    $requiredModules = @(
        "flask",
        "flask_socketio",
        "pyyaml",
        "requests",
        "pandas",
        "pandas_ta",
        "numpy",
        "schedule",
        "eventlet"
    )

    $allDepsFound = $true
    foreach ($module in $requiredModules) {
        $checkResult = & $VenvPython -c "import $module" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Check $module "PASS" "Installed" ""
        } else {
            Add-Check $module "FAIL" "Missing" "Run: .\Setup-GemmaTrader.ps1 -InstallDeps"
            $allDepsFound = $false
        }
    }

    # MetaTrader5 (optional)
    $mt5Result = & $VenvPython -c "import MetaTrader5" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Check "MetaTrader5" "PASS" "Installed (optional)" "For MT5 trading"
    } else {
        Add-Check "MetaTrader5" "WARN" "Not installed (optional)" "For MT5 trading"
    }

    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
#  4. EXTERNAL SERVICES
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  EXTERNAL SERVICES" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Ollama
Write-Host "  Checking Ollama..." -ForegroundColor DarkGray

$ollamaRunning = $false
$ollamaVersion = "Unknown"
$gemmaModels = @()

try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    $ollamaRunning = $true

    # Check for models
    if ($response.models) {
        $gemmaModels = @($response.models | Where-Object { $_.name -like "*gemma*" })
    }
} catch {
    # Ollama not responding
}

if ($ollamaRunning) {
    if ($gemmaModels.Count -gt 0) {
        $modelNames = $gemmaModels.name -join ", "
        Add-Check "Ollama Service" "PASS" "Running" "Service active"
        Add-Check "Gemma Models" "PASS" "Available" $modelNames
    } else {
        Add-Check "Ollama Service" "PASS" "Running" "Service active"
        Add-Check "Gemma Models" "WARN" "Not found" "Run: ollama pull gemma4"
    }
} else {
    Add-Check "Ollama Service" "FAIL" "Not running" "Download from https://ollama.com"
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Add-Check "Ollama CLI" "PASS" "Installed" "But service not running"
    } else {
        Add-Check "Ollama CLI" "WARN" "Not installed" "Download from https://ollama.com"
    }
}

# MetaTrader 5
Write-Host "  Checking MetaTrader 5..." -ForegroundColor DarkGray

$mt5Proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if ($mt5Proc) {
    Add-Check "MetaTrader 5" "PASS" "Running" "PID $($mt5Proc.Id)"
} else {
    $mt5Found = $false
    $mt5Paths = @(
        "C:\Program Files\MetaTrader 5\terminal64.exe",
        "C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
    )
    foreach ($path in $mt5Paths) {
        if (Test-Path $path) { $mt5Found = $true; break }
    }

    if ($mt5Found) {
        Add-Check "MetaTrader 5" "INFO" "Installed but not running" "Needed for live trading"
    } else {
        Add-Check "MetaTrader 5" "WARN" "Not installed" "Optional - needed for MT5 live trading"
    }
}

# Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = & git --version
    Add-Check "Git" "PASS" "Installed" $gitVer
} else {
    Add-Check "Git" "INFO" "Not installed" "Optional - for version control"
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  5. PORTS
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  NETWORK PORTS" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$portsToCheck = @(
    @{ Port = 8050; Service = "Dashboard (default)" },
    @{ Port = 11434; Service = "Ollama API" }
)

foreach ($portInfo in $portsToCheck) {
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        if ($listener.Port -contains $portInfo.Port) {
            Add-Check "Port $($portInfo.Port)" "INFO" "In use" $portInfo.Service
        } else {
            Add-Check "Port $($portInfo.Port)" "PASS" "Available" $portInfo.Service
        }
    } catch {
        Add-Check "Port $($portInfo.Port)" "INFO" "Status unknown" $portInfo.Service
    }
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  6. CONFIGURATION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

if (Test-Path $ConfigFile) {
    Write-Host "  CONFIGURATION ANALYSIS" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    try {
        $config = Get-Content $ConfigFile | ConvertFrom-Yaml
        if ($config) {
            $mode = $config.trading.mode
            $port = $config.server.port
            $symbols = $config.trading.allowed_symbols.Count
            $model = $config.ollama.model

            Add-Check "Trading Mode" "INFO" "Configured as" $mode
            Add-Check "Dashboard Port" "INFO" "Configured as" $port
            Add-Check "Trading Symbols" "INFO" "Count" "$symbols symbols"
            Add-Check "Ollama Model" "INFO" "Configured as" $model
        }
    } catch {
        Add-Check "Config Parsing" "WARN" "Could not parse config.yaml" "Check YAML syntax"
    }
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  7. SUMMARY REPORT
# ─────────────────────────────────────────────────────────────────────────────

$passCount = @($checks | Where-Object { $_.Status -eq "PASS" }).Count
$warnCount = @($checks | Where-Object { $_.Status -eq "WARN" }).Count
$failCount = @($checks | Where-Object { $_.Status -eq "FAIL" }).Count
$infoCount = @($checks | Where-Object { $_.Status -eq "INFO" }).Count

Write-Host "  VERIFICATION SUMMARY" -ForegroundColor White
Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ Passed    : $passCount" -ForegroundColor Green
Write-Host "  ! Warnings  : $warnCount" -ForegroundColor Yellow
Write-Host "  ✗ Failed    : $failCount" -ForegroundColor Red
Write-Host "  i Info      : $infoCount" -ForegroundColor Cyan
Write-Host "  ════════════════════════════════════════════════════════" -ForegroundColor Cyan

Write-Host ""

if ($failCount -eq 0) {
    if ($warnCount -gt 0) {
        Write-Host "  STATUS: ⚠️  READY WITH WARNINGS" -ForegroundColor Yellow
        Write-Host "  The application can run, but fix warnings above" -ForegroundColor Yellow
    } else {
        Write-Host "  STATUS: ✅ FULLY OPERATIONAL" -ForegroundColor Green
        Write-Host "  All systems ready! You can start trading." -ForegroundColor Green
    }
} else {
    Write-Host "  STATUS: ❌ NOT READY" -ForegroundColor Red
    Write-Host "  Fix the failed items above before running." -ForegroundColor Red
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  8. RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  RECOMMENDATIONS" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$recommendations = @()

if ($failCount -gt 0) {
    $recommendations += "1. Fix all FAILED items above"
}

if (@($checks | Where-Object { $_.Name -eq "Ollama Service" -and $_.Status -eq "FAIL" }).Count -gt 0) {
    $recommendations += "2. Download and install Ollama from https://ollama.com"
}

if (@($checks | Where-Object { $_.Name -eq "Gemma Models" -and $_.Status -eq "WARN" }).Count -gt 0) {
    $recommendations += "2. Pull Gemma model: ollama pull gemma4"
}

if (@($checks | Where-Object { $_.Name -eq "Virtual Env" -and $_.Status -eq "WARN" }).Count -gt 0) {
    $recommendations += "3. Run setup: .\Setup-GemmaTrader.ps1"
}

if ($recommendations.Count -eq 0) {
    Write-Host "  All systems operational. Ready to trade!" -ForegroundColor Green
} else {
    foreach ($rec in $recommendations) {
        Write-Host "  • $rec" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "  Next Steps:" -ForegroundColor Green
Write-Host "  • Launch trading bot: .\Run-GemmaTrader.ps1" -ForegroundColor Cyan
Write-Host "  • Dashboard: http://localhost:8050" -ForegroundColor Cyan
Write-Host "  • Stop trading: .\Stop-GemmaTrader.ps1" -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  9. DETAILED OUTPUT (if requested)
# ─────────────────────────────────────────────────────────────────────────────

if ($Detailed) {
    Write-Host "  DETAILED CHECKS LOG" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""

    foreach ($check in $checks) {
        $color = switch ($check.Status) {
            "PASS" { "Green"  }
            "WARN" { "Yellow" }
            "FAIL" { "Red"    }
            "INFO" { "Cyan"   }
        }
        Write-Host "  [$($check.Status)]" -ForegroundColor $color -NoNewline
        Write-Host " $($check.Name)" -NoNewline
        Write-Host " - $($check.Message)" -ForegroundColor White
        if ($check.Details) {
            Write-Host "       Details: $($check.Details)" -ForegroundColor DarkGray
        }
    }

    Write-Host ""
}

if ($allPass -and $failCount -eq 0) {
    exit 0
} else {
    exit 1
}
