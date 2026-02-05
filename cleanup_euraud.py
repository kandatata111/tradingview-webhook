"""
EURAUDの重複・空レコードをクリーンアップ
"""
import sqlite3
import json

DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== EURAUD Cleanup ===\n')

# 全EURAUDレコードを確認
cursor.execute('''
    SELECT rowid, tf, clouds_json, received_at
    FROM states
    WHERE symbol = 'EURAUD'
    ORDER BY tf
''')

rows = cursor.fetchall()

print('Current EURAUD records:')
for rowid, tf, clouds_json, received_at in rows:
    clouds_count = 0
    if clouds_json:
        try:
            clouds = json.loads(clouds_json)
            clouds_count = len(clouds)
        except:
            pass
    
    status = '✅ OK' if clouds_count > 0 else '❌ EMPTY'
    print(f'  rowid={rowid:3d}, tf={tf:5s}, clouds={clouds_count}, received={received_at[:19] if received_at else "N/A"}, {status}')

# 空のレコードを特定
print('\n--- Identifying empty records ---')
cursor.execute('''
    SELECT rowid, tf
    FROM states
    WHERE symbol = 'EURAUD' AND (clouds_json IS NULL OR clouds_json = '' OR clouds_json = '[]')
''')

empty_rows = cursor.fetchall()

if empty_rows:
    print(f'Found {len(empty_rows)} empty records:')
    for rowid, tf in empty_rows:
        print(f'  rowid={rowid}, tf={tf}')
    
    response = input('\nDelete these empty records? (yes/no): ')
    if response.lower() == 'yes':
        for rowid, tf in empty_rows:
            cursor.execute('DELETE FROM states WHERE rowid = ?', (rowid,))
            print(f'  Deleted: rowid={rowid}, tf={tf}')
        
        conn.commit()
        print(f'\n✅ {len(empty_rows)} records deleted')
    else:
        print('Cancelled')
else:
    print('No empty records found')

# 重複チェック（同じtfが複数）
print('\n--- Checking for duplicates ---')
cursor.execute('''
    SELECT tf, COUNT(*) as cnt
    FROM states
    WHERE symbol = 'EURAUD'
    GROUP BY tf
    HAVING cnt > 1
''')

duplicates = cursor.fetchall()

if duplicates:
    print(f'Found {len(duplicates)} duplicate timeframes:')
    for tf, cnt in duplicates:
        print(f'  {tf}: {cnt} records')
        
        # 各重複の詳細
        cursor.execute('''
            SELECT rowid, clouds_json, received_at
            FROM states
            WHERE symbol = 'EURAUD' AND tf = ?
            ORDER BY received_at DESC
        ''', (tf,))
        
        tf_rows = cursor.fetchall()
        for i, (rowid, clouds_json, received_at) in enumerate(tf_rows):
            clouds_count = 0
            if clouds_json:
                try:
                    clouds = json.loads(clouds_json)
                    clouds_count = len(clouds)
                except:
                    pass
            
            marker = '[LATEST]' if i == 0 else '[OLD]'
            print(f'    {marker} rowid={rowid}, clouds={clouds_count}, received={received_at[:19] if received_at else "N/A"}')
        
        # 最新以外を削除
        print(f'  Keep only the latest record for {tf}?')
        response = input('  Delete old duplicates? (yes/no): ')
        if response.lower() == 'yes':
            # 最新のrowid以外を削除
            latest_rowid = tf_rows[0][0]
            for rowid, _, _ in tf_rows[1:]:
                cursor.execute('DELETE FROM states WHERE rowid = ?', (rowid,))
                print(f'    Deleted: rowid={rowid}')
            
            conn.commit()
            print(f'  ✅ Kept rowid={latest_rowid}, deleted {len(tf_rows)-1} old records')
else:
    print('No duplicates found')

conn.close()

print('\n=== Cleanup Complete ===')
