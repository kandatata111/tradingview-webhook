#!/usr/bin/env python
"""
Flask サーバー自動再起動スクリプト
サーバーがクラッシュした場合、自動的に再起動します
"""

import subprocess
import sys
import time
from datetime import datetime
import pytz
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'webhook_error.log')
RENDER_SERVER = os.path.join(BASE_DIR, 'render_server.py')

def log_event(message):
    """イベントをログファイルに記録"""
    jst = pytz.timezone('Asia/Tokyo')
    timestamp = datetime.now(jst).isoformat()
    full_message = f'{timestamp} - {message}'
    
    print(full_message)
    
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{full_message}\n')
    except:
        pass

def run_server():
    """Flask サーバーを実行（クラッシュするまで）"""
    log_event('[AUTO-RESTART] Starting Flask server...')
    
    try:
        # Python サーバーをサブプロセスで実行
        process = subprocess.Popen(
            [sys.executable, RENDER_SERVER],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8'
        )
        
        # プロセスの出力をリアルタイムでログに記録
        while True:
            line = process.stdout.readline()
            if not line:
                # プロセスが終了した
                break
            
            output_line = line.strip()
            if output_line:
                print(output_line)
                try:
                    with open(LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(f'{output_line}\n')
                except:
                    pass
        
        return_code = process.wait()
        log_event(f'[AUTO-RESTART] Flask server exited with code {return_code}')
        
    except Exception as e:
        log_event(f'[AUTO-RESTART ERROR] {str(e)}')

def main():
    """メインループ：サーバー再起動を試みる"""
    jst = pytz.timezone('Asia/Tokyo')
    log_event(f'\n{"="*80}')
    log_event(f'[AUTO-RESTART] Auto-restart wrapper started at {datetime.now(jst).isoformat()}')
    log_event(f'{"="*80}\n')
    
    restart_count = 0
    
    while True:
        restart_count += 1
        log_event(f'[AUTO-RESTART] Restart attempt #{restart_count}')
        
        run_server()
        
        log_event(f'[AUTO-RESTART] Server crashed/exited. Restarting in 5 seconds...')
        time.sleep(5)

if __name__ == '__main__':
    main()
