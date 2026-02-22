import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

# Get latest USDJPY record
c.execute("SELECT symbol, tf, clouds_json FROM states WHERE symbol = 'USDJPY' ORDER BY rowid DESC LIMIT 5")
rows = c.fetchall()

for symbol, tf, clouds_json in rows:
    print(f'\n=== {symbol} TF={tf} ===')
    try:
        clouds = json.loads(clouds_json)
        for cloud in clouds:
            label = cloud.get('label')
            dauten = cloud.get('dauten')
            gc = cloud.get('gc')
            bos_count = cloud.get('bos_count')
            print(f'  Label: {label}, Dauten: {repr(dauten)}, GC: {repr(gc)}, BOS: {repr(bos_count)}')
    except Exception as e:
        print(f'  Error parsing JSON: {e}')

conn.close()
