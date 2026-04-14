# ================================================================
#  TeleTrader -- Windows Server Deployment Script
# ================================================================
#
#  Deploys the TeleTrader system (Telegram Bot + API Server) on
#  a Windows Server so that MT5 EA can poll for trading signals.
#
#  Usage:
#    1. Open PowerShell as Administrator
#    2. Set-ExecutionPolicy Bypass -Scope Process -Force
#    3. .\deploy_windows.ps1 -BotToken "YOUR_BOT_TOKEN" -ApiId "12345" -ApiHash "abc123" -Phone "+919876543210" -Channels "signal_channel"
#
#  Recommended specs:
#    - 2+ CPU cores, 4+ GB RAM
#    - Windows Server 2019/2022 or Windows 10/11
#    - MetaTrader 5 installed (or use -SkipMT5)
#
# ================================================================

param(
    [string]$InstallDir    = "C:\TeleTrader",
    [string]$BotToken      = "",
    [string]$ChatId        = "",
    [string]$ApiId         = "",       # Telegram API ID (from my.telegram.org)
    [string]$ApiHash       = "",       # Telegram API Hash
    [string]$Phone         = "",       # Your phone number (e.g. +919876543210)
    [string]$Channels      = "",       # Comma-separated channel usernames to monitor
    [int]$ApiPort          = 8100,
    [string]$PythonVersion = "3.12.8",
    [switch]$SkipMT5,
    [switch]$ServiceOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

# ----------------------------------------------------------------
#  Helper functions
# ----------------------------------------------------------------
function Write-Step($num, $total, $msg) {
    Write-Host "`n[$num/$total] $msg" -ForegroundColor Yellow
}
function Write-OK($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}
function Write-Warn($msg) {
    Write-Host "  [!] $msg" -ForegroundColor Red
}
function Write-Info($msg) {
    Write-Host "  $msg" -ForegroundColor White
}

$TOTAL_STEPS = 10

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "     TeleTrader -- Windows Deployment" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "  Target directory : $InstallDir" -ForegroundColor White
Write-Host "  API port         : $ApiPort" -ForegroundColor White
Write-Host ""

# ----------------------------------------------------------------
#  Validate bot token early
# ----------------------------------------------------------------
if (-not $BotToken) {
    $BotToken = Read-Host "Enter your Telegram Bot Token (from @BotFather)"
    if (-not $BotToken) {
        Write-Warn "Bot token is required. Exiting."
        exit 1
    }
}

if ($ServiceOnly) {
    # Jump straight to service registration (steps 7-8)
    Write-Info "ServiceOnly mode -- skipping to startup scripts..."
    $stepOffset = 6
    goto :ServiceSetup  # PowerShell doesn't have goto, handled below
}

# ================================================================
#  STEP 1: System Prerequisites
# ================================================================
Write-Step 1 $TOTAL_STEPS "Installing system prerequisites..."

# Install Git if not present
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Info "Downloading Git..."
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/Git-2.47.1.2-64-bit.exe"
    $gitInstaller = "$env:TEMP\GitSetup.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller
    Start-Process -Wait -FilePath $gitInstaller -ArgumentList "/VERYSILENT", "/NORESTART"
    $env:PATH = "C:\Program Files\Git\cmd;" + $env:PATH
    Write-OK "Git installed"
} else {
    Write-OK "Git already installed"
}

# Visual C++ Redistributable
Write-Info "Ensuring Visual C++ Redistributable..."
$vcUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
$vcInstaller = "$env:TEMP\vc_redist.x64.exe"
Invoke-WebRequest -Uri $vcUrl -OutFile $vcInstaller -ErrorAction SilentlyContinue
Start-Process -Wait -FilePath $vcInstaller -ArgumentList "/quiet", "/norestart" -ErrorAction SilentlyContinue
Write-OK "Visual C++ Redistributable OK"

# ================================================================
#  STEP 2: Install Python
# ================================================================
Write-Step 2 $TOTAL_STEPS "Installing Python $PythonVersion..."

