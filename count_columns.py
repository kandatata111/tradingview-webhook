columns_in_insert = """symbol, timestamp, tf, price,
daily_dow_status, daily_dow_bos, daily_dow_time,
swing_dow_status, swing_dow_bos, swing_dow_time,
row_order, cloud_order,
cloud_5m_gc, cloud_5m_thickness, cloud_5m_angle, cloud_5m_fire_count, cloud_5m_elapsed,
cloud_5m_distance_from_price, cloud_5m_distance_from_prev,
cloud_15m_gc, cloud_15m_thickness, cloud_15m_angle, cloud_15m_fire_count, cloud_15m_elapsed,
cloud_15m_distance_from_price, cloud_15m_distance_from_prev,
cloud_1h_gc, cloud_1h_thickness, cloud_1h_angle, cloud_1h_fire_count, cloud_1h_elapsed,
cloud_1h_distance_from_price, cloud_1h_distance_from_prev,
cloud_4h_gc, cloud_4h_thickness, cloud_4h_angle, cloud_4h_fire_count, cloud_4h_elapsed,
cloud_4h_distance_from_price, cloud_4h_distance_from_prev,
cloud_5m_topPrice, cloud_5m_bottomPrice,
cloud_15m_topPrice, cloud_15m_bottomPrice,
cloud_1h_topPrice, cloud_1h_bottomPrice,
cloud_4h_topPrice, cloud_4h_bottomPrice"""

cols = [c.strip() for c in columns_in_insert.replace('\n', '').split(',') if c.strip()]
print(f"INSERT文のカラム数: {len(cols)}")
for i, col in enumerate(cols):
    print(f"{i:2d}: {col}")

placeholders = "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
print(f"\nプレースホルダー数: {placeholders.count('%s')}")
