import sqlite3, json
DB='webhook_data.db'
conn=sqlite3.connect(DB)
c=conn.cursor()
c.execute('SELECT id,name,rule_json FROM rules')
rows=c.fetchall()
print('rowcount', len(rows))
for rid,name,rj in rows:
    rule=json.loads(rj)
    print('RULE', rid, name)
    print('align', rule.get('cloudAlign') or rule.get('alignment'))
    print('voice_keys', list(rule.get('voice', {}).keys()))
    print('---')
conn.close()
