import requests, json
r = requests.get('http://127.0.0.1:5000/current_states')
data = r.json()
states = data.get('states', [])
from collections import defaultdict
by_symbol = defaultdict(list)
for s in states:
    by_symbol[s['symbol']].append(s)

for symbol in sorted(by_symbol.keys()):
    print('='*40)
    print(symbol)
    for s in sorted(by_symbol[symbol], key=lambda x: x['tf']):
        clouds = [c.get('label') for c in s.get('clouds', [])]
        print(f"  tf={s['tf']}, tf_normalized={s.get('tf_normalized')}, row_order={s.get('row_order')}, clouds={clouds}, price={s.get('price')}")
    print()