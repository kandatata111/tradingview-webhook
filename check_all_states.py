import sqlite3, json
conn=sqlite3.connect('webhook_data.db')
c=conn.cursor()
c.execute('SELECT symbol, tf, clouds_json FROM states ORDER BY rowid DESC LIMIT 15')
rows=c.fetchall()
conn.close()
for r in rows:
    clouds = json.loads(r[2])
    labels = [cl.get('label') for cl in clouds]
    print(f'{r[0]}/{r[1]}: clouds count = {len(clouds)}, labels = {labels}')
