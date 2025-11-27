import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

# 15分ダウ転換ルールを確認
c.execute("SELECT id, name, rule_json FROM rules WHERE name LIKE '%15%ダウ%'")
rows = c.fetchall()
for row in rows:
    print(f"=== {row[0]}: {row[1]} ===")
    rule = json.loads(row[2])
    print(json.dumps(rule, indent=2, ensure_ascii=False))
    print()

# fire_historyから15分ダウ転換の最近の発火を確認
print("\n=== 15分ダウ転換の発火履歴（最新10件）===")
c.execute("""
    SELECT fired_at, symbol, last_state_snapshot 
    FROM fire_history 
    WHERE rule_id LIKE '%15分ダウ%' 
    ORDER BY fired_at DESC 
    LIMIT 10
""")
for row in c.fetchall():
    state = json.loads(row[2])
    print(f"\n{row[0]} | {row[1]}")
    print(f"  15m.dauten = {state.get('15m.dauten')}")
    print(f"  15m.gc = {state.get('15m.gc')}")
    print(f"  __conditions_matched__ = {state.get('__conditions_matched__')}")

conn.close()
