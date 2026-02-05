"""
EURAUDの最新日足データをlocalhost:5000に送信してDBを更新
"""
import json
import requests
from pathlib import Path
from datetime import datetime
import pytz

BACKUP_DIR = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
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
print(f'  PO Status: {data.get("po", {}).get("status")}')

# render_serverに送信
url = 'http://localhost:5000/webhook'
headers = {'Content-Type': 'application/json'}

print(f'\n=== Sending to {url} ===')

try:
    response = requests.post(url, json=data, headers=headers, timeout=10)
    
    if response.status_code == 200:
        print(f'✅ Success! Status code: {response.status_code}')
        print(f'Response: {response.text[:200]}')
    else:
        print(f'❌ Failed! Status code: {response.status_code}')
        print(f'Response: {response.text}')
except requests.exceptions.ConnectionError:
    print('❌ Connection failed! Is render_server.py running?')
    print('   Please start the server first:')
    print('   cd C:\\Users\\kanda\\Desktop\\PythonData')
    print('   python TradingViewWebhook/render_server.py')
except Exception as e:
    print(f'❌ Error: {e}')
