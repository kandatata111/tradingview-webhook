import time
import requests

print("Waiting for server...")
time.sleep(2)

url = "http://127.0.0.1:5000/webhook"
data = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "up",
    "gc": False,
    "bos_count": 0
}

print(f"Sending request to {url}")
try:
    response = requests.post(url, json=data, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
