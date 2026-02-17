import sqlite3
p = r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\render_production_db.db'
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT tf, row_order, clouds_json, symbol FROM states WHERE row_order IS NOT NULL AND row_order != ''")
rows = cur.fetchall()
problems = []
for tf, row_order, clouds_json, symbol in rows:
    ro = row_order
    # If row_order contains numeric-only tokens like '15' or '60' (without m/H) while clouds_json uses '15m'/'1H', report
for tf, row_order, clouds_json, symbol in rows:
    if '15,' in row_order or row_order.startswith('15') or ',15' in row_order:
        if '15m' not in row_order:
            problems.append((symbol, tf, row_order))
    if '60,' in row_order or row_order.startswith('60') or ',60' in row_order:
        if '1H' not in row_order and '60' in row_order:
            problems.append((symbol, tf, row_order))

print('Checked', len(rows), 'rows. Found potential mismatches:')
for p in problems[:50]:
    print(p)

conn.close()