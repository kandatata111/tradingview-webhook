"""
ローカルDBのスキーマ確認
"""
import sqlite3

DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# テーブル一覧
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('=== Tables in webhook_data.db ===')
for table in tables:
    print(f'  {table[0]}')

print('\n=== Schema for states table ===')
cursor.execute("PRAGMA table_info(states)")
columns = cursor.fetchall()
for col in columns:
    print(f'  {col[1]} ({col[2]})')

# EURAUDのデータがあるか確認
print('\n=== EURAUD Records ===')
cursor.execute('SELECT * FROM states WHERE symbol = "EURAUD"')
rows = cursor.fetchall()
print(f'Total EURAUD records: {len(rows)}')

if len(rows) > 0:
    print('\nColumn names:')
    for i, desc in enumerate(cursor.description):
        print(f'  {i}: {desc[0]}')
    
    print('\nFirst record:')
    for i, val in enumerate(rows[0]):
        col_name = cursor.description[i][0]
        if isinstance(val, str) and len(val) > 100:
            print(f'  {col_name}: {val[:100]}...')
        else:
            print(f'  {col_name}: {val}')

conn.close()
