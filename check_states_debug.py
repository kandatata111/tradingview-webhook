import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

# states テーブルのカラムを確認
c.execute("PRAGMA table_info(states)")
columns = c.fetchall()
print("=== states テーブルのカラム一覧 ===")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# 最新データを確認
print("\n=== 最新の states データ（USDJPY/5m）===")
c.execute('SELECT * FROM states WHERE symbol = "USDJPY" AND tf = "5" ORDER BY rowid DESC LIMIT 1')
row = c.fetchone()

if row:
    col_names = [d[0] for d in c.description]
    state_dict = dict(zip(col_names, row))
    
    # 重要なフィールドをチェック
    important_fields = ['dauten', 'bos_count', 'gc', 'daytrade_status', 'daytrade_bos', 'daytrade_time']
    
    print("重要なフィールド:")
    for field in important_fields:
        value = state_dict.get(field)
        print(f"  {field}: {value} (type: {type(value).__name__})")
    
    print("\nすべてのフィールド:")
    for k, v in state_dict.items():
        if k not in important_fields:
            print(f"  {k}: {v}")
else:
    print("データなし")

conn.close()
