import urllib.request, json, sys
url = 'http://localhost:5000/current_states'
try:
    data = json.load(urllib.request.urlopen(url))
except Exception as e:
    print('ERROR fetching', url, e)
    sys.exit(1)
states = [s for s in data.get('states', []) if s.get('symbol') == 'USDJPY' and str(s.get('tf')) in ('15','15m')]
print(json.dumps(states, ensure_ascii=False, indent=2))
