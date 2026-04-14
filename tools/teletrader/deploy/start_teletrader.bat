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

REM Start the Channel Forwarder in this window
echo Starting Channel Forwarder...
echo.
echo =============================================
echo   API:       http://127.0.0.1:%API_PORT%/health
echo   Bot:       Listening for direct signals
echo   Forwarder: Monitoring channels for signals
echo =============================================
echo.
"%VENV_DIR%\Scripts\python.exe" -m teletrader.telegram.forwarder

pause
