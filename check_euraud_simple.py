"""
EURAUD日足の更新確認（エンコードエラー回避版）
"""
import sqlite3
from datetime import datetime
import pytz

DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'
JST = pytz.timezone('Asia/Tokyo')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# EURAUD日足のみ
cursor.execute('''
    SELECT symbol, tf, timestamp, received_at, price, daytrade_bos
    FROM states
    WHERE symbol = 'EURAUD' AND tf = 'D'
''')

row = cursor.fetchone()

if row:
    symbol, tf, timestamp, received_at, price, daytrade_bos = row
    
    print('=== EURAUD Daily (D) Record ===')
    print(f'Symbol: {symbol}')
    print(f'Timeframe: {tf}')
    print(f'Data Timestamp: {timestamp}')
    print(f'Received At: {received_at}')
    print(f'Price: {price}')
    print(f'Daytrade BOS: {daytrade_bos}')
    
    # 受信日時の比較
    if '2026-02-05' in str(received_at) and '07:01' in str(received_at):
        print('\n✅ SUCCESS! Data has been updated to 2026-02-05 07:01:xx')
    elif '2026-01-30' in str(received_at):
        print('\n❌ FAILED! Data is still 2026-01-30 (old data)')
    else:
        print(f'\n⚠️ Unexpected received_at: {received_at}')
else:
    print('❌ No EURAUD D record found!')

# 他の時間足も確認
print('\n=== All EURAUD Timeframes ===')
cursor.execute('''
    SELECT tf, received_at
    FROM states
    WHERE symbol = 'EURAUD'
    ORDER BY 
        CASE tf
            WHEN 'D' THEN 1
            WHEN '4H' THEN 2
            WHEN '240' THEN 2
            WHEN '1H' THEN 3
            WHEN '60' THEN 3
            WHEN '15m' THEN 4
            WHEN '15' THEN 4
            ELSE 99
        END
''')

rows = cursor.fetchall()
for tf, rcv in rows:
    print(f'{tf:5s}: {rcv}')

conn.close()
