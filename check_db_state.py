import sqlite3
import json

DB_PATH = r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 各タイムフレームの現在の状態を確認
c.execute("""SELECT symbol, tf, clouds_json, timestamp 
             FROM states 
             WHERE tf IN ('5', '15', '60', '240') AND symbol='USDJPY' 
             ORDER BY tf""")
rows = c.fetchall()

print("=== USDJPY 現在のDB状態 ===")
for r in rows:
    symbol, tf, clouds_json, timestamp = r
    print(f"\n[{symbol}/{tf}] timestamp: {timestamp}")
    if clouds_json:
        try:
            clouds = json.loads(clouds_json)
            for cloud in clouds:
                label = cloud.get('label', '?')
                dauten = cloud.get('dauten', 'N/A')
                gc = cloud.get('gc', 'N/A')
                print(f"  {label}: dauten={dauten}, gc={gc}")
        except Exception as e:
            print(f"  (parse error: {e})")

conn.close()
