import sqlite3, json
conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
print('tables:', [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])
print('rules count', c.execute('SELECT COUNT(*) FROM rules').fetchone()[0])
print('recent rules:')
for row in c.execute('SELECT id, name FROM rules ORDER BY id DESC LIMIT 20'):
    print(row)
print('\nfire_history count:', c.execute('SELECT COUNT(*) FROM fire_history').fetchone()[0])
print('\nlast 30 fire_history:')
for row in c.execute('SELECT id, rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot FROM fire_history ORDER BY id DESC LIMIT 30'):
    print('id', row[0], 'rule', row[1], 'sym', row[2], 'tf', row[3], 'fired_at', row[4])
    try:
        cs = json.loads(row[5])
    except Exception:
        cs = row[5]
    if isinstance(cs, dict):
        print('  conditions_snapshot dict', cs)
    elif isinstance(cs, list):
        print('  conditions_snapshot LIST len', len(cs))
    else:
        print('  conditions_snapshot', cs)
    try:
        ls = json.loads(row[6])
    except Exception:
        ls = row[6]
    if isinstance(ls, dict):
        print('  last_state_snapshot keys', list(ls.keys())[:20], 'len', len(ls))
    else:
        print('  last_state_snapshot', ls)
conn.close()