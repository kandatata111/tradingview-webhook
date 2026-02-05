"""
EURAUDの全時間足の最新バックアップをサーバーに送信
"""
import json
import requests
from pathlib import Path
from datetime import datetime
import pytz
import time

BACKUP_DIR = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
JST = pytz.timezone('Asia/Tokyo')

# 復旧する時間足
timeframes = ['D', '4H', '1H', '15m', '5m']

print('=== EURAUD Backup Restoration ===\n')

for tf in timeframes:
    print(f'--- Timeframe: {tf} ---')
    
    # フォルダ確認
    folder = Path(BACKUP_DIR) / 'EURAUD' / tf
    if not folder.exists():
        print(f'  ⚠️ Folder not found: {folder}')
        continue
    
    # ファイル一覧
    files = list(folder.glob('*.json'))
    if not files:
        print(f'  ⚠️ No files found')
        continue
    
    # 最新ファイル
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest_file.stat().st_mtime, tz=JST)
    
    print(f'  File: {latest_file.name}')
    print(f'  Modified: {mtime.strftime("%Y-%m-%d %H:%M:%S")}')
    
    # ファイル読み込み
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f'  Symbol: {data.get("symbol")}, TF: {data.get("tf")}, Clouds: {len(data.get("clouds", []))}')
    
    # サーバーに送信
    url = 'http://localhost:5000/webhook'
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f'  ✅ Sent successfully')
        else:
            print(f'  ❌ Failed: status {response.status_code}')
            print(f'     Response: {response.text[:100]}')
    except requests.exceptions.ConnectionError:
        print(f'  ❌ Connection failed! Server not running?')
        break
    except Exception as e:
        print(f'  ❌ Error: {e}')
    
    # サーバー負荷軽減のため少し待機
    time.sleep(0.5)
    print()

print('=== Restoration Complete ===')
