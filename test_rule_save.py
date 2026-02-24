import requests, json

url = 'http://localhost:5000/rules'
rule = {
    'id': 'rule_test_demo',
    'name': 'テスト D 表示足',
    'displayTf': 'D',
    'scope': {'symbol': ''},
    'voice': {'message': 'テスト'},
    'cloudAlign': {'allTimeframes': False, 'timeframes': [], 'missingBehavior': 'ignore'},
    'conditions': [{'timeframe':'D','field':'dauten','value':''}],
    'enabled': True
}
print('sending',rule)
resp = requests.post(url, json=rule)
print(resp.status_code, resp.text)

# now fetch rules
r = requests.get(url)
print(r.status_code, json.dumps(r.json(), ensure_ascii=False, indent=2))