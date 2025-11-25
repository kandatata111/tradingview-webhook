import requests
import json

url = "http://127.0.0.1:5000/webhook"
data = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "up",
    "gc": False,
    "bos_count": 0
}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