$pythonCheck = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCheck) {
    $pyUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
    $pyInstaller = "$env:TEMP\python-$PythonVersion-amd64.exe"
    Write-Info "Downloading Python $PythonVersion..."
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    Write-Info "Installing Python (this may take a minute)..."
    Start-Process -Wait -FilePath $pyInstaller -ArgumentList `
        "/quiet", "InstallAllUsers=1", "PrependPath=1", `
        "Include_pip=1", "Include_launcher=1"
    $env:PATH = "C:\Program Files\Python312;C:\Program Files\Python312\Scripts;" + $env:PATH
    Write-OK "Python $PythonVersion installed"
} else {
    $pyVer = python --version 2>&1
    Write-OK "Python already installed: $pyVer"
}

python -m pip install --upgrade pip 2>$null
Write-OK "pip upgraded"

# ================================================================
#  STEP 3: Install MetaTrader 5
# ================================================================
if (-not $SkipMT5) {
    Write-Step 3 $TOTAL_STEPS "Installing MetaTrader 5..."

    $mt5Paths = @(
        "C:\Program Files\MetaTrader 5\terminal64.exe",
        "C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
        "$env:APPDATA\MetaQuotes\Terminal\*\terminal64.exe"
    )
    $mt5Found = $false
    foreach ($p in $mt5Paths) {
        if (Test-Path $p) { $mt5Found = $true; break }
    }

    if (-not $mt5Found) {
        $mt5Url = "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
        $mt5Installer = "$env:TEMP\mt5setup.exe"
        Write-Info "Downloading MetaTrader 5..."
        Invoke-WebRequest -Uri $mt5Url -OutFile $mt5Installer
        Write-Info "Installing MetaTrader 5..."
        Start-Process -Wait -FilePath $mt5Installer -ArgumentList "/auto"
        Write-OK "MetaTrader 5 installed"
    } else {
        Write-OK "MetaTrader 5 already installed"
    }

    Write-Warn "MANUAL STEP: Open MT5, login to your broker, enable AutoTrading"
} else {
    Write-Step 3 $TOTAL_STEPS "Skipping MT5 (--SkipMT5)"
}

# ================================================================
#  STEP 4: Clone / Copy Project Files
# ================================================================
Write-Step 4 $TOTAL_STEPS "Setting up project directory at $InstallDir..."

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$repoUrl  = "https://github.com/ninad-k/AlgoStrategies.git"
$repoDir  = "$InstallDir\AlgoStrategies"
$teleDir  = "$repoDir\tools\teletrader"

if (-not (Test-Path $repoDir)) {
    Write-Info "Cloning repository..."
    git clone $repoUrl $repoDir
    Write-OK "Repository cloned"
} else {
    Write-Info "Pulling latest changes..."
    Push-Location $repoDir
    git pull origin main
    Pop-Location
    Write-OK "Repository updated"
}

# ================================================================
#  STEP 5: Python Virtual Environment + Dependencies
# ================================================================
Write-Step 5 $TOTAL_STEPS "Creating Python virtual environment and installing dependencies..."

$venvDir = "$InstallDir\venv"
if (-not (Test-Path "$venvDir\Scripts\python.exe")) {
    python -m venv $venvDir
    Write-OK "Virtual environment created"
} else {
    Write-OK "Virtual environment already exists"
}

& "$venvDir\Scripts\python.exe" -m pip install --upgrade pip
& "$venvDir\Scripts\pip.exe" install -e "$teleDir[telegram,forwarder]"
Write-OK "TeleTrader + dependencies installed (bot + forwarder)"

# ================================================================
#  STEP 6: Create .env Configuration
# ================================================================
Write-Step 6 $TOTAL_STEPS "Writing .env configuration..."

$envFile = "$InstallDir\.env"
$envContent = @"
# TeleTrader Configuration
# Generated by deploy_windows.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

TELETRADER_MODE=local
TELETRADER_API_PORT=$ApiPort

