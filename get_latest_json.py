"""
本番サーバー(TradingViewから実際にデータを受信している)から
最新のJSONコードを取得してクリップボードにコピー
"""
import requests
import json
import pyperclip

# 本番サーバーのURL (TradingViewから実際のデータを受信)
PRODUCTION_URL = 'https://tradingview-webhook-s5x1.onrender.com/current_states'

# ローカルサーバーのURL (テスト用データのみ)
LOCAL_URL = 'http://localhost:5000/current_states'

print("どちらのサーバーからJSONを取得しますか?")
print("1. 本番サーバー (TradingViewから最新データを受信) - 推奨")
print("2. ローカルサーバー (テストデータのみ)")
choice = input("選択 (1 or 2): ").strip()

if choice == '1':
    url = PRODUCTION_URL
    print(f"\n📡 本番サーバーに接続中: {url}")
else:
    url = LOCAL_URL
    print(f"\n📡 ローカルサーバーに接続中: {url}")

try:
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        # JSONを整形して取得
        json_data = response.json()
        formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
        
        # クリップボードにコピー
        pyperclip.copy(formatted_json)
        
        print("✅ JSONコードをクリップボードにコピーしました!")
        print("\n--- JSONプレビュー ---")
        print(formatted_json[:500] + "..." if len(formatted_json) > 500 else formatted_json)
        
        # ファイルにも保存
        with open('latest_json.json', 'w', encoding='utf-8') as f:
            f.write(formatted_json)
        print("\n📁 latest_json.json ファイルにも保存しました")
        
    else:
        print(f"❌ エラー: ステータスコード {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("❌ サーバーに接続できません。render_server.pyが起動しているか確認してください")
except Exception as e:
    print(f"❌ エラー: {e}")
