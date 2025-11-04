@echo off
cd /d "%~dp0"

echo ========================================
echo Local Development Environment
echo ========================================

REM Stop existing Python processes
echo Stopping existing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 1 /nobreak > nul

REM Start development server
echo Starting development server...
set PYTHONIOENCODING=utf-8
start "Dev Server" cmd /k "cd /d %~dp0 && python render_server.py"

echo Waiting for server to start...
timeout /t 5 /nobreak > nul

REM Sync latest data from production
echo.
echo Syncing latest data from production server...
python sync_production_data.py

echo.
echo ========================================
echo Development Environment Ready!
echo ========================================
echo.
echo Dashboard: http://localhost:5000/
echo Production: https://tradingview-webhook-s5x1.onrender.com/
echo.
echo To sync latest data again: python sync_production_data.py
echo.
echo Press Ctrl+C to stop
echo ========================================

pause