# Telegram Bot (for sending signals directly to the bot)
TELETRADER_TELEGRAM_BOT_TOKEN=$BotToken
TELETRADER_TELEGRAM_CHAT_ID=$ChatId

# Channel Forwarder (auto-copy signals from channels)
TELETRADER_TELEGRAM_API_ID=$ApiId
TELETRADER_TELEGRAM_API_HASH=$ApiHash
TELETRADER_TELEGRAM_PHONE=$Phone
TELETRADER_FORWARDER_CHANNELS=$Channels

# Storage (sqlite or memory)
TELETRADER_STORE_BACKEND=sqlite
TELETRADER_DB_PATH=$InstallDir\teletrader.db

# Logging
TELETRADER_LOG_FILE=$InstallDir\logs\teletrader.log
TELETRADER_LOG_LEVEL=INFO
"@
[System.IO.File]::WriteAllText($envFile, $envContent, [System.Text.UTF8Encoding]::new($false))
Write-OK "Configuration written to $envFile"

# Also copy to teletrader source dir so pydantic-settings picks it up
Copy-Item -Path $envFile -Destination "$teleDir\.env" -Force
Write-OK ".env copied to teletrader package directory"

# ================================================================
#  STEP 7: Create Logs Directory
# ================================================================
Write-Step 7 $TOTAL_STEPS "Initializing logs directory..."

$logsDir = "$InstallDir\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
Write-OK "Logs directory ready: $logsDir"

# ================================================================
#  STEP 8: Create Startup Scripts + Windows Service
# ================================================================
Write-Step 8 $TOTAL_STEPS "Creating startup scripts and registering service..."

# --- start_teletrader.bat (manual start) ---
$batchContent = @"
@echo off
echo =============================================
echo   TeleTrader -- Starting Services
echo =============================================
echo.

REM Change to install directory (where .env lives)
cd /d "$InstallDir"

REM Start the API server in a minimized window
echo Starting API server on port $ApiPort...
start "TeleTrader API" /min "$venvDir\Scripts\python.exe" -m uvicorn teletrader.api.app:app --host 127.0.0.1 --port $ApiPort

REM Wait briefly for API to be ready
timeout /t 3 /nobreak >nul

REM Start the Telegram bot in a minimized window
echo Starting Telegram bot...
start "TeleTrader Bot" /min "$venvDir\Scripts\python.exe" -m teletrader.telegram.bot

REM Wait briefly
timeout /t 2 /nobreak >nul

REM Start the Channel Forwarder in this window
echo Starting Channel Forwarder...
echo.
echo =============================================
echo   API:       http://127.0.0.1:$ApiPort/health
echo   Dashboard: http://127.0.0.1:$ApiPort/dashboard
echo   Bot:       Listening for direct signals
echo   Forwarder: Monitoring channels for signals
echo =============================================
echo.
"$venvDir\Scripts\python.exe" -m teletrader.telegram.forwarder

pause
"@
$batchContent | Out-File -FilePath "$InstallDir\start_teletrader.bat" -Encoding ascii
Write-OK "Created start_teletrader.bat"

# --- stop_teletrader.bat ---
$stopContent = @"
@echo off
echo Stopping TeleTrader services...

REM Kill uvicorn (API server)
taskkill /F /FI "WINDOWTITLE eq TeleTrader API" >nul 2>&1

REM Kill any python processes running teletrader modules
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%teletrader%%'" get processid /format:list ^| find "="') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo TeleTrader services stopped.
pause
"@
$stopContent | Out-File -FilePath "$InstallDir\stop_teletrader.bat" -Encoding ascii
Write-OK "Created stop_teletrader.bat"

# --- run_service.ps1 (for Task Scheduler) ---
# Use single-quoted here-string to avoid all variable expansion,
# then replace placeholders with actual values.
$serviceTemplate = @'
# TeleTrader -- Service Runner
# Starts API server, Telegram bot, and Channel Forwarder as background jobs
# Restarts them if they crash

