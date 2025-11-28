from flask import Flask, request, jsonify, render_template, send_from_directory, make_response
import os, sqlite3, json, base64, hashlib
from datetime import datetime
import threading
import pytz
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# IMMEDIATELY log the file path to confirm which render_server.py is running
with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as _f:
    _f.write(f'\n====== LOADING render_server.py FROM: {__file__} ======\n')
    _f.write(f'====== BASE_DIR: {BASE_DIR} ======\n\n')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
socketio = SocketIO(app, cors_allowed_origins="*")
DB_PATH = os.path.join(BASE_DIR, 'webhook_data.db')
NOTE_IMAGES_DIR = os.path.expanduser(r'C:\Users\kanda\Desktop\NoteImages')

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'status': 'error', 'msg': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'status': 'error', 'msg': 'Internal server error'}), 500

# 画像アップロードエンドポイント
@app.route('/api/upload-note-image', methods=['POST'])
def upload_note_image():
    try:
        # ディレクトリが存在しなければ作成
        if not os.path.exists(NOTE_IMAGES_DIR):
            os.makedirs(NOTE_IMAGES_DIR, exist_ok=True)
            print(f'[NOTE] Created directory: {NOTE_IMAGES_DIR}')
        
        # Base64エンコード済みの画像データを取得
        data = request.get_json()
        image_data = data.get('imageData')
        
        if not image_data or ',' not in image_data:
            return jsonify({'status': 'error', 'msg': 'Invalid image data'}), 400
        
        # Base64データをデコード
        header, encoded = image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        
        # 画像データのハッシュ値を計算
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # ハッシュ値からファイル名を生成
        filename = f'note_image_{image_hash}.png'
        filepath = os.path.join(NOTE_IMAGES_DIR, filename)
        
        print(f'[NOTE] Upload attempt: {filename}')
        print(f'[NOTE] Target path: {filepath}')
        print(f'[NOTE] Directory exists: {os.path.exists(NOTE_IMAGES_DIR)}')
        print(f'[NOTE] Directory writable: {os.access(NOTE_IMAGES_DIR, os.W_OK)}')
        
        # ファイルが既に存在しない場合のみ保存
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            file_size = len(image_bytes)
            print(f'[NOTE] ✓ Image saved: {filename} ({file_size} bytes)')
        else:
            print(f'[NOTE] Image already exists: {filename}')
        
        # 保存を確認
        saved_correctly = os.path.exists(filepath)
        print(f'[NOTE] Verification - File exists after save: {saved_correctly}')
        
        if saved_correctly:
            actual_size = os.path.getsize(filepath)
            print(f'[NOTE] Actual file size on disk: {actual_size} bytes')
        
        # ファイルパスをJSONで返す
        return jsonify({
            'status': 'success',
            'imageHash': image_hash,
            'filename': filename,
            'filepath': filepath,
            'fileExists': saved_correctly
        }), 200
    
    except Exception as e:
        print(f'[ERROR] Image upload failed: {e}')
        import traceback
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'msg': str(e)}), 500

# 画像取得エンドポイント
@app.route('/api/note-image/<image_hash>')
def get_note_image(image_hash):
    try:
        # ファイル名を再構築
        filename = f'note_image_{image_hash}.png'
        filepath = os.path.join(NOTE_IMAGES_DIR, filename)
        
        # ファイルが存在するかチェック
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'msg': 'Image not found'}), 404
        
        # ファイルを返す
        response = make_response(send_from_directory(NOTE_IMAGES_DIR, filename))
        
        # CORS ヘッダーを追加
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        # キャッシング設定
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1年間キャッシュ
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        return response
    
    except Exception as e:
        print(f'[ERROR] Image fetch failed: {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/note-image/<image_hash>', methods=['OPTIONS'])
def note_image_options(image_hash):
    # CORS プリフライト対応
    response = make_response('', 204)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

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
    # Add sort_order column if it doesn't exist
    try:
        c.execute('ALTER TABLE rules ADD COLUMN sort_order INTEGER DEFAULT 0')
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print('[OK] Rules table ensured')
    
    # fire_history テーブル（発火履歴記録用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fire_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        fired_at TEXT NOT NULL,
        conditions_snapshot TEXT,
        last_state_snapshot TEXT
    )''')
    # Add last_state_snapshot column if it doesn't exist
    try:
        c.execute('ALTER TABLE fire_history ADD COLUMN last_state_snapshot TEXT')
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print('[OK] Fire history table ensured')
    
    # market_status テーブル（最後の受信時刻記録用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS market_status (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_receive_time TEXT
    )''')
    # Insert initial record if not exists
    c.execute('INSERT OR IGNORE INTO market_status (id, last_receive_time) VALUES (1, NULL)')
    conn.commit()
    conn.close()
    print('[OK] Market status table ensured')
    
    # ノートデータファイルの確認
    notes_path = os.path.join(BASE_DIR, 'notes_data.json')
    if os.path.exists(notes_path):
        try:
            with open(notes_path, 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
            note_count = len(notes_data) if isinstance(notes_data, list) else 1
            print(f'[OK] Notes data file found with {note_count} page(s)')
        except Exception as e:
            print(f'[WARNING] Notes data file exists but could not be read: {e}')
    else:
        print('[INFO] No notes data file found, will be created on first save')

def is_fx_market_open():
    """
    FX市場の営業時間を判定（データ受信ベース）
    最後のJSON受信から1時間以内なら営業中と判定
    """
    try:
        # 最後の受信時刻を取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT last_receive_time FROM market_status WHERE id = 1')
        row = c.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return False  # 未受信
        
        # 時刻をパース
        last_time = datetime.fromisoformat(row[0])
        utc_now = datetime.now(pytz.UTC)
        
        # 1時間以内受信で営業中
        time_diff = (utc_now - last_time).total_seconds()
        return time_diff <= 3600  # 1時間 = 3600秒
        
    except Exception as e:
        print(f'[ERROR] is_fx_market_open check failed: {e}')
        return False  # エラー時は休場


def _get_nth_weekday(year, month, weekday, n):
    """
    指定された年月の第n番目の曜日を取得
    weekday: 0=月, 1=火, ..., 6=日
    n: 第n番目
    """
    first_day = datetime(year, month, 1)
    first_weekday = first_day.weekday()

    # 第1日曜日までの日数
    days_to_first = (weekday - first_weekday) % 7

    # 第n日曜日
    target_date = 1 + days_to_first + (n - 1) * 7

    return target_date

@app.route('/Alarm/<path:filename>')
def serve_alarm_file(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'Alarm'), filename)

@app.route('/api/chime_files')
def get_chime_files():
    """Alarmフォルダ内の音声ファイルリストを返す"""
    try:
        alarm_dir = os.path.join(BASE_DIR, 'Alarm')
        if not os.path.exists(alarm_dir):
            return jsonify([])
        
        files = []
        for filename in os.listdir(alarm_dir):
            if filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                files.append(filename)
        
        files.sort()
        return jsonify(files)
    except Exception as e:
        print(f'[ERROR] Getting chime files: {e}')
        return jsonify([])

