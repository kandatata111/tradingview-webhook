#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render本番サーバーのDBをダウンロードして内容を確認
"""

import requests
import sqlite3
import os
import json
from datetime import datetime

# Render本番サーバーURL
RENDER_URL = "https://tradingview-webhook-s5x1.onrender.com"

print("=" * 100)
print("📥 Render本番サーバーのDB状態を確認")
print("=" * 100)

# DBをダウンロード
print("\n1. Render本番DBをダウンロード中...")
try:
    response = requests.get(f"{RENDER_URL}/download_db", timeout=30)
    if response.status_code == 200:
        # 一時ファイルに保存
        temp_db_path = "render_production_db.db"
        with open(temp_db_path, 'wb') as f:
            f.write(response.content)
        print(f"   ✅ ダウンロード成功: {len(response.content)} bytes")
        
        # DBの内容を確認
        print("\n2. Render本番DBの内容を確認...")
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, price
            FROM states
            WHERE symbol = 'USDJPY'
            ORDER BY timestamp DESC
        """)
        
        print("\n📊 USDJPY 全時間軸の状態（タイムスタンプ順）:")
        print("-" * 100)
        
        for row in cursor.fetchall():
            tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, price = row
            print(f"\n時間軸: {tf}")
            print(f"  タイムスタンプ: {timestamp}")
            print(f"  ダウ転: {daytrade_status}")
            print(f"  BOS: {daytrade_bos}")
            print(f"  ダウ転時間: {daytrade_time}")
            print(f"  価格: {price}")
        
        # clouds_jsonも確認
        print("\n" + "=" * 100)
        print("☁️  Clouds配列の詳細:")
        print("=" * 100)
        
        cursor.execute("""
            SELECT tf, clouds_json
            FROM states
            WHERE symbol = 'USDJPY' AND clouds_json IS NOT NULL AND clouds_json != '[]'
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
            tf, clouds_json = row
            try:
                clouds = json.loads(clouds_json)
                for cloud in clouds:
                    if cloud.get('label') in ['5m', '15m', '1H', '4H', 'D']:
                        print(f"\n[{tf}] {cloud.get('label')}:")
                        print(f"  dauten: {cloud.get('dauten')}")
                        print(f"  bos_count: {cloud.get('bos_count')}")
                        print(f"  dauten_start_time_str: {cloud.get('dauten_start_time_str')}")
            except:
                pass
        
        conn.close()
        
        print("\n" + "=" * 100)
        print(f"✅ Render本番DBの確認完了 - ファイル保存: {temp_db_path}")
        print("=" * 100)
        
    else:
        print(f"   ❌ ダウンロード失敗: HTTP {response.status_code}")
        
except Exception as e:
    print(f"   ❌ エラー: {e}")
    import traceback
    traceback.print_exc()
