"""
ローカルDB（webhook_data.db）のEURAUDデータを詳細調査
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
    SELECT symbol, tf, timestamp, price, clouds_json, row_order, cloud_order, received_at,
           daytrade_status, daytrade_bos
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
            WHEN '5m' THEN 5
            WHEN '5' THEN 5
            ELSE 99
        END
''')

rows = cursor.fetchall()

if not rows:
    print('❌ No EURAUD data found in database!')
else:
    print(f'Total EURAUD records: {len(rows)}\n')
    
    for row in rows:
        symbol, tf, timestamp, price, clouds_json, row_order, cloud_order, received_at, daytrade_status, daytrade_bos = row
        
        print('='*70)
        print(f'Timeframe: {tf}')
        print(f'  Data Timestamp: {timestamp}')
        print(f'  Received At: {received_at}')
        print(f'  Price: {price}')
        print(f'  Daytrade: {daytrade_status} / {daytrade_bos}')
        print(f'  Row Order: {row_order}')
        print(f'  Cloud Order: {cloud_order}')
        
        # cloudsをパース
        if clouds_json:
            try:
                clouds = json.loads(clouds_json)
                print(f'  Clouds count: {len(clouds)}')
                
                # 各cloudの詳細
                for cloud in clouds:
                    label = cloud.get('label', 'N/A')
                    gc_val = cloud.get('gc', None)
                    
                    # gcの表示
                    if isinstance(gc_val, bool):
                        gc = 'GC' if gc_val else 'DC'
                    else:
                        gc = str(gc_val)
                    
                    thickness = cloud.get('thickness', 'N/A')
                    angle = cloud.get('angle', 'N/A')
                    dauten = cloud.get('dauten', 'N/A')
                    po = cloud.get('po', 'N/A')
                    
                    # 小数点2桁に丸める
                    if isinstance(thickness, (int, float)):
                        thickness = f'{thickness:.2f}'
                    if isinstance(angle, (int, float)):
                        angle = f'{angle:.2f}'
                    
                    print(f'    [{label:3s}] GC:{gc:5s} thick:{thickness:>7s} angle:{angle:>7s} dauten:{dauten:10s} PO:{po}')
            except Exception as e:
                print(f'  ❌ Failed to parse clouds: {e}')
                print(f'  Raw clouds (first 300 chars): {clouds_json[:300]}')
        else:
            print(f'  ⚠️ No clouds data!')
        
        print()

# 比較: 他の通貨ペアの状態
print('\n' + '='*70)
print('=== Other Symbols Status (for comparison) ===\n')
cursor.execute('''
    SELECT symbol, COUNT(*) as cnt
    FROM states
    GROUP BY symbol
    ORDER BY symbol
''')
symbol_stats = cursor.fetchall()
for sym, cnt in symbol_stats:
    print(f'  {sym}: {cnt} timeframes')

# 全体の最終更新時刻
print('\n' + '='*70)
print('=== Latest Updates per Symbol (D timeframe) ===\n')
cursor.execute('''
    SELECT symbol, tf, timestamp, received_at
    FROM states
    WHERE tf IN ('D', 'W', 'M')
    ORDER BY symbol, tf
''')
daily_rows = cursor.fetchall()
for sym, tf, ts, rcv in daily_rows:
    print(f'{sym:8s} {tf:3s}: timestamp={ts}, received={rcv}')

conn.close()
