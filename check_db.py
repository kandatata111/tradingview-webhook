import sqlite3

# データベース接続
conn = sqlite3.connect('webhook_data.db')
cursor = conn.cursor()

# テーブル一覧を取得
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [table[0] for table in cursor.fetchall()]
print("📊 データベース内のテーブル:")
print(tables)

# current_statesテーブルのカラム名を確認
if 'current_states' in tables:
    cursor.execute("PRAGMA table_info(current_states)")
    columns = cursor.fetchall()
    print(f"\n📋 current_statesのカラム:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # データを取得
    cursor.execute("SELECT * FROM current_states ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"\n📈 最新データ (timestamp: {row[1]}):")
        for i, col in enumerate(columns):
            if 'topPrice' in col[1] or 'bottomPrice' in col[1]:
                print(f"  {col[1]}: {row[i]}")
    else:
        print("\n⚠️ データが見つかりません")

conn.close()
