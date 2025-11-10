"""
ローカル開発用サーバー起動スクリプト
- render_server.py をインポートして使用
- SQLiteを使用（PostgreSQL不要）
- 自動的にブラウザを開く
- ホットリロード有効
- テストデータ自動送信機能付き
"""
import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

# 環境変数をローカル用に設定
os.environ['FLASK_ENV'] = 'development'
os.environ['RENDER'] = 'false'  # Render環境ではないことを明示
os.environ['PORT'] = '5000'

# .env.localから環境変数を読み込み（存在する場合）
env_file = Path(__file__).parent / '.env.local'
if env_file.exists():
    print("📝 Loading local environment variables...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# ブラウザが既に開かれたかどうかを追跡
browser_opened = False

def wait_for_server(url='http://localhost:5000/health', timeout=30):
    """サーバーが起動するまで待機"""
    import requests
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False

def send_test_data():
    """テストデータを自動送信（クリップボードからJSONを取得）"""
    import requests
    import json
    import subprocess
    
    print("\n🧪 テストデータ送信準備中...")
    
    # PowerShellでクリップボードの内容を取得
    try:
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Clipboard'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            clipboard_content = result.stdout.strip()
            print("📋 クリップボードからデータを取得しました")
            
            # JSONとしてパース
            try:
                json_data = json.loads(clipboard_content)
                print("✅ JSONパース成功")
                
                # /current_states のレスポンス形式かチェック
                if isinstance(json_data, dict) and 'states' in json_data and isinstance(json_data['states'], list) and len(json_data['states']) > 0:
                    print("📊 /current_states 形式を検出しました。TradingView形式に変換します")
                    # states[0] を取り出して TradingView形式に変換
                    state = json_data['states'][0]
                    test_data = convert_current_state_to_webhook_format(state)
                else:
                    # そのまま使用（TradingViewの生JSONと仮定）
                    test_data = json_data
                
            except json.JSONDecodeError as e:
                print(f"❌ クリップボードの内容が有効なJSONではありません: {e}")
                print("   デフォルトのテストデータを使用します")
                test_data = get_default_test_data()
        else:
            print("📋 クリップボードが空です。デフォルトのテストデータを使用します")
            test_data = get_default_test_data()
            
    except Exception as e:
        print(f"❌ クリップボード取得エラー: {e}")
        print("   デフォルトのテストデータを使用します")
        test_data = get_default_test_data()
    
    # Webhook送信
    try:
        response = requests.post('http://localhost:5000/webhook', json=test_data)
        print(f"✅ テストデータ送信完了: {response.status_code}")
        if response.status_code == 200:
            response_data = response.json()
            print(f"📨 レスポンス: {response_data.get('message', 'OK')}")
            if response_data.get('notifications', 0) > 0:
                print(f"🔔 {response_data['notifications']}件の通知を生成")
        else:
            print(f"📨 エラー: {response.text}")
    except Exception as e:
        print(f"❌ 送信失敗: {e}")

def convert_current_state_to_webhook_format(state):
    """current_states の形式を TradingView webhook の形式に変換"""
    # clouds を配列形式に変換
    clouds_array = []
    if 'clouds' in state and isinstance(state['clouds'], dict):
        for label, cloud_data in state['clouds'].items():
            cloud = {
                'label': label,
                'tf': label,  # 仮定
                'gc': cloud_data.get('gc', False),
                'fire_count': cloud_data.get('fire_count', 0),
                'max_reached': False,  # 情報がないのでFalse
                'thickness': cloud_data.get('thickness', 0),
                'angle': cloud_data.get('angle', 0),
                'elapsed': str(cloud_data.get('elapsed', '')),
                'distance_from_price': cloud_data.get('distance_from_price', 0),
                'distance_from_prev': cloud_data.get('distance_from_prev', 0)
            }
            clouds_array.append(cloud)
    
    # TradingView webhook形式に変換
    webhook_data = {
        'symbol': state.get('symbol', 'UNKNOWN'),
        'tf': state.get('tf', '5'),
        'time': int(state.get('timestamp', '2025-01-01T00:00:00').replace('-', '').replace(':', '').replace('T', '').replace('.', '')[:13]),  # 簡易変換
        'state': {'flag': '', 'word': ''},  # 情報がないので空
        'daytrade': {
            'status': state.get('daily_dow', {}).get('status', ''),
            'bos': state.get('daily_dow', {}).get('bos', ''),
            'time': state.get('daily_dow', {}).get('time', '')
        },
        'swing': {
            'status': state.get('swing_dow', {}).get('status', ''),
            'bos': state.get('swing_dow', {}).get('bos', ''),
            'time': state.get('swing_dow', {}).get('time', '')
        },
        'row_order': state.get('row_order', ['price', '5m', '15m', '1H', '4H']),
        'cloud_order': state.get('cloud_order', ['5m', '15m', '1H', '4H']),
        'clouds': clouds_array,
        'price': state.get('price', 0)
    }
    
    return webhook_data

def get_default_test_data():
    """デフォルトのテストデータを返す"""
    return {
        "symbol": "USDJPY",
        "tf": "5",
        "time": 1761015000000,
        "state": {
            "flag": "",
            "word": ""
        },
        "daytrade": {
            "status": "上昇ダウ",
            "bos": "",
            "time": 85
        },
        "swing": {
            "status": "上昇ダウ",
            "bos": "",
            "time": 70
        },
        "row_order": ["price", "5m", "15m", "1H", "4H"],
        "cloud_order": ["5m", "15m", "1H", "4H"],
        "clouds": [
            {
                "label": "5m",
                "tf": "5m",
                "gc": True,
                "fire_count": 0,
                "max_reached": False,
                "thickness": 8.4931644999,
                "angle": 34.9518849832,
                "elapsed": 80,
                "distance_from_price": 13.8942757109,
                "distance_from_prev": 14.09754284913
            },
            {
                "label": "15m",
                "tf": "15m",
                "gc": True,
                "fire_count": 0,
                "max_reached": False,
                "thickness": 8.1868170684,
                "angle": 34.1117507595,
                "elapsed": 65,
                "distance_from_price": 27.9738185599,
                "distance_from_prev": 12.16005330563
            },
            {
                "label": "1H",
                "tf": "1H",
                "gc": True,
                "fire_count": 2,
                "max_reached": False,
                "thickness": 4.8675369955,
                "angle": 1.5,
                "elapsed": 95,
                "distance_from_price": 0.29,
                "distance_from_prev": 0.5
            }
        ],
        "price": 151.219
    }

def main():
    print("=" * 60)
    print("🚀 ローカル開発サーバーを起動中...")
    print("=" * 60)
    print(f"\n📁 作業ディレクトリ: {os.getcwd()}")
    print(f"🔧 開発モード: {os.environ.get('FLASK_ENV')}")
    print(f"🗄️  データベース: SQLite (webhook_data.db)")

    # render_server.py をインポート
    try:
        from render_server import app, init_db
        print("\n✅ render_server.py のインポート成功")
    except ImportError as e:
        print(f"\n❌ render_server.py のインポート失敗: {e}")
        print("   render_server.py が同じディレクトリにあることを確認してください")
        sys.exit(1)

    # データベースを初期化
    print("\n📦 データベースを初期化中...")
    try:
        init_db()
        print("✅ データベース初期化完了")
    except Exception as e:
        print(f"❌ データベース初期化失敗: {e}")
        sys.exit(1)

    # サーバーを起動
    print("\n🌐 Flaskサーバーを起動中...")
    print("   URL: http://localhost:5000")
    print("   ダッシュボード: http://localhost:5000/")
    print("   終了: Ctrl+C\n")

    # 別スレッドでサーバー起動を待ってブラウザを開く
    def open_browser_when_ready():
        global browser_opened
        if browser_opened:
            return  # 既にブラウザを開いている場合は何もしない
        
        # Flaskのリローダーの子プロセスでは実行しない
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            if wait_for_server():
                print("✅ サーバー起動完了！")
                time.sleep(1)
                print("🌐 ブラウザを開いています...")
                webbrowser.open('http://localhost:5000')
                browser_opened = True  # ブラウザを開いたことを記録

                # 5秒後にテストデータを送信
                print("\n⏳ 5秒後にテストデータを送信します...\n")
                time.sleep(5)
                send_test_data()

                print("\n💡 ヒント:")
                print("   - render_server.py を編集すると自動的にリロードされます")
                print("   - テストデータを再送信: python send_test_webhook.py")
                print("   - 全テスト実行: python test_webhook.py local all")

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    # Flaskサーバーを起動（ホットリロード有効）
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 サーバーを停止しました")
        sys.exit(0)