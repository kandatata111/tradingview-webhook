import sqlite3
import json

DB_PATH = r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 最近の発火履歴を詳細に確認
c.execute('''SELECT fired_at, rule_id, symbol, conditions_snapshot, last_state_snapshot 
             FROM fire_history ORDER BY fired_at DESC LIMIT 50''')
rows = c.fetchall()

print("=== 最近の発火履歴（最新50件）===")
print("")

for row in rows:
    fired_at, rule_id, symbol, cond_snap, state_snap = row
    print(f"[{fired_at}] {rule_id} ({symbol})")
    
    if state_snap:
        try:
            state = json.loads(state_snap)
            # 5m のデータを表示
            dauten_5m = state.get('5m.dauten', 'N/A')
            gc_5m = state.get('5m.gc', 'N/A')
            dauten_15m = state.get('15m.dauten', 'N/A')
            gc_15m = state.get('15m.gc', 'N/A')
            
            print(f"    5m: dauten={dauten_5m}, gc={gc_5m}")
            print(f"    15m: dauten={dauten_15m}, gc={gc_15m}")
            
            # 条件マッチフラグ
            matched = state.get('__conditions_matched__', 'N/A')
            print(f"    conditions_matched: {matched}")
        except:
            print(f"    (state parse error)")
    print("")

conn.close()
