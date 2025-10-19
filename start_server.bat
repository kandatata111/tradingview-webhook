@echo off
echo ========================================
echo 🚀 TradingView Webhook Server 起動
echo ========================================
echo.

cd /d "%~dp0"

echo 📍 カレントディレクトリ: %CD%
echo.

echo 🔧 必要なパッケージを確認中...
python -c "import psycopg2" 2>nul
if %errorlevel% neq 0 (
    echo ❌ psycopg2が見つかりません。インストールしてください:
    echo    pip install psycopg2-binary
    echo.
    pause
    exit /b 1
) else (
    echo ✅ psycopg2 OK
)

python -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Flaskが見つかりません。インストールしてください:
    echo    pip install flask
    echo.
    pause
    exit /b 1
) else (
    echo ✅ Flask OK
)

echo.
echo 🔧 仮想環境をアクティベート中...
if exist "..\venv\Scripts\activate.bat" (
    call ..\venv\Scripts\activate.bat
    echo ✅ 仮想環境アクティベート成功
) else (
    echo ⚠️  仮想環境が見つからないため、システムPythonを使用します
)

echo.
echo 🚀 サーバー起動中...
echo 📡 Webhook URL: http://localhost:5000/webhook
echo 🌐 ダッシュボード: http://localhost:5000
echo 🛑 停止するには Ctrl+C を押してください
echo.

python render_server.py

echo.
echo 🛑 サーバーが停止しました
pause
