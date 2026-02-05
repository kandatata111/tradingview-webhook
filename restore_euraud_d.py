"""
EURAUDの最新バックアップファイルを使ってDBを復旧
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import pytz

BACKUP_DIR = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'
JST = pytz.timezone('Asia/Tokyo')

# EURAUDの最新日足ファイルを取得
euraud_d_folder = Path(BACKUP_DIR) / 'EURAUD' / 'D'
files = list(euraud_d_folder.glob('*.json'))
if not files:
    print('❌ No EURAUD D files found!')
    exit(1)

# 最新ファイル
latest_file = max(files, key=lambda f: f.stat().st_mtime)
print(f'Latest EURAUD D file: {latest_file.name}')
print(f'File modified: {datetime.fromtimestamp(latest_file.stat().st_mtime, tz=JST).strftime("%Y-%m-%d %H:%M:%S")}')

# ファイルを読み込み
with open(latest_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'\nJSON data:')
print(f'  Symbol: {data.get("symbol")}')
print(f'  TF: {data.get("tf")}')
print(f'  Clouds: {len(data.get("clouds", []))}')
print(f'  Daytrade BOS: {data.get("daytrade", {}).get("bos")}')

# ファイル名から日時を抽出
# 20260205_070101_D_1770242461000.json
parts = latest_file.stem.split('_')
date_str = parts[0]  # 20260205
time_str = parts[1]  # 070101
time_ms = int(parts[3])  # 1770242461000

received_dt = datetime.fromtimestamp(time_ms / 1000, tz=JST)
received_at = received_dt.isoformat()

print(f'  Received At: {received_at}')

# DBに保存（trend_strength_calculator_v2.pyのロジックを使用）
print('\n=== Updating Database ===')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 現在のEURAUD Dレコードを確認
cursor.execute('SELECT timestamp, received_at FROM states WHERE symbol = ? AND tf = ?', ('EURAUD', 'D'))
old_record = cursor.fetchone()
if old_record:
    print(f'Old record: timestamp={old_record[0]}, received={old_record[1]}')

# trend_strength_calculator_v2.pyの処理をシミュレート
# (実際にはrender_server.pyを経由する必要があるが、直接DBを更新してテスト)

symbol = data.get('symbol')
tf = data.get('tf')
clouds = data.get('clouds', [])
daytrade = data.get('daytrade', {})
po = data.get('po', {})
row_order = data.get('row_order', [])

# cloudsから各データを抽出
clouds_json = json.dumps(clouds, ensure_ascii=False)
row_order_str = ','.join(row_order) if row_order else ''

# cloud_orderを生成（labelの順序）
cloud_order = [c['label'] for c in clouds]
cloud_order_str = ','.join(cloud_order)

# daytrade情報
daytrade_bos = daytrade.get('bos', '')

# 現在のtimestampを生成
timestamp = datetime.now(JST).isoformat()

print(f'\nNew data to save:')
print(f'  Symbol: {symbol}')
print(f'  TF: {tf}')
print(f'  Timestamp: {timestamp}')
print(f'  Received At: {received_at}')
print(f'  Clouds JSON length: {len(clouds_json)}')
print(f'  Row Order: {row_order_str}')
print(f'  Cloud Order: {cloud_order_str}')
print(f'  Daytrade BOS: {daytrade_bos}')

# 確認
response = input('\nDo you want to update the database? (yes/no): ')
if response.lower() != 'yes':
    print('Cancelled.')
    conn.close()
    exit(0)

# render_server.pyのprocess_data()を呼び出すのではなく、
# まずは手動でJSONをPOSTする方法を提示
print('\n✅ To properly restore the data, please:')
print('1. Ensure render_server.py is running (python TradingViewWebhook/render_server.py)')
print('2. Use the Dashboard UI to restore the latest EURAUD D backup file')
print('3. Select "Replace Mode" to overwrite the old data')
print('')
print('Alternatively, you can POST the JSON directly:')
print(f'  File: {latest_file}')
print(f'  JSON: {json.dumps(data, ensure_ascii=False)[:200]}...')

conn.close()
