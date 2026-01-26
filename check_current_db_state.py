#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DBの現在の状態を詳細に確認
"""

import sqlite3
import json
from datetime import datetime
import pytz

db_path = 'webhook_data.db'
jst = pytz.timezone('Asia/Tokyo')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 100)
print("📊 USDJPY 現在のDB状態")
print("=" * 100)

cursor.execute("""
    SELECT tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, clouds_json
    FROM states
    WHERE symbol = 'USDJPY'
    ORDER BY 
        CASE tf
            WHEN '5' THEN 1
            WHEN '15' THEN 2
            WHEN '60' THEN 3
            WHEN '240' THEN 4
            WHEN 'D' THEN 5
            ELSE 6
        END
""")

for row in cursor.fetchall():
    tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, clouds_json = row
    
    print(f"\n{'=' * 100}")
    print(f"⏱️  時間軸: {tf}")
    print(f"{'=' * 100}")
    print(f"📅 タイムスタンプ: {timestamp}")
    print(f"📈 Daytrade:")
    print(f"   ダウ転: {daytrade_status}")
    print(f"   BOS: {daytrade_bos}")
    print(f"   ダウ転時間: {daytrade_time}")
    
    if clouds_json:
        try:
            clouds = json.loads(clouds_json)
            print(f"\n☁️  Clouds配列 ({len(clouds)}個):")
            for i, cloud in enumerate(clouds):
                if cloud.get('label') == tf or (tf == '5' and cloud.get('label') == '5m') or \
                   (tf == '15' and cloud.get('label') == '15m') or \
                   (tf == '60' and cloud.get('label') == '1H') or \
                   (tf == '240' and cloud.get('label') == '4H'):
                    print(f"   [{i}] {cloud.get('label')}: dauten={cloud.get('dauten')}, bos_count={cloud.get('bos_count')}, dauten_time={cloud.get('dauten_start_time_str')}")
        except:
            print(f"   ❌ JSON解析エラー")

conn.close()

print("\n" + "=" * 100)
