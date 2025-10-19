# Pine表完全再現テストスクリプト

Write-Host "サーバー起動確認中..." -ForegroundColor Cyan

# サーバー起動待機
Start-Sleep -Seconds 3

# テストデータ送信
Write-Host "`nUSDJPY データ送信中..." -ForegroundColor Yellow

$body = @{
    symbol = "USDJPY"
    tf = "5m"
    price = 149.856
    daily_dow = @{
        status = "ダウ"
        bos = "BOS-3"
        time = "00/10:05"
    }
    swing_dow = @{
        status = "ダウ+"
        bos = "BOS+1"
        time = "00/08:40"
    }
    cloud_order = @("4H", "5m", "15m", "1H")
    clouds = @(
        @{
            label = "5m"
            gc = $true
            fire_count = 8
            thickness = 3.1
            angle = 31.9
            elapsed = "00/04:45"
            distance_from_price = 8.6
            distance_from_prev = 8.6
        },
        @{
            label = "15m"
            gc = $true
            fire_count = 6
            thickness = 5.2
            angle = 30.2
            elapsed = "00/09:45"
            distance_from_price = 6.3
            distance_from_prev = 15.0
        },
        @{
            label = "1H"
            gc = $true
            fire_count = 1
            thickness = 27.7
            angle = 29.6
            elapsed = "00/03:10"
            distance_from_price = 1.0
            distance_from_prev = 14.6
        },
        @{
            label = "4H"
            gc = $false
            fire_count = 0
            thickness = 35.5
            angle = -2.8
            elapsed = "03/01:45"
            distance_from_price = -29.6
            distance_from_prev = -2.8
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri 'http://localhost:5000/webhook' -Method Post -Body $body -ContentType 'application/json'
    Write-Host "✓ USDJPY送信成功!" -ForegroundColor Green
    Write-Host "  通知数: $($response.notifications)" -ForegroundColor Gray
} catch {
    Write-Host "✗ エラー: $_" -ForegroundColor Red
}

Write-Host "`nブラウザで http://localhost:5000 を確認してください!" -ForegroundColor Cyan
