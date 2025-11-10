import requests

# 本番DBの生データを取得
r = requests.get('https://tradingview-webhook-s5x1.onrender.com/debug_db')
columns = r.json()['columns']

print("本番DBのカラム順序:")
for i, col in enumerate(columns):
    print(f"{i:2d}: {col['name']}")

# 期待されるVALUES順序
print("\n期待されるVALUES配列の順序:")
expected = [
    "symbol", "timestamp", "tf", "price",
    "daily_dow_status", "daily_dow_bos", "daily_dow_time",
    "swing_dow_status", "swing_dow_bos", "swing_dow_time",
    "row_order", "cloud_order",
    # 5m
    "cloud_5m_gc", "cloud_5m_thickness", "cloud_5m_angle", "cloud_5m_fire_count", 
    "cloud_5m_elapsed", "cloud_5m_distance_from_price", "cloud_5m_distance_from_prev",
    # 15m
    "cloud_15m_gc", "cloud_15m_thickness", "cloud_15m_angle", "cloud_15m_fire_count",
    "cloud_15m_elapsed", "cloud_15m_distance_from_price", "cloud_15m_distance_from_prev",
    # 1H
    "cloud_1h_gc", "cloud_1h_thickness", "cloud_1h_angle", "cloud_1h_fire_count",
    "cloud_1h_elapsed", "cloud_1h_distance_from_price", "cloud_1h_distance_from_prev",
    # 4H
    "cloud_4h_gc", "cloud_4h_thickness", "cloud_4h_angle", "cloud_4h_fire_count",
    "cloud_4h_elapsed", "cloud_4h_distance_from_price", "cloud_4h_distance_from_prev",
    # topPrice/bottomPrice
    "cloud_5m_topPrice", "cloud_5m_bottomPrice",
    "cloud_15m_topPrice", "cloud_15m_bottomPrice",
    "cloud_1h_topPrice", "cloud_1h_bottomPrice",
    "cloud_4h_topPrice", "cloud_4h_bottomPrice"
]

for i, name in enumerate(expected):
    print(f"{i:2d}: {name}")

# 不一致をチェック
print("\n不一致:")
for i, (col, exp) in enumerate(zip(columns, expected)):
    if col['name'] != exp:
        print(f"位置 {i}: DB={col['name']} vs 期待={exp}")
