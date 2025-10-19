# 簡易テストスクリプト

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "ダウ雲システム 動作確認" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# ヘルスチェック
Write-Host "【1】 ヘルスチェック..." -ForegroundColor Yellow
$response1 = Invoke-RestMethod -Uri "http://localhost:5000/health" -Method GET
Write-Host "結果: $($response1.status)" -ForegroundColor Green
Write-Host ""

# Webhook送信
Write-Host "【2】 Webhook送信テスト..." -ForegroundColor Yellow
$json = '{"symbol":"USDJPY","tf":"5","price":151.219,"clouds":[{"label":"5m","tf":"5m","gc":true,"fire_count":1,"max_reached":false,"thickness":1.23,"angle":-21.88,"elapsed":80},{"label":"1H","tf":"1H","gc":true,"fire_count":2,"max_reached":false,"thickness":0.29,"angle":1.55,"elapsed":95}]}'
$response2 = Invoke-RestMethod -Uri "http://localhost:5000/webhook" -Method POST -ContentType "application/json" -Body $json
Write-Host "結果: $($response2.status)" -ForegroundColor Green
Write-Host "通知数: $($response2.notifications)" -ForegroundColor Green
Write-Host ""

# アラート履歴
Write-Host "【3】 アラート履歴確認..." -ForegroundColor Yellow
$response3 = Invoke-RestMethod -Uri "http://localhost:5000/alerts" -Method GET
Write-Host "結果: $($response3.status)" -ForegroundColor Green
Write-Host "保存件数: $($response3.alerts.Count)" -ForegroundColor Green
Write-Host ""

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✓ すべてのテスト成功！" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Yellow
Write-Host "  ブラウザで http://localhost:5000 を開いてください" -ForegroundColor White
