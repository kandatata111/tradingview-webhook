import requests
import json

# テストデータ (PineScript形式に合わせる)
test_data = {
    "symbol": "USDJPY",
    "tf": "5",
    "time": 1761015000000,
    "state": {"flag": "買", "word": "強気"},
    "daytrade": {"status": "上昇ダウ", "bos": "BOS+1", "time": 50},
    "swing": {"status": "上昇ダウ", "bos": "", "time": 70},
    "row_order": ["price", "5m", "15m", "1H", "4H"],
    "cloud_order": ["5m", "15m", "1H", "4H"],
    "clouds": {
        "5m": {"gc": True, "fire_count": 0, "thickness": 8.49, "angle": 34.95, "elapsed": 80, "distance_from_price": 10.5, "distance_from_prev": 5.3, "topPrice": 151.50, "bottomPrice": 151.30},
        "15m": {"gc": True, "fire_count": 0, "thickness": 8.19, "angle": 34.11, "elapsed": 65, "distance_from_price": 15.2, "distance_from_prev": 8.7, "topPrice": 151.60, "bottomPrice": 151.40},
        "1H": {"gc": True, "fire_count": 2, "thickness": 4.87, "angle": 1.55, "elapsed": 95, "distance_from_price": 25.8, "distance_from_prev": 12.4, "topPrice": 151.80, "bottomPrice": 151.20},
        "4H": {"gc": False, "fire_count": 0, "thickness": 0.0, "angle": 0.0, "elapsed": 0, "distance_from_price": 0.0, "distance_from_prev": 0.0, "topPrice": "na", "bottomPrice": "na"}
    },
    "price": 151.40
}

# Webhookに送信
url = 'http://localhost:5000/webhook'
response = requests.post(url, json=test_data)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
