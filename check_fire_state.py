import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
cursor = conn.cursor()

# 「5分ダウ+交差」ルールの最近の発火履歴
print("=== 5分ダウ+交差 ルールの発火履歴 ===")
cursor.execute("""
    SELECT rule_id, symbol, fired_at, last_state_snapshot 
    FROM fire_history 
    WHERE rule_id = '5分ダウ+交差' 
    ORDER BY fired_at DESC 
    LIMIT 5
""")

rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"\nルール: {row[0]}")
        print(f"シンボル: {row[1]}")
        print(f"発火時刻: {row[2]}")
        if row[3]:
            state = json.loads(row[3])
            print(f"状態スナップショット: {json.dumps(state, ensure_ascii=False, indent=2)}")
        else:
            print("状態スナップショット: None")
else:
    print("発火履歴なし")

# 現在のDB状態を確認
print("\n\n=== 現在のDB状態 (USDJPY) ===")
cursor.execute("""
    SELECT symbol, tf, clouds_json 
    FROM states 
    WHERE symbol = 'USDJPY' 
    ORDER BY 
        CASE tf 
            WHEN '5' THEN 1 
            WHEN '15' THEN 2 
            WHEN '60' THEN 3 
            WHEN '240' THEN 4 
            ELSE 5 
        END
""")

for row in cursor.fetchall():
    symbol, tf, clouds_json = row
    if clouds_json:
        clouds = json.loads(clouds_json)
        if clouds:
            cloud = clouds[0]  # 最初のクラウド
            print(f"\n{symbol}/{tf}:")
            print(f"  dauten: {cloud.get('dauten', 'N/A')}")
            print(f"  gc: {cloud.get('gc', 'N/A')}")
            print(f"  bos_count: {cloud.get('bos_count', 'N/A')}")

conn.close()
