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
echo [Step 1/5] Checking Git repository...
cd /d C:\Users\kanda\Desktop\PythonData\TradingViewWebhook
git status >nul 2>&1
if errorlevel 1 (
    echo    ^> ERROR: Not a git repository
    pause
    exit /b 1
)
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Add all changes
echo [Step 2/5] Adding changes to Git...
git add .
echo    ^> Done
timeout /t 1 /nobreak >nul

REM Commit changes
echo [Step 3/5] Committing changes...
set commit_msg=Update dashboard - %date% %time%
git commit -m "%commit_msg%"
if errorlevel 1 (
    echo    ^> No changes to commit
) else (
    echo    ^> Committed successfully
)
timeout /t 1 /nobreak >nul

REM Push to GitHub
echo [Step 4/5] Pushing to GitHub...
git push origin master
if errorlevel 1 (
    echo    ^> ERROR: Failed to push to GitHub
    pause
    exit /b 1
)
echo    ^> Pushed to GitHub successfully
timeout /t 1 /nobreak >nul

REM Notify about Render deployment
echo [Step 5/5] Triggering Render deployment...
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