$env:PATH = "C:\Program Files\Python312;C:\Program Files\Python312\Scripts;" + $env:PATH

$installDir = "__INSTALL_DIR__"
$venvPython = "__VENV_DIR__\Scripts\python.exe"
$logDir     = "__INSTALL_DIR__\logs"
$apiPort    = __API_PORT__

Set-Location $installDir

function Start-TeleTraderServices {
    $jobs = @()

    # Start API server
    $apiJob = Start-Job -Name "TeleTrader-API" -ArgumentList $venvPython, $installDir, $logDir, $apiPort -ScriptBlock {
        param($py, $dir, $logs, $port)
        Set-Location $dir
        & $py -m uvicorn teletrader.api.app:app --host 127.0.0.1 --port $port 2>&1 |
            Tee-Object -FilePath "$logs\api.log" -Append
    }
    $jobs += $apiJob

    Start-Sleep -Seconds 3

    # Start Telegram bot
    $botJob = Start-Job -Name "TeleTrader-Bot" -ArgumentList $venvPython, $installDir, $logDir -ScriptBlock {
        param($py, $dir, $logs)
        Set-Location $dir
        & $py -m teletrader.telegram.bot 2>&1 |
            Tee-Object -FilePath "$logs\bot.log" -Append
    }
    $jobs += $botJob

    Start-Sleep -Seconds 2

    # Start Channel Forwarder
    $fwdJob = Start-Job -Name "TeleTrader-Forwarder" -ArgumentList $venvPython, $installDir, $logDir -ScriptBlock {
        param($py, $dir, $logs)
        Set-Location $dir
        & $py -m teletrader.telegram.forwarder 2>&1 |
            Tee-Object -FilePath "$logs\forwarder.log" -Append
    }
    $jobs += $fwdJob

    return $jobs
}

Write-Output "[$(Get-Date)] TeleTrader service starting..."
$jobs = Start-TeleTraderServices

