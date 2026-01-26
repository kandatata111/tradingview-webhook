#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提供されたJSONコードを手動で送信してDB保存をテスト
"""

import requests
import json

# ローカルサーバーURL
url = "http://localhost:5000/webhook"

# 提供された15分足のJSONコード
json_15m = {
    "symbol": "USDJPY",
    "tf": "15",
    "time": 1769418000000,
    "daytrade": {
        "status": "上昇ダウ",
        "bos": "-",
        "time": "26/01/26/15:00"
    },
    "row_order": ["D", "4H", "1H", "15m", "price"],
    "cloud_order": ["15m", "1H", "4H", "D"],
    "clouds": [
        {
            "label": "15m",
            "tf": "15m",
            "gc": False,
            "thickness": 6.0929461457,
            "angle": -34.1149444196,
            "elapsed": 45,
            "cross_start_time": 1769415300000,
            "elapsed_str": "26/01/26/17:15",
            "in_cloud": False,
            "star": False,
            "distance_from_price": -9.788526927,
            "distance_from_prev": -9.788526927,
            "topPrice": 154.05835,
            "bottomPrice": 153.9974205385,
            "dauten": "up",
            "bos_count": 0,
            "dauten_start_time": 1769407200000,
            "dauten_start_time_str": "26/01/26/15:00"
        }
    ],
    "price": 153.93
}

# 1時間足のJSONコード
json_1h = {
    "symbol": "USDJPY",
    "tf": "60",
    "time": 1769414400000,
    "daytrade": {
        "status": "下降ダウ",
        "bos": "BOS-1",
        "time": "26/01/23/02:00"
    },
    "row_order": ["D", "4H", "1H", "W", "price"],
    "cloud_order": ["1H", "4H", "D", "W"],
    "clouds": [
        {
            "label": "1H",
            "tf": "1H",
            "gc": False,
            "thickness": 101.8387795182,
            "angle": -35.8493722606,
            "elapsed": 4260,
            "cross_start_time": 1769158800000,
            "elapsed_str": "26/01/23/18:00",
            "in_cloud": False,
            "star": False,
            "distance_from_price": -106.7856102408,
            "distance_from_prev": -106.7856102408,
            "topPrice": 155.49905,
            "bottomPrice": 154.4806622048,
            "dauten": "down",
            "bos_count": 0,
            "dauten_start_time": 1769101200000,
            "dauten_start_time_str": "26/01/23/02:00"
        }
    ],
    "price": 153.922
}

# 4時間足のJSONコード
json_4h = {
    "symbol": "USDJPY",
    "tf": "240",
    "time": 1769392800000,
    "daytrade": {
        "status": "下降ダウ",
        "bos": "-",
        "time": "26/01/23/23:00"
    },
    "row_order": ["D", "4H", "W", "price", "M"],
    "cloud_order": ["4H", "D", "W", "M"],
    "clouds": [
        {
            "label": "4H",
            "tf": "4H",
            "gc": False,
            "thickness": 120.9397211553,
            "angle": -35.9380826096,
            "elapsed": 3600,
            "cross_start_time": 1769176800000,
            "elapsed_str": "26/01/23/23:00",
            "in_cloud": False,
            "star": False,
            "distance_from_price": -297.9951394224,
            "distance_from_prev": -297.9951394224,
            "topPrice": 157.69365,
            "bottomPrice": 156.4842527884,
            "dauten": "down",
            "bos_count": 0,
            "dauten_start_time": 1769176800000,
            "dauten_start_time_str": "26/01/23/23:00"
        }
    ],
    "price": 154.109
}

print("=" * 80)
print("提供されたJSONコードを手動送信")
print("=" * 80)

# 15分足を送信
print("\n1. 15分足を送信...")
try:
    response = requests.post(url, json=json_15m, timeout=10)
    print(f"   ステータス: {response.status_code}")
    print(f"   レスポンス: {response.json()}")
except Exception as e:
    print(f"   ❌ エラー: {e}")

# 1時間足を送信
print("\n2. 1時間足を送信...")
try:
    response = requests.post(url, json=json_1h, timeout=10)
    print(f"   ステータス: {response.status_code}")
    print(f"   レスポンス: {response.json()}")
except Exception as e:
    print(f"   ❌ エラー: {e}")

# 4時間足を送信
print("\n3. 4時間足を送信...")
try:
    response = requests.post(url, json=json_4h, timeout=10)
    print(f"   ステータス: {response.status_code}")
    print(f"   レスポンス: {response.json()}")
except Exception as e:
    print(f"   ❌ エラー: {e}")

print("\n" + "=" * 80)
print("送信完了 - DBを確認してください")
print("=" * 80)
