import sqlite3
from datetime import datetime

conn = sqlite3.connect('webhook_data.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# テーブル一覧
print('=== テーブル一覧 ===')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
for t in tables:
    print(t['name'])

# fire_historyテーブルの内容確認
print('\n=== fire_history テーブル（最新20件） ===')
try:
    cur.execute("SELECT * FROM fire_history ORDER BY rowid DESC LIMIT 20")
    rows = cur.fetchall()
    if rows:
        print(f"カラム: {rows[0].keys()}")
        for row in rows:
            print(dict(row))
except Exception as e:
    print(f"Error: {e}")

# statesテーブルの15分足を確認
print('\n=== states テーブル（15分足のみ） ===')
try:
    cur.execute("SELECT * FROM states WHERE timeframe='15m' ORDER BY rowid DESC LIMIT 10")
    for row in cur.fetchall():
        print(dict(row))
except Exception as e:
    print(f"Error: {e}")

# rulesテーブルの内容確認
print('\n=== rules テーブル ===')
try:
    cur.execute("SELECT * FROM rules")
    for row in cur.fetchall():
        print(dict(row))
except Exception as e:
    print(f"Error: {e}")

conn.close()
