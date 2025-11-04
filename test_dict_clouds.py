"""dict形式のcloudsをテスト"""
import requests
import json

# dict形式のテストデータ(quick_test.pyと同じ)
test_data = {
    "symbol": "USDJPY",
    "price": 151.40,
    "tf": "5",
    "daytrade": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "85"
    },
    "swing": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "70"
    },
    "clouds": {
        "5m": {
            "gc": True,
            "thickness": 0.5,
            "angle": 45,
            "fire_count": 2,
            "elapsed": "10s",
            "distance_from_price": 0.1,
            "distance_from_prev": 0.05,
            "topPrice": 151.5,
            "bottomPrice": 151.3
        },
        "15m": {
            "gc": False,
            "thickness": 0.3,
            "angle": 30,
            "fire_count": 0,
            "elapsed": "5s",
            "distance_from_price": 0.2,
            "distance_from_prev": 0.1,
            "topPrice": 151.6,
            "bottomPrice": 151.2
        },
        "1H": {
            "gc": True,
            "thickness": 0.8,
            "angle": 60,
            "fire_count": 5,
            "elapsed": "20s",
            "distance_from_price": 0.3,
            "distance_from_prev": 0.15,
            "topPrice": 151.7,
            "bottomPrice": 151.1
        },
        "4H": {
            "gc": False,
            "thickness": 0.2,
            "angle": 15,
            "fire_count": 1,
            "elapsed": "2s",
            "distance_from_price": 0.05,
            "distance_from_prev": 0.02,
            "topPrice": "na",
            "bottomPrice": "na"
        }
    }
}

url = "http://localhost:5000/webhook"

print("📤 dict形式のテストデータを送信中...")
print(json.dumps(test_data, indent=2, ensure_ascii=False))
print()

try:
    response = requests.post(url, json=test_data)
    print(f"✅ ステータスコード: {response.status_code}")
    print(f"📨 レスポンス: {response.json()}")
except Exception as e:
    print(f"❌ エラー: {e}")
