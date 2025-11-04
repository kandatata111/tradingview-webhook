"""APIレスポンスでtopPrice/bottomPriceを確認"""
import requests
import json
import time

print("サーバーに接続中...")
time.sleep(2)

try:
    r = requests.get('http://localhost:5000/current_states')
    print(f"ステータスコード: {r.status_code}")
    
    data = r.json()
    print(f"取得したデータ: {len(data.get('states', []))} states")
    
    if data.get('states'):
        state = data['states'][0]
        print(f"\nシンボル: {state.get('symbol')}")
        print(f"価格: {state.get('price')}")
        
        print("\n=== 5m雲データ ===")
        cloud_5m = state['clouds']['5m']
        for key, value in cloud_5m.items():
            print(f"  {key}: {value}")
        
        print("\n=== topPrice/bottomPrice確認 ===")
        print(f"5m  topPrice: {cloud_5m.get('topPrice', 'NOT FOUND')}")
        print(f"5m  bottomPrice: {cloud_5m.get('bottomPrice', 'NOT FOUND')}")
        print(f"15m topPrice: {state['clouds']['15m'].get('topPrice', 'NOT FOUND')}")
        print(f"15m bottomPrice: {state['clouds']['15m'].get('bottomPrice', 'NOT FOUND')}")
        
except Exception as e:
    print(f"エラー: {e}")
    import traceback
    traceback.print_exc()
