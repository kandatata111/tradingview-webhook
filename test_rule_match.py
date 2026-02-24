import sqlite3, json, sys
sys.path.insert(0, '.')
from ichimoku_utils import _evaluate_rule_match

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

c.execute('SELECT id, name, rule_json FROM rules WHERE enabled = 1')
rules = c.fetchall()

c.execute('SELECT symbol, tf, clouds_json, cloud_order FROM states ORDER BY rowid DESC')
all_states = c.fetchall()
conn.close()

# symbol -> {tf -> row} のマップ
states_map = {}
for sym, tf, cj, co in all_states:
    if sym not in states_map:
        states_map[sym] = {}
    states_map[sym][tf] = (cj, co)

_tf_priority = ['5', '15', '60', '240', '1440', '10080']

for rule_id, rule_name, rule_json in rules:
    rule = json.loads(rule_json)
    cond_tfs = [(c.get('timeframe') or c.get('label', '')) for c in rule.get('conditions', [])]
    
    _tf_label_to_db = {'5m':['5','5m'],'15m':['15','15m'],'1H':['60','1H'],'4H':['240','4H'],'D':['D','1440'],'W':['W','10080']}
    candidate_db_tfs = []
    for lbl in ['5m','15m','1H','4H','D','W']:
        if lbl in cond_tfs:
            candidate_db_tfs.extend(_tf_label_to_db[lbl])
    if not candidate_db_tfs:
        candidate_db_tfs = _tf_priority[:]
    
    print(f"\n=== {rule_name} (candidate_db_tfs={candidate_db_tfs}) ===")
    
    for sym in sorted(states_map.keys()):
        sym_states = states_map[sym]
        found_row = None
        for db_tf in candidate_db_tfs:
            if db_tf in sym_states and sym_states[db_tf][0]:
                found_row = sym_states[db_tf]
                break
        if not found_row:
            print(f"  {sym}: no data")
            continue
        
        cj, co = found_row
        clouds = json.loads(cj)
        cloud_data = {}
        for cloud in clouds:
            label = cloud.get('label')
            if label:
                cloud_data[label] = cloud
        if co:
            cloud_data['__cloud_order__'] = co
        
        direction = _evaluate_rule_match(rule, cloud_data)
        if direction:
            print(f"  {sym}: MATCH direction={direction}")
        else:
            # デバッグ: 条件の実際の値を表示
            for cond in rule.get('conditions', []):
                tf_lbl = cond.get('timeframe') or cond.get('label')
                fld = cond.get('field')
                td = cloud_data.get(tf_lbl, {})
                val = td.get(fld) if td else 'KEY_NOT_FOUND'
                print(f"  {sym}: NO_MATCH tf={tf_lbl} field={fld} actual={val!r} keys={list(cloud_data.keys())[:6]}")
                break
