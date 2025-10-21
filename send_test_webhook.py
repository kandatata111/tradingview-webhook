import json
import requests

PAYLOAD = {
    "symbol": "USDJPY",
    "tf": "5",
    "time": 1760621400000,
    "state": {"flag": "", "word": ""},
    "daytrade": {"status": "上昇ダウ", "bos": "BOS-1", "time": "65バー"},
    "swing": {"status": "下降ダウ", "bos": "BOS+1", "time": "245バー"},
    "row_order": ["4H", "1H", "price", "15m", "5m"],  # 価格が真ん中に来る例
    "clouds": [
        {
            "label": "5m",
            "tf": "5m",
            "gc": False,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 1.2250927251,
            "angle": -21.8826924485,
            "elapsed": 80,
            "distance_from_price": 0.5,
            "distance_from_prev": 1.2
        },
        {
            "label": "15m",
            "tf": "15m",
            "gc": False,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 0.111211148,
            "angle": -24.6340678976,
            "elapsed": 103,
            "distance_from_price": -0.3,
            "distance_from_prev": 0.8
        },
        {
            "label": "1H",
            "tf": "1H",
            "gc": True,
            "fire_count": 2,
            "max_reached": False,
            "thickness": 0.286961272,
            "angle": 1.553924035,
            "elapsed": 95,
            "distance_from_price": 1.1,
            "distance_from_prev": -0.5
        },
        {
            "label": "4H",
            "tf": "4H",
            "gc": False,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 23.0627544224,
            "angle": -12.858702161,
            "elapsed": 2540,
            "distance_from_price": -2.0,
            "distance_from_prev": 3.5
        }
    ],
    "price": 151.219
}

if __name__ == "__main__":
    # クラウドテスト用
    response = requests.post("https://tradingview-webhook-s5x1.onrender.com/webhook", json=PAYLOAD, timeout=10)
    print(response.status_code)
    print(response.text)
