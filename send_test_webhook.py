import json
import requests
import sys

# デフォルトのテストデータ
DEFAULT_PAYLOAD = {
    "symbol": "USDJPY",
    "tf": "5",
    "time": 176110700000,
    "state": {"flag": "", "word": ""},
    "daytrade": {"status": "上昇ダウ", "bos": "", "time": "90バ一", "swing": {"status": "上昇ダウ", "bos": "", "time": "1665バ一"}},
    "row_order": ["5m", "15m", "price", "1H", "4H"],
    "cloud_order": ["5m", "15m", "1H", "4H"],
    "clouds": [
        {
            "label": "5m",
            "tf": "15m",
            "gc": False,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 0.3898628362,
            "angle": -2.2053648999,
            "elapsed": "10",
            "distance_from_price": -1.0888977796,
            "distance_from_prev": -0.3042852534
        },
        {
            "label": "15m",
            "tf": "15m",
            "gc": True,
            "fire_count": 0,
            "max_reached": False,
            "thickness": 0.039661755,
            "angle": -0.3235691074,
            "elapsed": "10",
            "distance_from_price": -0.7046404526,
            "distance_from_prev": -2.3611390073
        },
        {
            "label": "1H",
            "tf": "1H",
            "gc": True,
            "fire_count": 10,
            "max_reached": True,
            "thickness": 7.2063262372
        }
    ]
}

def load_payload_from_file(filepath):
    """JSONファイルからペイロードを読み込む"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return None

if __name__ == "__main__":
    # コマンドライン引数からJSONファイルを受け取る
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        PAYLOAD = load_payload_from_file(json_file)
        if PAYLOAD is None:
            print("Failed to load JSON file. Using default payload.")
            PAYLOAD = DEFAULT_PAYLOAD
    else:
        PAYLOAD = DEFAULT_PAYLOAD
    
    # Webhook送信
    try:
        response = requests.post("http://localhost:5000/webhook", json=PAYLOAD, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error sending webhook: {e}")
