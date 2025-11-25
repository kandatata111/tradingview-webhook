import requests
import time

url = "http://127.0.0.1:5000/webhook"

# ステップ1: 方向不一致で条件を満たさない (dauten=up, gc=False = mismatch)
print("Step 1: Direction mismatch (dauten=up, gc=False)")
data1 = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "up",
    "gc": False,
    "bos_count": 0
}
response1 = requests.post(url, json=data1)
print(f"Response 1: {response1.status_code} - Should NOT fire\n")

time.sleep(2)

# ステップ2: 方向一致で条件を満たす (dauten=down, gc=False = both down)
print("Step 2: Direction aligned (dauten=down, gc=False)")
data2 = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "down",
    "gc": False,
    "bos_count": 0
}
response2 = requests.post(url, json=data2)
print(f"Response 2: {response2.status_code} - SHOULD FIRE!")
print("\nCheck webhook_error.log for 'Conditions alignment changed: not_matched -> matched, firing'")
