@echo off
REM Apply latest production JSON to local test server (double-click to run)
REM 1) Starts the local server (using the venv python), 2) waits until server is ready,
REM 3) downloads production JSON, 4) POSTs it to local /webhook, 5) opens dashboard in browser.

cd /d "%~dp0"

:: Path to venv python - adjust if your venv is elsewhere
set VENV_PY=C:\Users\kanda\Desktop\PythonData\venv\Scripts\python.exe

:: Production endpoint to pull JSON from. Change if needed (e.g. /fire_history)
set PROD_URL=https://tradingview-webhook-s5x1.onrender.com/current_states

:START_SERVER
echo Checking if local server at http://127.0.0.1:5000/ is already responding...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; Write-Host 'Local server responding'; exit 0 } catch { Write-Host 'No local server response'; exit 1 }" > "%~dp0check_server.log" 2>&1
if %errorlevel%==0 (
  echo Local server is already running. Skipping start.
) else (
  echo Starting local test server using %VENV_PY% ...
  REM Use cmd /c to ensure stdout/stderr redirection for the started process
  start "TVWebhook Server" cmd /c ""%VENV_PY%" "%~dp0render_server.py" > "%~dp0server_output.log" 2>&1"
  echo Server stdout/stderr will be saved to %~dp0server_output.log
)

echo Waiting for local server to become available at http://127.0.0.1:5000/ ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$uri='http://127.0.0.1:5000/'; for ($i=0; $i -lt 60; $i++) { try { $r=Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; if ($r.StatusCode -eq 200) { Write-Host 'Server is up'; exit 0 } } catch { Start-Sleep -Seconds 1 } }; Write-Host 'Timed out waiting for server'; exit 1"  > "%~dp0wait_server.log" 2>&1
if errorlevel 1 (
  echo Server did not start within timeout. Check %~dp0server_output.log and %~dp0wait_server.log for details.
  if exist "%~dp0server_output.log" (
    echo Opening server_output.log...
    start "" "%~dp0server_output.log"
  ) else (
    echo server_output.log not found.
  )
  echo Opening wait_server.log...
  if exist "%~dp0wait_server.log" start "" "%~dp0wait_server.log"
  pause
  goto :eof
)

:FETCH_AND_POST
echo Downloading production JSON from %PROD_URL% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%PROD_URL%' -UseBasicParsing -OutFile '%~dp0latest_prod.json' -ErrorAction Stop; Write-Host 'Saved to latest_prod.json' } catch { Write-Host 'Failed to download from %PROD_URL%'; exit 1 }"
if errorlevel 1 (
  echo Failed to download production JSON. Aborting.
  pause
  goto :eof
)

:: Post the saved JSON to local /webhook endpoint
echo Posting production JSON to local test /webhook ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $body = Get-Content -Raw -Path '%~dp0latest_prod.json'; Invoke-RestMethod -Uri 'http://127.0.0.1:5000/webhook' -Method Post -ContentType 'application/json' -Body $body -ErrorAction Stop; Write-Host 'Posted to /webhook' } catch { Write-Host 'POST failed:'; Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
  echo POST failed. See message above.
  pause
  goto :eof
)

:: Open dashboard in default browser
echo Opening local dashboard...
start "" "http://127.0.0.1:5000/"
echo Done. Check the browser to see test web table updated. If the data structure differs you may need to extract the correct object from latest_prod.json and POST it instead.
pause
exit /b 0
