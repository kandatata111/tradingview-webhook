@echo off
echo ========================================
echo 🚀 TradingView Webhook 統合テスト
echo ========================================
echo.

echo 📋 テスト内容:
echo 1. ローカルクライアント起動確認
echo 2. Renderサーバーへのテストデータ送信
echo 3. LINE通知・デスクトップ通知・音声再生確認
echo.

echo ⚠️  事前準備:
echo - local_client.py が起動していること
echo - ngrok が http 5001 を公開していること
echo - Render環境変数 LOCAL_CLIENT_URL が設定されていること
echo - LINE_NOTIFY_TOKEN が設定されていること
echo.

set /p RENDER_URL="RenderアプリのURLを入力 (例: https://your-app.onrender.com): "
if "%RENDER_URL%"=="" (
    echo ❌ Render URLが入力されていません
    pause
    exit /b 1
)

echo.
echo 🧪 テストデータ送信中...
echo.

curl -X POST "%RENDER_URL%/webhook" ^
     -H "Content-Type: application/json" ^
     -d "{ ^
  \"symbol\":\"USDJPY\", ^
  \"tf\":\"5\", ^
  \"time\":1760621400000, ^
  \"price\":151.219, ^
  \"clouds\":[ ^
    {\"label\":\"5m\",\"tf\":\"5m\",\"gc\":true,\"fire_count\":1,\"max_reached\":false,\"thickness\":1.22,\"angle\":-21.88,\"elapsed\":80}, ^
    {\"label\":\"15m\",\"tf\":\"15m\",\"gc\":false,\"fire_count\":0,\"max_reached\":false,\"thickness\":0.11,\"angle\":-24.63,\"elapsed\":103}, ^
    {\"label\":\"1H\",\"tf\":\"1H\",\"gc\":true,\"fire_count\":2,\"max_reached\":false,\"thickness\":0.28,\"angle\":1.55,\"elapsed\":95}, ^
    {\"label\":\"4H\",\"tf\":\"4H\",\"gc\":false,\"fire_count\":0,\"max_reached\":false,\"thickness\":23.06,\"angle\":-12.85,\"elapsed\":2540} ^
  ] ^
}"

echo.
echo ✅ テスト完了
echo.
echo 🎯 確認事項:
echo - LINEアプリに通知が届いたか？
echo - デスクトップ通知が表示されたか？
echo - 音声 (short_up.wav) が再生されたか？
echo - Webダッシュボードでデータが表示されたか？
echo.
echo 🌐 ダッシュボード確認: %RENDER_URL%
echo.

pause