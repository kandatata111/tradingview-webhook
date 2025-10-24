import requests
import os

# 本番サーバーにリクエスト
url = "https://tradingview-webhook-s5x1.onrender.com/debug_db"

print("🔍 本番データベースのカラム情報を取得...")
r = requests.get(url)

if r.status_code == 200:
    print("✅ レスポンス受信")
    print(r.text)
else:
    print(f"❌ エラー: {r.status_code}")
    print(r.text)