# Monitor and restart on failure
while ($true) {
    Start-Sleep -Seconds 30

    foreach ($job in $jobs) {
        if ($job.State -eq "Failed" -or $job.State -eq "Completed") {
            Write-Output "[$(Get-Date)] Job $($job.Name) exited ($($job.State)). Restarting..."
            Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
            $jobs = Start-TeleTraderServices
            break
        }
    }
}
'@
$serviceScript = $serviceTemplate `
    -replace '__INSTALL_DIR__', $InstallDir `
    -replace '__VENV_DIR__', $venvDir `
    -replace '__API_PORT__', $ApiPort
$serviceScript | Out-File -FilePath "$InstallDir\run_service.ps1" -Encoding utf8
Write-OK "Created run_service.ps1"

# --- Task Scheduler XML ---
$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>TeleTrader — Telegram signal relay for MetaTrader 5</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT60S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-ExecutionPolicy Bypass -File "$InstallDir\run_service.ps1"</Arguments>
      <WorkingDirectory>$InstallDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
$taskXml | Out-File -FilePath "$InstallDir\TeleTrader_Task.xml" -Encoding unicode
Write-OK "Created Task Scheduler XML"

# Register the scheduled task
Write-Info "Registering scheduled task..."
schtasks /Create /TN "TeleTrader" /XML "$InstallDir\TeleTrader_Task.xml" /F 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-OK "Scheduled task 'TeleTrader' registered (starts on boot)"
} else {
    Write-Warn "Could not register task -- run manually: schtasks /Create /TN TeleTrader /XML $InstallDir\TeleTrader_Task.xml /F"
}

# ================================================================
#  STEP 9: Copy MQL5 Files to MT5
# ================================================================
Write-Step 9 $TOTAL_STEPS "Copying MQL5 files to MetaTrader 5..."

$mql5Src = "$teleDir\mql5"

if (-not $SkipMT5) {
    # Auto-detect MT5 data folder
    $mt5DataRoot = "$env:APPDATA\MetaQuotes\Terminal"
    if (Test-Path $mt5DataRoot) {
        $terminals = Get-ChildItem -Path $mt5DataRoot -Directory
        foreach ($term in $terminals) {
            $mql5Dest = "$($term.FullName)\MQL5"
            if (Test-Path $mql5Dest) {
                # Copy EA
                $expertsDest = "$mql5Dest\Experts"
                if (-not (Test-Path $expertsDest)) { New-Item -ItemType Directory -Path $expertsDest -Force | Out-Null }
                Copy-Item -Path "$mql5Src\experts\TelegramSignalTrader_EA.mq5" -Destination $expertsDest -Force
                Write-OK "EA copied to $expertsDest"

                # Copy Include
                $includeDest = "$mql5Dest\Include"
                if (-not (Test-Path $includeDest)) { New-Item -ItemType Directory -Path $includeDest -Force | Out-Null }
                Copy-Item -Path "$mql5Src\include\PendingOrderManager.mqh" -Destination $includeDest -Force
                Write-OK "Include copied to $includeDest"

                Write-Info "MT5 terminal: $($term.FullName)"
            }
        }
    } else {
        Write-Warn "MT5 data folder not found at $mt5DataRoot"
        Write-Info "Manually copy files from: $mql5Src"
        Write-Info "  EA     -> MQL5\Experts\TelegramSignalTrader_EA.mq5"
        Write-Info "  Include -> MQL5\Include\PendingOrderManager.mqh"
    }
} else {
    Write-Info "MT5 skipped. MQL5 source files are at: $mql5Src"
}

# ================================================================
#  STEP 10: Verify Installation
# ================================================================
Write-Step 10 $TOTAL_STEPS "Verifying installation..."

$checks = @(
    @{Name="Python";     Cmd="python --version"},
    @{Name="pip";        Cmd="pip --version"},
    @{Name="Git";        Cmd="git --version"},
    @{Name="FastAPI";    Cmd="& '$venvDir\Scripts\python.exe' -c `"import fastapi; print(fastapi.__version__)`""},
    @{Name="Telegram";   Cmd="& '$venvDir\Scripts\python.exe' -c `"import telegram; print(telegram.__version__)`""},
    @{Name="Telethon";   Cmd="& '$venvDir\Scripts\python.exe' -c `"import telethon; print(telethon.__version__)`""},
    @{Name="TeleTrader"; Cmd="& '$venvDir\Scripts\python.exe' -c `"import teletrader; print('OK')`""},
    @{Name=".env";       Cmd="if (Test-Path '$envFile') { 'OK' } else { throw 'missing' }"},
    @{Name="Bot files";  Cmd="if (Test-Path '$teleDir\src\teletrader\telegram\bot.py') { 'OK' } else { throw 'missing' }"},
    @{Name="Forwarder";  Cmd="if (Test-Path '$teleDir\src\teletrader\telegram\forwarder.py') { 'OK' } else { throw 'missing' }"},
    @{Name="SQLite store"; Cmd="if (Test-Path '$teleDir\src\teletrader\store\sqlite_store.py') { 'OK' } else { throw 'missing' }"},
    @{Name="Dashboard";  Cmd="if (Test-Path '$teleDir\src\teletrader\static\dashboard.html') { 'OK' } else { throw 'missing' }"}
)

foreach ($check in $checks) {
    try {
        $result = Invoke-Expression $check.Cmd 2>&1
        Write-OK "$($check.Name): $result"
    } catch {
        Write-Warn "$($check.Name): FAILED"
    }
}

# Quick API health check
Write-Info "Testing API server..."
$apiProc = Start-Process -FilePath "$venvDir\Scripts\python.exe" `
    -ArgumentList "-m uvicorn teletrader.api.app:app --host 127.0.0.1 --port $ApiPort" `
    -WorkingDirectory $InstallDir `
    -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 4

try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 5
    Write-OK "API health check: $($health.Content)"
} catch {
    Write-Warn "API health check failed (may need manual start)"
}

# Stop the test API server
Stop-Process -Id $apiProc.Id -Force -ErrorAction SilentlyContinue

# ================================================================
#  DONE
# ================================================================

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Green
Write-Host "     TELETRADER SETUP COMPLETE!" -ForegroundColor Green
Write-Host "  =============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Files:" -ForegroundColor Cyan
Write-Host ("    Install dir : " + $InstallDir) -ForegroundColor White
Write-Host ("    Config      : " + $envFile) -ForegroundColor White
Write-Host ("    Start       : " + $InstallDir + "\start_teletrader.bat") -ForegroundColor White
Write-Host ("    Stop        : " + $InstallDir + "\stop_teletrader.bat") -ForegroundColor White
Write-Host ("    Logs        : " + $logsDir) -ForegroundColor White
Write-Host ("    MQL5 source : " + $mql5Src) -ForegroundColor White
Write-Host ""
Write-Host "  BEFORE FIRST RUN:" -ForegroundColor Yellow
Write-Host ""
if (-not $SkipMT5) {
    Write-Host "    1. Open MetaTrader 5 and login to your broker" -ForegroundColor White
    Write-Host "    2. Tools > Options > Expert Advisors > Allow WebRequest" -ForegroundColor White
    Write-Host ("       Add URL: http://127.0.0.1:" + $ApiPort) -ForegroundColor White
    Write-Host "    3. Attach TelegramSignalTrader_EA to any chart" -ForegroundColor White
    Write-Host "    4. Click AutoTrading button (must be GREEN)" -ForegroundColor White
    Write-Host ""
}
Write-Host "  FIRST-TIME FORWARDER SETUP:" -ForegroundColor Yellow
Write-Host "    The channel forwarder needs a one-time Telegram login." -ForegroundColor White
Write-Host "    Run this once manually to enter the verification code:" -ForegroundColor White
Write-Host ("      cd " + $InstallDir) -ForegroundColor White
Write-Host ("      " + $venvDir + "\Scripts\python.exe -m teletrader.telegram.forwarder") -ForegroundColor White
Write-Host "    After login, a session file is saved. Future starts are automatic." -ForegroundColor White
Write-Host ""
Write-Host "  SERVICES (3 processes):" -ForegroundColor Cyan
Write-Host ("    1. API Server   - stores signals (port " + $ApiPort + ")") -ForegroundColor White
Write-Host "    2. Telegram Bot - receives direct/forwarded signals" -ForegroundColor White
Write-Host "    3. Forwarder    - auto-copies from monitored channels" -ForegroundColor White
Write-Host ""
Write-Host "  TO START:" -ForegroundColor Cyan
Write-Host ("    Double-click : " + $InstallDir + "\start_teletrader.bat") -ForegroundColor White
Write-Host "    Or run       : schtasks /Run /TN TeleTrader" -ForegroundColor White
Write-Host ""
Write-Host "  TO STOP:" -ForegroundColor Cyan
Write-Host ("    Double-click : " + $InstallDir + "\stop_teletrader.bat") -ForegroundColor White
Write-Host ""
Write-Host "  LOGS:" -ForegroundColor Cyan
Write-Host ("    API:       " + $logsDir + "\api.log") -ForegroundColor White
Write-Host ("    Bot:       " + $logsDir + "\bot.log") -ForegroundColor White
Write-Host ("    Forwarder: " + $logsDir + "\forwarder.log") -ForegroundColor White
Write-Host ("    TeleTrader:" + $logsDir + "\teletrader.log") -ForegroundColor White
Write-Host ""
Write-Host "  DATABASE:" -ForegroundColor Cyan
Write-Host ("    SQLite:    " + $InstallDir + "\teletrader.db") -ForegroundColor White
Write-Host ""
Write-Host "  URLS:" -ForegroundColor Cyan
Write-Host ("    Health:    http://127.0.0.1:" + $ApiPort + "/health") -ForegroundColor White
Write-Host ("    Dashboard: http://127.0.0.1:" + $ApiPort + "/dashboard") -ForegroundColor White
Write-Host ""
