import sqlite3
from datetime import datetime
import json

conn = sqlite3.connect('webhook_data.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 今日18時台の発火履歴を確認
print('=== 今日18時台の発火履歴 ===')
cur.execute("""
    SELECT id, rule_id, symbol, fired_at, conditions_snapshot, last_state_snapshot 
    FROM fire_history 
    WHERE fired_at LIKE '2025-11-27T18:%'
    ORDER BY id
""")
for row in cur.fetchall():
    state = json.loads(row['last_state_snapshot'])
    matched = state.get('__conditions_matched__', 'N/A')
    # 15mのdauten, gc情報を抽出
    dauten_15m = state.get('15m.dauten', 'N/A')
    gc_15m = state.get('15m.gc', 'N/A')
    dauten_5m = state.get('5m.dauten', 'N/A')
    gc_5m = state.get('5m.gc', 'N/A')
    
    print(f"\nID: {row['id']} | {row['fired_at']}")
    print(f"  ルール: {row['rule_id']} | 通貨: {row['symbol']}")
    print(f"  条件マッチ: {matched}")
    print(f"  15m.dauten={dauten_15m}, 15m.gc={gc_15m}")
    print(f"  5m.dauten={dauten_5m}, 5m.gc={gc_5m}")

# statesテーブルの構造確認
print('\n\n=== states テーブル構造 ===')
cur.execute("PRAGMA table_info(states)")
for row in cur.fetchall():
    print(dict(row))

print('\n\n=== states テーブルサンプル ===')
cur.execute("SELECT * FROM states LIMIT 3")
for row in cur.fetchall():
    print(dict(row))

conn.close()
