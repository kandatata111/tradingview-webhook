from flask import Flask, request, jsonify, render_template
import os, sqlite3, json
from datetime import datetime
import threading
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
DB_PATH = os.path.join(BASE_DIR, 'webhook_data.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS states (
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        timestamp TEXT,
        price REAL,
        time INTEGER,
        state_flag TEXT,
        state_word TEXT,
        daytrade_status TEXT,
        daytrade_bos TEXT,
        daytrade_time TEXT,
        swing_status TEXT,
        swing_bos TEXT,
        swing_time TEXT,
        row_order TEXT,
        cloud_order TEXT,
        clouds_json TEXT,
        meta_json TEXT,
        PRIMARY KEY (symbol, tf)
    )''')
    conn.commit()
    conn.close()
    print('[OK] DB initialized')

    # rules テーブル（ルール保存用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rules (
        id TEXT PRIMARY KEY,
        name TEXT,
        enabled INTEGER,
        scope_json TEXT,
        rule_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )''')
    # Add updated_at column if it doesn't exist (for existing databases)
    try:
        c.execute('ALTER TABLE rules ADD COLUMN updated_at TEXT')
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print('[OK] Rules table ensured')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def dashboard():
    print('[ACCESS] Dashboard request')
    try:
        return render_template('dashboard.html')
    except Exception as e:
        print(f'[ERROR] Dashboard error: {e}')
        return f'Error: {e}', 500

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'msg': 'No JSON'}), 400
        
        # 受信タイムスタンプをログ（JST）
        jst = pytz.timezone('Asia/Tokyo')
        received_at = datetime.now(jst).isoformat()
        print(f'[WEBHOOK RECEIVED] {received_at} - {data.get("symbol", "UNKNOWN")}/{data.get("tf", "5")}')
        
        # 10秒後にデータを保存するタイマーをセット
        def save_data():
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''INSERT OR REPLACE INTO states (
                        symbol, tf, timestamp, price, time,
                        state_flag, state_word,
                        daytrade_status, daytrade_bos, daytrade_time,
                        swing_status, swing_bos, swing_time,
                        row_order, cloud_order, clouds_json, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (data.get('symbol', 'UNKNOWN'), data.get('tf', '5'),
                     datetime.now(jst).isoformat(), float(data.get('price', 0)),
                     data.get('time', 0),
                     data.get('state', {}).get('flag', ''),
                     data.get('state', {}).get('word', ''),
                     data.get('daytrade', {}).get('status', ''),
                     data.get('daytrade', {}).get('bos', ''),
                     data.get('daytrade', {}).get('time', ''),
                     data.get('swing', {}).get('status', ''),
                     data.get('swing', {}).get('bos', ''),
                     data.get('swing', {}).get('time', ''),
                     ','.join(data.get('row_order', [])),
                     ','.join(data.get('cloud_order', [])),
                     json.dumps(data.get('clouds', []), ensure_ascii=False),
                     json.dumps(data.get('meta', {}), ensure_ascii=False)))
                conn.commit()
                conn.close()
                symbol_val = data.get('symbol', 'UNKNOWN')
                tf_val = data.get('tf', '5')
                saved_at = datetime.now(jst).isoformat()
                print(f'[OK] Saved after 10s delay: {symbol_val}/{tf_val} at {saved_at}')
            except Exception as e:
                print(f'[ERROR] Saving data after delay: {e}')
        
        # 10秒タイマーで保存
        timer = threading.Timer(10.0, save_data)
        timer.start()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/current_states')
def current_states():
    print('[ACCESS] Current states request')
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT * FROM states')
        rows, cols = c.fetchall(), [d[0] for d in c.description]
        conn.close()
        
        print(f'[INFO] Found {len(rows)} states in DB')
        
        states = []
        for r in rows:
            d = dict(zip(cols, r))
            d['clouds'] = json.loads(d.get('clouds_json', '[]'))
            d['meta'] = json.loads(d.get('meta_json', '{}'))
            d['row_order'] = d.get('row_order', '').split(',') if d.get('row_order') else []
            d['cloud_order'] = d.get('cloud_order', '').split(',') if d.get('cloud_order') else []
            d['state'] = {'flag': d.get('state_flag', ''), 'word': d.get('state_word', '')}
            d['daytrade'] = {'status': d.get('daytrade_status', ''), 'bos': d.get('daytrade_bos', ''), 'time': d.get('daytrade_time', '')}
            d['swing'] = {'status': d.get('swing_status', ''), 'bos': d.get('swing_bos', ''), 'time': d.get('swing_time', '')}
            print(f'[INFO] State: {d.get("symbol")}/{d.get("tf")}')
            states.append(d)
        return jsonify({'status': 'success', 'states': states}), 200
    except Exception as e:
        print(f'[ERROR] {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules', methods=['GET', 'POST'])
