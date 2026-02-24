import sqlite3, json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

# ルールの完全なJSONを確認
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled = 1')
rules = c.fetchall()
for rule in rules:
    rj = json.loads(rule[2])
    print(f"\n=== Rule id={rule[0]} name={rule[1]} ===")
    print(json.dumps(rj, ensure_ascii=False, indent=2))

conn.close()
