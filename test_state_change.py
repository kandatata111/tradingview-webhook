import requests
import time

url = "http://127.0.0.1:5000/webhook"

# ステップ1: 条件を満たさない状態にする (upとdown = mismatch)
print("Step 1: Making conditions not match (dauten=up, gc=True)")
data1 = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "up",
    "gc": True,
    "bos_count": 0
}
response1 = requests.post(url, json=data1)
print(f"Response 1: {response1.status_code}\n")

time.sleep(2)

# ステップ2: 条件を満たす状態にする (downとdown = aligned)
print("Step 2: Making conditions match (dauten=down, gc=False)")
data2 = {
    "symbol": "USDJPY",
    "tf": "5",
    "dauten": "down",
    "gc": False,
    "bos_count": 0
}
response2 = requests.post(url, json=data2)
print(f"Response 2: {response2.status_code}")
print("Check webhook_error.log for firing notification!")