def rules():
    try:
        if request.method == 'GET':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT id, name, enabled, scope_json, rule_json, created_at, updated_at FROM rules')
            rows = c.fetchall()
            conn.close()
            res = []
            for r in rows:
                res.append({
                    'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                    'scope': json.loads(r[3]) if r[3] else None,
                    'rule': json.loads(r[4]) if r[4] else None,
                    'created_at': r[5],
                    'updated_at': r[6] if len(r) > 6 else r[5]
                })
            return jsonify({'status': 'success', 'rules': res}), 200

        # POST: 保存（新規/更新）
        payload = request.json
        if not payload:
            return jsonify({'status': 'error', 'msg': 'no json payload'}), 400
        # server-side validation: ensure alignment settings (if present) are sane
        rule_obj = payload.get('rule') or {}
        align = rule_obj.get('alignment')
        if align:
            try:
                tfs = align.get('tfs') or []
                # n may come as string or number
                n_raw = align.get('n')
                if n_raw is None:
                    return jsonify({'status':'error','msg':'alignment.n missing'}), 400
                try:
                    n_val = int(n_raw)
                except Exception:
                    return jsonify({'status':'error','msg':'alignment.n must be an integer'}), 400
                if not isinstance(tfs, list) or any(not isinstance(x, str) for x in tfs):
                    return jsonify({'status':'error','msg':'alignment.tfs must be list of TF strings'}), 400
                if len(tfs) < 2:
                    return jsonify({'status':'error','msg':'alignment requires at least 2 TFs to be selected'}), 400
                if n_val < 2:
                    return jsonify({'status':'error','msg':'alignment.n must be >= 2'}), 400
                if n_val > len(tfs):
                    return jsonify({'status':'error','msg':'alignment.n cannot be greater than number of selected TFs'}), 400
                missing_mode = align.get('missing')
                if missing_mode not in ('ignore','fail'):
                    return jsonify({'status':'error','msg':'alignment.missing must be "ignore" or "fail"'}), 400
            except Exception as e:
                return jsonify({'status':'error','msg': 'alignment validation error: ' + str(e)}), 400

        rid = payload.get('id') or payload.get('name') or str(datetime.now().timestamp())
        name = payload.get('name', 'unnamed')
        enabled = 1 if payload.get('enabled', True) else 0
        scope_json = json.dumps(payload.get('scope', {}), ensure_ascii=False)
        rule_json = json.dumps(payload.get('rule', {}), ensure_ascii=False)
        updated_at = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Check if rule exists to preserve created_at
        c.execute('SELECT created_at FROM rules WHERE id = ?', (rid,))
        existing = c.fetchone()
        created_at = existing[0] if existing else updated_at
        
        c.execute('INSERT OR REPLACE INTO rules (id, name, enabled, scope_json, rule_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (rid, name, enabled, scope_json, rule_json, created_at, updated_at))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'id': rid}), 200
    except Exception as e:
        print(f'[ERROR][rules] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'deleted': rule_id}), 200
    except Exception as e:
        print(f'[ERROR][delete_rule] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


def _find_cloud_field(state, label, field):
    # state expected to have 'clouds' array
    try:
        clouds = state.get('clouds', [])
        # helper: normalize label to minutes if possible
        def _tf_to_minutes(s):
            try:
                if s is None:
                    return None
                ss = str(s).strip().lower()
                if ss.isdigit():
                    return int(ss)
                # endswith m (minutes)
                if ss.endswith('m'):
                    return int(ss[:-1])
                # endswith h (hours)
                if ss.endswith('h'):
                    return int(ss[:-1]) * 60
                # contains 'min'
                if 'min' in ss:
                    num = ''.join([c for c in ss if c.isdigit()])
                    return int(num) if num else None
                # fallback: try to parse digits
                digits = ''.join([c for c in ss if c.isdigit()])
                if digits:
                    return int(digits)
            except Exception:
                return None
            return None

        req_min = _tf_to_minutes(label)
        for c in clouds:
            c_label = c.get('label')
            # exact match first
            if str(c_label) == str(label):
                val = c.get(field)
                # Special handling: if field is 'gc' and not present in cloud object,
                # default to False (DC) to match frontend display behavior
                if field == 'gc' and val is None and field not in c:
                    return False  # Default to False/DC when gc field is missing
                return val
            # try normalized minutes match
            try:
                cmin = _tf_to_minutes(c_label)
                if req_min is not None and cmin is not None and req_min == cmin:
                    val = c.get(field)
                    if field == 'gc' and val is None and field not in c:
                        return False  # Default to False/DC when gc field is missing
                    return val
            except Exception:
                pass
    except Exception:
        pass
    return None


def _parse_time_to_ms(val):
    # Accept integer ms, numeric string, or YY/MM/DD/HH:MM string
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if s.isdigit():
            return int(s)
        # try YY/MM/DD/HH:MM like '25/10/31/21:35'
        parts = s.split('/')
        if len(parts) >= 4:
            yy = int(parts[0]); mm = int(parts[1]); dd = int(parts[2]); timepart = parts[3]
            hh, mi = 0, 0
            if ':' in timepart:
                hp = timepart.split(':'); hh = int(hp[0]); mi = int(hp[1])
            else:
                hh = int(timepart)
            from datetime import datetime
            year = 2000 + yy if yy < 100 else yy
            dt = datetime(year, mm, dd, hh, mi)
            return int(dt.timestamp() * 1000)
    except Exception:
        return None
    return None


def _normalize_actual(field, val):
    """Normalize actual field values to Python types for comparison.
    - gc -> string ('GC' for true, 'DC' for false) to match display
    - dauten -> string ('up'/'down', or '▲'/'▼' variants)
    - bos_count -> keep as-is (string like "BOS-2" or number)
    - numeric fields -> float
    - otherwise return as-is
    """
    try:
        if val is None:
            return None
        
        # gc: normalize boolean to display string (GC/DC)
        if field in ('gc',):
            if isinstance(val, bool):
                return 'GC' if val else 'DC'
            s = str(val).strip().lower()
            if s in ('true','1','yes','y','gc','▲gc'):
                return 'GC'
            if s in ('false','0','no','n','dc','▼dc'):
                return 'DC'
            # fallback: treat non-empty as GC
            return 'GC' if s else 'DC'

        # dauten: normalize to lowercase string or symbol variant
        if field in ('dauten',):
            s = str(val).strip().lower()
            # accept ▲/▼ variants and normalize to consistent display terms
            if '▲' in s or 'up' in s or s == '上' or s == '上昇':
                return '上昇'
            if '▼' in s or 'down' in s or s == '下' or s == '下降':
                return '下降'
            return s

        # bos_count: keep as-is (can be string like "BOS-2" or numeric)
        if field in ('bos_count',):
            # Return as-is for string comparison
            return val

        if field in ('distance_from_prev','distance_from_price','angle','thickness'):
            try:
                return float(val)
            except Exception:
                return val

        # default: return original
        return val
    except Exception:
        return val


def _compare_values(a, op, b):
    """Compare values with operator. Handles numeric, boolean, and string comparisons.
    For gc field, both a and b should be normalized strings ('GC'/'DC').
    """
    try:
        if a is None:
            return False
        
        # Coerce b into a sensible Python type
        if isinstance(b, str):
            b_lower = b.strip().lower()
            # Check for boolean-like strings
            if b_lower in ('true','false'):
                b_val = (b_lower == 'true')
            # Check for gc display values
            elif b_lower in ('gc','▲gc','ゴールデンクロス','golden','goldencross'):
                b_val = 'GC'
            elif b_lower in ('dc','▼dc','デッドクロス','dead','deadcross'):
                b_val = 'DC'
            # Check for dauten display values
            elif b_lower in ('up','▲','▲dow','上','上昇','upward'):
                b_val = '上昇'
            elif b_lower in ('down','▼','▼dow','下','下降','downward'):
                b_val = '下降'
            else:
                # Try numeric
                try:
                    b_val = float(b)
                except Exception:
                    b_val = b
        else:
            b_val = b

        # Coerce a based on b_val type
        if isinstance(b_val, (int, float)):
            try:
                a_val = float(a)
            except Exception:
                return False
        elif isinstance(b_val, bool):
            try:
                if isinstance(a, bool):
                    a_val = a
                elif isinstance(a, (int, float)):
                    a_val = bool(a)
                else:
                    sa = str(a).strip().lower()
                    a_val = sa in ('true','1','yes','y')
            except Exception:
                a_val = False
        else:
            # String comparison (case-insensitive)
            if isinstance(a, str):
                a_val = a.strip().upper()
                if isinstance(b_val, str):
                    b_val = b_val.strip().upper()
            else:
                a_val = a

        if op == '==':
            return a_val == b_val
        if op == '!=':
            return a_val != b_val
        if op == '>':
            return a_val > b_val
        if op == '<':
            return a_val < b_val
        if op == '>=':
            return a_val >= b_val
        if op == '<=':
            return a_val <= b_val
    except Exception:
        return False
    return False


@app.route('/rules/test', methods=['POST'])
def rules_test():
    try:
        payload = request.json
        if not payload:
            return jsonify({'status':'error','msg':'no json payload'}), 400

        rule = payload.get('rule') or payload.get('rule_obj') or {}
        scope = payload.get('scope') or {}
        state_override = payload.get('state_override')

        # determine state to use
        used_state = None
        if state_override:
            used_state = state_override
        else:
            # query DB for latest state matching scope.symbol if provided
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            if scope and scope.get('symbol'):
                c.execute('SELECT * FROM states WHERE symbol = ? ORDER BY rowid DESC LIMIT 1', (scope.get('symbol'),))
            else:
                c.execute('SELECT * FROM states ORDER BY rowid DESC LIMIT 1')
            row = c.fetchone()
            cols = [d[0] for d in c.description] if c.description else []
            conn.close()
            if not row:
                return jsonify({'status':'error','msg':'no state available for test'}), 400
            d = dict(zip(cols, row))
            try:
                d['clouds'] = json.loads(d.get('clouds_json','[]'))
            except Exception:
                d['clouds'] = d.get('clouds_json')
            try:
                d['meta'] = json.loads(d.get('meta_json','{}'))
            except Exception:
                d['meta'] = d.get('meta_json')
            d['row_order'] = d.get('row_order','').split(',') if d.get('row_order') else []
            d['cloud_order'] = d.get('cloud_order','').split(',') if d.get('cloud_order') else []
            d['state'] = {'flag': d.get('state_flag',''), 'word': d.get('state_word','')}
            d['daytrade'] = {'status': d.get('daytrade_status',''), 'bos': d.get('daytrade_bos',''), 'time': d.get('daytrade_time','')}
            d['swing'] = {'status': d.get('swing_status',''), 'bos': d.get('swing_bos',''), 'time': d.get('swing_time','')}
            used_state = d

            # Load other states for the same symbol to allow fallback when a requested TF/cloud is missing
            states_for_symbol = []
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                sym = used_state.get('symbol') if used_state else None
                if sym:
                    c.execute('SELECT * FROM states WHERE symbol = ?', (sym,))
                    rows = c.fetchall()
                    cols = [d[0] for d in c.description] if c.description else []
                    for r in rows:
                        dd = dict(zip(cols, r))
                        try:
                            dd['clouds'] = json.loads(dd.get('clouds_json','[]'))
                        except Exception:
                            dd['clouds'] = dd.get('clouds_json')
                        states_for_symbol.append(dd)
                conn.close()
            except Exception:
                states_for_symbol = []

            # helper to find a field, with debug info: search used_state first then other states
            def _find_field_with_fallback(label, field):
                searched = []
                # normalize helper (reuse same normalization logic as _find_cloud_field)
                def _tf_to_minutes_local(s):
                    try:
                        if s is None:
                            return None
                        ss = str(s).strip().lower()
                        if ss.isdigit():
                            return int(ss)
                        if ss.endswith('m'):
                            return int(ss[:-1])
                        if ss.endswith('h'):
                            return int(ss[:-1]) * 60
                        if 'min' in ss:
                            num = ''.join([c for c in ss if c.isdigit()])
                            return int(num) if num else None
                        digits = ''.join([c for c in ss if c.isdigit()])
                        if digits:
                            return int(digits)
                    except Exception:
                        return None
                    return None

                req_min = _tf_to_minutes_local(label)

                # search a given state object for a matching cloud
                def _search_state_for(state_obj):
                    clouds = state_obj.get('clouds', [])
                    for c in clouds:
                        c_label = c.get('label')
                        searched.append({'state_tf': state_obj.get('tf'), 'cloud_label': c_label})
                        if str(c_label) == str(label):
                            val = c.get(field)
                            # Apply gc default handling here too
                            if field == 'gc' and val is None and field not in c:
                                val = False
                            return {'value': val, 'found_in': {'state_tf': state_obj.get('tf'), 'cloud_label': c_label}}
                        try:
                            cmin = _tf_to_minutes_local(c_label)
                            if req_min is not None and cmin is not None and req_min == cmin:
                                val = c.get(field)
                                if field == 'gc' and val is None and field not in c:
                                    val = False
                                return {'value': val, 'found_in': {'state_tf': state_obj.get('tf'), 'cloud_label': c_label}}
                        except Exception:
                            pass
                    return None

                # Strategy: search states with most clouds first (most complete data)
                # Sort states_for_symbol by number of clouds (descending)
                all_states = [used_state] if used_state else []
                try:
                    all_states.extend([s for s in states_for_symbol if s.get('symbol') == (used_state.get('symbol') if used_state else None)])
                except Exception:
                    pass
                
                # Remove duplicates and sort by cloud count
                seen_tfs = set()
                unique_states = []
                for st in all_states:
                    tf_key = st.get('tf')
                    if tf_key not in seen_tfs:
                        seen_tfs.add(tf_key)
                        unique_states.append(st)
                
                # Strategy: different priorities for different field types
                # For bos_count, dauten, dauten_start_time_str: prefer individual TF states (more specific)
                # For gc, angle, thickness, etc.: prefer complete states (tf="5")
                
                priority_fields_for_individual = ['bos_count', 'dauten', 'dauten_start_time_str']
                
                if field in priority_fields_for_individual:
                    # For these fields, prioritize individual TF states over complete state
                    # Sort: smallest cloud count first (individual states), then by timestamp (newest)
                    unique_states.sort(key=lambda s: (len(s.get('clouds', [])), -(s.get('time', 0) or 0)))
                else:
                    # For other fields, prioritize states with most clouds (complete data)
                    unique_states.sort(key=lambda s: len(s.get('clouds', [])), reverse=True)

                # Search across all states in priority order
                for state_obj in unique_states:
                    res = _search_state_for(state_obj)
                    if res and res.get('value') is not None:
                        res['searched'] = searched
                        return res

                # Not found anywhere
                return {'value': None, 'found_in': None, 'searched': searched}

            # wrapper to ensure callers always get a dict with value/found_in/searched
            def _get_info(label, field):
                try:
                    info = _find_field_with_fallback(label, field)
                    if isinstance(info, dict):
                        # ensure keys exist
                        if 'searched' not in info:
                            info['searched'] = []
                        if 'found_in' not in info:
                            info['found_in'] = None
                        return info
                    # non-dict (e.g., boolean False or raw value) -> wrap
                    return {'value': info, 'found_in': None, 'searched': []}
                except Exception:
                    return {'value': None, 'found_in': None, 'searched': []}

        # evaluate conditions
        conditions = (rule.get('conditions') or [])
        logic = rule.get('logic','AND').upper()
        details = []
        results = []

        # --- evaluate alignment if present ---
        align = rule.get('alignment') or rule.get('rule',{}).get('alignment')
        if align:
            try:
                tfs = align.get('tfs', [])
                missing_mode = align.get('missing', 'fail')
                n_raw = align.get('n', None)
                try:
                    n = int(n_raw) if n_raw is not None else None
                except Exception:
                    n = None

                # if N is not set, treat alignment as disabled (skip)
                if not n:
                    # do not add a condition for alignment
                    pass
                else:
                    match_up = 0
                    match_down = 0
                    effectiveCount = 0
                    missingFound = False
                    for tf in tfs:
                        info = _get_info(tf, 'dauten')
                        actual = _normalize_actual('dauten', info.get('value'))
                        # attach debug info when missing
                        if actual is None:
                            details.append({'cond': f'alignment.{tf}', 'label': tf, 'found_in': info.get('found_in') if isinstance(info, dict) else None, 'searched': info.get('searched') if isinstance(info, dict) else None})
                        if actual is None:
                            missingFound = True
                        else:
                            effectiveCount += 1
                            if str(actual) == '上昇': match_up += 1
                            if str(actual) == '下降': match_down += 1

                    reason = None
                    align_ok = False
                    if len(tfs) == 0:
                        align_ok = False; reason = 'no_selection'
                    elif len(tfs) == 1:
                        align_ok = False; reason = 'need_at_least_2'
                    else:
                        if missing_mode == 'fail' and missingFound:
                            align_ok = False; reason = 'missing_fail'
                        else:
                            if missing_mode == 'ignore' and effectiveCount < n:
                                align_ok = False; reason = 'effective_lt_n'
                            else:
                                # alignment succeeds if either up or down count meets N
                                max_match = max(match_up, match_down)
                                align_ok = (max_match >= n)

                    details.append({'cond':'alignment','tfs':tfs,'missing_mode':missing_mode,'n':n,'match_up':match_up,'match_down':match_down,'effectiveCount':effectiveCount,'result':bool(align_ok),'reason':reason})
                    results.append(bool(align_ok))
            except Exception as e:
                details.append({'cond':'alignment','error':str(e),'result':False})
                results.append(False)

        for cond in conditions:
            # support simple field conds: {label, field, op, value}
            if cond.get('field'):
                label = cond.get('label')
                field = cond.get('field')
                op = cond.get('op', '==')
                val = cond.get('value')
                
                # Special handling for bos_count: use state-level daytrade_bos instead of cloud.bos_count
                # This matches the frontend display logic which uses state.daytrade.bos
                if field == 'bos_count':
                    # Find the state that matches the requested TF/label
                    bos_value = None
                    found_state = None
                    # Search all states for matching TF
                    all_states = [used_state] if used_state else []
                    all_states.extend(states_for_symbol)
                    for st in all_states:
                        # Match by label (normalize TF)
                        st_tf = str(st.get('tf', ''))
                        # Normalize: 5->5m, 15->15m, 60->1H, 240->4H
                        if st_tf == '5': st_tf = '5m'
                        elif st_tf == '15': st_tf = '15m'
                        elif st_tf == '60': st_tf = '1H'
                        elif st_tf == '240': st_tf = '4H'
                        
                        if st_tf.lower() == label.lower():
                            bos_value = st.get('daytrade_bos')
                            found_state = st
                            break
                    
                    if bos_value is not None:
                        info = {
                            'value': bos_value,
                            'found_in': {'state_tf': found_state.get('tf') if found_state else None, 'field': 'daytrade_bos'},
                            'searched': [{'state_tf': st.get('tf')} for st in all_states[:3]]  # limit for brevity
                        }
                    else:
                        # Fallback to cloud.bos_count if daytrade_bos not found
                        info = _get_info(label, field)
                else:
                    info = _get_info(label, field)
                
                actual = _normalize_actual(field, info.get('value'))
                # keep debug info available in details for missing cases
                info_searched = info.get('searched')
                info_found = info.get('found_in')

                # Special numeric-threshold semantics for selected fields:
                numeric_threshold_fields = ['distance_from_prev', 'distance_from_price', 'angle', 'thickness']
                if field in numeric_threshold_fields:
                    # Interpret user-entered threshold as absolute N (positive expected).
                    # Match if actual >= +N (up) or actual <= -N (down). Inclusive comparison.
                    try:
                        if val is None or val == '':
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': False, 'reason': 'no_threshold_provided'})
                            results.append(False)
                        else:
                            try:
                                N = float(val)
                            except Exception:
                                details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': False, 'reason': 'invalid_threshold'})
                                results.append(False)
                                continue

                            if actual is None:
                                details.append({'cond': f"{label}.{field}", 'actual': None, 'threshold': N, 'result': False, 'reason': 'missing_field'})
                                results.append(False)
                            else:
                                try:
                                    a_val = float(actual)
                                except Exception:
                                    details.append({'cond': f"{label}.{field}", 'actual': actual, 'threshold': N, 'result': False, 'reason': 'non_numeric_actual'})
                                    results.append(False)
                                    continue

                                matched_dir = None
                                ok = False
                                if a_val >= N:
                                    ok = True; matched_dir = 'up'
                                elif a_val <= -N:
                                    ok = True; matched_dir = 'down'
                                details.append({'cond': f"{label}.{field}", 'actual': a_val, 'threshold': N, 'match_direction': matched_dir, 'result': bool(ok)})
                                results.append(bool(ok))
                    except Exception as e:
                        details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                        results.append(False)
                    continue

                # Special handling for transfer_time_diff: time difference between dauten and cross in same direction
                if field == 'transfer_time_diff':
                    try:
                        # Get times
                        dauten_info_t = _get_info(label, 'dauten_start_time_str')
                        cross_info_t = _get_info(label, 'cross_start_time')
                        dauten_time_ms = _parse_time_to_ms(dauten_info_t.get('value'))
                        cross_time_ms = _parse_time_to_ms(cross_info_t.get('value'))
                        # Get directions
                        dauten_info = _get_info(label, 'dauten')
                        cross_info = _get_info(label, 'gc')
                        dauten_dir = _normalize_actual('dauten', dauten_info.get('value'))
                        cross_dir = _normalize_actual('gc', cross_info.get('value'))
                        
                        if dauten_time_ms is None or cross_time_ms is None or dauten_dir is None or cross_dir is None:
                            details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'missing_data', 'dauten_dir': dauten_dir, 'cross_dir': cross_dir})
                            results.append(False)
                        elif str(dauten_dir) not in ('上昇', '下降', 'up', 'down') or str(cross_dir) not in ('GC', 'DC'):
                            details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'invalid_direction', 'dauten_dir': str(dauten_dir), 'cross_dir': str(cross_dir)})
                            results.append(False)
                        else:
                            # Check if directions match: dauten '上昇'/'下降' matches gc 'GC'/'DC' (GC=上昇, DC=下降)
                            dauten_up = str(dauten_dir) in ('上昇', 'up')
                            cross_up = str(cross_dir) == 'GC'
                            if dauten_up != cross_up:
                                details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'directions_mismatch'})
                                results.append(False)
                            else:
                                # Calculate absolute time difference in minutes
                                delta_min = abs(dauten_time_ms - cross_time_ms) / 60000.0
                                try:
                                    threshold_min = float(val)
                                except Exception:
                                    details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'invalid_threshold'})
                                    results.append(False)
                                    continue
                                ok = delta_min <= threshold_min
                                details.append({'cond': f"{label}.{field}", 'delta_min': delta_min, 'actual': delta_min, 'threshold': threshold_min, 'result': bool(ok)})
                                results.append(bool(ok))
                    except Exception as e:
                        details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                        results.append(False)
                    continue

                # Generic comparison handler for simple fields (e.g. dauten, gc, bos_count, etc.)
                try:
                    # If no value provided, check field behavior
                    if val is None or val == '':
                        if actual is None:
                            details.append({'cond': f"{label}.{field}", 'actual': None, 'value': val, 'result': False, 'reason': 'missing_field', 'found_in': info_found, 'searched': info_searched})
                            results.append(False)
                        else:
                            # For gc/dauten: value not specified means "exists and is truthy"
                            # But for gc, 'DC' should be treated as existing (not falsy in presence sense)
                            # For toggle fields like gc/dauten, if no value specified, just check existence (always true if field exists)
                            ok = True  # field exists
                            if field in ('gc', 'dauten'):
                                # These are always "present" if they have any value
                                ok = True
                            else:
                                # Other fields: interpret falsy strings as False ('false','0','')
                                try:
                                    if isinstance(actual, str):
                                        la = actual.strip().lower()
                                        if la in ('false','0',''):
                                            ok = False
                                    else:
                                        ok = bool(actual)
                                except Exception:
                                    ok = bool(actual)
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': bool(ok), 'reason': 'presence_check', 'found_in': info_found, 'searched': info_searched})
                            results.append(bool(ok))
                    else:
                        if actual is None:
                            details.append({'cond': f"{label}.{field}", 'actual': None, 'value': val, 'result': False, 'reason': 'missing_field', 'found_in': info_found, 'searched': info_searched})
                            results.append(False)
                        else:
                            ok = _compare_values(actual, op, val)
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'op': op, 'value': val, 'result': bool(ok), 'found_in': info_found, 'searched': info_searched})
                            results.append(bool(ok))
                except Exception as e:
                    details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                    results.append(False)
                continue

            # timediff cond: either type=='timediff' or has left/right
            if cond.get('type') == 'timediff' or (cond.get('left') and cond.get('right')):
                left = cond.get('left')
                right = cond.get('right')
                op = cond.get('op','<=')
                # obtain ms
                def resolve_time(spec):
                    # spec can be dict {label, field} or string '1H.field'
                    if isinstance(spec, dict):
                        vinfo = _get_info(spec.get('label'), spec.get('field'))
                        return _parse_time_to_ms(vinfo.get('value'))
                    if isinstance(spec, str):
                        if '.' in spec:
                            lab, fld = spec.split('.',1)
                            vinfo = _get_info(lab, fld)
                            return _parse_time_to_ms(vinfo.get('value'))
                        else:
                            return _parse_time_to_ms(spec)
                    return _parse_time_to_ms(spec)

                left_ms = resolve_time(left)
                right_ms = resolve_time(right)
                if left_ms is None or right_ms is None:
                    details.append({'cond': 'timediff', 'left': left, 'right': right, 'result': False, 'reason':'missing time'})
                    results.append(False)
                else:
                    delta_min = abs(left_ms - right_ms) / 60000.0
                    compare_val = cond.get('value_minutes') or cond.get('value') or 0
                    try:
                        compare_val = float(compare_val)
                    except Exception:
                        compare_val = 0
                    if op == '<=':
                        ok = delta_min <= compare_val
                    elif op == '>=':
                        ok = delta_min >= compare_val
                    elif op == '<':
                        ok = delta_min < compare_val
                    elif op == '>':
                        ok = delta_min > compare_val
                    else:
                        ok = False
                    details.append({'cond':'timediff','left_ms':left_ms,'right_ms':right_ms,'delta_min':delta_min,'op':op,'value':compare_val,'result':bool(ok)})
                    results.append(bool(ok))
                continue

            # unknown cond
            details.append({'cond': cond, 'result': False, 'reason':'unsupported condition type'})
            results.append(False)

        # --- Direction consistency check ---
        # If conditions include directional fields (dauten, gc), check that all directions match
        # Extract directions from conditions that passed
        directions = []
        for i, cond in enumerate(conditions):
            if i >= len(results):
                continue
            if not results[i]:
                continue  # Skip failed conditions
            
            field = cond.get('field')
            if field in ('dauten', 'gc'):
                # Get actual value from details
                detail = next((d for d in details if d.get('cond') == f"{cond.get('label')}.{field}"), None)
                if detail:
                    actual = detail.get('actual')
                    if actual:
                        # Map to direction: dauten -> '上昇'/'下降', gc -> 'GC'(上昇)/'DC'(下降)
                        if field == 'dauten':
                            direction = '上昇' if ('上昇' in str(actual) or 'up' in str(actual).lower()) else '下降'
                        elif field == 'gc':
                            direction = '上昇' if str(actual).upper() == 'GC' else '下降'
                        directions.append(direction)
        
        # Check if all directions are the same
        direction_consistent = True
        if len(directions) >= 2:
            first_direction = directions[0]
            if not all(d == first_direction for d in directions):
                direction_consistent = False
                details.append({
                    'cond': 'direction_consistency',
                    'directions': directions,
                    'result': False,
                    'reason': 'directions_mismatch'
                })

        matched = False
        if logic == 'AND':
            matched = all(results) if results else False
            # Apply direction consistency check
            if matched and not direction_consistent:
                matched = False
        else:
            matched = any(results) if results else False

        return jsonify({'status':'success','matched': matched, 'details': details, 'used_state': used_state}), 200
    except Exception as e:
        print('[ERROR][rules/test]', e)
        import traceback; traceback.print_exc()
        return jsonify({'status':'error','msg': str(e)}), 500

if __name__ == '__main__':
    init_db()
    print('[START] Port 5000')
    app.run(host='0.0.0.0', port=5000, debug=False)
