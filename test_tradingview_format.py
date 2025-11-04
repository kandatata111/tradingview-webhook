"""
TradingViewのJSONをテスト送信
"""
import requests
import json

# TradingViewから送信されるJSONフォーマット
tradingview_data = {
    "symbol": "USDJPY",
    "tf": "5",
    "price": 152.6,  # 追加: 現在価格
    "time": 1761263100000,
    "state": {
        "flag": "",
        "word": ""
    },
    "daytrade": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "20"  # 文字列に変換
    },
    "swing": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "1425"  # 文字列に変換
    },
    "row_order": [
        "5m",
        "15m",
        "price",
        "1H",
        "4H"
    ],
    "cloud_order": [
        "5m",
        "15m",
        "1H",
        "4H"
    ],
    "clouds": [
        {
            "label": "5m",
            "tf": "5m",
            "gc": True,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 0.8765790013,
            "angle": 21.89154077,
            "elapsed": "45",  # 文字列に変換
            "distance_from_price": -1.0197433676,
            "distance_from_prev": 0,
            "topPrice": 152.605803314,
            "bottomPrice": 152.5978145413
        },
        {
            "label": "15m",
            "tf": "15m",
            "gc": False,
            "fire_count": 8,
            "max_reached": False,
            "thickness": 0.1712263538,
            "angle": 17.0466275589,
            "elapsed": "315",  # 文字列に変換
            "distance_from_price": -0.2144865016,
            "distance_from_prev": 0.8053071366,
            "topPrice": 152.5950004968,
            "bottomPrice": 152.5938283323
        },
        # 1Hと4Hのダミーデータを追加
        {
            "label": "1H",
            "tf": "1H",
            "gc": True,
            "fire_count": 5,
            "max_reached": False,
            "thickness": 1.5,
            "angle": 25.0,
            "elapsed": "3600",
            "distance_from_price": 5.0,
            "distance_from_prev": 3.0,
            "topPrice": 152.7,
            "bottomPrice": 152.5
        },
        {
            "label": "4H",
            "tf": "4H",
            "gc": False,
            "fire_count": 2,
            "max_reached": False,
            "thickness": 2.5,
            "angle": 30.0,
            "elapsed": "14400",
            "distance_from_price": 10.0,
            "distance_from_prev": 5.0,
            "topPrice": 153.0,
            "bottomPrice": 152.3
        }
    ]
}

print("=" * 60)
print("TradingView JSONフォーマット テスト送信")
print("=" * 60)

# ローカルサーバーにテスト送信
print("\n[1] ローカルサーバーに送信...")
try:
    response = requests.post(
        'http://localhost:5000/webhook',
        json=tradingview_data,
        timeout=5
    )
    print(f"✅ ステータスコード: {response.status_code}")
    print(f"レスポンス: {response.json()}")
except Exception as e:
    print(f"❌ エラー: {e}")
    print("ヒント: render_server.py が起動しているか確認してください")

# データ確認
print("\n[2] 送信後のデータを確認...")
try:
    response = requests.get('http://localhost:5000/current_states')
    data = response.json()
    
    if data['states']:
        state = data['states'][0]
        print(f"\n✅ データ取得成功")
        print(f"シンボル: {state['symbol']}")
        print(f"価格: {state['price']}")
        print(f"\n雲データ:")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            top = cloud.get('topPrice', 'なし')
            bottom = cloud.get('bottomPrice', 'なし')
            gc = cloud.get('gc', False)
            print(f"  {tf}: GC={gc}, topPrice={top}, bottomPrice={bottom}")
        
        print(f"\nダウ理論:")
        print(f"  Daily: {state.get('daily_dow', {})}")
        print(f"  Swing: {state.get('swing_dow', {})}")
    else:
        print("❌ データがありません")
        
except Exception as e:
    print(f"❌ エラー: {e}")

print("\n" + "=" * 60)
