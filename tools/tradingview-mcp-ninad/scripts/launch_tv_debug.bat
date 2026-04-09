@echo off
REM Launch TradingView Desktop on Windows with Chrome DevTools Protocol enabled.
REM Usage: scripts\launch_tv_debug.bat [port]

set PORT=%1
if "%PORT%"=="" set PORT=9222

set TV_PATH=%LOCALAPPDATA%\TradingView\TradingView.exe
if not exist "%TV_PATH%" set TV_PATH=%PROGRAMFILES%\TradingView\TradingView.exe
if not exist "%TV_PATH%" set TV_PATH=%PROGRAMFILES(X86)%\TradingView\TradingView.exe

if not exist "%TV_PATH%" (
    echo TradingView not found. Install from https://www.tradingview.com/desktop/
    exit /b 1
)

taskkill /F /IM TradingView.exe >nul 2>&1
timeout /t 2 >nul

echo Launching TradingView with CDP on port %PORT%...
start "" "%TV_PATH%" --remote-debugging-port=%PORT%

echo Waiting for CDP...
for /L %%i in (1,1,15) do (
    curl -s http://localhost:%PORT%/json/version >nul 2>&1 && (
        echo TradingView ready on http://localhost:%PORT%
        exit /b 0
    )
    timeout /t 1 >nul
)

echo TradingView launched but CDP not ready yet. Try again in a few seconds.
