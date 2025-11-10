"""
問題診断レポート
"""
import requests
import json

print("=" * 60)
print("問題診断: topPrice/bottomPrice が 0.0 になっている")
print("=" * 60)

# 本番サーバーのデータを取得
print("\n[1] 本番サーバーのデータを確認...")
prod_response = requests.get('https://tradingview-webhook-s5x1.onrender.com/current_states')
prod_data = prod_response.json()

# ローカルサーバーのデータを取得
print("[2] ローカルサーバーのデータを確認...")
local_response = requests.get('http://localhost:5000/current_states')
local_data = local_response.json()

print("\n" + "=" * 60)
print("本番サーバー (TradingViewから受信)")
print("=" * 60)
if prod_data['states']:
    state = prod_data['states'][0]
    print(f"シンボル: {state['symbol']}")
    print(f"価格: {state['price']}")
    print(f"タイムスタンプ: {state['timestamp']}")
    print(f"\n雲データ:")
    for tf in ['5m', '15m', '1H', '4H']:
        cloud = state['clouds'].get(tf, {})
        top = cloud.get('topPrice', 'なし')
        bottom = cloud.get('bottomPrice', 'なし')
        print(f"  {tf}: topPrice={top}, bottomPrice={bottom}")
    
    print(f"\nダウ理論:")
    print(f"  Daily: {state.get('daily_dow', {})}")
    print(f"  Swing: {state.get('swing_dow', {})}")

print("\n" + "=" * 60)
print("ローカルサーバー (本番から同期)")
print("=" * 60)
if local_data['states']:
    state = local_data['states'][0]
    print(f"シンボル: {state['symbol']}")
    print(f"価格: {state['price']}")
    print(f"タイムスタンプ: {state['timestamp']}")
    print(f"\n雲データ:")
    for tf in ['5m', '15m', '1H', '4H']:
        cloud = state['clouds'].get(tf, {})
        top = cloud.get('topPrice', 'なし')
        bottom = cloud.get('bottomPrice', 'なし')
        print(f"  {tf}: topPrice={top}, bottomPrice={bottom}")
    
    print(f"\nダウ理論:")
    print(f"  Daily: {state.get('daily_dow', {})}")
    print(f"  Swing: {state.get('swing_dow', {})}")

print("\n" + "=" * 60)
print("診断結果")
print("=" * 60)

prod_has_prices = 'topPrice' in prod_data['states'][0]['clouds']['5m']
local_has_prices = 'topPrice' in local_data['states'][0]['clouds']['5m']

print(f"\n本番サーバー: topPrice/bottomPrice {'存在' if prod_has_prices else '存在しない'}")
print(f"ローカルサーバー: topPrice/bottomPrice {'存在' if local_has_prices else '存在しない'}")

if not prod_has_prices:
    print("\n❌ 問題: 本番サーバーにtopPrice/bottomPriceがありません")
    print("原因: TradingViewのインジケーターがtopPrice/bottomPriceを送信していない")
    print("      または本番サーバーのrender_server.pyが古いバージョン")
    print("\n解決策:")
    print("  1. TradingViewのアラートを再設定して最新のインジケーターコードを使用")
    print("  2. 3-deploy_prod.bat を実行して本番サーバーを更新")
else:
    if prod_data['states'][0]['clouds']['5m']['topPrice'] == 0.0:
        print("\n⚠️ 問題: topPrice/bottomPriceは存在するが値が0.0")
        print("原因: 雲が薄すぎるか、MAの計算でエラーが発生している可能性")

print("\n" + "=" * 60)
