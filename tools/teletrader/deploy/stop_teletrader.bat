@echo off
echo =============================================
echo   TeleTrader -- Stopping Services
echo =============================================
echo.

REM Kill the API server and Bot windows
taskkill /F /FI "WINDOWTITLE eq TeleTrader API" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TeleTrader Bot" >nul 2>&1

REM Kill any python processes running teletrader modules
for /f "tokens=2 delims==" %%a in ('wmic process where "commandline like '%%teletrader%%'" get processid /value 2^>nul ^| find "="') do (
    echo Stopping process %%a...
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill any uvicorn processes on the TeleTrader port
for /f "tokens=2 delims==" %%a in ('wmic process where "commandline like '%%uvicorn%%teletrader%%'" get processid /value 2^>nul ^| find "="') do (
    echo Stopping uvicorn %%a...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo TeleTrader services stopped.
pause
