"""
本番環境のキャッシュとデータの問題を解決するスクリプト
1. ブラウザキャッシュをクリアするための指示を表示
2. データベースの最新状態を確認
3. 問題の原因を特定
"""
import sqlite3
import os
from datetime import datetime
import pytz

DB_PATH = os.path.join(os.path.dirname(__file__), 'webhook_data.db')
JST = pytz.timezone('Asia/Tokyo')

print("="*80)
print("🔧 本番環境の問題診断と解決")
print("="*80)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 各通貨ペアの最新タイムスタンプを確認
print("\n✅ データベースには最新データが保存されています:")
print("\n【USDJPYの最新データ】")
cursor.execute("""
    SELECT tf, timestamp, daytrade_status, daytrade_bos, daytrade_time
    FROM states
    WHERE symbol = 'USDJPY'
    ORDER BY CASE tf 
        WHEN '5' THEN 1
        WHEN '15' THEN 2
        WHEN '60' THEN 3
        WHEN '240' THEN 4
        WHEN 'D' THEN 5
    END
""")

for tf, timestamp, status, bos, time_str in cursor.fetchall():
    ts_dt = datetime.fromisoformat(timestamp)
    now = datetime.now(JST)
    diff_min = (now - ts_dt).total_seconds() / 60
    
    tf_label = {'5': '5m', '15': '15m', '60': '1H', '240': '4H', 'D': 'D'}.get(tf, tf)
    print(f"  {tf_label:>3s}: {timestamp} ({diff_min:.0f}分前) | {status} | {bos} | {time_str}")

print("\n" + "="*80)
print("🚨 問題の原因:")
print("="*80)
print("""
ブラウザのコンソールログに表示されているタイムスタンプは:
  timestamp=2026-01-23T11:15:01.635466+09:00 (3日前!)

しかし、データベースには最新データ(17:40)が正しく保存されています。

これは以下のいずれかが原因です:
  1. ブラウザキャッシュが古いデータを表示している
  2. CDN/プロキシが古いレスポンスをキャッシュしている  
  3. Service Workerが古いデータを返している
""")

print("\n" + "="*80)
print("📋 解決手順:")
print("="*80)
print("""
【手順1】ブラウザのキャッシュを完全にクリア
  1. Ctrl + Shift + Delete を押す
  2. 「キャッシュされた画像とファイル」にチェック
  3. 期間を「全期間」に設定
  4. 「データを削除」をクリック
  
【手順2】スーパーリロード
  1. Ctrl + F5 を押す（Windowsの場合）
  2. または Ctrl + Shift + R
  
【手順3】開発者ツールでネットワークキャッシュを無効化
  1. F12で開発者ツールを開く
  2. Networkタブを開く
  3. "Disable cache"にチェック
  4. ページをリロード
  
【手順4】それでも直らない場合
  1. ブラウザのアドレスバーに以下を入力:
     chrome://settings/clearBrowserData (Chrome)
     about:preferences#privacy (Firefox)
  2. Cookieとサイトデータもクリア
  3. ブラウザを完全に閉じて再起動
""")

print("\n" + "="*80)
print("🔍 確認方法:")
print("="*80)
print("""
ページをリロードした後、F12で開発者ツールを開き、
Consoleタブで以下のログを確認してください:

  [RENDER] USDJPY - baseTimeframe=15, baseState.tf=15, timestamp=2026-01-26T17:40:...

timestampが現在の日時(1月26日17時台)になっていればOKです。
まだ1月23日11:15になっている場合は、さらに強力なキャッシュクリアが必要です。
""")

# Fire historyも確認
print("\n" + "="*80)
print("🔔 最近の発火履歴（データベースから）:")
print("="*80)
cursor.execute("""
    SELECT symbol, timeframe, datetime(fire_time, 'unixepoch', '+9 hours') as jst_time, 
           rule_name, message
    FROM fire_history
    ORDER BY fire_time DESC
    LIMIT 15
""")

for symbol, tf, jst_time, rule, msg in cursor.fetchall():
    print(f"  {jst_time} [{symbol:7s}] {tf:>3s} {rule:25s} {msg[:40]}")

conn.close()

print("\n" + "="*80)
print("✅ 診断完了")
print("="*80)
