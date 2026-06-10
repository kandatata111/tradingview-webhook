import sqlite3
conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
for row in c.execute("SELECT id, name, scope_json, rule_json, enabled FROM rules ORDER BY id"):
    print('id', row[0], 'name', row[1], 'enabled', row[4])
    print(' scope=', row[2])
    print(' rule=', row[3])
    print()
conn.close()