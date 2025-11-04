"""
本番サーバーから最新のJSONデータを取得して
ローカルサーバーのデータベースに同期する
"""
import requests
import json
import sqlite3

PRODUCTION_URL = 'https://tradingview-webhook-s5x1.onrender.com/current_states'
LOCAL_DB = 'webhook_data.db'

print("🔄 本番サーバーから最新データを取得中...")

try:
    # 本番サーバーから最新データを取得
    response = requests.get(PRODUCTION_URL, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ 最新データを取得しました")
        
        # JSONをファイルに保存
        with open('latest_json.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("📁 latest_json.json に保存しました")
        
        # 本番データをローカルサーバーに送信
        if 'states' in data and len(data['states']) > 0:
            state = data['states'][0]
            
            # Webhook形式に変換（全てのデータを含める）
            webhook_data = {
                'symbol': state.get('symbol', 'USDJPY'),
                'price': state.get('price', 0),
                'tf': state.get('tf', '5'),
                'clouds': state.get('clouds', {}),
                'daily_dow': state.get('daily_dow', {}),
                'swing_dow': state.get('swing_dow', {})
            }
            
            print("\n🔄 ローカルサーバーにデータを送信中...")
            local_response = requests.post(
                'http://localhost:5000/webhook',
                json=webhook_data,
                timeout=5
            )
            
            if local_response.status_code == 200:
                print("✅ ローカルサーバーのデータベースを更新しました!")
                print("\n📊 更新内容:")
                print(f"  シンボル: {webhook_data['symbol']}")
                print(f"  価格: {webhook_data['price']}")
                if '5m' in webhook_data['clouds']:
                    cloud_5m = webhook_data['clouds']['5m']
                    print(f"  5m雲: topPrice={cloud_5m.get('topPrice', 'N/A')}, bottomPrice={cloud_5m.get('bottomPrice', 'N/A')}")
                
                print("\n✅ http://localhost:5000 を更新して最新データを確認できます")
            else:
                print(f"❌ ローカルサーバーへの送信失敗: {local_response.status_code}")
                print("ヒント: render_server.py が起動しているか確認してください")
        else:
            print("⚠️ 本番サーバーにデータがありません")
    else:
        print(f"❌ エラー: ステータスコード {response.status_code}")
        
except requests.exceptions.ConnectionError as e:
    if 'localhost' in str(e):
        print("❌ ローカルサーバーに接続できません")
        print("💡 render_server.py を起動してから再実行してください")
    else:
        print("❌ 本番サーバーに接続できません")
        print(f"エラー: {e}")
except Exception as e:
    print(f"❌ エラー: {e}")
