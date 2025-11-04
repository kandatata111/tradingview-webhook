"""
完全なTradingViewフォーマットのテストデータを本番サーバーに送信
"""
import requests
import json

# 完全なTradingViewフォーマット
complete_data = {
    "symbol": "USDJPY",
    "price": 152.6,  # 現在価格を追加
    "tf": "5",
    "time": 1761263100000,
    "state": {
        "flag": "",
        "word": ""
    },
    "daytrade": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "20"
    },
    "swing": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "1425"
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
            "elapsed": "45",
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
            "elapsed": "315",
            "distance_from_price": -0.2144865016,
            "distance_from_prev": 0.8053071366,
            "topPrice": 152.5950004968,
            "bottomPrice": 152.5938283323
        },
        # 1Hデータを追加
        {
            "label": "1H",
            "tf": "1H",
            "gc": True,
            "fire_count": 5,
            "max_reached": False,
            "thickness": 1.5,
            "angle": 25.5,
            "elapsed": "3600",
            "distance_from_price": 5.2,
            "distance_from_prev": 3.1,
            "topPrice": 152.8,
            "bottomPrice": 152.5
        },
        # 4Hデータを追加
        {
            "label": "4H",
            "tf": "4H",
            "gc": False,
            "fire_count": 2,
            "max_reached": False,
            "thickness": 2.3,
            "angle": 30.2,
            "elapsed": "14400",
            "distance_from_price": 10.5,
            "distance_from_prev": 5.8,
            "topPrice": 153.2,
            "bottomPrice": 152.4
        }
    ]
}

print("=" * 60)
print("完全なテストデータを本番サーバーに送信")
print("=" * 60)

# 本番サーバーに送信
print("\n[1] 本番サーバーに送信中...")
try:
    response = requests.post(
        'https://tradingview-webhook-s5x1.onrender.com/webhook',
        json=complete_data,
        timeout=30
    )
    print(f"✅ ステータスコード: {response.status_code}")
    print(f"レスポンス: {response.json()}")
except Exception as e:
    print(f"❌ エラー: {e}")

# データ確認
print("\n[2] 本番サーバーのデータを確認...")
try:
    response = requests.get('https://tradingview-webhook-s5x1.onrender.com/current_states', timeout=10)
    data = response.json()
    
    if data['states']:
        state = data['states'][0]
        print(f"\n✅ データ取得成功")
        print(f"シンボル: {state['symbol']}")
        print(f"価格: {state['price']}")
        print(f"タイムスタンプ: {state['timestamp']}")
        
        print(f"\n雲データ:")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            top = cloud.get('topPrice', 'なし')
            bottom = cloud.get('bottomPrice', 'なし')
            gc = cloud.get('gc', False)
            thickness = cloud.get('thickness', 0)
            print(f"  {tf}: GC={gc}, thickness={thickness:.2f}, topPrice={top}, bottomPrice={bottom}")
        
        print(f"\nダウ理論:")
        print(f"  Daily: {state.get('daily_dow', {})}")
        print(f"  Swing: {state.get('swing_dow', {})}")
        
        # 価格が雲の範囲内かチェック
        print(f"\n★マーク判定 (価格 {state['price']}):")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            top = cloud.get('topPrice', 0)
            bottom = cloud.get('bottomPrice', 0)
            if top and bottom and bottom <= state['price'] <= top:
                print(f"  {tf} ★ (範囲内: {bottom} ≤ {state['price']} ≤ {top})")
            else:
                print(f"  {tf}   (範囲外)")
    else:
        print("❌ データがありません")
        
except Exception as e:
    print(f"❌ エラー: {e}")

print("\n" + "=" * 60)
print("✅ 本番サーバーにテストデータを送信しました")
print("https://tradingview-webhook-s5x1.onrender.com/ で確認できます")
print("=" * 60)
