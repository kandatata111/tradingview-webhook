import requests
import time

# サーバーが起動するまで待機
time.sleep(1)

r = requests.get('http://localhost:5000/current_states')
states = r.json()['states']

print(f'Total states: {len(states)}')
for i, s in enumerate(states):
    print(f'{i}: {s["symbol"]} - {s["timestamp"]}')
