import sqlite3, json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

# USDJPYの全TFを確認
c.execute('SELECT symbol, tf, clouds_json FROM states WHERE symbol = ? ORDER BY rowid DESC', ('USDJPY',))
rows = c.fetchall()
for r in rows:
    clouds = json.loads(r[2]) if r[2] else []
    labels = [cl.get('label') for cl in clouds]
    dauten = [cl.get('dauten') for cl in clouds]
    gc = [cl.get('gc') for cl in clouds]
    print(f"symbol={r[0]} tf={r[1]} cloud_labels={labels} dauten={dauten} gc={gc}")

print()
# ルールの条件を確認
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled = 1')
rules = c.fetchall()
for rule in rules:
    rj = json.loads(rule[2])
    conds = rj.get('conditions', [])
    print(f"Rule: {rule[1]}")
    for cond in conds:
        print(f"  label={cond.get('label')} field={cond.get('field')} value={cond.get('value')!r}")

conn.close()
