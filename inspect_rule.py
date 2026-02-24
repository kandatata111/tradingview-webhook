import sqlite3, json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
c.execute("SELECT rule_json FROM rules WHERE id='rule_test_demo'")
r = c.fetchone()
print('row', r)
if r:
    print(json.dumps(json.loads(r[0]), ensure_ascii=False, indent=2))
conn.close()
