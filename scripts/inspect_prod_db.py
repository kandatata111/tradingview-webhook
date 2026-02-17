import sqlite3, json, pprint
p = r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\render_production_db.db'
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT tf, clouds_json, row_order FROM states WHERE symbol='USDJPY' ORDER BY tf")
rows = cur.fetchall()
out = []
for tf, clouds_json, row_order in rows:
    try:
        clouds = json.loads(clouds_json) if clouds_json else None
    except Exception as e:
        clouds = f'ERROR: {e}'
    out.append((tf, clouds, row_order))

pprint.pprint(out)
conn.close()