"""
Renderのデプロイ状況を確認
"""
import requests
import time

PRODUCTION_URL = 'https://tradingview-webhook-s5x1.onrender.com'

print("🔍 Renderデプロイ状況確認")
print("=" * 60)

# ヘルスチェック
print("\n[1] サーバーの応答確認...")
try:
    response = requests.get(f"{PRODUCTION_URL}/", timeout=10)
    print(f"✅ ステータスコード: {response.status_code}")
    print(f"✅ サーバーは稼働中")
except Exception as e:
    print(f"❌ サーバーに接続できません: {e}")
    print("⏳ デプロイ中の可能性があります")
    exit()

# APIバージョン確認（render_server.pyに__version__があれば）
print("\n[2] current_states エンドポイント確認...")
try:
    response = requests.get(f"{PRODUCTION_URL}/current_states", timeout=10)
    data = response.json()
    
    if data['states']:
        state = data['states'][0]
        print(f"✅ データ取得成功")
        print(f"   シンボル: {state['symbol']}")
        print(f"   価格: {state['price']}")
        print(f"   タイムスタンプ: {state['timestamp']}")
        
        # topPrice/bottomPriceの確認
        print("\n[3] topPrice/bottomPrice チェック...")
        has_top_bottom = False
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            if 'topPrice' in cloud:
                has_top_bottom = True
                print(f"   {tf}: topPrice={cloud['topPrice']}, bottomPrice={cloud['bottomPrice']}")
        
        if not has_top_bottom:
            print("   ❌ topPrice/bottomPrice が存在しません")
            print("\n📌 原因:")
            print("   - TradingViewのインジケーターが古いバージョン")
            print("   - または送信されているJSONにtopPrice/bottomPriceが含まれていない")
            print("\n💡 解決策:")
            print("   1. TradingViewのチャートで「ダウ雲3」インジケーターを確認")
            print("   2. アラート条件で最新のJSONフォーマットを使用しているか確認")
            print("   3. テスト送信: Webhook URLにPOSTリクエストを送信")
        else:
            print("   ✅ topPrice/bottomPrice が正しく含まれています")
            
except Exception as e:
    print(f"❌ エラー: {e}")

print("\n" + "=" * 60)
print("デプロイ確認完了")
print("=" * 60)
