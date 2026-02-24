import sqlite3, json, os
import render_server

# prepare sample data: pick a symbol and tf value from states
conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
c.execute('SELECT symbol, tf, clouds_json, time FROM states LIMIT 1')
row = c.fetchone()
conn.close()
if not row:
    print('no state in db')
    exit(0)

symbol, tf, clouds_json, time_val = row
print('using state', symbol, tf)

# parse clouds_json to construct data dict similar to webhook
clouds = json.loads(clouds_json) if clouds_json else []
data = {
    'symbol': symbol,
    'tf': tf,
    'clouds': clouds,
    'time': time_val,
}

# call evaluation
render_server.evaluate_and_fire_rules(data, symbol, tf)
print('active_fires now:', render_server.active_fires)

# also inspect the current_states output to see if last_fire fields are populated
try:
    resp = render_server.current_states()
    print('[TEST] current_states length:', len(resp.get('states', [])))
    fires = [s for s in resp.get('states', []) if s.get('last_fire')]
    print('[TEST] states with last_fire:', fires)
except Exception as e:
    print('unable to call current_states:', e)