@app.route('/')
def dashboard():
    print('[ACCESS] Dashboard request')
    try:
        response = make_response(render_template('dashboard.html'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f'[ERROR] Dashboard error: {e}')
        return f'Error: {e}', 500

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/json_test_panel')
def json_test_panel():
    response = make_response(render_template('json_test_panel.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    # OPTIONSリクエストに対応（CORS プリフライト）
    if request.method == 'OPTIONS':
        response = make_response('', 204)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    try:
        data = request.json
        if not data:
            error_msg = 'No JSON data received'
            print(f'[WEBHOOK ERROR] {error_msg}')
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(pytz.timezone("Asia/Tokyo")).isoformat()} - {error_msg}\n')
            response = jsonify({'status': 'error', 'msg': error_msg})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 400
        
        # FX休場時は更新を無視（データ受信ベースなので常に保存）
        # 受信したら営業中と判定するため、チェックを削除
        
        # 受信タイムスタンプをログ（JST）
        jst = pytz.timezone('Asia/Tokyo')
        received_at = datetime.now(jst).isoformat()
        symbol_val = data.get("symbol", "UNKNOWN")
        tf_val = data.get("tf", "5")
        print(f'[WEBHOOK RECEIVED] {received_at} - {symbol_val}/{tf_val}')
        
        # ログをファイルに保存
        try:
            log_entry = f'{received_at} - {symbol_val}/{tf_val} - {json.dumps(data, ensure_ascii=False)}\n'
            with open(os.path.join(BASE_DIR, 'webhook_log.txt'), 'a', encoding='utf-8') as f:
                f.write(log_entry)
            # 同時にエラーログにも記録（トラッキング用）
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{received_at} - OK: {symbol_val}/{tf_val}\n')
        except Exception as e:
            error_msg = f'[LOG ERROR] Failed to write logs: {str(e)}'
            print(error_msg)
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
        
        # 設定から更新遅延時間を取得
        settings_path = os.path.join(BASE_DIR, 'settings.json')
        delay_seconds = 10.0  # デフォルト
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                delay_seconds = float(settings.get('update_delay_seconds', 10.0))
        except Exception as e:
            print(f'[WARNING] Failed to load settings: {e}')
        
        # 遅延処理を削除して即時保存
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
                    (symbol_val, tf_val,
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
            saved_at = datetime.now(jst).isoformat()
            print(f'[OK] Saved immediately: {symbol_val}/{tf_val} at {saved_at}')
            
            # 全てのタイムフレーム（5, 15, 60, 240）でルール評価と発火を実行
            try:
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE_EVAL_START for {symbol_val}/{tf_val}\n')
                    f.flush()
                evaluate_and_fire_rules(data, symbol_val, tf_val)
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE_EVAL_END for {symbol_val}/{tf_val}\n')
                    f.flush()
            except Exception as e:
                print(f'[ERROR] Rule evaluation failed: {str(e)}')
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE ERROR for {symbol_val}/{tf_val}: {str(e)}\n')
                    import traceback
                    f.write(traceback.format_exc())
                    f.flush()
            
            # Socket.IOで即時更新通知（全クライアントに配信）
            socketio.emit('update_table', {'message': 'New data received', 'symbol': symbol_val, 'tf': tf_val})
            
            # 市場ステータス更新通知
            market_open = is_fx_market_open()
            socketio.emit('market_status_update', {'market_open': market_open})
            
            # 最後の受信時刻を更新
            try:
                conn_time = sqlite3.connect(DB_PATH)
                c_time = conn_time.cursor()
                c_time.execute('UPDATE market_status SET last_receive_time = ? WHERE id = 1', 
                              (datetime.now(pytz.UTC).isoformat(),))
                conn_time.commit()
                conn_time.close()
                print(f'[OK] Updated last receive time')
            except Exception as e:
                print(f'[ERROR] Updating last receive time: {e}')
        except Exception as e:
            error_msg = f'Database save failed: {str(e)}'
            print(f'[ERROR] {error_msg}')
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - SAVE ERROR for {symbol_val}/{tf_val}: {str(e)}\n')
            response = jsonify({'status': 'error', 'msg': error_msg})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 500
        
        response = jsonify({'status': 'success'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        error_msg = f'Webhook handler exception: {str(e)}'
        print(f'[ERROR] {error_msg}')
        jst = pytz.timezone('Asia/Tokyo')
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
        except:
            pass
        response = jsonify({'status': 'error', 'msg': error_msg})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500

@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント（サーバーが起動しているか確認）"""
    try:
        jst = pytz.timezone('Asia/Tokyo')
        
        # データベース接続テスト
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM states')
            states_count = c.fetchone()[0]
            conn.close()
            db_ok = True
        except Exception as e:
            db_ok = False
            states_count = None
        
        # webhook_log.txt 確認
        webhook_log_exists = os.path.exists(os.path.join(BASE_DIR, 'webhook_log.txt'))
        
        return jsonify({
            'status': 'healthy',
            'server_time': datetime.now(jst).isoformat(),
            'database_ok': db_ok,
            'states_count': states_count,
            'webhook_log_exists': webhook_log_exists,
            'uptime_message': 'Server is running normally'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

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
            # sort_orderでソート（小さい順）
            c.execute('SELECT id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order FROM rules ORDER BY sort_order ASC, created_at ASC')
            rows = c.fetchall()
            conn.close()
            res = []
            for r in rows:
                res.append({
                    'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                    'scope': json.loads(r[3]) if r[3] else None,
                    'rule': json.loads(r[4]) if r[4] else None,
                    'created_at': r[5],
                    'updated_at': r[6] if len(r) > 6 else r[5],
                    'sort_order': r[7] if len(r) > 7 else 0
                })
            return jsonify({'status': 'success', 'rules': res}), 200

        # POST: 保存（新規/更新）
        payload = request.json
        if not payload:
            return jsonify({'status': 'error', 'msg': 'no json payload'}), 400
        
        # Debug: log the incoming payload for voice settings
        print(f'[DEBUG] Received payload: {json.dumps(payload, ensure_ascii=False, indent=2)}')
        
        # server-side validation: ensure alignment settings (if present) are sane
        rule_obj = payload.get('rule') or {}
        align = rule_obj.get('alignment')
        if align:
            try:
                tfs = align.get('tfs') or []
                if not isinstance(tfs, list) or any(not isinstance(x, str) for x in tfs):
                    return jsonify({'status':'error','msg':'alignment.tfs must be list of TF strings'}), 400
                if len(tfs) < 2:
                    return jsonify({'status':'error','msg':'alignment requires at least 2 TFs to be selected'}), 400
                
                # n may come as string or number; if missing, default to len(tfs)
                n_raw = align.get('n')
                if n_raw is None:
                    n_val = len(tfs)  # Default: require ALL TFs to match
                else:
                    try:
                        n_val = int(n_raw)
                    except Exception:
                        return jsonify({'status':'error','msg':'alignment.n must be an integer'}), 400
                
                if n_val < 2:
                    return jsonify({'status':'error','msg':'alignment.n must be >= 2'}), 400
                if n_val > len(tfs):
                    return jsonify({'status':'error','msg':'alignment.n cannot be greater than number of selected TFs'}), 400
                missing_mode = align.get('missing')
                if missing_mode not in ('ignore','fail'):
                    return jsonify({'status':'error','msg':'alignment.missing must be "ignore" or "fail"'}), 400
                
                # Ensure n is set in the alignment object for consistency
                if n_raw is None:
                    align['n'] = n_val
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
        # Check if rule exists to preserve created_at and sort_order
        c.execute('SELECT created_at, sort_order FROM rules WHERE id = ?', (rid,))
        existing = c.fetchone()
        created_at = existing[0] if existing else updated_at
        sort_order = existing[1] if existing else 9999  # 新規ルールは最後に追加
        
        c.execute('INSERT OR REPLACE INTO rules (id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (rid, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'id': rid}), 200
    except Exception as e:
        print(f'[ERROR][rules] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/reorder', methods=['POST'])
def reorder_rules():
    """ルールの並び順を更新"""
    try:
        payload = request.json
        if not payload or 'order' not in payload:
            return jsonify({'status': 'error', 'msg': 'order array required'}), 400
        
        order = payload['order']  # [rule_id1, rule_id2, ...] の配列
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for idx, rule_id in enumerate(order):
            c.execute('UPDATE rules SET sort_order = ? WHERE id = ?', (idx, rule_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][reorder_rules] {e}')
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


@app.route('/rules/test', methods=['GET', 'POST'])
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
        states_for_symbol = []
        
        if state_override:
            # state_override を使用（5m JSON には全TFの雲データが含まれる）
            used_state = state_override
            
            # Ensure proper data structure
            if 'clouds' not in used_state:
                try:
                    if 'clouds_json' in used_state:
                        used_state['clouds'] = json.loads(used_state.get('clouds_json','[]')) if isinstance(used_state.get('clouds_json'), str) else used_state.get('clouds_json', [])
                    else:
                        used_state['clouds'] = []
                except Exception:
                    used_state['clouds'] = []
            
            # Ensure row_order is a list
            if 'row_order' in used_state and isinstance(used_state['row_order'], str):
                used_state['row_order'] = used_state['row_order'].split(',') if used_state['row_order'] else []
            elif 'row_order' not in used_state:
                used_state['row_order'] = []
            
            # Ensure nested objects exist
            if 'state' not in used_state:
                used_state['state'] = {'flag': used_state.get('state_flag', ''), 'word': used_state.get('state_word', '')}
            if 'daytrade' not in used_state:
                used_state['daytrade'] = {'status': used_state.get('daytrade_status', ''), 'bos': used_state.get('daytrade_bos', ''), 'time': used_state.get('daytrade_time', '')}
            if 'swing' not in used_state:
                used_state['swing'] = {'status': used_state.get('swing_status', ''), 'bos': used_state.get('swing_bos', ''), 'time': used_state.get('swing_time', '')}
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
        # (This applies to both state_override and DB-queried cases)
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
        if align and align.get('tfs'):
            try:
                tfs = align.get('tfs', [])
                missing_mode = align.get('missing', 'fail')
                
                # Get row_order from used_state
                row_order = used_state.get('row_order', []) if used_state else []
                
                reason = None
                align_ok = False
                missingFound = False
                missing_tfs = []
                effective_tfs = []
                row_order_effective = []
                
                if not row_order:
                    align_ok = False; reason = 'no_row_order'
                elif len(tfs) == 0:
                    align_ok = False; reason = 'no_selection'
                elif len(tfs) == 1:
                    align_ok = False; reason = 'need_at_least_2'
                else:
                    # Check which tfs are missing in row_order
                    missing_tfs = [tf for tf in tfs if tf not in row_order]
                    missingFound = len(missing_tfs) > 0
                    
                    if missing_mode == 'fail' and missingFound:
                        align_ok = False; reason = 'missing_fail'
                    else:
                        # Exclude missing tfs and check if remaining tfs match the corresponding subsequence in row_order or its reverse
                        effective_tfs = [tf for tf in tfs if tf in row_order]
                        if len(effective_tfs) < 2:
                            align_ok = False; reason = 'too_few_effective_tfs'
                        else:
                            # Get the subsequence of row_order that matches effective_tfs
                            row_order_effective = [tf for tf in row_order if tf in effective_tfs]
                            align_ok = (effective_tfs == row_order_effective or effective_tfs == row_order_effective[::-1])
                            if not align_ok:
                                reason = 'order_mismatch'
                
                details.append({'cond':'alignment','tfs':tfs,'row_order':row_order,'missing_mode':missing_mode,'missing_found':missingFound,'missing_tfs':missing_tfs,'effective_tfs':effective_tfs,'row_order_effective':row_order_effective,'result':bool(align_ok),'reason':reason})
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

@app.route('/api/test_fire', methods=['POST'])
def api_test_fire():
    """テスト発火エンドポイント: 指定通貨の最新 5m 状態を取得してテスト通知を作成"""
    try:
        payload = request.json or {}
        symbol = payload.get('symbol', 'USDJPY')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 指定通貨の最新 5m データを取得
        c.execute('SELECT * FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol, '5'))
        row = c.fetchone()
        cols = [d[0] for d in c.description] if c.description else []
        conn.close()
        
        if not row:
            return jsonify({'status': 'error', 'msg': f'No data available for {symbol}'}), 404
        
        # 行データを辞書に変換
        state_dict = dict(zip(cols, row))
        
        # JSON フィールドをパース
        try:
            state_dict['clouds'] = json.loads(state_dict.get('clouds_json', '[]'))
        except:
            state_dict['clouds'] = []
        
        try:
            state_dict['meta'] = json.loads(state_dict.get('meta_json', '{}'))
        except:
            state_dict['meta'] = {}
        
        # テスト通知を作成
        jst = pytz.timezone('Asia/Tokyo')
        test_notification = {
            'rule_id': 'test-fire',
            'rule_name': 'テスト発火',
            'symbol': state_dict.get('symbol', symbol),
            'tf': state_dict.get('tf', '5'),
            'direction': '上昇',  # デフォルト方向
            'message': 'テスト発火メッセージ',
            'timestamp': datetime.now(jst).isoformat(),
            'price': float(state_dict.get('price', 0))
        }
        
        # 通知をファイルに保存
        notifications_path = os.path.join(BASE_DIR, 'notifications.json')
        try:
            if os.path.exists(notifications_path):
                with open(notifications_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            else:
                existing = []
            
            existing.append(test_notification)
            
            # 最新100件のみ保持
            if len(existing) > 100:
                existing = existing[-100:]
            
            with open(notifications_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            
            print(f'[TEST FIRE] Test notification created for {symbol}: {test_notification}')
        except Exception as e:
            print(f'[ERROR] Saving test notification: {e}')
        
        return jsonify({'status': 'success', 'notification': test_notification}), 200
    except Exception as e:
        print(f'[ERROR][api/test_fire] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    settings_path = os.path.join(BASE_DIR, 'settings.json')
    try:
        if request.method == 'GET':
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {"update_delay_seconds": 10}
            return jsonify({'status': 'success', 'settings': settings}), 200
        else:  # POST
            data = request.json
            if not data or 'update_delay_seconds' not in data:
                return jsonify({'status': 'error', 'msg': 'Invalid data'}), 400
            try:
                delay = int(data['update_delay_seconds'])
                if delay < 0 or delay > 300:  # 0-5分
                    return jsonify({'status': 'error', 'msg': 'Delay must be 0-300 seconds'}), 400
            except ValueError:
                return jsonify({'status': 'error', 'msg': 'Delay must be integer'}), 400
            
            settings = {"update_delay_seconds": delay}
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    # Log client info for debugging
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    print(f'[API/NOTIFICATIONS] Client: {client_ip}, User-Agent: {user_agent[:50]}...')
    
    notifications_path = os.path.join(BASE_DIR, 'notifications.json')
    try:
        if os.path.exists(notifications_path):
            with open(notifications_path, 'r', encoding='utf-8') as f:
                notifications = json.load(f)
        else:
            notifications = []
        
        # Return latest 50 notifications
        return jsonify({'status': 'success', 'notifications': notifications[-50:]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/clear_notifications', methods=['POST'])
def api_clear_notifications():
    """Clear all notifications"""
    try:
        notifications_path = os.path.join(BASE_DIR, 'notifications.json')
        
        # Clear notifications file
        with open(notifications_path, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        
        print('[API/CLEAR_NOTIFICATIONS] Notifications cleared')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][api/clear_notifications] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/market_status', methods=['GET'])
def api_market_status():
    """Get current FX market status"""
    try:
        market_open = is_fx_market_open()
        utc_now = datetime.now(pytz.UTC)
        jst_now = datetime.now(pytz.timezone('Asia/Tokyo'))
        return jsonify({
            'status': 'success',
            'market_open': market_open,
            'utc_time': utc_now.isoformat(),
            'jst_time': jst_now.isoformat()
        }), 200
    except Exception as e:
        print(f'[ERROR][api/market_status] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/clear_fire_history', methods=['POST'])
def api_clear_fire_history():
    """Clear fire history database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM fire_history')
        conn.commit()
        conn.close()
        
        print('[API/CLEAR_FIRE_HISTORY] Fire history cleared')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][api/clear_fire_history] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/webhook_logs')
def api_webhook_logs():
    try:
        log_path = os.path.join(BASE_DIR, 'webhook_log.txt')
        if not os.path.exists(log_path):
            return jsonify({'status': 'success', 'logs': []}), 200
        
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 最新50件を返す
        return jsonify({'status': 'success', 'logs': lines[-50:]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

def evaluate_and_fire_rules(data, symbol, tf_val):
    """Evaluate all enabled rules against the incoming data and fire notifications if matched.
    
    各タイムフレーム（5, 15, 60, 240）のJSONについて、独立してルール評価を実行。
    - tf=5 の場合：全雲情報を含むため、通常のルール評価
    - tf=15,60,240 の場合：当該時間足のダウ転・突破数・時間情報でルール評価
    """
    def wlog(msg):
        """Debug message to both console and file"""
        print(msg)
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{msg}\n')
        except:
            pass
    
    try:
        jst = pytz.timezone('Asia/Tokyo')
        wlog(f'[EVALUATE] Starting rule evaluation for {symbol}/{tf_val}')
        
        # 全タイムフレームの最新データをDBから取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 5m, 15m, 1H, 4H の全データを取得
        tf_states = {}
        base_cols = None
        for tf_key, tf_label in [('5', '5m'), ('15', '15m'), ('60', '1H'), ('240', '4H')]:
            c.execute('SELECT * FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol, tf_key))
            tf_row = c.fetchone()
            if tf_row:
                if base_cols is None:
                    base_cols = [d[0] for d in c.description] if c.description else []
                tf_state = dict(zip(base_cols, tf_row))
                tf_states[tf_label] = tf_state
        
        conn.close()
        
        if not tf_states:
            wlog(f'[FIRE] No state data found for {symbol} in database')
            return
        
        wlog(f'[FIRE] Retrieved states from DB for {symbol}: {list(tf_states.keys())}')
        wlog(f'[DEBUG] Calling _evaluate_rules_with_db_state for {symbol}')
        
        # webhook JSON の clouds 配列から受信したタイムフレームのデータを抽出
        current_cloud = None
        clouds = data.get('clouds', [])
        if clouds:
            # tf_val に対応する tf_label を作成
            tf_label = {'5': '5m', '15': '15m', '60': '1H', '240': '4H'}.get(tf_val, tf_val)
            # clouds 配列から該当するタイムフレームを検索
            for cloud in clouds:
                if cloud.get('label') == tf_label or cloud.get('tf') == tf_label:
                    current_cloud = cloud
                    wlog(f'[DEBUG] Found current cloud for {tf_label}: dauten={cloud.get("dauten")}, gc={cloud.get("gc")}')
                    break
        
        if not current_cloud:
            wlog(f'[WARNING] No cloud data found in webhook for tf={tf_val}')
        
        # 5mのJSONには全TFのデータが含まれているので、全て抽出
        all_clouds = {}
        if clouds:
            for cloud in clouds:
                label = cloud.get('label')
                if label in ['5m', '15m', '1H', '4H']:
                    all_clouds[label] = cloud
                    wlog(f'[DEBUG] Extracted cloud from webhook: {label} - dauten={cloud.get("dauten")}, gc={cloud.get("gc")}')
        
        # 統合データを使用してルール評価
        _evaluate_rules_with_db_state(tf_states, symbol, all_clouds, tf_val)
        wlog(f'[DEBUG] _evaluate_rules_with_db_state completed for {symbol}')
        
    except Exception as e:
        wlog(f'[ERROR] evaluate_and_fire_rules: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_db_state(tf_states, symbol, all_clouds=None, current_tf=None):
    """DBから取得した全タイムフレームのデータを使用してルール評価
    
    表に表示されている現在値を基にルール判定
    - 5mのDBレコードには雲情報（gc, thickness等）
    - 各TF（15m, 1H, 4H）のDBレコードにはそのTFのダウ転換情報
    all_clouds: webhook から受け取った全TFのクラウドデータ {tf_label: cloud_data, ...}
    """
    # Simple inline logging function - writes directly to file
    def wlog(msg):
        """Write log directly to file"""
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'[RULE_V3] {msg}\n')
                f.flush()
        except:
            pass
    
    wlog('===== FUNCTION ENTRY =====')
    
    try:
        # tf_label -> {field: value, ...} のマッピングを作成
        # 表の視覚的内容を正確に反映するため、各TFのDBレコードから取得
        tf_cloud_data = {}
        
        wlog(f'[DEBUG] all_clouds={list(all_clouds.keys()) if all_clouds else None}, current_tf={current_tf}')
        
        # 1. まず5mのDBレコードから全TFの雲情報（gc, thickness等）を取得
        tf_state_5m = tf_states.get('5m')
        if tf_state_5m:
            clouds_json_str = tf_state_5m.get('clouds_json', '[]')
            try:
                clouds = json.loads(clouds_json_str)
                for cloud in clouds:
                    label = cloud.get('label')
                    if label in ['5m', '15m', '1H', '4H']:
                        tf_cloud_data[label] = cloud.copy()
                        wlog(f'[DB] Loaded cloud data for {label} from 5m DB: gc={cloud.get("gc")}, dauten={cloud.get("dauten")}')
            except Exception as e:
                wlog(f'[ERROR] Failed to parse 5m clouds_json: {e}')
        
        # 2. 各TF（15m, 1H, 4H）のDBレコードからダウ転換情報を上書き（これが表の視覚的内容）
        for tf_key, tf_label in [('15', '15m'), ('60', '1H'), ('240', '4H')]:
            tf_state = tf_states.get(tf_label)
            if tf_state:
                clouds_json_str = tf_state.get('clouds_json', '[]')
                try:
                    clouds = json.loads(clouds_json_str)
                    if clouds:
                        tf_cloud = clouds[0]  # 各TFのレコードには1つのクラウドのみ
                        if tf_label in tf_cloud_data:
                            # ダウ転換情報を上書き
                            tf_cloud_data[tf_label]['dauten'] = tf_cloud.get('dauten')
                            tf_cloud_data[tf_label]['bos_count'] = tf_cloud.get('bos_count')
                            tf_cloud_data[tf_label]['dauten_start_time'] = tf_cloud.get('dauten_start_time')
                            wlog(f'[DB] Overwrote dauten for {tf_label} from {tf_label} DB: dauten={tf_cloud.get("dauten")}, bos={tf_cloud.get("bos_count")}')
                        else:
                            tf_cloud_data[tf_label] = tf_cloud.copy()
                            wlog(f'[DB] Loaded {tf_label} data from {tf_label} DB: dauten={tf_cloud.get("dauten")}')
                except Exception as e:
                    wlog(f'[ERROR] Failed to parse {tf_label} clouds_json: {e}')
        
        # 3. webhook から受け取ったデータで上書き（最新データ優先）
        # ただし、dauten と bos_count は各TFのDBレコードから取得した値を維持
        # （表の視覚的内容と一致させるため）
        if all_clouds:
            for tf_label, cloud in all_clouds.items():
                if tf_label in tf_cloud_data:
                    # 最新のwebhookデータで上書き（dauten, bos_count は除く）
                    for key, value in cloud.items():
                        # dauten と bos_count は DB の値を維持（表の視覚的内容）
                        if key in ['dauten', 'bos_count', 'dauten_start_time', 'dauten_start_time_str']:
                            continue
                        tf_cloud_data[tf_label][key] = value
                    wlog(f'[WEBHOOK] Updated {tf_label} with webhook data (dauten/bos excluded): gc={cloud.get("gc")}')
                else:
                    tf_cloud_data[tf_label] = cloud.copy()
                    wlog(f'[WEBHOOK] Added {tf_label} from webhook: dauten={cloud.get("dauten")}, gc={cloud.get("gc")}')
        
        wlog(f'[DEBUG] tf_cloud_data final keys: {list(tf_cloud_data.keys())}')
        for tf_label, data in tf_cloud_data.items():
            wlog(f'[DEBUG] {tf_label}: dauten={data.get("dauten")}, gc={data.get("gc")}')
        
        # ルールを取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol} using DB state')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # ルールの音声設定を取得
                voice_settings = rule.get('voice', {})
                
                wlog(f'[RULE] Processing rule "{rule_name}" scope={scope}')
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != symbol:
                    wlog(f'[RULE] Rule "{rule_name}" skipped: scope symbol mismatch ({scope.get("symbol")} != {symbol})')
                    continue
                
                wlog(f'[RULE] Testing rule "{rule_name}" for {symbol}')
                
                # ルール条件を評価（AND条件：すべての条件が満たされる必要がある）
                conditions = rule.get('conditions', [])
                all_matched = True
                matched_conditions = []
                
                # 複数条件の場合、各条件から方向を収集
                condition_directions = []
                
                for cond in conditions:
                    tf_label = cond.get('label')  # '5m', '15m', '1H', '4H'
                    field = cond.get('field')      # 'dauten', 'bos_count', 'gc' など
                    value = cond.get('value')      # 期待値
                    
                    # クラウドデータから値を取得
                    cloud_data = tf_cloud_data.get(tf_label)
                    if cloud_data is None:
                        wlog(f'[RULE] Cloud data not available for {tf_label}')
                        all_matched = False
                        break
                    
                    found_value = cloud_data.get(field)
                    
                    # 条件をチェック
                    condition_met = False
                    if value is None:
                        # Presence check: フィールドが存在し、None でないかチェック
                        condition_met = found_value is not None
                    else:
                        # Value check: 値が一致するかチェック
                        condition_met = found_value == value
                    
                    if condition_met:
                        matched_conditions.append(cond)
                        wlog(f'[RULE] Condition met: {tf_label}.{field} = {found_value}')
                        
                        # 各フィールドから方向を判定
                        direction = None
                        if field == 'dauten':
                            if found_value == 'up':
                                direction = 'up'
                            elif found_value == 'down':
                                direction = 'down'
                        elif field == 'gc':
                            # gc=True は上昇（青）、gc=False は下降（赤）
                            if found_value is True:
                                direction = 'up'
                            elif found_value is False:
                                direction = 'down'
                        elif field == 'bos_count':
                            if found_value is not None:
                                try:
                                    bos_num = float(found_value) if found_value != '' else 0
                                    if bos_num > 0:
                                        direction = 'up'
                                    elif bos_num < 0:
                                        direction = 'down'
                                except:
                                    pass
                        
                        condition_directions.append(direction)
                        wlog(f'[RULE] Added direction: {direction}')
                    else:
                        all_matched = False
                        wlog(f'[RULE] Condition not met: {tf_label}.{field} (found={found_value}, expected={value})')
                        break
                
                # 複数条件の場合、方向の整合性をチェック
                wlog(f'[RULE] === Direction check START === all_matched={all_matched}, num_conditions={len(conditions)}, directions={condition_directions}')
                if all_matched and len(conditions) > 1:
                    # None以外の方向を収集
                    valid_directions = [d for d in condition_directions if d is not None]
                    wlog(f'[RULE] Valid directions: {valid_directions}')
                    
                    if len(valid_directions) > 1:
                        # 方向が複数ある場合、すべて同じ方向かチェック
                        if len(set(valid_directions)) > 1:
                            # 方向が一致していない
                            all_matched = False
                            wlog(f'[RULE] Direction mismatch: {valid_directions} - not firing')
                        else:
                            wlog(f'[RULE] Direction aligned: {valid_directions[0]}')
                    elif len(valid_directions) == 1:
                        wlog(f'[RULE] Single direction: {valid_directions[0]}')
                    else:
                        wlog(f'[RULE] No direction info available')
                
                # ===== Alignment チェック =====
                # ルールに alignment 設定がある場合、cloud_order の並び順をチェック
                alignment_config = rule.get('alignment')
                alignment_direction = None  # 整列の方向（'上昇' or '下降'）
                current_tf_order = None  # 現在のTF順序（価格を除外）
                
                if alignment_config and all_matched:
                    wlog(f'[RULE] Checking alignment: {alignment_config}')
                    
                    tfs = alignment_config.get('tfs', [])  # ['5m', '15m', '1H', '4H']
                    
                    # DBから現在の cloud_order を取得
                    conn_order = sqlite3.connect(DB_PATH)
                    c_order = conn_order.cursor()
                    c_order.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                    row_order = c_order.fetchone()
                    conn_order.close()
                    
                    if row_order and row_order[0]:
                        cloud_order_str = row_order[0]  # '5m,15m,1H,4H,価格' のような文字列
                        cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                        
                        # 「価格」を除外してTFのみ抽出
                        cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                        
                        # 選択されたTFのみを抽出（順序を保持）
                        selected_order = [x for x in cloud_order_tfs if x in tfs]
                        
                        # 現在のTF順序を保存（価格除外）
                        current_tf_order = ','.join(selected_order)
                        
                        # 期待する昇順と降順
                        expected_asc = tfs  # ['5m', '15m', '1H', '4H']
                        expected_desc = list(reversed(tfs))  # ['4H', '1H', '15m', '5m']
                        
                        # 整列判定
                        is_aligned = (selected_order == expected_asc or selected_order == expected_desc)
                        
                        if is_aligned:
                            # 整列方向を判定
                            if selected_order == expected_asc:
                                alignment_direction = '上昇'
                            else:
                                alignment_direction = '下降'
                            wlog(f'[RULE] Alignment OK: {selected_order} matches expected order (direction={alignment_direction})')
                        else:
                            all_matched = False
                            wlog(f'[RULE] Alignment failed: {selected_order} does not match expected order (asc={expected_asc}, desc={expected_desc})')
                    else:
                        all_matched = False
                        wlog(f'[RULE] Alignment failed: cloud_order not found in DB')
                
                wlog(f'[RULE] Rule "{rule_name}" result: all_matched={all_matched}')

                
                # ===== 発火判定ロジック（条件揃い状態に関わらず実行）=====
                num_conditions = len(conditions)
                should_fire = False
                
                # ===== 前回の発火状態を取得 =====
                # 発火した記録のみがfire_historyに保存されているため、最新の発火時の状態と比較
                conn_check = sqlite3.connect(DB_PATH)
                c_check = conn_check.cursor()
                c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                   WHERE rule_id = ? AND symbol = ? AND tf = ?
                                   ORDER BY fired_at DESC LIMIT 1''', 
                               (rule_id, symbol, ''))
                last_fire = c_check.fetchone()
                conn_check.close()
                
                last_state = None
                
                if last_fire and last_fire[0]:
                    try:
                        last_state = json.loads(last_fire[0])
                    except:
                        last_state = None
                
                # ===== 今回の条件揃い状態 =====
                current_conditions_matched = all_matched
                
                # ===== 発火判定ロジック =====
                # 「DBの状態が変化して、その結果ルール条件を満たした」場合に発火
                # 1. 条件を満たしている (all_matched=True)
                # 2. かつ、前回の発火時と比較して少なくとも1つのフィールド値が変化している
                
                should_fire = False
                
                if all_matched:
                    # 条件を満たしている場合、フィールド値の変化をチェック
                    has_field_change = False
                    
                    if last_state is None:
                        # 初回評価の場合は発火
                        has_field_change = True
                        wlog(f'[RULE] First evaluation with matched conditions, should_fire=True')
                    else:
                        # Alignment ルールの場合は TF順序（価格除外）の変化をチェック
                        if alignment_config:
                            # 現在のTF順序を取得（価格除外）
                            conn_order_check = sqlite3.connect(DB_PATH)
                            c_order_check = conn_order_check.cursor()
                            c_order_check.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                            row_order_check = c_order_check.fetchone()
                            conn_order_check.close()
                            
                            if row_order_check and row_order_check[0]:
                                cloud_order_str = row_order_check[0]
                                cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                                # 価格を除外してTFのみ抽出
                                cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                                tfs = alignment_config.get('tfs', [])
                                selected_order = [x for x in cloud_order_tfs if x in tfs]
                                current_tf_order = ','.join(selected_order)
                            else:
                                current_tf_order = ''
                            
                            last_tf_order = last_state.get('tf_order', '')
                            
                            # TF順序が変化し、かつ現在整列している場合に発火
                            if current_tf_order != last_tf_order:
                                has_field_change = True
                                wlog(f'[RULE] TF order change detected: {last_tf_order} → {current_tf_order}')
                            else:
                                wlog(f'[RULE] TF order unchanged: {current_tf_order}')
                        else:
                            # 通常のルール: 各条件のフィールド値が変化したかチェック
                            for cond in conditions:
                                tf_label = cond.get('label')
                                field = cond.get('field')
                                field_key = f'{tf_label}.{field}'
                                
                                current_value = tf_cloud_data.get(tf_label, {}).get(field)
                                last_value = last_state.get(field_key)
                                
                                if current_value != last_value:
                                    has_field_change = True
                                    wlog(f'[RULE] Field change detected: {field_key} = {last_value} → {current_value}')
                                    break
                        
                        if not has_field_change:
                            wlog(f'[RULE] Conditions matched but no field change, should_fire=False')
                    
                    should_fire = has_field_change
                else:
                    wlog(f'[RULE] Conditions not matched, should_fire=False')
                
                # ===== 発火処理 =====
                if should_fire:
                    wlog(f'[RULE] ✓ FIRING Rule: {rule_name}')
                    
                    # 状態スナップショットに__conditions_matched__フラグを追加
                    state_snapshot = {
                        'symbol': symbol,
                        'conditions': str(conditions),
                        '__conditions_matched__': current_conditions_matched
                    }
                    
                    # Alignment ルールの場合は tf_order（価格除外のTF順序）を保存
                    if alignment_config:
                        conn_order_snap = sqlite3.connect(DB_PATH)
                        c_order_snap = conn_order_snap.cursor()
                        c_order_snap.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                        row_order_snap = c_order_snap.fetchone()
                        conn_order_snap.close()
                        
                        if row_order_snap and row_order_snap[0]:
                            cloud_order_str = row_order_snap[0]
                            cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                            # 価格を除外してTFのみ抽出
                            cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                            tfs = alignment_config.get('tfs', [])
                            selected_order = [x for x in cloud_order_tfs if x in tfs]
                            state_snapshot['tf_order'] = ','.join(selected_order)
                            # cloud_order も参考として保存（ログ用）
                            state_snapshot['cloud_order'] = row_order_snap[0]
                    
                    # 各条件のタイムフレームごとにcloud_dataを追加
                    for cond in conditions:
                        tf_label = cond.get('label')
                        cond_cloud_data = tf_cloud_data.get(tf_label, {})
                        for k, v in cond_cloud_data.items():
                            state_snapshot[f'{tf_label}.{k}'] = v
                    
                    # 発火履歴を保存
                    fired_at = datetime.now(jst).isoformat()
                    try:
                        conn_fire = sqlite3.connect(DB_PATH)
                        c_fire = conn_fire.cursor()
                        
                        c_fire.execute('''INSERT INTO fire_history 
                                         (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                         VALUES (?, ?, ?, ?, ?, ?)''',
                                      (rule_id, symbol, '', fired_at, 
                                       json.dumps(conditions, ensure_ascii=False), 
                                       json.dumps(state_snapshot, ensure_ascii=False)))
                        
                        conn_fire.commit()
                        conn_fire.close()
                    except Exception as e:
                        wlog(f'[RULE] Error saving fire history: {e}')
                    
                    # 方向を判定
                    direction = None
                    
                    # Alignment ルールの場合は alignment_direction を優先
                    if alignment_direction:
                        direction = alignment_direction
                        wlog(f'[RULE] Direction from alignment: {direction}')
                    elif conditions:
                        primary_field = conditions[0].get('field')
                        primary_tf_label = conditions[0].get('label')
                        cloud_data = tf_cloud_data.get(primary_tf_label, {})
                        
                        wlog(f'[RULE] Direction check: primary_field={primary_field}, tf={primary_tf_label}, cloud_data keys={list(cloud_data.keys()) if cloud_data else None}')
                        
                        if primary_field == 'dauten':
                            dauten_value = cloud_data.get('dauten')
                            wlog(f'[RULE] Direction from dauten: {dauten_value}')
                            if dauten_value == 'up':
                                direction = '上昇'
                            elif dauten_value == 'down':
                                direction = '下降'
                        
                        elif primary_field == 'gc':
                            # gc=True は上昇（青）、gc=False は下降（赤）
                            gc_value = cloud_data.get('gc')
                            wlog(f'[RULE] Direction from gc: {gc_value}')
                            if gc_value is True:
                                direction = '上昇'
                            elif gc_value is False:
                                direction = '下降'
                        
                        elif primary_field == 'bos_count':
                            bos_value = cloud_data.get('bos_count')
                            wlog(f'[RULE] Direction from bos_count: {bos_value}')
                            if bos_value is not None:
                                try:
                                    bos_num = float(bos_value) if bos_value != '' else 0
                                    if bos_num > 0:
                                        direction = '上昇'
                                    elif bos_num < 0:
                                        direction = '下降'
                                except:
                                    pass
                    
                    wlog(f'[RULE] Final direction for "{rule_name}": {direction}')
                    
                    # メッセージを構築（方向別メッセージを含む）
                    common_message = voice_settings.get('message', '')
                    message_up = voice_settings.get('message_up', '')
                    message_down = voice_settings.get('message_down', '')
                    message_position = voice_settings.get('message_position', 'suffix')
                    
                    # 方向別メッセージを選択
                    if direction == '上昇' and message_up:
                        direction_message = message_up
                    elif direction == '下降' and message_down:
                        direction_message = message_down
                    else:
                        direction_message = ''
                    
                    # メッセージ結合
                    if message_position == 'prefix':
                        final_message = (direction_message + ' ' + common_message).strip() if direction_message else common_message
                    elif message_position == 'suffix':
                        final_message = (common_message + ' ' + direction_message).strip() if direction_message else common_message
                    elif message_position == 'both':
                        final_message = (direction_message + ' ' + common_message + ' ' + direction_message).strip() if direction_message else common_message
                    else:
                        final_message = common_message
                    
                    # メッセージが空の場合はルール名を使用
                    if not final_message:
                        final_message = rule_name
                    
                    fired_notifications.append({
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'symbol': symbol,
                        'tf': 'multi',
                        'timestamp': fired_at,
                        'message': final_message,
                        'direction': direction,
                        'voice_settings': voice_settings
                    })
                    wlog(f'[FIRE] ✓ Notification fired for rule "{rule_name}" direction={direction}')
                    wlog(f'[FIRE] ✓ Added to fired_notifications list (count={len(fired_notifications)})')
                else:
                    # 発火しない場合もログ出力
                    wlog(f'[RULE] Rule "{rule_name}" not firing')
                
            except Exception as e:
                error_msg = f'[FIRE] Error evaluating rule "{rule_name}": {e}'
                print(error_msg)
                wlog(error_msg)
                import traceback
                tb_str = traceback.format_exc()
                print(tb_str)
                wlog(tb_str)
        
        # 発火した通知をSocket.IOで配信
        wlog(f'[FIRE] Checking fired_notifications: count={len(fired_notifications)}')
        if fired_notifications:
            # 各通知を個別に送信
            for notification in fired_notifications:
                socketio.emit('new_notification', notification)
                print(f'[FIRE] Emitted new_notification event for rule "{notification["rule_name"]}"')
            print(f'[FIRE] Total {len(fired_notifications)} notifications sent')
        
    except Exception as e:
        print(f'[ERROR] _evaluate_rules_with_db_state: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_timeframe_data(data, symbol, tf_val):
    """tf=15, 60, 240 用のルール評価
    
    当該タイムフレームのダウ転・突破数でルール評価を実行
    """
    try:
        # tf値を時間足ラベルにマッピング
        tf_map = {
            '15': '15m',
            '60': '1H',
            '240': '4H'
        }
        tf_label = tf_map.get(tf_val, f'tf{tf_val}')
        
        # JSONから当該タイムフレームのデータを抽出
        clouds = data.get('clouds', [])
        tf_cloud = None
        
        for cloud in clouds:
            if cloud.get('label') == tf_label or cloud.get('tf') == tf_label:
                tf_cloud = cloud
                break
        
        if not tf_cloud:
            print(f'[FIRE] No cloud data found for {tf_label} in received JSON')
            return
        
        print(f'[FIRE] Evaluating rules for {symbol}/{tf_val} ({tf_label}) with cloud data: dauten={tf_cloud.get("dauten")}, bos={tf_cloud.get("bos_count")}')
        
        # ルールを取得して評価
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol}/{tf_val}')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != symbol:
                    print(f'[FIRE] Rule "{rule_name}" scope mismatch: {scope.get("symbol")} != {symbol}')
                    continue
                
                # Check scope: if scope has tf, must match
                if scope.get('tf') and scope['tf'] != tf_val:
                    print(f'[FIRE] Rule "{rule_name}" tf mismatch: {scope.get("tf")} != {tf_val}')
                    continue
                
                print(f'[FIRE] Testing rule "{rule_name}" for {symbol}/{tf_val}')
                
                # ルール条件を評価
                conditions = rule.get('conditions', [])
                all_matched = True
                
                for cond in conditions:
                    label = cond.get('label')
                    field = cond.get('field')
                    value = cond.get('value')
                    
                    # 条件のラベルが当該タイムフレームと一致するかチェック
                    if label != tf_label:
                        print(f'[FIRE] Condition label mismatch: {label} != {tf_label}, skipping condition')
                        all_matched = False
                        break
                    
                    # tf_cloudからフィールド値を取得
                    found_value = tf_cloud.get(field)
                    
                    # 条件をチェック
                    condition_met = False
                    if value is None:
                        # Presence check
                        condition_met = found_value is not None
                    else:
                        # Value check
                        condition_met = found_value == value
                    
                    if not condition_met:
                        all_matched = False
                        print(f'[FIRE] Condition not met: {label}.{field} (found={found_value}, expected={value})')
                        break
                
                print(f'[FIRE] Rule "{rule_name}" result: matched={all_matched}')
                
                # ルールが一致した場合は通知を発火
                if all_matched:
                    print(f'[FIRE] ✓ Rule MATCHED: {rule_name}')
                    
                    # Get last fired state for this rule/tf
                    conn_check = sqlite3.connect(DB_PATH)
                    c_check = conn_check.cursor()
                    c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                       WHERE rule_id = ? AND symbol = ? AND tf = ? 
                                       ORDER BY fired_at DESC LIMIT 1''', (rule_id, symbol, tf_val))
                    last_fire = c_check.fetchone()
                    conn_check.close()
                    
                    last_state = None
                    if last_fire and last_fire[0]:
                        try:
                            last_state = json.loads(last_fire[0])
                        except:
                            last_state = None
                    
                    # 状態変化をチェック（dauten, bos_countの変化を検出）
                    should_fire = False
                    
                    if last_state is None:
                        # 初回発火
                        should_fire = True
                        print(f'[FIRE] First time firing for this rule/symbol/tf')
                    else:
                        # 前回の状態と比較
                        prev_dauten = last_state.get('dauten')
                        prev_bos = last_state.get('bos_count')
                        curr_dauten = tf_cloud.get('dauten')
                        curr_bos = tf_cloud.get('bos_count')
                        
                        if prev_dauten != curr_dauten or prev_bos != curr_bos:
                            should_fire = True
                            print(f'[FIRE] State change detected: dauten {prev_dauten}->{curr_dauten}, bos {prev_bos}->{curr_bos}')
                        else:
                            print(f'[FIRE] No state change, skipping fire')
                    
                    if should_fire:
                        # 通知を記録してメッセージをキューに追加
                        try:
                            conn_fire = sqlite3.connect(DB_PATH)
                            c_fire = conn_fire.cursor()
                            
                            # 現在の状態をスナップショットとして保存
                            current_state_snapshot = json.dumps({
                                'dauten': tf_cloud.get('dauten'),
                                'bos_count': tf_cloud.get('bos_count'),
                                'gc': tf_cloud.get('gc')
                            }, ensure_ascii=False)
                            
                            c_fire.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, last_state_snapshot)
                                             VALUES (?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, tf_val, datetime.now(jst).isoformat(), current_state_snapshot))
                            conn_fire.commit()
                            conn_fire.close()
                            
                            fired_notifications.append({
                                'rule_id': rule_id,
                                'rule_name': rule_name,
                                'symbol': symbol,
                                'tf': tf_val
                            })
                            print(f'[FIRE] ✓ Notification fired for rule "{rule_name}"')
                        except Exception as e:
                            print(f'[FIRE] Error recording fire history: {e}')
                    
            except Exception as e:
                print(f'[FIRE] Error evaluating rule "{rule_name}": {e}')
                import traceback
                traceback.print_exc()
        
        # 発火した通知をSocket.IOで配信
        if fired_notifications:
            socketio.emit('rule_fired', {
                'notifications': fired_notifications,
                'timestamp': datetime.now(jst).isoformat()
            })
            print(f'[FIRE] Emitted {len(fired_notifications)} rule_fired events')
        
    except Exception as e:
        print(f'[ERROR] _evaluate_rules_with_timeframe_data: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_state(base_state):
    """統合されたstateデータを使用してルール評価を実行
    
    Note: この関数に到達するデータは evaluate_and_fire_rules() 内の時刻フィルターを
    通過済みのため、遅延アラート（過去データ再計算）は既に除外されている
    """
    try:
        currency_names = {
            'USDJPY': 'ドル円',
            'EURUSD': 'ユーロドル',
            'GBPUSD': 'ポンドドル',
            'GBPJPY': 'ポンド円',
            'AUDUSD': 'オージードル',
            'AUDJPY': 'オージー円',
            'NZDUSD': 'ニュージードル',
            'NZDJPY': 'ニュージー円',
            'CADJPY': 'カナダ円',
            'CHFJPY': 'スイス円',
            'EURJPY': 'ユーロ円',
            'GBPAUD': 'ポンドオージー',
            'EURGBP': 'ユーロポンド',
            'USDCAD': 'ドルカナダ',
            'USDCHF': 'ドルスイス'
        }
        
        # 統合データから symbol と tf を取得
        symbol = base_state.get('symbol', 'UNKNOWN')
        tf = '5'  # 統合データは常に tf=5 ベース
        
        # Get all enabled rules
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return  # No enabled rules
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol}/{tf}')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != base_state.get('symbol'):
                    print(f'[FIRE] Rule "{rule_name}" scope mismatch: {scope.get("symbol")} != {base_state.get("symbol")}')
                    continue
                
                print(f'[FIRE] Testing rule "{rule_name}" for {symbol}/{tf}')
                
                # Directly evaluate rule conditions against base_state (simplified version)
                # Check if all conditions are met
                conditions = rule.get('conditions', [])
                all_matched = True
                
                for cond in conditions:
                    label = cond.get('label')
                    field = cond.get('field')
                    value = cond.get('value')
                    
                    # Find the cloud field in base_state
                    found_value = None
                    for cloud in base_state.get('clouds', []):
                        if cloud.get('label') == label:
                            found_value = cloud.get(field)
                            break
                    
                    # Check if condition matches
                    condition_met = False
                    if value is None:
                        # Presence check: field should exist and have a value
                        condition_met = found_value is not None
                    else:
                        # Value check
                        condition_met = found_value == value
                    
                    if not condition_met:
                        all_matched = False
                        print(f'[FIRE] Condition not met: {label}.{field} (found={found_value}, expected={value})')
                        break
                
                # Build result object
                result = {
                    'status': 'success',
                    'matched': all_matched,
                    'details': [{'result': all_matched}] if all_matched else []
                }
                
                print(f'[FIRE] Rule "{rule_name}" result: matched={result.get("matched")}')
                
                if result.get('status') == 'success' and result.get('matched'):
                    # Categorize condition types:
                    # 1. State change fields (gc, dauten, bos_count) - fire when value changes
                    # 2. Threshold fields (angle, thickness, distance_*, transfer_time_diff) - fire when crossing threshold
                    # 3. Alignment - fire when alignment state changes (aligned -> not aligned -> aligned)
                    
                    # BOS count is now treated as state change (fires on every count change)
                    state_change_fields = ('gc', 'dauten', 'bos_count')
                    threshold_fields = ('angle', 'thickness', 'distance_from_prev', 'distance_from_price', 'transfer_time_diff')
                    
                    should_fire = False
                    changed_fields = []
                    rule_conditions = rule.get('conditions', [])
                    has_alignment = rule.get('alignment') is not None
                    
                    # Get last fired state for this rule
                    conn_check = sqlite3.connect(DB_PATH)
                    c_check = conn_check.cursor()
                    c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                       WHERE rule_id = ? AND symbol = ? AND tf = ? 
                                       ORDER BY fired_at DESC LIMIT 1''', (rule_id, symbol, tf))
                    last_fire = c_check.fetchone()
                    conn_check.close()
                    
                    last_state = None
                    if last_fire and last_fire[0]:
                        try:
                            last_state = json.loads(last_fire[0])
                        except:
                            last_state = None
                    
                    # Build current state snapshot
                    current_state = {}
                    curr_clouds = base_state.get('clouds', [])
                    
                    # Check state change fields (gc, dauten, bos_count)
                    for cond in rule_conditions:
                        field = cond.get('field')
                        label = cond.get('label')
                        
                        if field in state_change_fields:
                            # Find current value
                            curr_val = None
                            for c in curr_clouds:
                                if c.get('label') == label:
                                    curr_val = c.get(field)
                                    break
                            
                            state_key = f'{label}.{field}'
                            current_state[state_key] = curr_val
                            
                            # Compare with last state
                            if last_state is None or last_state.get(state_key) != curr_val:
                                should_fire = True
                                changed_fields.append(state_key)
                                prev_val = last_state.get(state_key) if last_state else None
                                print(f'[FIRE] State change: {state_key} changed from {prev_val} to {curr_val}')
                    
                    # Check threshold fields (angle, thickness, distance_*, transfer_time_diff)
                    for cond in rule_conditions:
                        field = cond.get('field')
                        label = cond.get('label')
                        threshold_value = cond.get('value')
                        
                        if field in threshold_fields:
                            # Find current value
                            curr_val = None
                            for c in curr_clouds:
                                if c.get('label') == label:
                                    curr_val = c.get(field)
                                    break
                            
                            # For transfer_time_diff, calculate based on detail results
                            if field == 'transfer_time_diff':
                                # Find the detail for this condition
                                details = result.get('details', [])
                                for detail in details:
                                    if detail.get('cond') == f'{label}.{field}':
                                        curr_val = detail.get('delta_min') or detail.get('actual')
                                        break
                            
                            state_key = f'{label}.{field}'
                            
                            # Determine if threshold is met
                            threshold_met = False
                            if curr_val is not None and threshold_value is not None:
                                try:
                                    curr_float = float(curr_val)
                                    threshold_float = float(threshold_value)
                                    
                                    # For distance/angle/thickness: value >= threshold
                                    # For transfer_time_diff: value <= threshold
                                    if field == 'transfer_time_diff':
                                        threshold_met = curr_float <= threshold_float
                                    else:
                                        # For angle, thickness, distance: check if >= +N or <= -N
                                        threshold_met = (curr_float >= threshold_float) or (curr_float <= -threshold_float)
                                except:
                                    threshold_met = False
                            
                            current_state[state_key] = threshold_met
                            
                            # Fire if: threshold is met AND (no last state OR last state was NOT met)
                            last_threshold_met = last_state.get(state_key) if last_state else None
                            
                            if threshold_met and (last_threshold_met is None or not last_threshold_met):
                                should_fire = True
                                changed_fields.append(state_key)
                                print(f'[FIRE] Threshold crossed: {state_key} = {curr_val} (threshold: {threshold_value}, was_met: {last_threshold_met} -> now_met: {threshold_met})')
                    
                    # Check alignment condition
                    if has_alignment:
                        alignment = rule.get('alignment')
                        
                        # Determine if alignment is met from details
                        alignment_met = False
                        details = result.get('details', [])
                        for detail in details:
                            if detail.get('cond') == 'alignment':
                                alignment_met = detail.get('result', False)
                                break
                        
                        state_key = 'alignment'
                        current_state[state_key] = alignment_met
                        
                        # Fire if: aligned AND (no last state OR last state was NOT aligned)
                        last_alignment_met = last_state.get(state_key) if last_state else None
                        
                        if alignment_met and (last_alignment_met is None or not last_alignment_met):
                            should_fire = True
                            changed_fields.append(state_key)
                            print(f'[FIRE] Alignment achieved: was_aligned: {last_alignment_met} -> now_aligned: {alignment_met}')
                    
                    if not should_fire:
                        print(f'[FIRE] Rule "{rule_name}" matched but no state change detected, skipping notification')
                        continue
                    
                    print(f'[FIRE] Rule "{rule_name}" FIRED! Changed fields: {changed_fields}')
                    
                    # Rule fired! Determine direction from dauten, bos_count, and gc fields
                    direction = None
                    
                    # Collect directions from cloud data directly (not from details)
                    directions_found = []
                    
                    # Extract direction from cloud conditions
                    rule_conditions = rule.get('conditions', [])
                    for cond in rule_conditions:
                        label = cond.get('label')
                        field = cond.get('field')
                        
                        # Find cloud value
                        for cloud in base_state.get('clouds', []):
                            if cloud.get('label') == label:
                                actual = cloud.get(field)
                                # gc の場合は dauten から方向を取得
                                dauten_value = cloud.get('dauten')
                                
                                if actual is not None:
                                    if field == 'dauten':
                                        if '上昇' in str(actual) or 'up' in str(actual).lower():
                                            directions_found.append('上昇')
                                        elif '下降' in str(actual) or 'down' in str(actual).lower():
                                            directions_found.append('下降')
                                    elif field == 'gc':
                                        # gc=True は上昇（青）、gc=False は下降（赤）
                                        if actual is True or str(actual).upper() == 'TRUE':
                                            directions_found.append('上昇')
                                        elif actual is False or str(actual).upper() == 'FALSE':
                                            directions_found.append('下降')
                                    elif field == 'bos_count':
                                        try:
                                            bos_val = float(actual)
                                            if bos_val > 0:
                                                directions_found.append('上昇')
                                            elif bos_val < 0:
                                                directions_found.append('下降')
                                        except:
                                            pass
                                break
                    
                    # Determine overall direction: majority vote, or first if tie
                    if directions_found:
                        up_count = directions_found.count('上昇')
                        down_count = directions_found.count('下降')
                        if up_count > down_count:
                            direction = '上昇'
                        elif down_count > up_count:
                            direction = '下降'
                        else:
                            direction = directions_found[0]  # Tie, use first
                    
                    # If no direction found, default to '上昇'
                    if direction is None:
                        direction = '上昇'
                    
                    # Get custom messages from rule
                    voice_settings = rule.get('voice', {})
                    message_up = voice_settings.get('message_up', f'{rule_name} が上昇方向で発火しました')
                    message_down = voice_settings.get('message_down', f'{rule_name} が下降方向で発火しました')
                    common_message = voice_settings.get('message', '')
                    message_position = voice_settings.get('message_position', 'suffix')
                    
                    # Select direction-specific message
                    direction_message = message_up if direction == '上昇' else message_down
                    
                    # Combine messages based on position
                    if message_position == 'prefix':
                        combined_message = direction_message + ' ' + common_message if common_message else direction_message
                    elif message_position == 'suffix':
                        combined_message = common_message + ' ' + direction_message if common_message else direction_message
                    elif message_position == 'both':
                        combined_message = direction_message + ' ' + common_message + ' ' + direction_message if common_message else direction_message + ' ' + direction_message
                    else:
                        combined_message = direction_message
                    
                    # Ensure message is not empty
                    if not combined_message.strip():
                        combined_message = f'{rule_name} が発火しました'
                    
                    # Replace {symbol} placeholder with Japanese currency name or insert based on position
                    symbol = base_state.get('symbol', 'UNKNOWN')
                    japanese_name = currency_names.get(symbol, symbol)
                    
                    if voice_settings.get('insert_symbol'):
                        position = voice_settings.get('symbol_insert_position', 'prefix')
                        if position == 'prefix':
                            combined_message = japanese_name + ' ' + combined_message
                        elif position == 'suffix':
                            combined_message = combined_message + ' ' + japanese_name
                        elif position == 'both':
                            combined_message = japanese_name + ' ' + combined_message + ' ' + japanese_name
                    else:
                        # Legacy behavior: replace {symbol} placeholder
                        combined_message = combined_message.replace('{symbol}', japanese_name)
                    
                    # Create notification
                    notification = {
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'symbol': base_state.get('symbol', 'UNKNOWN'),
                        'tf': base_state.get('tf', '5'),
                        'direction': direction,
                        'message': combined_message,
                        'timestamp': datetime.now(jst).isoformat(),
                        'price': float(base_state.get('price', 0)),
                        'voice_settings': voice_settings  # 音声設定を含める
                    }
                    
                    fired_notifications.append(notification)
                    
                    # Record fire event in history with current state snapshot
                    try:
                        conn_hist = sqlite3.connect(DB_PATH)
                        c_hist = conn_hist.cursor()
                        c_hist.execute('''INSERT INTO fire_history (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                         VALUES (?, ?, ?, ?, ?, ?)''',
                                      (rule_id, symbol, tf, datetime.now(jst).isoformat(), 
                                       json.dumps(rule.get('conditions', []), ensure_ascii=False),
                                       json.dumps(current_state, ensure_ascii=False)))
                        conn_hist.commit()
                        conn_hist.close()
                    except Exception as e:
                        print(f'[ERROR] Saving fire history: {e}')
                    
                    print(f'[RULE FIRED] {rule_name} - {direction} - {combined_message}')
            
            except Exception as e:
                print(f'[ERROR] Evaluating rule {rule_id}: {e}')
                continue
        
        # Save notifications to file
        if fired_notifications:
            notifications_path = os.path.join(BASE_DIR, 'notifications.json')
            try:
                if os.path.exists(notifications_path):
                    with open(notifications_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                else:
                    existing = []
                
                existing.extend(fired_notifications)
                
                # Keep only last 100 notifications
                if len(existing) > 100:
                    existing = existing[-100:]
                
                with open(notifications_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                
                print(f'[NOTIFICATIONS] Saved {len(fired_notifications)} notifications')
                
                # Socket.IOで新しい通知を送信
                for notification in fired_notifications:
                    socketio.emit('new_notification', notification)
                    print(f'[SOCKET.IO] Notification sent: {notification.get("rule_name")}')
            
            except Exception as e:
                print(f'[ERROR] Saving notifications: {e}')
    
    except Exception as e:
        print(f'[ERROR] evaluate_and_fire_rules: {e}')

# トラブルシューティング用エンドポイント
@app.route('/api/webhook-diagnostics', methods=['GET'])
def webhook_diagnostics():
    """Webhook受信と処理の状態を確認するエンドポイント"""
    try:
        jst = pytz.timezone('Asia/Tokyo')
        diagnostics = {
            'server_time': datetime.now(jst).isoformat(),
            'webhook_log_exists': os.path.exists(os.path.join(BASE_DIR, 'webhook_log.txt')),
            'webhook_error_log_exists': os.path.exists(os.path.join(BASE_DIR, 'webhook_error.log')),
            'database_exists': os.path.exists(DB_PATH),
        }
        
        # webhook_log.txt の最後の行を取得
        webhook_log_path = os.path.join(BASE_DIR, 'webhook_log.txt')
        if os.path.exists(webhook_log_path):
            try:
                with open(webhook_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    diagnostics['webhook_log_last_entries'] = lines[-10:] if lines else []
                    diagnostics['webhook_log_total_lines'] = len(lines)
            except:
                pass
        
        # webhook_error.log の最後の行を取得
        webhook_error_path = os.path.join(BASE_DIR, 'webhook_error.log')
        if os.path.exists(webhook_error_path):
            try:
                with open(webhook_error_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    diagnostics['error_log_last_entries'] = lines[-20:] if lines else []
                    diagnostics['error_log_total_lines'] = len(lines)
            except:
                pass
        
        # データベースの最後の記録
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT symbol, tf, time, timestamp FROM states WHERE symbol='USDJPY' AND tf='5' ORDER BY timestamp DESC LIMIT 1")
            last_record = c.fetchone()
            if last_record:
                diagnostics['last_usdjpy5_record'] = {
                    'symbol': last_record[0],
                    'tf': last_record[1],
                    'json_time': last_record[2],
                    'db_timestamp': last_record[3]
                }
            
            # fire_history の最後の記録
            c.execute("SELECT rule_id, symbol, tf, fired_at FROM fire_history WHERE symbol='USDJPY' AND tf='5' ORDER BY fired_at DESC LIMIT 1")
            last_fire = c.fetchone()
            if last_fire:
                diagnostics['last_rule_fire'] = {
                    'rule_id': last_fire[0],
                    'symbol': last_fire[1],
                    'tf': last_fire[2],
                    'fired_at': last_fire[3]
                }
            
            conn.close()
        except Exception as e:
            diagnostics['database_error'] = str(e)
        
        return jsonify(diagnostics), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/save_notes', methods=['POST'])
def save_notes():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({'status': 'error', 'msg': 'No data provided'}), 400
        
        # フロントエンドから送信される形式: {pages: [...], currentPage: ...}
        # またはそのままnotePages配列として送信される場合もある
        notes_data = payload
        
        notes_path = os.path.join(BASE_DIR, 'notes_data.json')
        print(f'[NOTE API] Saving notes to {notes_path}')
        print(f'[NOTE API] Data type: {type(notes_data)}, Content: {json.dumps(notes_data, ensure_ascii=False)[:200]}...')
        
        # ファイルに保存
        with open(notes_path, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, ensure_ascii=False, indent=2)
        
        print(f'[NOTE API] Notes saved successfully')
        return jsonify({'status': 'success', 'msg': 'Notes saved'})
    except Exception as e:
        error_msg = f'[ERROR] save_notes failed: {str(e)}'
        print(error_msg)
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/load_notes', methods=['GET'])
def load_notes():
    try:
        notes_path = os.path.join(BASE_DIR, 'notes_data.json')
        print(f'[NOTE API] Loading notes from {notes_path}')
        
        if os.path.exists(notes_path):
            with open(notes_path, 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
            print(f'[NOTE API] Loaded notes: {len(notes_data) if isinstance(notes_data, list) else "dict"} items')
            # フロントエンドは notes フィールドを期待している
            return jsonify({'status': 'success', 'notes': notes_data})
        else:
            print(f'[NOTE API] Notes file not found, returning empty array')
            return jsonify({'status': 'success', 'notes': []})
    except Exception as e:
        error_msg = f'[ERROR] load_notes failed: {str(e)}'
        print(error_msg)
        return jsonify({'status': 'error', 'msg': str(e)}), 500

if __name__ == '__main__':
    print('[DEBUG] Starting init_db...')
    init_db()
    print('[DEBUG] init_db completed')
    port = int(os.environ.get('PORT', 5000))
    
    # ログファイルの初期化
    jst = pytz.timezone('Asia/Tokyo')
    startup_log = os.path.join(BASE_DIR, 'webhook_error.log')
    try:
        with open(startup_log, 'a', encoding='utf-8') as f:
            f.write(f'\n{"="*80}\n')
            f.write(f'{datetime.now(jst).isoformat()} - [STARTUP] Starting Flask server on port {port}\n')
            f.write(f'{"="*80}\n')
    except:
        pass
    
    print(f'[START] Starting server on port {port} at {datetime.now(jst).isoformat()}')
    print('[DEBUG] About to call socketio.run...')
    
    try:
        print('[DEBUG] Calling socketio.run...')
        socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
        print('[DEBUG] socketio.run completed')
    except Exception as e:
        error_msg = f'[CRITICAL ERROR] Server crashed: {str(e)}'
        print(error_msg)
        import traceback
        print('[DEBUG] Full traceback:')
        traceback.print_exc()
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
                f.write(f'Full traceback:\n{traceback.format_exc()}\n')
        except:
            pass
        raise

