@echo off
cd /d "%~dp0"

echo ========================================
echo 🚀 TradingView Webhook 統合テスト
echo ========================================
echo.

echo 📋 テスト内容:
echo 1. 本番サーバーへのテストデータ送信
echo 2. Webダッシュボードでデータ表示確認
echo.

echo 🧪 テストデータ送信中...
echo.

REM Pythonでテストデータを送信
python clear_and_test_prod.py

if %errorlevel% equ 0 (
    echo.
    echo ✅ テスト完了
    echo.
    echo 🎯 確認事項:
    echo - Webダッシュボードでデータが表示されているか？
    echo - topPrice/bottomPriceが正しく表示されているか？
    echo - 価格が雲の範囲内の場合、★マークが表示されているか？
    echo.
    echo 🌐 本番ダッシュボード: https://tradingview-webhook-s5x1.onrender.com/
    echo 🌐 ローカルダッシュボード: http://localhost:5000/
    echo.
) else (
    echo.
    echo ❌ テスト失敗
    echo    エラーログを確認してください
    echo.
)

pause