"""
データベースの状態を診断するスクリプト
- 最新のタイムスタンプを確認
- 各通貨ペアの最終更新時刻を表示
- webhookログを確認
"""
import sqlite3
import os
from datetime import datetime
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'webhook_data.db')
JST = pytz.timezone('Asia/Tokyo')

print("="*80)
print("データベース診断レポート")
print("="*80)

# データベースファイルの存在確認
if not os.path.exists(DB_PATH):
    print(f"❌ データベースが見つかりません: {DB_PATH}")
    exit(1)

db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
print(f"\n📁 データベースファイル:")
print(f"   パス: {DB_PATH}")
print(f"   サイズ: {db_size_mb:.2f} MB")
print(f"   最終更新: {datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime('%Y-%m-%d %H:%M:%S')}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# テーブル一覧
print(f"\n📋 テーブル一覧:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"   - {table[0]}: {count} レコード")

# statesテーブルの最新データ
print(f"\n🕐 各通貨ペアの最新タイムスタンプ (statesテーブル):")
cursor.execute("""
    SELECT symbol, tf, last_update_time
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
states = cursor.fetchall()

current_symbol = None
for symbol, tf, last_update_str in states:
    if symbol != current_symbol:
        if current_symbol:
            print()
        print(f"\n   【{symbol}】")
        current_symbol = symbol
    
    # タイムスタンプ文字列をパース
    try:
        # ISO 8601形式をパース (2026-01-23T11:15:01.635466+09:00)
        ts_dt = datetime.fromisoformat(last_update_str)
        now = datetime.now(JST)
        diff_hours = (now - ts_dt).total_seconds() / 3600
        diff_hours = (now - ts_dt).total_seconds() / 3600
        
        tf_label = {
            '5': '5m',
            '15': '15m',
            '60': '1H',
            '240': '4H',
            'D': 'D'
        }.get(tf, tf)
        
        age_str = ""
        if diff_hours < 1:
            age_str = f"({diff_hours*60:.0f}分前)"
        elif diff_hours < 24:
            age_str = f"({diff_hours:.1f}時間前)"
        else:
            age_str = f"({diff_hours/24:.1f}日前) ⚠️"
        
        jst_time = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
        print(f"      {tf_label:>3s}: {jst_time} {age_str}")
    except Exception as e:
        print(f"      {tf}: パースエラー - {last_update_str[:50]}")

# 最も古いデータと新しいデータ
print(f"\n📊 タイムスタンプ分析:")
# last_update_timeは文字列なので、直接比較
cursor.execute("SELECT MIN(last_update_time), MAX(last_update_time) FROM states")
min_str, max_str = cursor.fetchone()

if min_str and max_str:
    try:
        min_dt = datetime.fromisoformat(min_str)
        max_dt = datetime.fromisoformat(max_str)
        max_dt = datetime.fromisoformat(max_str)
        print(f"   最古のデータ: {min_dt.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"   最新のデータ: {max_dt.strftime('%Y-%m-%d %H:%M:%S')} JST")
        
        now = datetime.now(JST)
        hours_ago = (now - max_dt).total_seconds() / 3600
        
        if hours_ago > 24:
            print(f"   ⚠️ 警告: 最新データが {hours_ago/24:.1f}日前で古すぎます!")
        elif hours_ago > 1:
            print(f"   ⚠️ 注意: 最新データが {hours_ago:.1f}時間前です")
        else:
            print(f"   ✅ 最新データは {hours_ago*60:.0f}分前で正常です")
    except Exception as e:
        print(f"   エラー: {e}")

# fire_historyテーブルの最新発火
print(f"\n🔔 最近の発火履歴 (fire_history):")
cursor.execute("""
    SELECT symbol, timeframe, fire_time, rule_name, message
    FROM fire_history
    ORDER BY fire_time DESC
    LIMIT 10
""")
fires = cursor.fetchall()

if fires:
    for symbol, tf, fire_time, rule, msg in fires:
        fire_dt = datetime.fromtimestamp(fire_time, tz=JST)
        print(f"   {fire_dt.strftime('%m/%d %H:%M')} [{symbol:7s}] {tf:>3s} {rule:20s} {msg[:50]}")
else:
    print("   発火履歴なし")

# webhookログファイルの確認
log_file = os.path.join(BASE_DIR, 'webhook_log.txt')
error_log_file = os.path.join(BASE_DIR, 'webhook_error.log')

print(f"\n📝 ログファイル:")
if os.path.exists(log_file):
    log_size = os.path.getsize(log_file) / 1024
    log_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
    print(f"   webhook_log.txt: {log_size:.1f} KB (最終更新: {log_mtime.strftime('%Y-%m-%d %H:%M:%S')})")
else:
    print(f"   webhook_log.txt: ファイルなし")

if os.path.exists(error_log_file):
    error_size = os.path.getsize(error_log_file) / 1024
    error_mtime = datetime.fromtimestamp(os.path.getmtime(error_log_file))
    print(f"   webhook_error.log: {error_size:.1f} KB (最終更新: {error_mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # エラーログの最後の数行を表示
    print(f"\n   最新のエラーログ (最後の10行):")
    with open(error_log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(f"      {line.rstrip()}")
else:
    print(f"   webhook_error.log: ファイルなし")

conn.close()

print("\n" + "="*80)
print("診断完了")
print("="*80)
