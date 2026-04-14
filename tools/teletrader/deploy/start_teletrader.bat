@echo off
echo =============================================
echo   TeleTrader -- Starting Services
echo =============================================
echo.

REM Default install directory -- update if you installed elsewhere
set INSTALL_DIR=C:\TeleTrader
set VENV_DIR=%INSTALL_DIR%\venv
set API_PORT=8100

REM Change to install directory (where .env lives)
cd /d "%INSTALL_DIR%"

REM Check venv exists
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at %VENV_DIR%
    echo Run deploy_windows.ps1 first.
    pause
    exit /b 1
)

REM Start the API server in a minimized window
echo Starting API server on port %API_PORT%...
start "TeleTrader API" /min "%VENV_DIR%\Scripts\python.exe" -m uvicorn teletrader.api.app:app --host 127.0.0.1 --port %API_PORT%

REM Wait for API to be ready
timeout /t 3 /nobreak >nul

REM Start the Telegram bot in a minimized window
echo Starting Telegram bot...
start "TeleTrader Bot" /min "%VENV_DIR%\Scripts\python.exe" -m teletrader.telegram.bot

REM Wait briefly
timeout /t 2 /nobreak >nul

REM Start the Channel Forwarder in a minimized window
echo Starting Channel Forwarder...
start "TeleTrader Forwarder" /min "%VENV_DIR%\Scripts\python.exe" -m teletrader.telegram.forwarder

REM Wait briefly for all services to initialize
timeout /t 2 /nobreak >nul

echo.
echo =============================================
echo   All services started!
echo.
echo   API:       http://127.0.0.1:%API_PORT%/health
echo   Dashboard: http://127.0.0.1:%API_PORT%/dashboard
echo   Bot:       Listening for direct signals
echo   Forwarder: Monitoring channels for signals
echo =============================================
echo.

REM Open dashboard in default browser
echo Opening dashboard in browser...
start "" "http://127.0.0.1:%API_PORT%/dashboard"

echo.
echo Press any key to stop all TeleTrader services...
pause >nul

echo Stopping TeleTrader services...
taskkill /F /FI "WINDOWTITLE eq TeleTrader API" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TeleTrader Bot" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TeleTrader Forwarder" >nul 2>&1
echo TeleTrader services stopped.

pause
