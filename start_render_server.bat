@echo off
rem TradingViewWebhook render_server startup wrapper for Task Scheduler
set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%..\venv\Scripts\python.exe
cd /d "%SCRIPT_DIR%"
"%PYTHON%" "%SCRIPT_DIR%render_server.py" >> "%SCRIPT_DIR%render_server_task.log" 2>&1
