import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

print("=== ルール評価シミュレーション ===\n")

# 1. 有効なルールを取得
c.execute('SELECT id, name, rule_json FROM rules WHERE enabled = 1')
rules = c.fetchall()

print(f"有効なルール数: {len(rules)}\n")

# 2. USDJPY の全タイムフレームデータを取得
symbol = 'USDJPY'
tf_states = {}
base_cols = None

for tf_key, tf_label in [('5', '5m'), ('15', '15m'), ('60', '1H'), ('240', '4H')]:
    c.execute('SELECT * FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol, tf_key))
    tf_row = c.fetchone()
    if tf_row:
        if base_cols is None:
            base_cols = [d[0] for d in c.description]
        tf_state = dict(zip(base_cols, tf_row))
        tf_states[tf_label] = tf_state

print(f"取得したタイムフレーム: {list(tf_states.keys())}\n")

# 3. clouds_json を解析してクラウドデータを抽出
tf_cloud_data = {}

for tf_label, tf_state in tf_states.items():
    clouds_json_str = tf_state.get('clouds_json', '[]')
    try:
        clouds = json.loads(clouds_json_str)
        for cloud in clouds:
            if cloud.get('label') == tf_label or cloud.get('tf') == tf_label:
                tf_cloud_data[tf_label] = cloud
                print(f"[{tf_label}] dauten={cloud.get('dauten')}, gc={cloud.get('gc')}, bos_count={cloud.get('bos_count')}")
                break
    except Exception as e:
        print(f"[{tf_label}] JSON解析エラー: {e}")
        tf_cloud_data[tf_label] = {}

print(f"\nクラウドデータ抽出完了: {list(tf_cloud_data.keys())}\n")

# 4. 各ルールを評価
for rule_id, rule_name, rule_json in rules:
    print(f"=== ルール: {rule_name} (ID: {rule_id}) ===")
    
    try:
        rule = json.loads(rule_json)
        conditions = rule.get('conditions', [])
        
        print(f"条件数: {len(conditions)}")
        
        all_matched = True
        
        for i, cond in enumerate(conditions):
            tf_label = cond.get('label')
            field = cond.get('field')
            value = cond.get('value')
            
            print(f"  条件 {i+1}: {tf_label}.{field} == {value}")
            
            # クラウドデータから値を取得
            cloud_data = tf_cloud_data.get(tf_label)
            
            if cloud_data is None:
                print(f"    → ✗ クラウドデータなし")
                all_matched = False
                break
            
            found_value = cloud_data.get(field)
            print(f"    → 実際の値: {found_value} (type: {type(found_value).__name__})")
            
            # 条件をチェック
            condition_met = False
            if value is None:
                # Presence check
                condition_met = found_value is not None
                print(f"    → Presence check: {condition_met}")
            else:
                # Value check
                condition_met = found_value == value
                print(f"    → Value check: {found_value} == {value} → {condition_met}")
            
            if not condition_met:
                all_matched = False
                print(f"    → ✗ 条件不一致")
            else:
                print(f"    → ✓ 条件一致")
        
        print(f"\n最終結果: {'✓ ルール一致' if all_matched else '✗ ルール不一致'}\n")
        
        # 一致した場合、発火履歴をチェック
        if all_matched:
            c.execute('''SELECT last_state_snapshot, fired_at FROM fire_history 
                         WHERE rule_id = ? AND symbol = ?
                         ORDER BY fired_at DESC LIMIT 1''', (rule_id, symbol))
            last_fire = c.fetchone()
            
            if last_fire:
                print(f"前回の発火: {last_fire[1]}")
                try:
                    last_state = json.loads(last_fire[0])
                    print(f"前回の状態: {json.dumps(last_state, ensure_ascii=False)}")
                except:
                    print(f"前回の状態: 解析エラー")
                
                # 現在の状態
                current_state = {
                    'dauten': {k: tf_cloud_data[k].get('dauten', '') for k in tf_cloud_data}
                }
                print(f"現在の状態: {json.dumps(current_state, ensure_ascii=False)}")
                
                if json.dumps(current_state, sort_keys=True) != json.dumps(last_state, sort_keys=True):
                    print("→ 状態変化あり、発火すべき")
                else:
                    print("→ 状態変化なし、発火スキップ")
            else:
                print("前回の発火なし → 初回発火すべき")
        
        print()
        
    except Exception as e:
        print(f"エラー: {e}\n")
        import traceback
        traceback.print_exc()

conn.close()
