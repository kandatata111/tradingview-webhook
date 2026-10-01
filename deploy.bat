@echo off
chcp 65001 >nul
cls
echo ====================================
echo   Deploy to Render.com Production
echo ====================================
echo.
echo Starting deployment process...
echo.

REM Check if in git repository
echo [Step 1/6] Checking Git repository...
cd /d C:\Users\kanda\Desktop\PythonData\TradingViewWebhook
git status >nul 2>&1
if errorlevel 1 (
    echo    ^> ERROR: Not a git repository
    pause
    exit /b 1
)
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Pull latest changes from remote
echo [Step 2/6] Pulling latest changes from GitHub...
git pull origin main --rebase
if errorlevel 1 (
    echo    ^> WARNING: Pull had conflicts or failed
    echo    ^> Attempting to continue...
)
echo    ^> Done
timeout /t 1 /nobreak >nul

REM 本番(Render)の最新のヒートマップ状態をダウンロードしてから取り込む
REM (webhook_data.db と同じやり方: このファイルをGitにコミットして一緒にデプロイすることで、
REM  Renderの無料プラン=永続ディスク無しでも「前回デプロイ時点の状態」を引き継げるようにする。
REM  ダウンロードに失敗しても(本番がまだ起動していない等)デプロイ自体は続行する)
echo [Step 4.5/7] Downloading latest heatmap state from production...
curl -fsS -o angle_state.json https://tradingview-webhook-s5x1.onrender.com/download_angle_state
if errorlevel 1 (
    echo    ^> WARNING: angle_state.json のダウンロードに失敗しました(継続します)
) else (
    echo    ^> angle_state.json を更新しました
)
curl -fsS -o dow_alert_history.json https://tradingview-webhook-s5x1.onrender.com/download_dow_alert_history
if errorlevel 1 (
    echo    ^> WARNING: dow_alert_history.json のダウンロードに失敗しました(継続します)
) else (
    echo    ^> dow_alert_history.json を更新しました
)
timeout /t 1 /nobreak >nul

REM Add all changes
echo [Step 5/7] Adding changes to Git...
git add .
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Ensure requirements_render.txt exists
echo [Step 5.5/7] Ensuring requirements_render.txt exists...
if not exist requirements_render.txt (
    echo    ^> Creating requirements_render.txt from requirements.txt
    copy requirements.txt requirements_render.txt
    REM Remove problematic packages for Render
    powershell -Command "(Get-Content requirements_render.txt) -replace 'playsound2==1.3.0', '' | Set-Content requirements_render.txt"
)
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Add requirements_render.txt if created
echo [Step 5.6/7] Adding requirements_render.txt...
git add requirements_render.txt
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Commit changes
echo [Step 6/7] Committing changes...
set commit_msg=Deploy: Update dashboard and fix requirements - %date% %time%
git commit -m "%commit_msg%"
if errorlevel 1 (
    echo    ^> No changes to commit
) else (
    echo    ^> Committed successfully
)
timeout /t 1 /nobreak >nul

REM Push to GitHub (using main branch)
echo [Step 7/7] Pushing to GitHub...
git push origin HEAD:main
if errorlevel 1 (
    echo    ^> ERROR: Failed to push to GitHub
    echo    ^> Trying alternative push...
    git push origin HEAD:main --force-with-lease
    if errorlevel 1 (
        echo    ^> ERROR: All push attempts failed
        pause
        exit /b 1
    )
)
echo    ^> Pushed to GitHub successfully
timeout /t 1 /nobreak >nul

REM Notify about Render deployment
echo [Step 7/7] Triggering Render deployment...
echo    ^> Changes pushed to GitHub
echo    ^> Render will auto-deploy in a few moments
timeout /t 1 /nobreak >nul

echo.
echo ====================================
echo   DEPLOYMENT COMPLETED SUCCESSFULLY!
echo ====================================
echo.
echo Your changes have been pushed to GitHub.
echo Render.com will automatically deploy the latest commit.
echo.
echo Production URL:
echo   https://tradingview-webhook-s5x1.onrender.com/
echo.
echo Please wait 1-2 minutes for Render to complete deployment.
echo Check deployment status at:
echo   https://dashboard.render.com/
echo.
echo ====================================

pause
