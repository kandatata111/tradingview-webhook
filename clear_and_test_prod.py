"""
本番データベースをクリアしてから新しいテストデータを送信
"""
import requests
import time

print("🗑️  本番データベースをクリア...")

# まず現在のデータを全て削除するため、存在する全通貨ペアを確認
response = requests.get('https://tradingview-webhook-s5x1.onrender.com/current_states', timeout=10)
current_data = response.json()

if current_data['states']:
    for state in current_data['states']:
        symbol = state['symbol']
        print(f"  削除: {symbol}")
        # 各通貨ペアを個別に削除するAPIはないので、USDJPYを送信して上書き

# 新しいUSDJPYデータを送信
test_data = {
    "symbol": "USDJPY",
    "price": 152.6,
    "tf": "5",
    "daytrade": {"status": "上昇ダウ", "bos": "", "time": "20"},
    "swing": {"status": "上昇ダウ", "bos": "", "time": "1425"},
    "row_order": ["price", "5m", "15m", "1H", "4H"],
    "cloud_order": ["5m", "15m", "1H", "4H"],
    "clouds": [
        {
            "label": "5m",
            "gc": True,
            "thickness": 0.88,
            "angle": 21.89,
            "fire_count": 0,
            "elapsed": "45",
            "distance_from_price": -1.02,
            "distance_from_prev": 0,
            "topPrice": 152.605803314,
            "bottomPrice": 152.5978145413
        },
        {
            "label": "15m",
            "gc": False,
            "thickness": 0.17,
            "angle": 17.05,
            "fire_count": 8,
            "elapsed": "315",
            "distance_from_price": -0.21,
            "distance_from_prev": 0.81,
            "topPrice": 152.5950004968,
            "bottomPrice": 152.5938283323
        },
        {
            "label": "1H",
            "gc": True,
            "thickness": 1.5,
            "angle": 25.5,
            "fire_count": 5,
            "elapsed": "3600",
            "distance_from_price": 5.2,
            "distance_from_prev": 3.1,
            "topPrice": 152.8,
            "bottomPrice": 152.5
        },
        {
            "label": "4H",
            "gc": False,
            "thickness": 2.3,
            "angle": 30.2,
            "fire_count": 2,
            "elapsed": "14400",
            "distance_from_price": 10.5,
            "distance_from_prev": 5.8,
            "topPrice": 153.2,
            "bottomPrice": 152.4
        }
    ]
}

print("\n📤 新しいUSDJPYデータを送信...")
response = requests.post(
    'https://tradingview-webhook-s5x1.onrender.com/webhook',
    json=test_data,
    timeout=30
)
print(f"✅ ステータス: {response.status_code}")
print(f"レスポンス: {response.json()}")

print("\n⏱️  2秒待機...")
time.sleep(2)

print("\n🔍 本番データを確認...")
response = requests.get('https://tradingview-webhook-s5x1.onrender.com/current_states', timeout=10)
data = response.json()

if data['states']:
    print(f"\n✅ {len(data['states'])} 件のデータ:")
    for i, state in enumerate(data['states']):
        print(f"\n[{i}] {state['symbol']} - {state['timestamp']}")
        print(f"    Price: {state['price']}")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            print(f"    {tf}: topPrice={cloud.get('topPrice', 'N/A')}, bottomPrice={cloud.get('bottomPrice', 'N/A')}")

print("\n✅ 完了")
