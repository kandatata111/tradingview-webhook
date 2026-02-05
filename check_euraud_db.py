"""
ローカルDB（webhook_data.db）のEURAUDデータを調査
"""
import sqlite3
import json
from datetime import datetime
import pytz

DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'
JST = pytz.timezone('Asia/Tokyo')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== EURAUD Data in Local DB (webhook_data.db) ===\n')

# EURAUDのデータを取得
cursor.execute('''
    SELECT symbol, timeframe, clouds, timestamp, last_updated
    FROM states
    WHERE symbol = 'EURAUD'
    ORDER BY timeframe
''')

rows = cursor.fetchall()

if not rows:
    print('❌ No EURAUD data found in database!')
else:
    print(f'Total EURAUD records: {len(rows)}\n')
    
    for row in rows:
        symbol, tf, clouds_json, timestamp, last_updated = row
        
        # タイムスタンプを変換
        if timestamp:
            ts_dt = datetime.fromtimestamp(timestamp / 1000, tz=JST)
            ts_str = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            ts_str = 'N/A'
        
        if last_updated:
            lu_dt = datetime.fromtimestamp(last_updated, tz=JST)
            lu_str = lu_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            lu_str = 'N/A'
        
        print(f'Timeframe: {tf}')
        print(f'  Data Timestamp: {ts_str}')
        print(f'  Last Updated: {lu_str}')
        
        # cloudsをパース
        if clouds_json:
            try:
                clouds = json.loads(clouds_json)
                print(f'  Clouds count: {len(clouds)}')
                
                # 各cloudの詳細
                for cloud in clouds:
                    label = cloud.get('label', 'N/A')
                    gc = cloud.get('gc', 'N/A')
                    thickness = cloud.get('thickness', 'N/A')
                    angle = cloud.get('angle', 'N/A')
                    dauten = cloud.get('dauten', 'N/A')
                    po = cloud.get('po', 'N/A')
                    print(f'    [{label}] GC:{gc}, thickness:{thickness}, angle:{angle}, dauten:{dauten}, PO:{po}')
            except Exception as e:
                print(f'  ❌ Failed to parse clouds: {e}')
                print(f'  Raw clouds (first 200 chars): {clouds_json[:200]}')
        else:
            print(f'  ⚠️ No clouds data!')
        
        print()

# 全テーブルの統計
print('\n=== Database Statistics ===')
cursor.execute('SELECT COUNT(DISTINCT symbol) FROM states')
symbol_count = cursor.fetchone()[0]
print(f'Total symbols: {symbol_count}')

cursor.execute('SELECT COUNT(*) FROM states')
total_records = cursor.fetchone()[0]
print(f'Total records: {total_records}')

cursor.execute('SELECT symbol, COUNT(*) as cnt FROM states GROUP BY symbol ORDER BY cnt DESC')
symbol_stats = cursor.fetchall()
print(f'\nRecords per symbol:')
for sym, cnt in symbol_stats:
    print(f'  {sym}: {cnt}')

conn.close()
