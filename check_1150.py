import sqlite3
import json

DB_PATH = r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 11:50頃の発火履歴を確認
c.execute("""SELECT fired_at, rule_id, last_state_snapshot FROM fire_history 
             WHERE fired_at LIKE '%T11:5%' OR fired_at LIKE '%T11:49%'
             ORDER BY fired_at DESC LIMIT 50""")
rows = c.fetchall()

print("=== 11:50頃の発火履歴 ===")
for r in rows:
    fired_at, rule_id, state_snap = r
    dauten_5m = "N/A"
    gc_5m = "N/A"
    if state_snap:
        try:
            state = json.loads(state_snap)
            dauten_5m = state.get('5m.dauten', 'N/A')
            gc_5m = state.get('5m.gc', 'N/A')
        except:
            pass
    print(f'{fired_at} | {rule_id} | 5m: dauten={dauten_5m}, gc={gc_5m}')

conn.close()
