"""
バックアップファイルの最新状態を確認
"""
import os
from pathlib import Path
from datetime import datetime
import pytz

BACKUP_DIR = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
JST = pytz.timezone('Asia/Tokyo')

symbols = ['USDJPY', 'EURUSD', 'GBPUSD', 'EURJPY', 'GBPJPY', 'AUDJPY', 'EURAUD', 'GBPAUD', 'AUDUSD']
timeframes = ['D', 'W', 'M', '4H', '1H', '15m', '5m']

print('=== Backup Status (Latest Files) ===\n')

for symbol in symbols:
    print(f'{symbol}:')
    for tf in timeframes:
        folder = Path(BACKUP_DIR) / symbol / tf
        if not folder.exists():
            print(f'  {tf:3s}: [NO FOLDER]')
            continue
        
        files = list(folder.glob('*.json'))
        if not files:
            print(f'  {tf:3s}: [EMPTY]')
            continue
        
        # 最新ファイルを取得
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        mtime = latest_file.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=JST)
        
        # ファイル名から日時を抽出（20260205_070101_D_1770242461000.json）
        try:
            parts = latest_file.stem.split('_')
            date_str = parts[0]  # 20260205
            time_str = parts[1]  # 070101
            formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
            formatted_time = f'{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}'
            data_time = f'{formatted_date} {formatted_time}'
        except:
            data_time = latest_file.stem
        
        print(f'  {tf:3s}: {data_time} (file: {dt.strftime("%m/%d %H:%M")})')
    
    print()
