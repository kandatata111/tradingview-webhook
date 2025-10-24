"""
ローカル環境で完全なテストを実行
"""
import subprocess
import time
import requests
import json

print("=" * 60)
print("ローカル環境完全テスト")
print("=" * 60)

# ステップ1: Pythonプロセスをクリーンアップ
print("\n[1] Pythonプロセスをクリーンアップ中...")
try:
    subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                   stderr=subprocess.DEVNULL, 
                   stdout=subprocess.DEVNULL)
    time.sleep(2)
    print("✅ クリーンアップ完了")
except:
    pass

# ステップ2: データベースマイグレーション
print("\n[2] データベースマイグレーション実行中...")
result = subprocess.run(['python', 'migrate_database.py'], 
                       capture_output=True, 
                       text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"❌ エラー: {result.stderr}")

# ステップ3: サーバー起動
print("\n[3] サーバー起動中...")
server_process = subprocess.Popen(
    ['python', 'render_server.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)
time.sleep(5)
print("✅ サーバー起動完了")

# ステップ4: テストデータ送信
print("\n[4] テストデータ送信中...")

test_data = {
    "symbol": "USDJPY",
    "price": 152.6,
    "tf": "5",
    "daytrade": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "20"
    },
    "swing": {
        "status": "上昇ダウ",
        "bos": "",
        "time": "1425"
    },
    "row_order": ["5m", "15m", "price", "1H", "4H"],
    "cloud_order": ["5m", "15m", "1H", "4H"],
    "clouds": [
        {
            "label": "5m",
            "gc": True,
            "fire_count": 0,
            "thickness": 0.8765790013,
            "angle": 21.89154077,
            "elapsed": "45",
            "distance_from_price": -1.0197433676,
            "distance_from_prev": 0,
            "topPrice": 152.605803314,
            "bottomPrice": 152.5978145413
        },
        {
            "label": "15m",
            "gc": False,
            "fire_count": 8,
            "thickness": 0.1712263538,
            "angle": 17.0466275589,
            "elapsed": "315",
            "distance_from_price": -0.2144865016,
            "distance_from_prev": 0.8053071366,
            "topPrice": 152.5950004968,
            "bottomPrice": 152.5938283323
        },
        {
            "label": "1H",
            "gc": True,
            "fire_count": 5,
            "thickness": 1.5,
            "angle": 25.5,
            "elapsed": "3600",
            "distance_from_price": 5.2,
            "distance_from_prev": 3.1,
            "topPrice": 152.8,
            "bottomPrice": 152.5
        },
        {
            "label": "4H",
            "gc": False,
            "fire_count": 2,
            "thickness": 2.3,
            "angle": 30.2,
            "elapsed": "14400",
            "distance_from_price": 10.5,
            "distance_from_prev": 5.8,
            "topPrice": 153.2,
            "bottomPrice": 152.4
        }
    ]
}

try:
    response = requests.post('http://localhost:5000/webhook', json=test_data, timeout=5)
    print(f"✅ ステータスコード: {response.status_code}")
    print(f"レスポンス: {response.json()}")
except Exception as e:
    print(f"❌ エラー: {e}")

# ステップ5: データベース直接確認
print("\n[5] データベース直接確認...")
import sqlite3
conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

c.execute('''SELECT symbol, price, 
             cloud_5m_topPrice, cloud_5m_bottomPrice, 
             cloud_15m_topPrice, cloud_15m_bottomPrice,
             cloud_1h_topPrice, cloud_1h_bottomPrice,
             cloud_4h_topPrice, cloud_4h_bottomPrice
             FROM current_states 
             WHERE symbol='USDJPY' 
             ORDER BY timestamp DESC LIMIT 1''')

row = c.fetchone()
if row:
    print(f"\n✅ データベースの内容:")
    print(f"Symbol: {row[0]}")
    print(f"Price: {row[1]}")
    print(f"\n雲データ (データベース):")
    print(f"5m:  topPrice={row[2]}, bottomPrice={row[3]}")
    print(f"15m: topPrice={row[4]}, bottomPrice={row[5]}")
    print(f"1H:  topPrice={row[6]}, bottomPrice={row[7]}")
    print(f"4H:  topPrice={row[8]}, bottomPrice={row[9]}")
    
    # 期待値との比較
    print(f"\n📊 期待値との比較:")
    print(f"5m:  期待={test_data['clouds'][0]['topPrice']:.4f}/{test_data['clouds'][0]['bottomPrice']:.4f}, 実際={row[2]}/{row[3]}")
    print(f"15m: 期待={test_data['clouds'][1]['topPrice']:.4f}/{test_data['clouds'][1]['bottomPrice']:.4f}, 実際={row[4]}/{row[5]}")
    print(f"1H:  期待={test_data['clouds'][2]['topPrice']:.1f}/{test_data['clouds'][2]['bottomPrice']:.1f}, 実際={row[6]}/{row[7]}")
    print(f"4H:  期待={test_data['clouds'][3]['topPrice']:.1f}/{test_data['clouds'][3]['bottomPrice']:.1f}, 実際={row[8]}/{row[9]}")
    
    # 一致チェック
    if (abs(row[2] - test_data['clouds'][0]['topPrice']) < 0.0001 and
        abs(row[3] - test_data['clouds'][0]['bottomPrice']) < 0.0001):
        print("\n✅ データベース保存: 正しい")
    else:
        print("\n❌ データベース保存: 不一致")
else:
    print("❌ データが見つかりません")

conn.close()

# ステップ6: API経由でデータ確認
print("\n[6] API経由でデータ確認...")
time.sleep(1)
try:
    response = requests.get('http://localhost:5000/current_states', timeout=5)
    data = response.json()
    
    if data['states']:
        state = data['states'][0]
        print(f"\n✅ API レスポンス:")
        print(f"Symbol: {state['symbol']}")
        print(f"Price: {state['price']}")
        print(f"\n雲データ (API):")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            print(f"{tf}: topPrice={cloud.get('topPrice', 'なし')}, bottomPrice={cloud.get('bottomPrice', 'なし')}")
        
        # ★マーク判定
        print(f"\n★マーク判定 (価格 {state['price']}):")
        for tf in ['5m', '15m', '1H', '4H']:
            cloud = state['clouds'].get(tf, {})
            top = cloud.get('topPrice', 0)
            bottom = cloud.get('bottomPrice', 0)
            if top and bottom and bottom <= state['price'] <= top:
                print(f"  {tf} ★ (範囲内: {bottom} ≤ {state['price']} ≤ {top})")
            else:
                print(f"  {tf}   (範囲外)")
    else:
        print("❌ データがありません")
        
except Exception as e:
    print(f"❌ エラー: {e}")

# サーバープロセスを終了
print("\n[7] クリーンアップ中...")
server_process.terminate()
time.sleep(1)

print("\n" + "=" * 60)
print("テスト完了")
print("=" * 60)
