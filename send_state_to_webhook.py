import sqlite3, json, requests, os

# pick a specific state row
DB_PATH = os.path.join(os.path.dirname(__file__), 'webhook_data.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT symbol, tf, clouds_json, time, row_order, cloud_order, sent_time FROM states LIMIT 1')
row = c.fetchone()
conn.close()
if not row:
    print('no rows')
    exit(1)
symbol, tf, clouds_json, time_val, row_order, cloud_order, sent_time = row
print('sending', symbol, tf)
def safe_load(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []

ndata = {
    'symbol': symbol,
    'tf': tf,
    'clouds': json.loads(clouds_json) if clouds_json else [],
    'time': time_val,
    'row_order': safe_load(row_order),
    'cloud_order': safe_load(cloud_order),
    'sent_time': sent_time or ''
}
resp = requests.post('http://localhost:5000/webhook', json=ndata)
print('status', resp.status_code, resp.text)

# now fetch current_states for debugging
try:
    resp2 = requests.get('http://localhost:5000/current_states')
    print('fetched current_states, total states', len(resp2.json().get('states', [])))
    with open('last_states.json', 'w', encoding='utf-8') as f:
        json.dump(resp2.json(), f, ensure_ascii=False, indent=2)
    print('saved last_states.json')
except Exception as e:
    print('error fetching current_states', e)
