import sqlite3, json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled=1')
for row in c.fetchall():
    rid, name, rj = row
    rd = json.loads(rj) if rj else {}
    dtf = rd.get('displayTf', '(empty)')
    print(f'ID={rid}  name={name}  displayTf={dtf}')
    conds = rd.get('conditions', [])
    for cond in conds:
        print(f'  cond: {cond}')
conn.close()
