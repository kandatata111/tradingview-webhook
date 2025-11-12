import sqlite3, json
conn=sqlite3.connect('webhook_data.db')
c=conn.cursor()
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled=1')
rows=c.fetchall()
conn.close()
print('Enabled rules:')
for r in rows:
    rule = json.loads(r[2])
    print(f'{r[1]}: {rule.get("conditions", [])}')