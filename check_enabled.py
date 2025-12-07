import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
c.execute('SELECT id, name, enabled, rule_json FROM rules')
rows = c.fetchall()
conn.close()

print("=" * 80)
print("ルールの enabled 状態チェック")
print("=" * 80)
for r in rows:
    rule_json = json.loads(r[3])
    json_enabled = rule_json.get('enabled', 'NOT SET')
    print(f"ID: {r[0]}")
    print(f"  Name: {r[1]}")
    print(f"  DB enabled column: {r[2]}")
    print(f"  JSON enabled field: {json_enabled}")
    print(f"  一致: {'YES' if r[2] == (1 if json_enabled else 0) else 'NO - 問題あり!'}")
    print("-" * 40)
