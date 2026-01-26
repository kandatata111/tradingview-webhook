"""
データベースの15Mを15に修正し、古いデータをクリーンアップ
"""
import sqlite3
import os
from datetime import datetime, timedelta
import pytz

DB_PATH = os.path.join(os.path.dirname(__file__), 'webhook_data.db')
JST = pytz.timezone('Asia/Tokyo')

print("="*80)
print("🔧 データベース修復スクリプト")
print("="*80)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 問題1: 15M → 15 に修正
print("\n【修正1】15M を 15 に変更...")
cursor.execute("SELECT COUNT(*) FROM states WHERE tf = '15M'")
count_15m = cursor.fetchone()[0]
print(f"  15M のレコード数: {count_15m}")

if count_15m > 0:
    # 既存の15のレコードを削除
    cursor.execute("DELETE FROM states WHERE tf = '15'")
    deleted = cursor.rowcount
    print(f"  既存の15のレコードを削除: {deleted}件")
    
    # 15M を 15 に変更
    cursor.execute("UPDATE states SET tf = '15' WHERE tf = '15M'")
    updated = cursor.rowcount
    print(f"  15Mを15に変更: {updated}件")
    
    conn.commit()
    print("  ✅ 修正完了")
else:
    print("  15Mのレコードは見つかりませんでした")

# 修正後の状態を確認
print("\n【確認】各通貨ペアの最新タイムスタンプ:")
cursor.execute("""
    SELECT symbol, tf, timestamp
    FROM states
    ORDER BY symbol, 
             CASE tf 
                WHEN '5' THEN 1
                WHEN '15' THEN 2
                WHEN '60' THEN 3
                WHEN '240' THEN 4
                WHEN 'D' THEN 5
             END
""")

current_symbol = None
for symbol, tf, timestamp in cursor.fetchall():
    if symbol != current_symbol:
        print(f"\n  【{symbol}】")
        current_symbol = symbol
    
    try:
        ts_dt = datetime.fromisoformat(timestamp)
        now = datetime.now(JST)
        diff_hours = (now - ts_dt).total_seconds() / 3600
        
        tf_label = {'5': '5m', '15': '15m', '60': '1H', '240': '4H', 'D': 'D'}.get(tf, tf)
        
        age_str = ""
        if diff_hours < 1:
            age_str = f"({diff_hours*60:.0f}分前)"
        elif diff_hours < 24:
            age_str = f"({diff_hours:.1f}時間前)"
        else:
            age_str = f"({diff_hours/24:.1f}日前) ⚠️"
        
        jst_time = ts_dt.strftime('%m/%d %H:%M')
        print(f"    {tf_label:>3s}: {jst_time} {age_str}")
    except Exception as e:
        print(f"    {tf}: エラー - {str(e)[:30]}")

conn.close()

print("\n" + "="*80)
print("✅ 修復完了")
print("="*80)
print("\n次のステップ:")
print("  1. ブラウザでCtrl+Shift+Deleteを押してキャッシュをクリア")
print("  2. Ctrl+F5でスーパーリロード")
print("  3. 表示が最新になったか確認")
