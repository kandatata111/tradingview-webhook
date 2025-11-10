import requests

r = requests.get('http://localhost:5000/current_states')
data = r.json()

if data['states']:
    state = data['states'][0]
    print(f"✅ 最新データ:")
    print(f"Symbol: {state['symbol']}")
    print(f"Price: {state['price']}")
    print(f"\n雲データ:")
    for tf in ['5m', '15m', '1H', '4H']:
        cloud = state['clouds'][tf]
        print(f"{tf}: topPrice={cloud['topPrice']}, bottomPrice={cloud['bottomPrice']}")
else:
    print("データなし")
