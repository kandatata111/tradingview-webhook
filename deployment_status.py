"""
デプロイ状況と次のステップ
"""
import requests

print("=" * 60)
print("デプロイ状況レポート")
print("=" * 60)

# 本番サーバー確認
prod_url = 'https://tradingview-webhook-s5x1.onrender.com'

print("\n✅ 本番サーバー: 稼働中")
print(f"   URL: {prod_url}")

try:
    response = requests.get(f"{prod_url}/current_states", timeout=10)
    data = response.json()
    
    if data['states']:
        print(f"   データ: {len(data['states'])} 件")
        state = data['states'][0]
        print(f"   最終更新: {state['timestamp']}")
        
        # topPrice/bottomPrice確認
        cloud_5m = state['clouds'].get('5m', {})
        if 'topPrice' in cloud_5m:
            print(f"   ✅ topPrice/bottomPrice サポート: あり")
        else:
            print(f"   ❌ topPrice/bottomPrice サポート: なし")
    else:
        print(f"   データ: なし (TradingViewからのアラート待ち)")
        
except Exception as e:
    print(f"   ❌ エラー: {e}")

print("\n" + "=" * 60)
print("次のステップ")
print("=" * 60)

print("\n【重要】本番サーバーのデータベースは空です")
print("\nTradingViewから新しいアラートを送信する必要があります:")
print("\n1. TradingViewでチャートを開く")
print("2. 「ダウ雲3」インジケーターを追加")
print("3. アラート作成:")
print("   - 条件: インジケーター「ダウ雲3」")
print("   - Webhook URL: https://tradingview-webhook-s5x1.onrender.com/webhook")
print("   - メッセージ: インジケーターのアラートメッセージをそのまま使用")
print("4. アラートが発火するまで待つ")
print("\n💡 または、手動でテストデータを送信:")
print(f"   curl -X POST {prod_url}/webhook \\")
print('   -H "Content-Type: application/json" \\')
print('   -d @test_data.json')

print("\n" + "=" * 60)
