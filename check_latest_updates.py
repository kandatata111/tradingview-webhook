import sqlite3
from datetime import datetime
import pytz

db_path = 'webhook_data.db'
jst = pytz.timezone('Asia/Tokyo')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 100)
print("📊 USDJPY 全時間軸の最新状態（タイムスタンプ順）")
print("=" * 100)

cursor.execute("""
    SELECT tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, price
    FROM states
    WHERE symbol = 'USDJPY'
    ORDER BY timestamp DESC
""")

for row in cursor.fetchall():
    tf, timestamp, daytrade_status, daytrade_bos, daytrade_time, price = row
    print(f"\n時間軸: {tf}")
    print(f"  タイムスタンプ: {timestamp}")
    print(f"  ダウ転: {daytrade_status}")
    print(f"  BOS: {daytrade_bos}")
    print(f"  ダウ転時間: {daytrade_time}")
    print(f"  価格: {price}")

conn.close()
