import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

print("=== 有効なルール詳細 ===\n")
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled = 1')
rules = c.fetchall()

for rule_id, name, rule_json in rules:
    print(f"Rule ID: {rule_id}, Name: {name}")
    try:
        rule_data = json.loads(rule_json)
        conditions = rule_data.get('conditions', [])
        print(f"  Conditions count: {len(conditions)}")
        for i, cond in enumerate(conditions):
            print(f"    Condition {i}: label={cond.get('label')}, field={cond.get('field')}, value={cond.get('value')}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

# fire_history をチェック
print("\n=== 最近の発火履歴 ===")
c.execute('SELECT rule_id, symbol, fired_at FROM fire_history ORDER BY fired_at DESC LIMIT 10')
history = c.fetchall()
if history:
    for rule_id, symbol, fired_at in history:
        print(f"Rule {rule_id}, Symbol {symbol}, Time {fired_at}")
else:
    print("発火履歴がありません")

conn.close()
