# Webhook テストスクリプト

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "ダウ雲アラートシステム テスト" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. ヘルスチェック
Write-Host "[1/3] ヘルスチェック..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri http://localhost:5000/health -Method GET
    Write-Host "✓ サーバー稼働中" -ForegroundColor Green
    Write-Host "  レスポンス: $($health.Content)" -ForegroundColor Gray
} catch {
    Write-Host "✗ サーバーに接続できません" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 2. Webhook送信テスト
Write-Host "[2/3] Webhook送信テスト..." -ForegroundColor Yellow

$testJson = '{"symbol":"USDJPY","tf":"5","time":1760621400000,"price":151.219,"clouds":[{"label":"5m","tf":"5m","gc":true,"fire_count":1,"max_reached":false,"thickness":1.23,"angle":-21.88,"elapsed":80},{"label":"15m","tf":"15m","gc":false,"fire_count":0,"max_reached":false,"thickness":0.11,"angle":-24.63,"elapsed":103},{"label":"1H","tf":"1H","gc":true,"fire_count":2,"max_reached":false,"thickness":0.29,"angle":1.55,"elapsed":95},{"label":"4H","tf":"4H","gc":false,"fire_count":0,"max_reached":false,"thickness":23.06,"angle":-12.86,"elapsed":2540}]}'

try {
    $webhook = Invoke-WebRequest -Uri http://localhost:5000/webhook -Method POST -ContentType "application/json" -Body $testJson
    Write-Host "✓ Webhook受信成功" -ForegroundColor Green
    Write-Host "  レスポンス: $($webhook.Content)" -ForegroundColor Gray
} catch {
    Write-Host "✗ Webhook送信エラー" -ForegroundColor Red
    Write-Host "  エラー: $_" -ForegroundColor Red
}

Write-Host ""

# 3. アラート履歴確認
Write-Host "[3/3] アラート履歴確認..." -ForegroundColor Yellow
try {
    $alerts = Invoke-WebRequest -Uri http://localhost:5000/alerts -Method GET
    $alertsData = $alerts.Content | ConvertFrom-Json
    Write-Host "✓ アラート履歴取得成功" -ForegroundColor Green
    Write-Host "  保存件数: $($alertsData.alerts.Count)" -ForegroundColor Gray
} catch {
    Write-Host "✗ アラート履歴取得エラー" -ForegroundColor Red
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "テスト完了！" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Yellow
Write-Host "  1. ブラウザで http://localhost:5000 を開く" -ForegroundColor White
Write-Host "  2. Webダッシュボードを確認" -ForegroundColor White
Write-Host "  3. local_client.py を起動してデスクトップ通知をテスト" -ForegroundColor White
