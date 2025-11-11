@echo off
cd /d "%~dp0"

echo ========================================
echo Starting Local Development Environment
echo ========================================
echo.

REM Stop existing Python processes
echo [1/4] Stopping existing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 1 /nobreak > nul

REM Start development server
echo [2/4] Starting development server...
set PYTHONIOENCODING=utf-8
start "Dev Server" cmd /k "cd /d %~dp0 && python render_server.py"

echo [3/4] Waiting for server to start...
timeout /t 5 /nobreak > nul

REM Sync latest data from production
echo [4/4] Syncing latest data from production server...
python sync_production_data.py

echo.
echo ========================================
echo Development Environment Ready!
echo ========================================
echo.
echo Dashboard: http://localhost:5000/
echo Production: https://tradingview-webhook-s5x1.onrender.com/
echo.
echo Usage:
echo   1. Open http://localhost:5000/ in browser
echo   2. Latest TradingView data is displayed
echo   3. To sync again: python sync_production_data.py
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

pause
