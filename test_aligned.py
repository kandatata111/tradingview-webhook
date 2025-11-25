import requests

url = "http://127.0.0.1:5000/webhook"
data = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "down",  # down方向
    "gc": False,       # False = down方向
    "bos_count": 0
}

print(f"Sending request with dauten=down, gc=False (both down)")
try:
    response = requests.post(url, json=data, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
